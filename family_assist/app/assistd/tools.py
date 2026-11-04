from __future__ import annotations

import contextlib
import inspect
import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pathspec
import regex

from .questions import ASK_USER
from .questions import SCHEMA as ASK_USER_SCHEMA
from .rules import Rules
from .skills import LOAD_SKILL
from .skills import SCHEMA as LOAD_SKILL_SCHEMA

READ_TOOLS = ("list_dir", "find", "grep", "read_file")
INTERACTIVE_TOOLS = (ASK_USER, LOAD_SKILL)  # handled by the agent loop, not by the Sandbox
WRITE_TOOLS = ("create_file", "write_file", "append_file", "replace_in_file")

MAX_FILE_BYTES = 256 * 1024
MAX_SCAN_BYTES = 2 * 1024 * 1024
MAX_LIST_ENTRIES = 500
MAX_FIND_RESULTS = 200
MAX_WALK_ENTRIES = 20000
MAX_GREP_RESULTS = 100
MAX_EDITS = 50
GREP_DEADLINE_SECONDS = 10.0
INSTRUCTIONS_MAX_BYTES = 32 * 1024


class ToolError(Exception):
    pass


@dataclass
class Outcome:
    text: str
    ok: bool = True
    touched: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()


def effective_tools(rules: Rules, allow_commits: bool) -> list[str]:
    available = READ_TOOLS + INTERACTIVE_TOOLS + (WRITE_TOOLS if allow_commits else ())
    if rules.tools is None:
        return list(available)
    return [t for t in available if t in rules.tools]


def unknown_tool_names(rules: Rules) -> list[str]:
    if rules.tools is None:
        return []
    return sorted(rules.tools - set(READ_TOOLS) - set(INTERACTIVE_TOOLS) - set(WRITE_TOOLS))


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


_STR = {"type": "string"}
SCHEMAS: dict[str, tuple[str, dict[str, Any]]] = {
    ASK_USER: ASK_USER_SCHEMA,
    LOAD_SKILL: LOAD_SKILL_SCHEMA,
    "list_dir": (
        "List the files and folders in a folder of the environment. Folders end with '/'.",
        _obj(
            {
                "path": {
                    **_STR,
                    "description": "Folder relative to the environment root; empty for the root",
                }
            },
            [],
        ),
    ),
    "find": (
        (
            "Find files by glob pattern (gitignore syntax, e.g. '*.md' or 'Mathe/**/Klasse-8*'). "
            "A pattern ending in '/' finds folders instead of files."
        ),
        _obj(
            {
                "pattern": _STR,
                "path": {**_STR, "description": "Folder to search in; empty for the root"},
            },
            ["pattern"],
        ),
    ),
    "grep": (
        "Search text files with a regular expression. Returns 'path:line: text' matches.",
        _obj(
            {
                "pattern": {**_STR, "description": "Regular expression"},
                "path": {**_STR, "description": "File or folder to search; empty for the root"},
                "glob": {**_STR, "description": "Optional file name filter such as '*.md'"},
                "ignore_case": {"type": "boolean", "description": "Default true"},
            },
            ["pattern"],
        ),
    ),
    "read_file": (
        "Read a text file, optionally only a range of lines.",
        _obj(
            {
                "path": _STR,
                "start_line": {"type": "integer", "description": "First line, 1-based"},
                "end_line": {"type": "integer", "description": "Last line, inclusive"},
            },
            ["path"],
        ),
    ),
    "create_file": (
        "Create a new file. Fails if the file already exists.",
        _obj({"path": _STR, "content": _STR}, ["path", "content"]),
    ),
    "write_file": (
        "Create a file or overwrite it completely with the given content.",
        _obj({"path": _STR, "content": _STR}, ["path", "content"]),
    ),
    "append_file": (
        "Append text to the end of a file (created if missing).",
        _obj({"path": _STR, "content": _STR}, ["path", "content"]),
    ),
    "replace_in_file": (
        (
            "Replace exact text in a file. Give either old_string and new_string, or a list of "
            "edits. Every old_string must occur exactly once; if any edit fails, nothing is "
            "changed."
        ),
        _obj(
            {
                "path": _STR,
                "old_string": _STR,
                "new_string": _STR,
                "edits": {
                    "type": "array",
                    "items": _obj(
                        {"old_string": _STR, "new_string": _STR}, ["old_string", "new_string"]
                    ),
                },
            },
            ["path"],
        ),
    ),
}


def tool_schemas(enabled: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": n, "description": SCHEMAS[n][0], "parameters": SCHEMAS[n][1]},
        }
        for n in enabled
    ]


def _int(value: Any, name: str, default: int | None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be an integer") from None


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "")
    return default if value is None else bool(value)


