import asyncio
from pathlib import Path
from typing import Any

import pytest
from assistd import agent
from assistd.agent import Deps, Principal, run_turn
from assistd.identity import StaticUsers
from assistd.questions import SKIPPED, PendingQuestion, QuestionError, parse_question
from assistd.web import create_app
from fastapi.testclient import TestClient
from test_agent_web import USERS, Chunk, FakeOllama, as_user, call, make_deps, plain_env, say


def ask(**args: Any) -> list[Chunk]:
    chunks: list[Chunk] = call("ask_user", **args)
    return chunks


def test_parse_question_defaults_and_validation() -> None:
    q = parse_question({"question": " Name? "})
    assert (q.text, q.kind, q.options, q.required) == ("Name?", "text", (), True)
    q = parse_question(
        '{"question": "Pick", "kind": "multiple", "options": ["a", "b", "a"], "required": false}'
    )
    assert (q.kind, q.options, q.required) == ("multiple", ("a", "b"), False)
    for bad in [
        {},
        {"question": ""},
        {"question": "x", "kind": "radio"},
        {"question": "x", "kind": "single"},
        {"question": "x", "kind": "single", "options": ["only"]},
        {"question": "x", "kind": "single", "options": ["a", 1]},
        "[]",
    ]:
        with pytest.raises(QuestionError):
            parse_question(bad)


def test_answer_validation() -> None:
    async def go() -> None:
        single = PendingQuestion(
            parse_question({"question": "q", "kind": "single", "options": ["a", "b"]})
        )
        for bad in ("c", ["a"], None):
            with pytest.raises(QuestionError):
                single.answer(bad)
        with pytest.raises(QuestionError):
            single.answer("a", skipped=True)  # mandatory questions cannot be skipped
        single.answer("b")
        assert single.future.result() == "b"
        with pytest.raises(QuestionError):
            single.answer("a")

        multiple = PendingQuestion(
            parse_question({"question": "q", "kind": "multiple", "options": ["a", "b", "c"]})
        )
        with pytest.raises(QuestionError):
            multiple.answer(["a", "x"])
        multiple.answer(["c", "a"])
        assert multiple.future.result() == "a\nc"

        optional = PendingQuestion(parse_question({"question": "q", "required": False}))
        optional.answer("   ")
        assert optional.future.result() == SKIPPED

        text = PendingQuestion(parse_question({"question": "q"}))
        with pytest.raises(QuestionError):
            text.answer("  ")
        text.answer(" hello ")
        assert text.future.result() == "hello"

    asyncio.run(go())


def drive(deps: Deps, conv: dict[str, Any], answers: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Run a turn and answer each question with the next entry of `answers`."""

    async def go() -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        async for event in run_turn(deps, Principal("u1", "Marten"), conv, "hi", []):
            events.append(event)
            if event["type"] == "question":
                assert deps.queue.running == 0  # the slot is free while the user thinks
                deps.pending[("u1", conv["id"])].answer(*answers.pop(0))
        return events

    return asyncio.run(go())


def test_questions_are_asked_one_at_a_time_and_answers_reach_the_model(
    tmp_path: Path, checkout: Path
) -> None:
    ollama = FakeOllama(
        [
            ask(question="Which?", kind="single", options=["a", "b"]),
            ask(question="Why?", required=False),
            say("done"),
            say("Ctx: title"),
        ]
    )
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    conv = deps.store.create("u1")
    events = drive(deps, conv, [("b",), (None, True)])
    questions = [e for e in events if e["type"] == "question"]
    assert [(q["question"], q["kind"], q["required"]) for q in questions] == [
        ("Which?", "single", True),
        ("Why?", "text", False),
    ]
    tools = [e for e in events if e["type"] == "tool"]
    assert [(t["name"], t["result"], t["ok"]) for t in tools] == [
        ("ask_user", "b", True),
        ("ask_user", SKIPPED, True),
    ]
    assert ollama.calls[1]["messages"][-1] == {
        "role": "tool",
        "tool_name": "ask_user",
        "content": "b",
    }
    assert not deps.pending and deps.queue.running == 0
    assert events[-1] == {"type": "done"}


def test_invalid_question_is_an_error_result(tmp_path: Path, checkout: Path) -> None:
    ollama = FakeOllama([ask(question="Which?", kind="single"), say("ok"), say("Ctx: t")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    events = drive(deps, deps.store.create("u1"), [])
    assert not any(e["type"] == "question" for e in events)
    tool = next(e for e in events if e["type"] == "tool")
    assert tool["ok"] is False and tool["result"].startswith("Error: options")


def test_unanswered_question_times_out(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent, "ANSWER_TIMEOUT_SECONDS", 0.01)
    ollama = FakeOllama([ask(question="Name?"), say("ok"), say("Ctx: t")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)

    async def go() -> list[dict[str, Any]]:
        return [
            e
            async for e in run_turn(
                deps, Principal("u1", "Marten"), deps.store.create("u1"), "hi", []
            )
        ]

    events = asyncio.run(go())
    tool = next(e for e in events if e["type"] == "tool")
    assert tool["ok"] is False and "did not answer" in tool["result"]
    assert not deps.pending and deps.queue.running == 0


def test_answer_endpoint_needs_a_waiting_question(tmp_path: Path, checkout: Path) -> None:
    deps = make_deps(tmp_path, plain_env(checkout), FakeOllama([]))
    with TestClient(create_app(deps, StaticUsers(USERS), dev=True, background=False)) as client:
        kid = as_user("kid1")
        cid = client.post("/api/conversations", headers=kid).json()["id"]
        assert client.get(f"/api/conversations/{cid}", headers=kid).json()["question"] is None
        response = client.post(
            f"/api/conversations/{cid}/answer", headers=kid, json={"id": "x", "answer": "a"}
        )
        assert response.status_code == 409
