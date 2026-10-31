from __future__ import annotations

import base64
import contextlib
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

COMMITTER_NAME = "Family Assist"
COMMITTER_EMAIL = "family-assist@localhost"
GIT_TIMEOUT_SECONDS = 300


class GitError(Exception):
    pass


class BusyError(GitError):
    pass


def _clean_identity(text: str) -> str:
    return " ".join("".join(c for c in text if c not in "<>\r\n\0").split())[:60] or "Unknown"


class AgentEnvironment:
    """The local checkout of the Agent Environment and all git operations on it."""

    def __init__(self, path: Path, *, extra_protocols: tuple[str, ...] = ()):
        self.path = path
        self._extra_protocols = extra_protocols
        self._lock = threading.RLock()
        self._pending: set[str] = set()
        self._url = ""
        self._branch = "main"
        self._token = ""
        self.last_sync: float | None = None
        self.last_error: str | None = None
        self.diverged = False

    # --- configuration ---------------------------------------------------

    def configure(self, url: str, branch: str, token: str) -> None:
        with self._lock:
            self._url, self._branch, self._token = url, branch, token

    @property
    def configured(self) -> bool:
        return bool(self._url)

    def is_cloned(self) -> bool:
        return (self.path / ".git").exists()

    # --- git plumbing ----------------------------------------------------

    def _env(self) -> dict[str, str]:
        keep = ("PATH", "HOME", "LANG", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "TMPDIR")
        env = {k: os.environ[k] for k in keep if k in os.environ}
        env.update(
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_LITERAL_PATHSPECS="1",
            GIT_AUTHOR_NAME=COMMITTER_NAME,
            GIT_AUTHOR_EMAIL=COMMITTER_EMAIL,
            GIT_COMMITTER_NAME=COMMITTER_NAME,
            GIT_COMMITTER_EMAIL=COMMITTER_EMAIL,
        )
        if self._token:
            basic = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
            env.update(
                GIT_CONFIG_COUNT="1",
                GIT_CONFIG_KEY_0="http.extraHeader",
                GIT_CONFIG_VALUE_0=f"Authorization: Basic {basic}",
            )
        return env

    def _git(self, *args: str, cwd: Path | None = None, check: bool = True, input: str | None = None,
             env_extra: dict[str, str] | None = None) -> str:
        protocols = ["-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
                     "-c", "protocol.http.allow=always"]
        for name in self._extra_protocols:
            protocols += ["-c", f"protocol.{name}.allow=always"]
        cmd = ["git", "-c", f"core.hooksPath={os.devnull}", "-c", "credential.helper=", *protocols, *args]
        env = self._env()
        if env_extra:
            env.update(env_extra)
        try:
            proc = subprocess.run(
                cmd, cwd=cwd or self.path, env=env, input=input, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise GitError(f"git {args[0]} timed out") from None
        except OSError as exc:
            raise GitError(f"cannot run git: {exc}") from None
        if check and proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "").strip()
            if self._token:
                message = message.replace(self._token, "***")
            raise GitError(message[-500:] or f"git {args[0]} failed")
        return proc.stdout.strip()

    # --- status ------------------------------------------------------------

    def _ahead(self) -> int:
        out = self._git("rev-list", "--count", f"origin/{self._branch}..HEAD", check=False)
        return int(out) if out.isdigit() else 0

    def _behind(self) -> int:
        out = self._git("rev-list", "--count", f"HEAD..origin/{self._branch}", check=False)
        return int(out) if out.isdigit() else 0

    def status(self) -> dict:
        with self._lock:
            info: dict = {
                "configured": self.configured,
                "cloned": self.is_cloned(),
                "branch": self._branch,
                "head": None,
                "ahead": 0,
                "behind": 0,
                "pending": len(self._pending),
                "diverged": self.diverged,
                "last_sync": self.last_sync,
                "last_error": self.last_error,
            }
            if info["cloned"]:
                info["head"] = self._git("log", "-1", "--format=%h %s", check=False) or None
                info["ahead"] = self._ahead()
                info["behind"] = self._behind()
            return info

    # --- sync ------------------------------------------------------------

    def _clone(self) -> None:
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._git("clone", "--branch", self._branch, "--", self._url, str(self.path), cwd=self.path.parent)
        exclude = self.path / ".git" / "info" / "exclude"
        with contextlib.suppress(OSError):
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a", encoding="utf-8") as fh:
                fh.write("\n.fa-tmp-*\n")

    def sync(self) -> None:
        with self._lock:
            if not self._url:
                raise GitError("No repository configured")
            if self._pending:
                raise BusyError("Changes are being written; try again shortly")
            try:
                self._sync()
            except GitError as exc:
                self.last_error = str(exc)
                raise
            self.last_error = None
            self.last_sync = time.time()

    def _sync(self) -> None:
        branch = self._branch
        if not self.is_cloned():
            try:
                self._clone()
            except GitError:
                shutil.rmtree(self.path, ignore_errors=True)
                raise
            self.diverged = False
            return
        if self._git("remote", "get-url", "origin", check=False) != self._url:
            if self._ahead() > 0:
                raise GitError("The repository URL changed but there are unpushed commits")
            self._clone()
            self.diverged = False
            return
        self._git("fetch", "--prune", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
        current = self._git("rev-parse", "--abbrev-ref", "HEAD", check=False)
        if current != branch:
            if self._ahead() > 0:
                raise GitError(f"Unpushed commits exist on '{current}'; cannot switch to '{branch}'")
            self._git("checkout", "-q", "-B", branch, f"origin/{branch}")
        if self._ahead() == 0:
            self._git("reset", "-q", "--hard", f"origin/{branch}")
            self.diverged = False
        else:
            self._rebase()

    def _rebase(self) -> None:
        try:
            self._git("rebase", f"origin/{self._branch}")
        except GitError:
            self._git("rebase", "--abort", check=False)
            self.diverged = True
            raise GitError("Local commits conflict with the remote branch (diverged); nothing was discarded") from None
        self.diverged = False

    # --- writing ---------------------------------------------------------

    @contextlib.contextmanager
    def write_guard(self, rel: str):
        """Serialises file writes with Sync and marks the path as uncommitted."""
        with self._lock:
            self._pending.add(rel)
            yield

    def commit(self, paths: list[str], alias: str, acted_by: str | None = None) -> dict | None:
        paths = sorted(set(paths))
        if not paths:
            return None
        with self._lock:
            try:
                self._git("reset", "-q")
                self._git("add", "--", *paths)
                if not self._git("diff", "--cached", "--name-only"):
                    self._pending.difference_update(paths)
                    return None
                subject = f"Assist ({_clean_identity(alias)}): {', '.join(paths[:3])}"
                if len(paths) > 3:
                    subject += f" +{len(paths) - 3} more"
                message = subject[:120]
                if acted_by:
                    message += f"\n\nActed-By: {_clean_identity(acted_by)}"
                self._git(
                    "commit", "-q", "-F", "-", input=message + "\n",
                    env_extra={"GIT_AUTHOR_NAME": _clean_identity(alias),
                               "GIT_AUTHOR_EMAIL": COMMITTER_EMAIL},
                )
            except GitError:
                self._rollback(paths)
                raise
            self._pending.difference_update(paths)
            return {"commit": self._git("rev-parse", "--short", "HEAD"), "message": subject[:120], "files": paths}

    def _rollback(self, paths: list[str]) -> None:
        self._git("reset", "-q", check=False)
        for rel in paths:
            tracked = self._git("ls-files", "--error-unmatch", "--", rel, check=False)
            if tracked:
                self._git("checkout", "-q", "HEAD", "--", rel, check=False)
            else:
                with contextlib.suppress(OSError):
                    (self.path / rel).unlink()
        self._pending.difference_update(paths)

    def push(self) -> int:
        """Rebase onto the remote branch and push; returns the number of commits pushed."""
        with self._lock:
            if self._pending:
                raise BusyError("Changes are being written; try again shortly")
            try:
                self._git("fetch", "--prune", "origin", f"+refs/heads/{self._branch}:refs/remotes/origin/{self._branch}")
                if self._behind() > 0 and self._ahead() > 0:
                    self._rebase()
                ahead = self._ahead()
                if ahead:
                    self._git("push", "origin", f"HEAD:refs/heads/{self._branch}")
            except GitError as exc:
                self.last_error = str(exc)
                raise
            self.last_error = None
            return ahead
