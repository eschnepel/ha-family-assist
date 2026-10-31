import asyncio
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from assistd.ghcli import GitHubCli
from assistd.identity import StaticUsers
from assistd.web import create_app
from test_agent_web import FakeOllama, USERS, as_user, make_deps, plain_env

FAKE = (sys.executable, str(Path(__file__).with_name("fake_gh.py")))


def make_gh(tmp_path, **kw) -> GitHubCli:
    return GitHubCli(tmp_path / "gh", command=FAKE, **kw)


async def wait_for(predicate, seconds=10.0):
    for _ in range(int(seconds / 0.05)):
        if predicate():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("timed out")


def test_login_flow_shows_code_then_signs_in(tmp_path):
    async def go():
        gh = make_gh(tmp_path)
        done = []
        gh.on_success = lambda: done.append(True)
        assert (await gh.status())["logged_in"] is False and gh.token() == ""
        started = await gh.start_login()
        assert started["state"] == "pending" and started["code"] == "ABCD-1234"
        assert started["url"] == "https://github.com/login/device"
        assert (await gh.status())["logged_in"] is False
        (tmp_path / "gh" / "approve").write_text("")
        await wait_for(lambda: gh.login.state == "done")
        assert done == [True]
        status = await gh.status()
        assert status["logged_in"] and status["account"] == "octocat" and gh.token() == "gho_faketoken"
        await gh.logout()
        assert (await gh.status())["logged_in"] is False and gh.token() == ""
    asyncio.run(go())


def test_denied_and_timed_out_logins_fail_cleanly(tmp_path):
    async def go():
        gh = make_gh(tmp_path)
        await gh.start_login()
        (tmp_path / "gh" / "deny").write_text("")
        await wait_for(lambda: gh.login.state == "failed")
        assert "denied" in gh.login.error and gh.login.code == "ABCD-1234"
        slow = make_gh(tmp_path / "slow", login_timeout=0.5)
        await slow.start_login()
        await wait_for(lambda: slow.login.state == "failed")
        assert "timed out" in slow.login.error
    asyncio.run(go())


def test_flags_missing_in_an_older_gh_are_not_passed(tmp_path):
    async def go():
        env = {"FAKE_GH_UNSUPPORTED": "--insecure-storage,--skip-ssh-key"}
        gh = make_gh(tmp_path, extra_env=env)
        started = await gh.start_login()
        assert started["state"] == "pending" and started["code"] == "ABCD-1234"
        await gh.cancel()
    asyncio.run(go())


def test_gh_flag_error_is_shown_without_the_usage_text(tmp_path):
    async def go():
        gh = make_gh(tmp_path, extra_env={"FAKE_GH_UNSUPPORTED": "--web"})
        await gh.start_login()
        await wait_for(lambda: gh.login.state == "failed")
        assert gh.login.error == "unknown flag: --web"
        assert "with-token" not in gh.login.error
    asyncio.run(go())


def test_error_summary_keeps_the_message_and_drops_usage():
    from assistd.ghcli import error_summary
    usage = "unknown flag: --x\n\nUsage:\n  gh auth login [flags]\n\nFlags:\n  --with-token  Read token\n"
    assert error_summary(usage) == "unknown flag: --x"
    assert error_summary("a\nb\nauthorization denied\n") == "b | authorization denied"
    assert error_summary("") == "Sign-in failed"
    assert error_summary("Usage: gh\n  --with-token  Read token") == "Usage: gh"


def test_new_login_replaces_a_pending_one(tmp_path):
    async def go():
        gh = make_gh(tmp_path)
        await gh.start_login()
        first = gh._proc
        await gh.start_login()
        await asyncio.sleep(0.3)
        assert first.returncode is not None and gh.login.state == "pending"
        await gh.cancel()
        assert gh.login.state == "idle"
    asyncio.run(go())


def test_missing_cli_is_reported(tmp_path):
    gh = GitHubCli(tmp_path / "gh", command=("definitely-not-gh",))
    assert not gh.available and gh.token() == ""
    with pytest.raises(Exception):
        asyncio.run(gh.start_login())


@pytest.fixture
def web(tmp_path, checkout):
    deps = make_deps(tmp_path, plain_env(checkout), FakeOllama([]))
    deps.gh = make_gh(tmp_path)
    app = create_app(deps, StaticUsers(USERS), dev=True, background=False)
    with TestClient(app) as client:
        client.deps = deps
        yield client


def test_github_endpoints_are_admin_only(web):
    for method, path in [("get", "/api/admin/github"), ("post", "/api/admin/github/login"),
                         ("post", "/api/admin/github/logout")]:
        assert getattr(web, method)(path, headers=as_user("kid1")).status_code == 403


def test_login_through_the_api_and_token_reaches_git(web, tmp_path):
    admin = as_user("admin1")
    login = web.post("/api/admin/github/login", headers=admin).json()
    assert login["login"]["code"] == "ABCD-1234" and login["logged_in"] is False
    body = {"repo_url": "", "branch": "main", "allow_commits": False, "allow_push": False,
            "auth_method": "github_cli"}
    assert web.put("/api/admin/settings", headers=admin, json=body).json()["auth_method"] == "github_cli"
    assert web.deps.env._current_token() == ""
    (tmp_path / "gh" / "approve").write_text("")
    for _ in range(200):
        status = web.get("/api/admin/github", headers=admin).json()
        if status["logged_in"]:
            break
        time.sleep(0.05)
    assert status["logged_in"] and status["account"] == "octocat"
    assert web.deps.env._current_token() == "gho_faketoken"
    assert "gho_faketoken" not in web.get("/api/admin/status", headers=admin).text
    assert "gho_faketoken" not in web.get("/api/admin/settings", headers=admin).text
    body["auth_method"] = "token"
    web.put("/api/admin/settings", headers=admin, json=body)
    assert web.deps.env._current_token() == ""
    web.post("/api/admin/github/logout", headers=admin)
    assert web.get("/api/admin/github", headers=admin).json()["logged_in"] is False


def test_cli_token_is_sent_to_git_but_not_stored(tmp_path):
    from assistd.gitenv import AgentEnvironment
    env = AgentEnvironment(tmp_path / "env" / "repo")
    env.configure("http://127.0.0.1:9/none.git", "main", lambda: "gho_faketoken")
    with pytest.raises(Exception) as exc:
        env.sync()
    assert "gho_faketoken" not in str(exc.value)
    assert env._env("gho_faketoken")["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert not (tmp_path / "env" / "repo").exists()
