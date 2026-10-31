from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pathspec

# Not overridable by the repository's own rule files.
BUILTIN_HIDDEN = (".git",)
BUILTIN_READONLY = (".agenthidden", ".agentreadonly", ".agenttools", "AGENTS.md")

HIDDEN_FILE = ".agenthidden"
READONLY_FILE = ".agentreadonly"
TOOLS_FILE = ".agenttools"
_MAX_RULE_FILE_BYTES = 64 * 1024


def _spec(lines) -> pathspec.GitIgnoreSpec:
    return pathspec.GitIgnoreSpec.from_lines(list(lines))


_BUILTIN_HIDDEN_SPEC = _spec(BUILTIN_HIDDEN)
_BUILTIN_READONLY_SPEC = _spec(BUILTIN_READONLY)


def _match(spec: pathspec.GitIgnoreSpec, rel: str, is_dir: bool) -> bool:
    return spec.match_file(rel + "/" if is_dir else rel)


def _read_lines(root: Path, name: str) -> list[str] | None:
    path = root / name
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as fh:
            data = fh.read(_MAX_RULE_FILE_BYTES)
    except OSError:
        return None
    text = data.decode("utf-8", errors="replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


@dataclass(frozen=True)
class Rules:
    hidden_lines: tuple[str, ...] = ()
    readonly_lines: tuple[str, ...] = ()
    tools: frozenset[str] | None = None
    warnings: tuple[str, ...] = ()

    @staticmethod
    def load(root: Path) -> "Rules":
        warnings: list[str] = []
        hidden = _read_lines(root, HIDDEN_FILE) or []
        readonly = _read_lines(root, READONLY_FILE) or []
        tool_lines = _read_lines(root, TOOLS_FILE)
        if hidden and _match(_spec(hidden), "AGENTS.md", False):
            warnings.append(f"A rule in {HIDDEN_FILE} matches the root AGENTS.md and is ignored for it")
        tools = None if tool_lines is None else frozenset(tool_lines)
        return Rules(tuple(hidden), tuple(readonly), tools, tuple(warnings))

    @cached_property
    def _hidden_spec(self) -> pathspec.GitIgnoreSpec:
        return _spec(self.hidden_lines)

    @cached_property
    def _readonly_spec(self) -> pathspec.GitIgnoreSpec:
        return _spec(self.readonly_lines)

    def is_hidden(self, rel: str, is_dir: bool = False) -> bool:
        if not rel or rel == "AGENTS.md":
            return False
        if _match(_BUILTIN_HIDDEN_SPEC, rel, is_dir):
            return True
        return bool(self.hidden_lines) and _match(self._hidden_spec, rel, is_dir)

    def is_readonly(self, rel: str, is_dir: bool = False) -> bool:
        if _match(_BUILTIN_READONLY_SPEC, rel, is_dir):
            return True
        return bool(self.readonly_lines) and _match(self._readonly_spec, rel, is_dir)