class Sandbox:
    """File tools confined to one checkout, filtered by the repository's rules."""

    def __init__(
        self,
        root: Path,
        rules: Rules,
        enabled: list[str],
        *,
        max_result_bytes: int = 32 * 1024,
        write_guard: Callable[[str], contextlib.AbstractContextManager[Any]] | None = None,
    ):
        self.root = Path(os.path.realpath(root))
        self.rules = rules
        self.enabled = list(enabled)
        self.max_result_bytes = max_result_bytes
        self._guard = write_guard or (lambda rel: contextlib.nullcontext())

    # --- path handling -------------------------------------------------

    def _not_found(self, path: str) -> ToolError:
        return ToolError(f"not found: {path}")

    def _lexical(self, path: Any) -> str:
        if not isinstance(path, str):
            raise ToolError("path must be a string")
        if "\0" in path:
            raise self._not_found(path)
        parts = [p for p in path.replace("\\", "/").strip().split("/") if p not in ("", ".")]
        if ".." in parts:
            raise self._not_found(path)
        return "/".join(parts)

    def _resolve(self, path: Any) -> tuple[Path, str]:
        rel = self._lexical(path)
        target = Path(os.path.realpath(self.root / rel))
        try:
            real_rel = target.relative_to(self.root).as_posix()
        except ValueError:
            raise self._not_found(path) from None
        if real_rel == ".":
            real_rel = ""
        is_dir = target.is_dir()
        for candidate in {rel, real_rel}:
            if candidate and self.rules.is_hidden(candidate, is_dir):
                raise self._not_found(path)
        return target, real_rel

    def _resolve_writable(self, path: Any) -> tuple[Path, str]:
        target, rel = self._resolve(path)
        lexical = self._lexical(path)
        if not rel:
            raise ToolError("path must name a file")
        if target.is_dir():
            raise ToolError(f"{path} is a folder")
        for candidate in {rel, lexical}:
            if self.rules.is_readonly(candidate, False):
                raise ToolError(f"read-only: {path}")
        return target, rel

    def _visible(self, rel: str, is_dir: bool) -> bool:
        return not self.rules.is_hidden(rel, is_dir)

    @staticmethod
    def _is_link(path: Path) -> bool:
        """True for symlinks, junctions and anything below one (listings never follow links)."""
        return Path(os.path.realpath(path)) != path

    # --- read tools ----------------------------------------------------

    def tool_list_dir(self, path: str = "") -> Outcome:
        target, rel = self._resolve(path)
        if not target.is_dir():
            raise self._not_found(path)
        entries: list[str] = []
        with os.scandir(target) as it:
            for e in it:
                if self._is_link(Path(e.path)):
                    continue
                is_dir = e.is_dir(follow_symlinks=False)
                child = f"{rel}/{e.name}" if rel else e.name
                if self.rules.is_hidden(child, is_dir):
                    continue
                entries.append(e.name + ("/" if is_dir else ""))
        entries.sort(key=lambda s: (not s.endswith("/"), s.lower()))
        extra = len(entries) - MAX_LIST_ENTRIES
        text = "\n".join(entries[:MAX_LIST_ENTRIES]) or "(empty)"
        if extra > 0:
            text += f"\n[{extra} more entries omitted]"
        return Outcome(text, touched=(rel,))

    def _walk_files(self, start: Path, start_rel: str) -> Iterator[tuple[Path, str]]:
        """Yield (file_path, rel_to_root) for visible regular files below start."""
        scanned = 0
        for dirpath, dirnames, filenames in os.walk(start, followlinks=False):
            here = Path(dirpath).relative_to(self.root).as_posix()
            here = "" if here == "." else here
            dirnames[:] = sorted(
                d
                for d in dirnames
                if not self._is_link(Path(dirpath) / d)
                and not self.rules.is_hidden(f"{here}/{d}" if here else d, True)
            )
            for name in sorted(filenames):
                scanned += 1
                if scanned > MAX_WALK_ENTRIES:
                    return
                full = Path(dirpath) / name
                rel = f"{here}/{name}" if here else name
                if self._is_link(full) or self.rules.is_hidden(rel, False):
                    continue
                yield full, rel

    def tool_find(self, pattern: str, path: str = "") -> Outcome:
        if (
            not isinstance(pattern, str)
            or not pattern.strip()
            or pattern.lstrip().startswith(("!", "#"))
        ):
            raise ToolError("invalid pattern")
        target, rel = self._resolve(path)
        if not target.is_dir():
            raise self._not_found(path)
        dirs_mode = pattern.strip().endswith("/")
        spec = pathspec.GitIgnoreSpec.from_lines([pattern.strip()])
        prefix = f"{rel}/" if rel else ""
        found: list[str] = []
        if dirs_mode:
            for dirpath, dirnames, _ in os.walk(target, followlinks=False):
                here = Path(dirpath).relative_to(self.root).as_posix()
                here = "" if here == "." else here
                keep = []
                for d in sorted(dirnames):
                    child = f"{here}/{d}" if here else d
                    if self._is_link(Path(dirpath) / d) or self.rules.is_hidden(child, True):
                        continue
                    keep.append(d)
                    if spec.match_file(child[len(prefix) :] + "/"):
                        found.append(child + "/")
                dirnames[:] = keep
                if len(found) > MAX_FIND_RESULTS:
                    break
        else:
            for _, frel in self._walk_files(target, rel):
                if spec.match_file(frel[len(prefix) :]):
                    found.append(frel)
                    if len(found) > MAX_FIND_RESULTS:
                        break
        extra = len(found) > MAX_FIND_RESULTS
        text = "\n".join(found[:MAX_FIND_RESULTS]) or "(no matches)"
        if extra:
            text += "\n[more results omitted; narrow the pattern]"
        return Outcome(text, touched=(rel,))

    def _read_bytes(self, target: Path, limit: int) -> bytes:
        try:
            with target.open("rb") as fh:
                data = fh.read(limit + 1)
        except OSError:
            raise ToolError("cannot read file") from None
        if len(data) > limit:
            raise ToolError("file too large")
        if b"\0" in data[:4096]:
            raise ToolError("binary file")
        return data

    def tool_grep(
        self, pattern: str, path: str = "", glob: str = "", ignore_case: Any = True
    ) -> Outcome:
        if not isinstance(pattern, str) or not pattern or len(pattern) > 300:
            raise ToolError("invalid pattern")
        try:
            rx = regex.compile(pattern, regex.IGNORECASE if _bool(ignore_case, True) else 0)
        except regex.error as exc:
            raise ToolError(f"invalid regular expression: {exc}") from None
        target, rel = self._resolve(path)
        if not target.exists():
            raise self._not_found(path)
        glob_spec = (
            pathspec.GitIgnoreSpec.from_lines([glob.strip()])
            if isinstance(glob, str) and glob.strip()
            else None
        )
        files = [(target, rel)] if target.is_file() else self._walk_files(target, rel)
        deadline = time.monotonic() + GREP_DEADLINE_SECONDS
        results: list[str] = []
        note = ""
        for full, frel in files:
            if glob_spec and not glob_spec.match_file(frel):
                continue
            if time.monotonic() > deadline:
                note = "\n[search stopped: time limit]"
                break
            try:
                if full.stat().st_size > MAX_SCAN_BYTES:
                    continue
                data = self._read_bytes(full, MAX_SCAN_BYTES)
            except (ToolError, OSError):
                continue
            for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                try:
                    hit = rx.search(line[:2000], timeout=0.25)
                except TimeoutError:
                    raise ToolError("regular expression too slow") from None
                if hit:
                    results.append(f"{frel}:{number}: {line.strip()[:300]}")
                    if len(results) >= MAX_GREP_RESULTS:
                        break
            if len(results) >= MAX_GREP_RESULTS:
                note = "\n[more results omitted; narrow the search]"
                break
        return Outcome(("\n".join(results) or "(no matches)") + note, touched=(rel,))

    def tool_read_file(self, path: str, start_line: Any = None, end_line: Any = None) -> Outcome:
        target, rel = self._resolve(path)
        if not target.is_file():
            raise self._not_found(path)
        text = self._read_bytes(target, 4 * 1024 * 1024).decode("utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)
        first = max(1, _int(start_line, "start_line", 1) or 1)
        last = min(total, _int(end_line, "end_line", total) or total)
        body = "\n".join(lines[first - 1 : last])
        raw = body.encode("utf-8")
        if len(raw) > self.max_result_bytes:
            body = raw[: self.max_result_bytes].decode("utf-8", errors="ignore")
            last = first - 1 + body.count("\n") + 1
            body += f"\n[truncated; continue with start_line={last + 1}]"
        elif first != 1 or last != total:
            body += f"\n[lines {first}-{last} of {total}]"
        return Outcome(body, touched=(rel,))

    # --- write tools ---------------------------------------------------

    @staticmethod
    def _encode(content: Any) -> bytes:
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise ToolError(f"content too large (limit {MAX_FILE_BYTES // 1024} KB)")
        return data

    @staticmethod
    def _replace_atomic(target: Path, data: bytes) -> None:
        tmp = target.with_name(f".fa-tmp-{uuid.uuid4().hex}")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, target)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()

    def tool_create_file(self, path: str, content: str) -> Outcome:
        data = self._encode(content)
        target, rel = self._resolve_writable(path)
        with self._guard(rel):
            if target.exists():
                raise ToolError(f"{rel} already exists; use replace_in_file or write_file")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as fh:
                fh.write(data)
        return Outcome(f"Created {rel} ({len(data)} bytes)", touched=(rel,), changed=(rel,))

    def tool_write_file(self, path: str, content: str) -> Outcome:
        data = self._encode(content)
        target, rel = self._resolve_writable(path)
        with self._guard(rel):
            target.parent.mkdir(parents=True, exist_ok=True)
            self._replace_atomic(target, data)
        return Outcome(f"Wrote {rel} ({len(data)} bytes)", touched=(rel,), changed=(rel,))

    def tool_append_file(self, path: str, content: str) -> Outcome:
        data = self._encode(content)
        target, rel = self._resolve_writable(path)
        with self._guard(rel):
            old = self._read_bytes(target, MAX_FILE_BYTES) if target.exists() else b""
            if len(old) + len(data) > MAX_FILE_BYTES:
                raise ToolError(f"file would exceed {MAX_FILE_BYTES // 1024} KB")
            target.parent.mkdir(parents=True, exist_ok=True)
            self._replace_atomic(target, old + data)
        return Outcome(f"Appended {len(data)} bytes to {rel}", touched=(rel,), changed=(rel,))

    def tool_replace_in_file(
        self, path: str, old_string: Any = None, new_string: Any = None, edits: Any = None
    ) -> Outcome:
        if edits is None:
            if old_string is None or new_string is None:
                raise ToolError("give old_string and new_string, or edits")
            edits = [{"old_string": old_string, "new_string": new_string}]
        if not isinstance(edits, list) or not edits or len(edits) > MAX_EDITS:
            raise ToolError(f"edits must be a list of 1 to {MAX_EDITS} items")
        target, rel = self._resolve_writable(path)
        with self._guard(rel):
            if not target.is_file():
                raise self._not_found(path)
            text = self._read_bytes(target, MAX_FILE_BYTES).decode("utf-8", errors="strict")
            for index, edit in enumerate(edits, 1):
                if not isinstance(edit, dict):
                    raise ToolError(f"edit {index}: must be an object")
                old = edit.get("old_string", edit.get("old"))
                new = edit.get("new_string", edit.get("new"))
                if not isinstance(old, str) or not old or not isinstance(new, str):
                    raise ToolError(
                        f"edit {index}: old_string must be non-empty text and new_string text"
                    )
                count = text.count(old)
                if count != 1:
                    raise ToolError(
                        f"edit {index}: old_string found {count} times (must be exactly 1); "
                        "nothing was changed"
                    )
                text = text.replace(old, new, 1)
            data = self._encode(text)
            self._replace_atomic(target, data)
        return Outcome(f"Applied {len(edits)} edit(s) to {rel}", touched=(rel,), changed=(rel,))

    # --- instructions in subfolders -------------------------------------

    def locate_file(self, path: str, max_bytes: int = 5 * 1024 * 1024) -> Path:
        """Real path of a visible regular file inside the checkout, for downloads."""
        target, _ = self._resolve(path)
        if not target.is_file() or target.stat().st_size > max_bytes:
            raise self._not_found(path)
        return target

    def read_instructions(self, rel_dir: str) -> str | None:
        """Text of `<rel_dir>/AGENTS.md` if it is visible and readable."""
        try:
            target, _ = self._resolve(f"{rel_dir}/AGENTS.md")
            if not target.is_file():
                return None
            data = self._read_bytes(target, INSTRUCTIONS_MAX_BYTES)
        except ToolError:
            return None
        return data.decode("utf-8", errors="replace")

    # --- dispatch --------------------------------------------------------

    def execute(self, name: str, arguments: Any) -> Outcome:
        if name not in self.enabled:
            return Outcome(f"Error: unknown tool '{name}'", ok=False)
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except ValueError:
                arguments = None
        if not isinstance(arguments, dict):
            return Outcome("Error: arguments must be an object", ok=False)
        func = getattr(self, f"tool_{name}")
        try:
            outcome: Outcome = func(**arguments)
        except ToolError as exc:
            return Outcome(f"Error: {exc}", ok=False)
        except TypeError:
            params = ", ".join(inspect.signature(func).parameters)
            return Outcome(f"Error: invalid arguments for {name}; parameters: {params}", ok=False)
        except (OSError, UnicodeError):
            return Outcome("Error: file operation failed", ok=False)
        raw = outcome.text.encode("utf-8")
        if len(raw) > self.max_result_bytes:
            outcome.text = (
                raw[: self.max_result_bytes].decode("utf-8", errors="ignore")
                + "\n[output truncated; narrow the request]"
            )
        return outcome
