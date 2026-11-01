from __future__ import annotations

import dataclasses
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

DATA_DIR = Path(os.environ.get("FA_DATA", "/data"))


@dataclass(frozen=True)
class Options:
    """Add-on options from the Supervisor (`/data/options.json`)."""

    ollama_url: str = "http://homeassistant.local:11434"
    ollama_api_key: str = ""
    default_model: str = "qwen3:8b"
    vision_model: str = ""
    num_ctx: int = 16384
    sync_interval_minutes: int = 60
    queue_enabled: bool = True
    max_parallel_generations: int = 1
    max_tool_calls_per_turn: int = 25
    max_tool_result_kb: int = 32


def load_options(path: Path | None = None) -> Options:
    path = path or DATA_DIR / "options.json"
    raw = json.loads(path.read_text("utf-8")) if path.exists() else {}
    known = {f.name for f in dataclasses.fields(Options)}
    return Options(**{k: v for k, v in raw.items() if k in known and v is not None})


def write_json_atomic(path: Path, data: object, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        if private:
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ValidationError(ValueError):
    pass


_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")


def validate_repo_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if len(url) > 500 or any(c.isspace() or ord(c) < 32 for c in url):
        raise ValidationError("Invalid repository URL")
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ValidationError("Repository URL must start with https:// or http://")
    if parts.username or parts.password:
        raise ValidationError("Do not put credentials in the URL; use the token field")
    return url


def validate_branch(branch: str) -> str:
    branch = branch.strip()
    if not _BRANCH_RE.match(branch) or ".." in branch:
        raise ValidationError("Invalid branch name")
    return branch


def clean_alias(alias: str) -> str:
    alias = " ".join(re.sub(r"[\x00-\x1f<>]", " ", alias).split())
    return alias[:60]


DEFAULT_ENV_ID = "default"
ENV_ID_RE = re.compile(r"^[a-z0-9]{1,16}$")


def name_from_url(url: str) -> str:
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return clean_alias(last.removesuffix(".git")) or "Environment"


@dataclass
class EnvConfig:
    """One Agent Environment: a git repository and branch."""

    id: str
    name: str
    repo_url: str
    branch: str = "main"


@dataclass
class Settings:
    """Admin settings edited in the UI."""

    environments: list[EnvConfig] = field(default_factory=list)
    allow_commits: bool = False
    allow_push: bool = False
    aliases: dict[str, str] = field(default_factory=dict)
    auth_method: str = "token"  # token | github_cli
    # Single-environment settings of earlier versions; migrated by SettingsStore.get().
    repo_url: str = ""
    branch: str = "main"

    def env(self, env_id: str) -> EnvConfig | None:
        return next((e for e in self.environments if e.id == env_id), None)


class SettingsStore:
    def __init__(self, data_dir: Path):
        self._settings_path = data_dir / "settings.json"
        self._secrets_path = data_dir / "secrets.json"
        self._lock = threading.Lock()

    def get(self) -> Settings:
        with self._lock:
            raw = self._read(self._settings_path)
            known = {f.name for f in dataclasses.fields(Settings)} - {"environments"}
            settings = Settings(**{k: v for k, v in raw.items() if k in known})
            env_fields = {f.name for f in dataclasses.fields(EnvConfig)}
            for item in raw.get("environments") or []:
                if isinstance(item, dict) and env_fields <= item.keys():
                    settings.environments.append(EnvConfig(**{k: item[k] for k in env_fields}))
            if settings.repo_url:
                # Migration: the former single repository becomes the default environment, which keeps
                # its checkout and its conversations (conversations without an environment belong to it).
                if not settings.environments:
                    settings.environments.append(EnvConfig(
                        DEFAULT_ENV_ID, name_from_url(settings.repo_url), settings.repo_url, settings.branch))
                settings.repo_url, settings.branch = "", "main"
                write_json_atomic(self._settings_path, dataclasses.asdict(settings))
            return settings

    def save(self, settings: Settings) -> None:
        with self._lock:
            write_json_atomic(self._settings_path, dataclasses.asdict(settings))

    def git_token(self) -> str:
        with self._lock:
            return str(self._read(self._secrets_path).get("git_token", ""))

    def set_git_token(self, token: str) -> None:
        with self._lock:
            write_json_atomic(self._secrets_path, {"git_token": token.strip()}, private=True)

    @staticmethod
    def _read(path: Path) -> dict:
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
