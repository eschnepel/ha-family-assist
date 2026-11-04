from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import pathspec
import yaml

# Not overridable by the repository's own rule files.
BUILTIN_HIDDEN = (".git",)
BUILTIN_READONLY = (".family_assist.yaml", "AGENTS.md")

CONFIG_FILE = ".family_assist.yaml"
_MAX_RULE_FILE_BYTES = 64 * 1024


def _spec(lines: Iterable[str]) -> pathspec.GitIgnoreSpec:
    return pathspec.GitIgnoreSpec.from_lines(list(lines))


_BUILTIN_HIDDEN_SPEC = _spec(BUILTIN_HIDDEN)
_BUILTIN_READONLY_SPEC = _spec(BUILTIN_READONLY)


def _match(spec: pathspec.GitIgnoreSpec, rel: str, is_dir: bool) -> bool:
    return spec.match_file(rel + "/" if is_dir else rel)


def _read_config(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / CONFIG_FILE
    try:
        if path.is_symlink() or not path.is_file():
            return {}, []
        with path.open("rb") as fh:
            data = fh.read(_MAX_RULE_FILE_BYTES)
    except OSError:
        return {}, []
    try:
        doc = yaml.safe_load(data.decode("utf-8", errors="replace"))
    except yaml.YAMLError:
        return {}, [f"{CONFIG_FILE} is not valid YAML and is ignored"]
    if doc is None:
        return {}, []
    if not isinstance(doc, dict):
        return {}, [f"{CONFIG_FILE} must be a mapping and is ignored"]
    return doc, []


def _string_list(doc: dict[str, Any], key: str, warnings: list[str]) -> list[str] | None:
    if key not in doc or doc[key] is None:
        return None
    value = doc[key]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        warnings.append(f"{key} in {CONFIG_FILE} must be a list of strings and is ignored")
        return None
    return [v.strip() for v in value if v.strip()]


@dataclass(frozen=True)
class Rules:
    hidden_lines: tuple[str, ...] = ()
    readonly_lines: tuple[str, ...] = ()
    tools: frozenset[str] | None = None
    warnings: tuple[str, ...] = ()

    @staticmethod
    def load(root: Path) -> Rules:
        doc, warnings = _read_config(root)
        hidden = _string_list(doc, "hidden", warnings) or []
        readonly = _string_list(doc, "readonly", warnings) or []
        tool_lines = _string_list(doc, "tools", warnings)
        if hidden and _match(_spec(hidden), "AGENTS.md", False):
            warnings.append(
                f"A rule in {CONFIG_FILE} (hidden) matches the root AGENTS.md and is ignored for it"
            )
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
