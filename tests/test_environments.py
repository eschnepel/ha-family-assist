import json

import pytest
from fastapi.testclient import TestClient

from assistd.config import EnvConfig, SettingsStore
from assistd.identity import StaticUsers
from assistd.web import create_app
from conftest import write
from test_agent_web import DEAD_URL, FakeOllama, USERS, as_user, make_deps, plain_env, say


def test_single_repository_settings_migrate_to_default_environment(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.json").write_text(json.dumps(
        {"repo_url": "https://github.com/o/family-notes.git", "branch": "dev", "allow_commits": True}), "utf-8")
    store = SettingsStore(data)
    settings = store.get()
    assert [(e.id, e.name, e.repo_url, e.branch) for e in settings.environments] == [
        ("default", "family-notes", "https://github.com/o/family-notes.git", "dev")]
    assert settings.allow_commits and settings.repo_url == ""
    assert json.loads((data / "settings.json").read_text("utf-8"))["repo_url"] == ""
    assert store.get().environments == settings.environments


@pytest.fixture
def multi(tmp_path, checkout):
    deps = make_deps(tmp_path, plain_env(checkout), FakeOllama([say("A"), say("B")]))
    other = deps.env_for("abc123").path
    write(other, "AGENTS.md", "# Other\n")
    (other / ".git").mkdir()
    settings = deps.settings.get()
    settings.environments.append(EnvConfig("abc123", "Other", DEAD_URL, "main"))
    deps.settings.save(settings)
    deps.env_for("abc123").configure(DEAD_URL, "main", "")
    with TestClient(create_app(deps, StaticUsers(USERS), dev=True, background=False)) as client:
        client.deps, client.other = deps, other
        yield client


def test_conversations_belong_to_one_environment(multi):
    kid = as_user("kid1")
    me = multi.get("/api/me", headers=kid).json()
    assert [e["id"] for e in me["environments"]] == ["default", "abc123"]
    first = multi.post("/api/conversations", headers=kid).json()["id"]  # defaults to the first environment
    second = multi.post("/api/conversations?env=abc123", headers=kid).json()["id"]
    assert [c["id"] for c in multi.get("/api/conversations?env=default", headers=kid).json()] == [first]
    assert [c["id"] for c in multi.get("/api/conversations?env=abc123", headers=kid).json()] == [second]
    assert multi.post("/api/conversations?env=nope", headers=kid).status_code == 404
    multi.post(f"/api/conversations/{second}/messages", headers=kid, json={"text": "hi"})
    prompt = multi.deps.ollama.calls[0]["messages"][0]["content"]
    assert "# Other" in prompt and "# Rules" not in prompt


def test_legacy_conversation_without_environment_belongs_to_default(multi):
    conv = multi.deps.store.create("kid1")
    del conv["env_id"]
    multi.deps.store.save(conv)
    kid = as_user("kid1")
    assert [c["id"] for c in multi.get("/api/conversations?env=default", headers=kid).json()] == [conv["id"]]
    assert multi.get("/api/conversations?env=abc123", headers=kid).json() == []


def test_admin_removes_environment_and_its_conversations_are_hidden(multi):
    admin = as_user("admin1")
    kid = as_user("kid1")
    cid = multi.post("/api/conversations?env=abc123", headers=kid).json()["id"]
    body = {"environments": [{"id": "default", "name": "Default", "repo_url": DEAD_URL, "branch": "main"}],
            "allow_commits": False, "allow_push": False}
    saved = multi.put("/api/admin/settings", headers=admin, json=body).json()
    assert [e["id"] for e in saved["environments"]] == ["default"]
    assert not multi.other.exists()
    assert multi.get("/api/conversations?env=abc123", headers=kid).status_code == 404
    assert cid not in [c["id"] for c in multi.get("/api/conversations", headers=kid).json()]


def test_admin_adds_environment_with_generated_id(multi):
    admin = as_user("admin1")
    multi.deps.env.sync = lambda: None
    envs = [{"id": "default", "name": "Default", "repo_url": DEAD_URL, "branch": "main"},
            {"id": "abc123", "name": "Other", "repo_url": DEAD_URL, "branch": "main"},
            {"name": "", "repo_url": "https://example.invalid/o/third.git", "branch": "main"}]
    multi.deps.env_for = lambda eid, real=multi.deps.env_for: _quiet(real(eid))
    saved = multi.put("/api/admin/settings", headers=admin,
                      json={"environments": envs, "allow_commits": False, "allow_push": False}).json()
    third = saved["environments"][2]
    assert third["name"] == "third" and third["id"] not in ("default", "abc123")
    dup = envs[:1] * 2
    assert multi.put("/api/admin/settings", headers=admin,
                     json={"environments": dup, "allow_commits": False, "allow_push": False}).status_code == 422


def _quiet(env):
    env.sync = lambda: None
    return env
