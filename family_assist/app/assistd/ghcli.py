from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HOST = "github.com"
DEVICE_URL = "https://github.com/login/device"
_CODE_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b")
_ACCOUNT_RE = re.compile(r"account\s+(\S+)")
_TOKEN_CACHE_SECONDS = 30.0


class GhError(Exception):
    pass


@dataclass
class LoginState:
    state: str = "idle"  # idle | pending | done | failed
    code: str = ""
    error: str = ""


class GitHubCli:
    """Signs in to GitHub with the `gh` CLI (device flow) and hands out its token to git."""

    def __init__(self, config_dir: Path, *, command: tuple[str, ...] = ("gh",), login_timeout: float = 900.0):
        self.config_dir = config_dir
        self._command = tuple(command)
        self._login_timeout = login_timeout
        self.login = LoginState()
        self.on_success: Callable[[], None] | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None
        self._cached: tuple[float, str] | None = None

    @property
    def available(self) -> bool:
        return shutil.which(self._command[0]) is not None

    def _env(self) -> dict[str, str]:
        keep = ("PATH", "LANG", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "TMPDIR")
        env = {k: os.environ[k] for k in keep if k in os.environ}
        self.config_dir.mkdir(parents=True, exist_ok=True)
        env.update(GH_CONFIG_DIR=str(self.config_dir), HOME=str(self.config_dir), GH_PROMPT_DISABLED="1",
                   NO_COLOR="1", GH_NO_UPDATE_NOTIFIER="1", GH_NO_EXTENSION_UPDATE_NOTIFIER="1")
        return env

    def _run(self, *args: str, timeout: float = 15.0) -> subprocess.CompletedProcess:
        return subprocess.run([*self._command, *args], env=self._env(), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)

    def token(self) -> str:
        """Current token, or an empty string when not signed in. Safe to call from any thread."""
        now = time.monotonic()
        if self._cached and now - self._cached[0] < _TOKEN_CACHE_SECONDS:
            return self._cached[1]
        token = ""
        if self.available:
            try:
                proc = self._run("auth", "token", "--hostname", HOST)
                token = proc.stdout.strip() if proc.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                token = ""
        self._cached = (now, token)
        return token

    def _forget_token(self) -> None:
        self._cached = None

    def _account(self) -> str:
        try:
            proc = self._run("auth", "status", "--hostname", HOST)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        match = _ACCOUNT_RE.search(proc.stdout + proc.stderr)
        return match.group(1) if match else ""

    async def status(self) -> dict:
        info = {"available": self.available, "logged_in": False, "account": "", "login": self._login_info()}
        if info["available"]:
            info["logged_in"] = bool(await asyncio.to_thread(self.token))
            if info["logged_in"]:
                info["account"] = await asyncio.to_thread(self._account)
        return info

    def _login_info(self) -> dict:
        return {"state": self.login.state, "code": self.login.code, "url": DEVICE_URL, "error": self.login.error}

    async def start_login(self) -> dict:
        if not self.available:
            raise GhError("The GitHub CLI is not installed")
        await self.cancel()
        self.login = LoginState("pending")
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._command, "auth", "login", "--hostname", HOST, "--git-protocol", "https", "--web",
                "--insecure-storage", "--skip-ssh-key", env=self._env(), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except OSError as exc:
            self.login = LoginState("failed", error=f"Cannot start the GitHub CLI: {exc}"[:200])
            return self._login_info()
        self._task = asyncio.create_task(self._watch(self._proc, self.login))
        for _ in range(200):
            if self.login.code or self.login.state != "pending":
                break
            await asyncio.sleep(0.1)
        return self._login_info()

    async def _pump(self, proc: asyncio.subprocess.Process, login: LoginState) -> str:
        output = ""
        while True:
            chunk = await proc.stdout.read(512)
            if not chunk:
                break
            output += chunk.decode("utf-8", errors="replace")
            if not login.code:
                match = _CODE_RE.search(output)
                if match:
                    login.code = match.group(0)
        await proc.wait()
        return output

    async def _watch(self, proc: asyncio.subprocess.Process, login: LoginState) -> None:
        try:
            output = await asyncio.wait_for(self._pump(proc, login), self._login_timeout)
        except asyncio.TimeoutError:
            proc.kill()
            login.state, login.error = "failed", "The sign-in timed out"
            return
        except asyncio.CancelledError:
            proc.kill()
            raise
        self._forget_token()
        if proc.returncode == 0:
            login.state, login.code = "done", ""
            if self.on_success:
                self.on_success()
        else:
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            login.state, login.error = "failed", (lines[-1] if lines else "Sign-in failed")[:200]

    async def cancel(self) -> None:
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
        self._proc = None
        if self.login.state == "pending":
            self.login = LoginState()

    async def logout(self) -> None:
        await self.cancel()
        if self.available:
            try:
                await asyncio.to_thread(self._run, "auth", "logout", "--hostname", HOST)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self._forget_token()
        self.login = LoginState()
