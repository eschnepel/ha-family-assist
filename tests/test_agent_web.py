import asyncio
import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from assistd.agent import Deps, Principal, run_turn
from assistd.config import Options, SettingsStore
from assistd.genqueue import GenerationQueue
from assistd.gitenv import AgentEnvironment
from assistd.identity import HAUser, StaticUsers
from assistd.ollama import OllamaError
from assistd.store import ConversationStore
from assistd.web import create_app
from conftest import write


class FakeOllama:
    """Replays scripted replies; each reply is a list of stream chunks."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def chat_stream(self, *, model, messages, tools, num_ctx):
        self.calls.append({"model": model, "messages": [dict(m) for m in messages], "tools": tools})
        if not self.replies:
            raise OllamaError("no more replies")
        for chunk in self.replies.pop(0):
            yield chunk

    async def check_model(self, model):
        return {"model": model, "reachable": True, "exists": True, "tools": True, "vision": False}

    async def aclose(self):
        pass


def say(text):
    return [{"message": {"content": text}, "done": True}]


def call(name, **args):
    return [{"message": {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}, "done": True}]


def make_deps(tmp_path, env, ollama, **opts) -> Deps:
    options = Options(**opts)
    return Deps(options, SettingsStore(tmp_path / "data"), env, ollama,
                ConversationStore(tmp_path / "data" / "conversations"),
                GenerationQueue(options.queue_enabled, options.max_parallel_generations))


def plain_env(checkout) -> AgentEnvironment:
    return AgentEnvironment(checkout)


def collect(deps, conv, text="hi", images=None, alias="Marten", acted_by=None):
    async def go():
        return [e async for e in run_turn(deps, Principal("u1", alias, acted_by), conv, text, images or [])]
    return asyncio.run(go())


def new_conv(deps, uid="u1"):
    return deps.store.create(uid)


def test_turn_streams_and_persists(tmp_path, checkout):
    ollama = FakeOllama([say("Hallo")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    conv = new_conv(deps)
    events = collect(deps, conv)
    assert [e["type"] for e in events] == ["start", "token", "done"]
    saved = deps.store.load("u1", conv["id"])
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][1]["content"] == "Hallo" and saved["title"] == "hi"
    first = ollama.calls[0]
    assert first["model"] == "test-model"  # from the front matter of AGENTS.md
    system = first["messages"][0]["content"]
    assert "Current user: Marten" in system and "# Rules" in system
    assert [t["function"]["name"] for t in first["tools"]] == ["list_dir", "find", "grep", "read_file"]


def test_tool_loop_hidden_path_and_history_trimming(tmp_path, checkout):
    ollama = FakeOllama([call("read_file", path="Scripts/run.ps1"), say("not there"), say("second")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    conv = new_conv(deps)
    events = collect(deps, conv)
    tool = next(e for e in events if e["type"] == "tool")
    assert tool["ok"] is False and tool["result"].startswith("Error: not found")
    assert "secret script" not in json.dumps(events)
    second_call = ollama.calls[1]["messages"]
    assert second_call[-1] == {"role": "tool", "tool_name": "read_file", "content": tool["result"]}
    collect(deps, conv, text="again")
    replay = ollama.calls[2]["messages"]
    assert [m["role"] for m in replay] == ["system", "user", "assistant", "user"]


def test_nested_agents_md_loaded_once_and_never_when_hidden(tmp_path, checkout):
    ollama = FakeOllama([call("read_file", path="Mathe/Klasse-8/Marten/a.md"), call("list_dir", path="Mathe"),
                         call("list_dir", path="Scripts"), say("ok")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    conv = new_conv(deps)
    events = collect(deps, conv)
    tools = [e for e in events if e["type"] == "tool"]
    assert "[Additional instructions from Mathe/AGENTS.md]" in tools[0]["result"]
    assert "Additional instructions" not in tools[1]["result"]
    assert "script rules" not in json.dumps(events)


def test_tool_limit_ends_turn(tmp_path, checkout):
    ollama = FakeOllama([call("list_dir")] * 5)
    deps = make_deps(tmp_path, plain_env(checkout), ollama, max_tool_calls_per_turn=2)
    conv = new_conv(deps)
    events = collect(deps, conv)
    assert sum(e["type"] == "tool" for e in events) == 2
    assert {"type": "notice", "text": "tool_limit"} in events
    assert deps.store.load("u1", conv["id"])["messages"][-1]["notice"] == "tool_limit"


def test_ollama_error_is_reported_and_saved(tmp_path, checkout):
    deps = make_deps(tmp_path, plain_env(checkout), FakeOllama([]))
    conv = new_conv(deps)
    events = collect(deps, conv)
    assert events[-2]["type"] == "error"
    assert deps.store.load("u1", conv["id"])["messages"][-1]["error"]


def test_images_use_vision_model(tmp_path, checkout):
    ollama = FakeOllama([say("seen")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama, vision_model="vision-x")
    conv = new_conv(deps)
    collect(deps, conv, images=["data:image/jpeg;base64,QUJD"])
    assert ollama.calls[0]["model"] == "vision-x"
    assert ollama.calls[0]["messages"][-1]["images"] == ["QUJD"]


def test_commit_flow_with_write_tools(tmp_path, remote):
    env = AgentEnvironment(tmp_path / "env" / "repo", extra_protocols=("file",))
    env.configure(str(remote), "main", "")
    env.sync()
    ollama = FakeOllama([call("create_file", path="Mathe/t.md", content="hello"), say("done")])
    deps = make_deps(tmp_path, env, ollama)
    settings = deps.settings.get()
    settings.allow_commits = True
    deps.settings.save(settings)
    conv = new_conv(deps)
    events = collect(deps, conv, alias="Richard", acted_by="Papa")
    commit = next(e for e in events if e["type"] == "commit")
    assert commit["commit"] and commit["message"] == "Assist (Richard): Mathe/t.md"
    assert "create_file" in [t["function"]["name"] for t in ollama.calls[0]["tools"]]
    assert env.status()["ahead"] == 1 and env.status()["pending"] == 0
    log = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=env.path, capture_output=True, text=True).stdout
    assert "Acted-By: Papa" in log


def test_queue_is_fifo_and_releases():
    async def go():
        queue = GenerationQueue(True, 1)
        a, b, c = queue.enqueue(), queue.enqueue(), queue.enqueue()
        assert a.granted.is_set() and not b.granted.is_set()
        assert (queue.position(b), queue.position(c)) == (1, 2)
        queue.release(a)
        assert b.granted.is_set() and queue.position(c) == 1
        queue.release(c)  # cancelled while waiting
        queue.release(b)
        assert queue.running == 0 and queue.waiting == 0
        off = GenerationQueue(False, 1)
        assert all(off.enqueue().granted.is_set() for _ in range(3))
    asyncio.run(go())


# --- HTTP API -----------------------------------------------------------------

USERS = [HAUser("admin1", "Papa", True), HAUser("kid1", "Richard", False), HAUser("kid2", "Marten", False)]
H = {"X-Requested-With": "family-assist"}


@pytest.fixture
def client(tmp_path, checkout):
    ollama = FakeOllama([say("Antwort")])
    deps = make_deps(tmp_path, plain_env(checkout), ollama)
    app = create_app(deps, StaticUsers(USERS), dev=True, background=False)
    with TestClient(app) as c:
        c.deps = deps
        yield c


def as_user(uid, **extra):
    return {**H, "X-Remote-User-Id": uid, **extra}


def test_api_requires_identity_and_csrf_header(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"X-Remote-User-Id": "nobody"}).status_code == 403
    assert client.post("/api/conversations", headers={"X-Remote-User-Id": "kid1"}).status_code == 403
    response = client.get("/api/me", headers=as_user("kid1"))
    assert response.json() | {} == {"id": "kid1", "alias": "Richard", "is_admin": False, "real_alias": "Richard",
                                    "acting": False, "ready": True, "can_write": False}
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_admin_endpoints_are_admin_only(client):
    for method, path in [("get", "/api/admin/settings"), ("get", "/api/admin/status"), ("get", "/api/family")]:
        assert getattr(client, method)(path, headers=as_user("kid1")).status_code == 403
        assert getattr(client, method)(path, headers=as_user("admin1")).status_code == 200
    assert client.get("/api/me", headers=as_user("kid1", **{"X-Act-As": "kid2"})).status_code == 403


def test_chat_message_stream_and_acting_as(client):
    headers = as_user("admin1", **{"X-Act-As": "kid1"})
    assert client.get("/api/me", headers=headers).json()["acting"] is True
    cid = client.post("/api/conversations", headers=headers).json()["id"]
    response = client.post(f"/api/conversations/{cid}/messages", headers=headers, json={"text": "Hallo"})
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == {"type": "done"} and any(e["type"] == "token" for e in events)
    # The conversation belongs to the family member, not to the admin.
    assert client.get("/api/conversations", headers=as_user("admin1")).json() == []
    listed = client.get("/api/conversations", headers=as_user("kid1")).json()
    assert [c["id"] for c in listed] == [cid]
    conv = client.get(f"/api/conversations/{cid}", headers=as_user("kid1")).json()
    assert conv["messages"][0]["acted_by"] == "Papa" and "loaded_agents" not in conv
    assert client.get(f"/api/conversations/{cid}", headers=as_user("kid2")).status_code == 404
    system = client.deps.ollama.calls[0]["messages"][0]["content"]
    assert "Current user: Richard" in system


def test_settings_roundtrip_hides_token_and_validates(client, tmp_path):
    admin = as_user("admin1")
    body = {"repo_url": "file:///etc", "branch": "main", "allow_commits": False, "allow_push": False}
    assert client.put("/api/admin/settings", headers=admin, json=body).status_code == 422
    body = {"repo_url": "", "branch": "main", "allow_commits": True, "allow_push": False,
            "aliases": {"kid1": "  Richi<>  "}, "git_token": "ghp_secret"}
    saved = client.put("/api/admin/settings", headers=admin, json=body).json()
    assert saved["has_token"] is True and saved["aliases"] == {"kid1": "Richi"}
    assert "ghp_secret" not in json.dumps(saved) and "ghp_secret" not in client.get("/api/admin/status", headers=admin).text
    assert client.get("/api/me", headers=as_user("kid1")).json()["alias"] == "Richi"
    assert client.deps.settings.git_token() == "ghp_secret"
    body["git_token"] = None
    client.put("/api/admin/settings", headers=admin, json=body)
    assert client.deps.settings.git_token() == "ghp_secret"


def test_message_validation(client):
    headers = as_user("kid1")
    cid = client.post("/api/conversations", headers=headers).json()["id"]
    url = f"/api/conversations/{cid}/messages"
    assert client.post(url, headers=headers, json={"text": ""}).status_code == 422
    assert client.post(url, headers=headers, json={"text": "x", "images": ["javascript:alert(1)"]}).status_code == 422
    assert client.post(url, headers=headers, json={"text": "x", "images": ["data:image/svg+xml;base64,QUJD"]}).status_code == 422


def test_admin_status_reports_rules_and_models(client):
    status = client.get("/api/admin/status", headers=as_user("admin1")).json()
    assert status["rules"]["hidden"] == ["/Scripts/"]
    assert status["rules"]["tools"] == ["list_dir", "find", "grep", "read_file"]
    assert status["model"]["model"] == "test-model" and status["options"]["api_key_set"] is False


def test_static_index_served(client):
    response = client.get("/")
    assert response.status_code == 200 and "Family Assist" in response.text
    assert client.get("/static/app.js").status_code == 200
    assert "font-src 'self'" in response.headers["content-security-policy"]


def test_vendored_math_and_diagram_libraries_are_served_and_cached(client):
    for path in ["katex/katex.min.js", "katex/katex.min.css", "katex/fonts/KaTeX_Main-Regular.woff2",
                 "mermaid/mermaid.min.js"]:
        response = client.get(f"/static/vendor/{path}")
        assert response.status_code == 200, path
        assert "max-age" in response.headers["cache-control"]
    assert client.get("/static/app.js").headers["cache-control"] == "no-store"
