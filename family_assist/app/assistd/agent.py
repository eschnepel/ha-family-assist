from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator

import yaml

from .config import Options, SettingsStore
from .genqueue import GenerationQueue
from .ghcli import GitHubCli
from .gitenv import AgentEnvironment, GitError
from .ollama import OllamaClient, OllamaError
from .rules import Rules
from .store import ConversationStore
from .tools import Sandbox, effective_tools, tool_schemas

log = logging.getLogger(__name__)

ROOT_AGENTS_MAX_BYTES = 64 * 1024
HISTORY_MESSAGES = 20
KEEPALIVE_SECONDS = 10.0

PREAMBLE = """\
You are running inside Family Assist, a chat assistant for a family.
Current user: {alias}
Today: {today}

You can only use the tools provided to you to work with the files of your environment. \
Paths are relative to the environment root and use forward slashes. \
Some files may not exist for you; do not try to work around that. \
Never reveal or guess secrets, keys or tokens.
{write_note}
Follow the instructions below.

"""

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_MODEL_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,100}$")


@dataclass
class Deps:
    options: Options
    settings: SettingsStore
    env: AgentEnvironment
    ollama: OllamaClient
    store: ConversationStore
    queue: GenerationQueue
    gh: GitHubCli | None = None


@dataclass(frozen=True)
class Principal:
    """The family member a conversation belongs to, and the admin acting for them, if any."""

    id: str
    alias: str
    acted_by_alias: str | None = None


def read_root_agents(root) -> tuple[str, str | None]:
    """Text of the root AGENTS.md and the optional `modell:` from its front matter."""
    path = root / "AGENTS.md"
    try:
        if path.is_symlink() or not path.is_file():
            return "", None
        text = path.read_bytes()[:ROOT_AGENTS_MAX_BYTES].decode("utf-8", errors="replace")
    except OSError:
        return "", None
    model = None
    match = _FRONT_MATTER.match(text)
    if match:
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            meta = None
        value = meta.get("modell") if isinstance(meta, dict) else None
        if isinstance(value, str) and _MODEL_RE.match(value.strip()):
            model = value.strip()
    return text, model


def build_system_prompt(alias: str, agents_text: str, can_write: bool) -> str:
    write_note = (
        "You may create and change files; changes are saved automatically after your reply."
        if can_write
        else "You cannot change files."
    )
    return PREAMBLE.format(alias=alias, today=dt.date.today().isoformat(), write_note=write_note) + agents_text


def history_messages(conv: dict) -> list[dict]:
    """Earlier turns as plain user/assistant text; tool exchanges are not replayed."""
    out = []
    for msg in conv["messages"][-HISTORY_MESSAGES:]:
        if msg["role"] in ("user", "assistant") and msg.get("content"):
            out.append({"role": msg["role"], "content": msg["content"]})
    return out


def nested_instruction_dirs(sandbox: Sandbox, touched: tuple[str, ...], loaded: list[str]) -> list[tuple[str, str]]:
    found = []
    for rel in touched:
        parts = [p for p in rel.split("/") if p]
        if rel and not (sandbox.root / rel).is_dir():
            parts = parts[:-1]
        for i in range(1, len(parts) + 1):
            folder = "/".join(parts[:i])
            key = f"{folder}/AGENTS.md"
            if key in loaded:
                continue
            text = sandbox.read_instructions(folder)
            if text is not None:
                loaded.append(key)
                found.append((key, text))
    return found


