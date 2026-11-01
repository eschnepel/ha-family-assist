import pytest
from fastapi.testclient import TestClient

from assistd.agent import Deps
from assistd.gitenv import AgentEnvironment
from assistd.identity import StaticUsers
from assistd.web import create_app
from conftest import write
from test_agent_web import FakeOllama, USERS, as_user, call, make_deps, say


@pytest.fixture
def session(tmp_path, remote):
    env = AgentEnvironment(tmp_path / "env" / "repo", extra_protocols=("file",))
    env.configure(str(remote), "main", "")
    env.sync()
    write(env.path, ".family_assist.yaml", "hidden:\n  - /secret/\n")
    write(env.path, "secret/plan.md", "hidden")
    ollama = FakeOllama([call("create_file", path="Mathe/Aufgabe ä.md", content="# Aufgabe\n<script>1</script>\n"),
                         say("Fertig")])
    deps: Deps = make_deps(tmp_path, env, ollama)
    settings = deps.settings.get()
    settings.allow_commits = True
    deps.settings.save(settings)
    with TestClient(create_app(deps, StaticUsers(USERS), dev=True, background=False)) as client:
        headers = as_user("kid1")
        cid = client.post("/api/conversations", headers=headers).json()["id"]
        client.post(f"/api/conversations/{cid}/messages", headers=headers, json={"text": "Mach eine Aufgabe"})
        client.cid, client.deps = cid, deps
        yield client


def test_changed_files_are_listed_and_downloadable(session):
    headers = as_user("kid1")
    files = session.get(f"/api/conversations/{session.cid}/files", headers=headers).json()
    assert files == [{"path": "Mathe/Aufgabe ä.md", "name": "Aufgabe ä.md", "size": 29}]
    response = session.get(f"/api/conversations/{session.cid}/files/Mathe/Aufgabe%20%C3%A4.md", headers=headers)
    assert response.status_code == 200
    assert response.content == "# Aufgabe\n<script>1</script>\n".encode()
    # Never rendered by the browser: forced download with a neutral type.
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''Aufgabe%20%C3%A4.md" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_only_files_changed_in_the_conversation_can_be_downloaded(session):
    headers = as_user("kid1")
    base = f"/api/conversations/{session.cid}/files/"
    for path in ["AGENTS.md", "notes.md", "secret/plan.md", ".git/config", "../env/repo/AGENTS.md",
                 "%2e%2e/%2e%2e/etc/passwd", "Mathe"]:
        assert session.get(base + path, headers=headers).status_code == 404, path


def test_other_family_members_cannot_download_or_export(session):
    path = f"/api/conversations/{session.cid}/files/Mathe/Aufgabe%20%C3%A4.md"
    for url in [path, f"/api/conversations/{session.cid}/files", f"/api/conversations/{session.cid}/export"]:
        assert session.get(url, headers=as_user("kid2")).status_code == 404
    acting = as_user("admin1", **{"X-Act-As": "kid1"})
    assert session.get(path, headers=acting).status_code == 200


def test_hidden_rule_added_later_blocks_download(session):
    write(session.deps.env.path, ".family_assist.yaml", "hidden:\n  - /secret/\n  - Mathe/\n")
    headers = as_user("kid1")
    assert session.get(f"/api/conversations/{session.cid}/files", headers=headers).json() == []
    assert session.get(f"/api/conversations/{session.cid}/files/Mathe/Aufgabe%20%C3%A4.md",
                       headers=headers).status_code == 404


def test_export_is_markdown_without_tool_output(session):
    response = session.get(f"/api/conversations/{session.cid}/export", headers=as_user("kid1"))
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert "# Mach eine Aufgabe" in text and "## Richard" in text and "## Assistant" in text
    assert "Fertig" in text and "Files changed: `Mathe/Aufgabe ä.md`" in text
    assert "<script>" not in text and "Created Mathe" not in text
