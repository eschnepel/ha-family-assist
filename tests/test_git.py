import subprocess
from pathlib import Path

import pytest
from assistd.gitenv import AgentEnvironment, BusyError, GitError
from conftest import git, write


def make_env(tmp_path: Path, remote: Path) -> AgentEnvironment:
    env = AgentEnvironment(tmp_path / "env" / "repo", extra_protocols=("file",))
    env.configure(str(remote), "main", "")
    return env


def remote_log(remote: Path) -> list[str]:
    return subprocess.run(
        ["git", "--git-dir", str(remote), "log", "--format=%an|%ae|%cn|%B"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\n")


def test_clone_and_sync_updates(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    assert env.is_cloned() and (env.path / "AGENTS.md").exists()
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    write(other, "notes.md", "two\n")
    git(other, "commit", "-qam", "update")
    git(other, "push", "-q", "origin", "main")
    env.sync()
    assert (env.path / "notes.md").read_text() == "two\n"
    status = env.status()
    assert status["ahead"] == 0 and status["behind"] == 0 and status["last_error"] is None


def test_commit_and_push_with_attribution(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("Mathe/a.md"):
        write(env.path, "Mathe/a.md", "task\n")
    info = env.commit(["Mathe/a.md"], "Richard", acted_by="Papa")
    assert info and info["message"] == "Assist (Richard): Mathe/a.md"
    assert env.status()["ahead"] == 1 and env.status()["pending"] == 0
    assert env.push() == 1
    log = "\n".join(remote_log(remote))
    assert "Richard|family-assist@localhost|Family Assist|Assist (Richard): Mathe/a.md" in log
    assert "Acted-By: Papa" in log


def test_commit_without_net_change_returns_none(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("notes.md"):
        pass
    assert env.commit(["notes.md"], "Richard") is None
    assert env.status()["pending"] == 0


def test_pending_changes_block_sync(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("x.md"):
        write(env.path, "x.md", "x")
    with pytest.raises(BusyError):
        env.sync()
    env.commit(["x.md"], "Marten")
    env.sync()


def test_diverged_rebase_keeps_local_commits(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("notes.md"):
        write(env.path, "notes.md", "local\n")
    env.commit(["notes.md"], "Marten")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    write(other, "notes.md", "remote\n")
    git(other, "commit", "-qam", "remote change")
    git(other, "push", "-q", "origin", "main")
    with pytest.raises(GitError):
        env.sync()
    status = env.status()
    assert status["diverged"] and status["ahead"] == 1
    assert (env.path / "notes.md").read_text() == "local\n"
    assert not (env.path / ".git" / "rebase-merge").exists()


def test_rebase_succeeds_for_disjoint_changes(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("mine.md"):
        write(env.path, "mine.md", "mine\n")
    env.commit(["mine.md"], "Marten")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    write(other, "theirs.md", "theirs\n")
    git(other, "add", ".")
    git(other, "commit", "-qm", "theirs")
    git(other, "push", "-q", "origin", "main")
    assert env.push() == 1
    assert (env.path / "theirs.md").exists()


def test_failed_commit_rolls_back(tmp_path: Path, remote: Path) -> None:
    env = make_env(tmp_path, remote)
    env.sync()
    with env.write_guard("ignored.log"):
        write(env.path, "ignored.log", "x")
        write(env.path, ".gitignore", "*.log\n")
    with pytest.raises(GitError):
        env.commit(["ignored.log"], "Marten")
    assert not (env.path / "ignored.log").exists() and env.status()["pending"] == 0


def test_token_not_in_remote_config_or_errors(tmp_path: Path) -> None:
    env = AgentEnvironment(tmp_path / "env" / "repo")
    env.configure("http://127.0.0.1:9/none.git", "main", "SECRET-TOKEN")
    with pytest.raises(GitError) as exc:
        env.sync()
    assert "SECRET-TOKEN" not in str(exc.value)
    assert not (tmp_path / "env" / "repo").exists()


def test_url_validation() -> None:
    from assistd.config import ValidationError, validate_branch, validate_repo_url

    assert validate_repo_url("https://github.com/o/r.git")
    for bad in [
        "file:///etc",
        "ssh://git@x/r",
        "https://u:p@github.com/r",
        "ext::sh -c id",
        "https://a b",
    ]:
        with pytest.raises(ValidationError):
            validate_repo_url(bad)
    for bad in ["-evil", "a..b", "a b", ""]:
        with pytest.raises(ValidationError):
            validate_branch(bad)
    assert validate_branch("feature/x-1")