async def run_turn(deps: Deps, principal: Principal, conv: dict, text: str,
                   images: list[str]) -> AsyncIterator[dict]:
    """One turn; yields UI events. Always persists the conversation and commits changes."""
    options, env = deps.options, deps.env
    settings = deps.settings.get()
    user_msg: dict = {"role": "user", "content": text, "ts": _now()}
    if images:
        user_msg["images"] = images
    if principal.acted_by_alias:
        user_msg["acted_by"] = principal.acted_by_alias
    history = history_messages(conv)
    conv["messages"].append(user_msg)
    conv["title"] = conv["title"] or make_teaser(text)
    deps.store.save(conv)

    assistant: dict = {"role": "assistant", "content": "", "tools": [], "ts": _now()}
    changed: list[str] = []
    ticket = None
    try:
        if not env.is_cloned():
            raise OllamaError("The agent environment is not ready yet. Ask an admin to configure it.")
        rules = Rules.load(env.path)
        enabled = effective_tools(rules, settings.allow_commits)
        sandbox = Sandbox(env.path, rules, enabled, max_result_bytes=options.max_tool_result_kb * 1024,
                          write_guard=env.write_guard)
        agents_text, front_model = read_root_agents(env.path)
        model = front_model or options.default_model
        if images:
            model = options.vision_model or model
        system = build_system_prompt(principal.alias, agents_text, settings.allow_commits and bool(
            set(enabled) & {"create_file", "write_file", "append_file", "replace_in_file"}))
        last_user = {"role": "user", "content": text}
        if images:
            last_user["images"] = [i.split(",", 1)[1] for i in images]
        messages = [{"role": "system", "content": system}, *history, last_user]
        schemas = tool_schemas(enabled)

        ticket = deps.queue.enqueue()
        position = None
        while not ticket.granted.is_set():
            now_position = deps.queue.position(ticket)
            if now_position != position:
                position = now_position
                yield {"type": "queued", "position": position}
            ticket.moved.clear()
            try:
                await asyncio.wait_for(ticket.moved.wait(), KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                pass
        yield {"type": "start"}

        calls_made = 0
        limit_hit = False
        while not limit_hit:
            content, tool_calls = "", []
            async for chunk in deps.ollama.chat_stream(model=model, messages=messages, tools=schemas,
                                                       num_ctx=options.num_ctx):
                message = chunk.get("message") or {}
                if message.get("content"):
                    content += message["content"]
                    yield {"type": "token", "text": message["content"]}
                tool_calls.extend(message.get("tool_calls") or [])
            assistant["content"] += content
            if not tool_calls:
                break
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for call in tool_calls:
                if calls_made >= options.max_tool_calls_per_turn:
                    limit_hit = True
                    yield {"type": "notice", "text": "tool_limit"}
                    assistant["notice"] = "tool_limit"
                    break
                calls_made += 1
                function = call.get("function") or {}
                name = str(function.get("name", ""))
                args = function.get("arguments") or {}
                outcome = await asyncio.to_thread(sandbox.execute, name, args)
                result = outcome.text
                if outcome.ok:
                    for folder, extra in nested_instruction_dirs(sandbox, outcome.touched, conv["loaded_agents"]):
                        result += f"\n\n[Additional instructions from {folder}]\n{extra}"
                changed.extend(outcome.changed)
                entry = {"name": name, "args": args if isinstance(args, dict) else {}, "result": result,
                         "ok": outcome.ok, "changed": list(outcome.changed)}
                assistant["tools"].append(entry)
                yield {"type": "tool", **entry}
                messages.append({"role": "tool", "tool_name": name, "content": result})
        if not assistant["content"] and not assistant["tools"]:
            assistant["notice"] = "empty"
            yield {"type": "notice", "text": "empty"}
    except OllamaError as exc:
        assistant["error"] = str(exc)
        yield {"type": "error", "text": str(exc)}
    except Exception:
        log.exception("Turn failed")
        assistant["error"] = "Internal error"
        yield {"type": "error", "text": "Internal error"}
    finally:
        if ticket is not None:
            deps.queue.release(ticket)

    if changed:
        commit = await _commit(deps, settings, principal, changed)
        assistant["commit"] = commit
        yield {"type": "commit", **commit}
    conv["messages"].append(assistant)
    conv["updated"] = _now()
    deps.store.save(conv)
    yield {"type": "done"}


async def _commit(deps: Deps, settings, principal: Principal, changed: list[str]) -> dict:
    result: dict = {}
    try:
        info = await asyncio.to_thread(deps.env.commit, changed, principal.alias, principal.acted_by_alias)
        if info is None:
            return {"commit": None, "message": "no changes", "files": sorted(set(changed))}
        result = dict(info)
    except GitError as exc:
        return {"commit": None, "message": "commit failed", "files": sorted(set(changed)), "error": str(exc)}
    if settings.allow_push:
        try:
            await asyncio.to_thread(deps.env.push)
            result["pushed"] = True
        except GitError as exc:
            result["pushed"] = False
            result["error"] = str(exc)
    return result


def make_teaser(text: str, limit: int = 40) -> str:
    """Short chat title from the first prompt: whitespace collapsed, cut at a word boundary."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    if flat[limit] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") + "…"


def _now() -> float:
    return dt.datetime.now(dt.timezone.utc).timestamp()
