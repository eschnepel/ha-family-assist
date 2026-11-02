from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import dataclasses
import datetime as dt
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .agent import Deps, Principal, read_root_agents, run_turn
from .config import (DEFAULT_ENV_ID, EnvConfig, Settings, ValidationError, clean_alias, name_from_url,
                     validate_branch, validate_repo_url)
from .ghcli import GhError
from .gitenv import BusyError, GitError
from .identity import HAUser, UserDirectory, UserDirectoryError
from .rules import Rules
from .tools import Sandbox, ToolError, effective_tools, unknown_tool_names

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
INGRESS_ADDRESSES = {"172.30.32.2", "127.0.0.1", "::1"}
MAX_IMAGES = 4
MAX_IMAGE_CHARS = 8_000_000
_IMAGE_RE = re.compile(r"^data:image/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'")


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("empty title")
        return v


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    images: list[str] = Field(default_factory=list, max_length=MAX_IMAGES)
    lang: str = Field(default="en", pattern="^(de|en)$")

    @field_validator("images")
    @classmethod
    def _check_images(cls, images: list[str]) -> list[str]:
        for image in images:
            if len(image) > MAX_IMAGE_CHARS or not _IMAGE_RE.match(image):
                raise ValueError("invalid image")
            try:
                base64.b64decode(image.split(",", 1)[1], validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("invalid image") from None
        return images


class EnvIn(BaseModel):
    id: str | None = Field(default=None, max_length=16)
    name: str = Field(default="", max_length=100)
    repo_url: str = Field(max_length=500)
    branch: str = Field(default="main", max_length=100)


class SettingsIn(BaseModel):
    environments: list[EnvIn] = Field(default_factory=list, max_length=20)
    allow_commits: bool
    allow_push: bool
    aliases: dict[str, str] = Field(default_factory=dict)
    auth_method: Literal["token", "github_cli"] = "token"
    git_token: str | None = Field(default=None, max_length=500)


@dataclass
class Ctx:
    real: HAUser
    eff: HAUser
    real_alias: str
    eff_alias: str

    @property
    def acting(self) -> bool:
        return self.real.id != self.eff.id

    @property
    def principal(self) -> Principal:
        return Principal(self.eff.id, self.eff_alias, self.real_alias if self.acting else None)


@dataclass
class State:
    deps: Deps
    users: UserDirectory
    dev: bool
    running: set[tuple[str, str]] = field(default_factory=set)
    tasks: set[asyncio.Task] = field(default_factory=set)


def create_app(deps: Deps, users: UserDirectory, *, dev: bool = False, background: bool = True,
               dev_user: str = "") -> FastAPI:
    state = State(deps, users, dev)
    env, settings_store, gh = deps.env, deps.settings, deps.gh

    def apply_settings() -> Settings:
        settings = settings_store.get()
        token = gh.token if gh and settings.auth_method == "github_cli" else settings_store.git_token()
        for cfg in settings.environments:
            deps.env_for(cfg.id).configure(cfg.repo_url, cfg.branch, token)
        return settings

    def env_of(env_id: str):
        """The checkout of a configured environment, else 404."""
        if settings_store.get().env(env_id) is None:
            raise HTTPException(404, "unknown environment")
        return deps.env_for(env_id)

    def pick_env(requested: str) -> str:
        """The requested environment id, or the first configured one when none is given."""
        settings = settings_store.get()
        if requested:
            if settings.env(requested) is None:
                raise HTTPException(404, "unknown environment")
            return requested
        if not settings.environments:
            raise HTTPException(404, "no environment configured")
        return settings.environments[0].id

    async def sync_now(target=None) -> None:
        targets = [target] if target is not None else [
            deps.env_for(cfg.id) for cfg in settings_store.get().environments]
        for item in targets:
            if not item.configured:
                continue
            try:
                await asyncio.to_thread(item.sync)
            except GitError as exc:
                log.warning("Sync of %s failed: %s", item.path.name, exc)

    def spawn(coro) -> None:
        task = asyncio.create_task(coro)
        state.tasks.add(task)
        task.add_done_callback(state.tasks.discard)

    async def periodic_sync() -> None:
        interval = deps.options.sync_interval_minutes
        await sync_now()
        while interval > 0:
            await asyncio.sleep(interval * 60)
            await sync_now()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        apply_settings()
        if gh:
            gh.on_success = lambda: spawn(sync_now())
        if background:
            spawn(periodic_sync())
        yield
        for task in list(state.tasks):
            task.cancel()
        if gh:
            await gh.cancel()
        await deps.ollama.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def secure(request: Request, call_next):
        client = request.client.host if request.client else ""
        if not dev and client not in INGRESS_ADDRESSES:
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        if request.method not in ("GET", "HEAD") and request.headers.get("x-requested-with") != "family-assist":
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = (
            "public, max-age=86400" if request.url.path.startswith("/static/vendor/") else "no-store")
        return response

    def alias_of(user: HAUser) -> str:
        return settings_store.get().aliases.get(user.id) or user.name

    async def ctx(request: Request) -> Ctx:
        uid = request.headers.get("x-remote-user-id") or dev_user
        if not uid:
            raise HTTPException(401, "not authenticated")
        try:
            users_list = await state.users.users()
        except UserDirectoryError as exc:
            raise HTTPException(503, str(exc)) from None
        by_id = {u.id: u for u in users_list}
        real = by_id.get(uid)
        if real is None:
            raise HTTPException(403, "unknown user")
        eff = real
        act_as = request.headers.get("x-act-as", "")
        if act_as and act_as != real.id:
            if not real.is_admin:
                raise HTTPException(403, "admin only")
            eff = by_id.get(act_as)
            if eff is None:
                raise HTTPException(404, "unknown user")
        return Ctx(real, eff, alias_of(real), alias_of(eff))

    async def admin(c: Ctx = Depends(ctx)) -> Ctx:
        if not c.real.is_admin:
            raise HTTPException(403, "admin only")
        return c

    # --- chat ------------------------------------------------------------

    @app.get("/api/me")
    async def me(c: Ctx = Depends(ctx)):
        settings = settings_store.get()
        return {
            "id": c.eff.id, "alias": c.eff_alias, "is_admin": c.real.is_admin,
            "real_alias": c.real_alias, "acting": c.acting,
            "environments": [{"id": e.id, "name": e.name, "ready": deps.env_for(e.id).is_cloned()}
                             for e in settings.environments],
            "can_write": settings.allow_commits,
        }

    @app.get("/api/conversations")
    async def list_conversations(env: str = "", c: Ctx = Depends(ctx)):
        if not settings_store.get().environments:
            return []
        return deps.store.list(c.eff.id, pick_env(env))

    @app.post("/api/conversations")
    async def create_conversation(env: str = "", c: Ctx = Depends(ctx)):
        conv = deps.store.create(c.eff.id, pick_env(env))
        return {"id": conv["id"]}

    def public(conv: dict, uid: str) -> dict:
        return {**{k: v for k, v in conv.items() if k != "loaded_agents"},
                "busy": (uid, conv["id"]) in state.running}

    @app.get("/api/conversations/{cid}")
    async def get_conversation(cid: str, c: Ctx = Depends(ctx)):
        conv = deps.store.load(c.eff.id, cid)
        if conv is None:
            raise HTTPException(404, "not found")
        return public(conv, c.eff.id)

    @app.patch("/api/conversations/{cid}")
    async def rename_conversation(cid: str, body: RenameIn, c: Ctx = Depends(ctx)):
        conv = deps.store.load(c.eff.id, cid)
        if conv is None:
            raise HTTPException(404, "not found")
        if (c.eff.id, cid) in state.running:
            raise HTTPException(409, "a reply is being generated")
        conv["title"] = body.title
        deps.store.save(conv)
        return {"title": conv["title"]}

    @app.delete("/api/conversations/{cid}")
    async def delete_conversation(cid: str, c: Ctx = Depends(ctx)):
        conv = deps.store.load(c.eff.id, cid)
        if conv is None:
            raise HTTPException(404, "not found")
        if (c.eff.id, cid) in state.running:
            raise HTTPException(409, "a reply is being generated")
        deps.store.soft_delete(conv)
        return {"ok": True}

    @app.post("/api/conversations/{cid}/messages")
    async def post_message(cid: str, body: MessageIn, c: Ctx = Depends(ctx)):
        conv = deps.store.load(c.eff.id, cid)
        if conv is None:
            raise HTTPException(404, "not found")
        key = (c.eff.id, cid)
        if key in state.running:
            raise HTTPException(409, "a reply is already being generated")
        state.running.add(key)
        events: asyncio.Queue = asyncio.Queue()

        async def runner() -> None:
            try:
                async for event in run_turn(deps, c.principal, conv, body.text, body.images, body.lang):
                    events.put_nowait(event)
            finally:
                state.running.discard(key)
                events.put_nowait(None)

        spawn(runner())

        async def stream():
            while True:
                try:
                    event = await asyncio.wait_for(events.get(), 15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if event is None:
                    return
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no"})

    def changed_files(conv: dict) -> list[str]:
        """Paths the assistant wrote in this conversation; the only files offered for download."""
        seen: dict[str, None] = {}
        for message in conv["messages"]:
            for entry in message.get("tools", []):
                if entry.get("ok"):
                    seen.update(dict.fromkeys(entry.get("changed", [])))
        return list(seen)

    def visible_file(conv: dict, rel: str) -> Path | None:
        env = deps.env_for(conv.get("env_id", DEFAULT_ENV_ID))
        if rel not in changed_files(conv) or not env.is_cloned():
            return None
        try:
            return Sandbox(env.path, Rules.load(env.path), []).locate_file(rel)
        except ToolError:
            return None

    def attachment(data: bytes, filename: str, media_type: str) -> Response:
        ascii_name = re.sub(r'[^A-Za-z0-9._-]', "_", filename) or "download"
        disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
        return Response(data, media_type=media_type, headers={"Content-Disposition": disposition})

    def load_own(c: Ctx, cid: str) -> dict:
        conv = deps.store.load(c.eff.id, cid)
        if conv is None:
            raise HTTPException(404, "not found")
        return conv

    @app.get("/api/conversations/{cid}/files")
    async def conversation_files(cid: str, c: Ctx = Depends(ctx)):
        conv = load_own(c, cid)
        files = []
        for rel in changed_files(conv):
            target = visible_file(conv, rel)
            if target:
                files.append({"path": rel, "name": Path(rel).name, "size": target.stat().st_size})
        return files

    @app.get("/api/conversations/{cid}/files/{path:path}")
    async def download_file(cid: str, path: str, c: Ctx = Depends(ctx)):
        target = visible_file(load_own(c, cid), path)
        if target is None:
            raise HTTPException(404, "not found")
        return attachment(target.read_bytes(), Path(path).name, "application/octet-stream")

    @app.get("/api/conversations/{cid}/export")
    async def export_conversation(cid: str, c: Ctx = Depends(ctx)):
        conv = load_own(c, cid)
        created = dt.datetime.fromtimestamp(conv.get("created", 0), dt.timezone.utc).strftime("%Y-%m-%d")
        lines = [f"# {conv.get('title') or 'Conversation'}", "", f"{created}", ""]
        for message in conv["messages"]:
            lines += [f"## {c.eff_alias if message['role'] == 'user' else 'Assistant'}", ""]
            if message.get("content"):
                lines += [message["content"], ""]
            if message.get("images"):
                lines += [f"*{len(message['images'])} image(s) attached*", ""]
            if message.get("error"):
                lines += [f"> Error: {message['error']}", ""]
            files = list(dict.fromkeys(p for e in message.get("tools", []) if e.get("ok") for p in e.get("changed", [])))
            if files:
                lines += ["Files changed: " + ", ".join(f"`{p}`" for p in files), ""]
        slug = re.sub(r"[^a-z0-9]+", "-", (conv.get("title") or "").lower()).strip("-")[:40] or "conversation"
        return attachment("\n".join(lines).encode("utf-8"), f"{slug}-{created}.md", "text/markdown; charset=utf-8")

    @app.get("/api/family")
    async def family(c: Ctx = Depends(admin)):
        return [{"id": u.id, "name": u.name, "alias": alias_of(u), "is_admin": u.is_admin}
                for u in await state.users.users()]

    # --- admin -----------------------------------------------------------

    def settings_payload() -> dict:
        s = settings_store.get()
        return {"environments": [dataclasses.asdict(e) for e in s.environments],
                "allow_commits": s.allow_commits,
                "allow_push": s.allow_push, "aliases": s.aliases, "auth_method": s.auth_method,
                "has_token": bool(settings_store.git_token())}

    @app.get("/api/admin/settings")
    async def get_settings(c: Ctx = Depends(admin)):
        return settings_payload()

    @app.put("/api/admin/settings")
    async def put_settings(body: SettingsIn, c: Ctx = Depends(admin)):
        old = settings_store.get()
        old_token = settings_store.git_token()
        environments: list[EnvConfig] = []
        try:
            for item in body.environments:
                url = validate_repo_url(item.repo_url)
                if not url:
                    raise ValidationError("Every environment needs a repository URL")
                env_id = item.id if item.id and old.env(item.id) else uuid.uuid4().hex[:8]
                if any(e.id == env_id for e in environments):
                    raise ValidationError("Duplicate environment")
                environments.append(EnvConfig(env_id, clean_alias(item.name) or name_from_url(url), url,
                                              validate_branch(item.branch or "main")))
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from None
        aliases = {k[:64]: a for k, v in body.aliases.items() if (a := clean_alias(v))}
        settings_store.save(Settings(environments, body.allow_commits, body.allow_push, aliases,
                                     auth_method=body.auth_method))
        if body.git_token is not None:
            settings_store.set_git_token(body.git_token)
        new = apply_settings()
        token_changed = (new.auth_method, settings_store.git_token()) != (old.auth_method, old_token)
        for cfg in new.environments:
            before = old.env(cfg.id)
            if token_changed or before is None or (before.repo_url, before.branch) != (cfg.repo_url, cfg.branch):
                spawn(sync_now(deps.env_for(cfg.id)))
        for gone in old.environments:
            if new.env(gone.id) is None:
                await asyncio.to_thread(remove_checkout, gone.id)
        return settings_payload()

    def remove_checkout(env_id: str) -> None:
        """Deletes the checkout of a removed environment unless it holds work that exists nowhere else."""
        gone = deps.env_for(env_id)
        status = gone.status()
        if status["cloned"] and (status["ahead"] or status["pending"]):
            log.warning("Kept the checkout of removed environment %s: it has unpushed changes", env_id)
        else:
            shutil.rmtree(gone.path, ignore_errors=True)
        if env_id != DEFAULT_ENV_ID:
            deps.forget_env(env_id)

    @app.get("/api/admin/github")
    async def github_status(c: Ctx = Depends(admin)):
        if gh is None:
            return {"available": False, "logged_in": False, "account": "", "login": {"state": "idle"}}
        return await gh.status()

    @app.post("/api/admin/github/login")
    async def github_login(c: Ctx = Depends(admin)):
        if gh is None:
            raise HTTPException(503, "The GitHub CLI is not available")
        try:
            await gh.start_login()
        except GhError as exc:
            raise HTTPException(503, str(exc)) from None
        return await gh.status()

    @app.post("/api/admin/github/logout")
    async def github_logout(c: Ctx = Depends(admin)):
        if gh is None:
            raise HTTPException(503, "The GitHub CLI is not available")
        await gh.logout()
        return await gh.status()

    @app.post("/api/admin/sync")
    async def sync_endpoint(env: str = "", c: Ctx = Depends(admin)):
        target = env_of(pick_env(env))
        try:
            await asyncio.to_thread(target.sync)
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None
        except GitError as exc:
            raise HTTPException(502, str(exc)) from None
        return await asyncio.to_thread(target.status)

    @app.post("/api/admin/push")
    async def push_endpoint(env: str = "", c: Ctx = Depends(admin)):
        target = env_of(pick_env(env))
        try:
            await asyncio.to_thread(target.push)
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None
        except GitError as exc:
            raise HTTPException(502, str(exc)) from None
        return await asyncio.to_thread(target.status)

    async def environment_status(cfg: EnvConfig, settings: Settings) -> dict:
        target = deps.env_for(cfg.id)
        info: dict = {"id": cfg.id, "name": cfg.name, "env": await asyncio.to_thread(target.status),
                      "rules": None, "warnings": [], "model": None}
        model = deps.options.default_model
        if target.is_cloned():
            rules = Rules.load(target.path)
            text, front_model = read_root_agents(target.path)
            model = front_model or model
            info["rules"] = {"hidden": list(rules.hidden_lines), "readonly": list(rules.readonly_lines),
                             "tools": effective_tools(rules, settings.allow_commits)}
            info["warnings"] += list(rules.warnings)
            info["warnings"] += [f"Unknown tool in .family_assist.yaml: {n}" for n in unknown_tool_names(rules)]
            if not text:
                info["warnings"].append("The environment has no root AGENTS.md")
        info["model"] = await deps.ollama.check_model(model)
        if info["model"].get("tools") is False:
            info["warnings"].append(f"Model {model} does not report tool support")
        return info

    @app.get("/api/admin/deleted")
    async def deleted_conversations(c: Ctx = Depends(admin)):
        return await asyncio.to_thread(deps.store.list_deleted)

    @app.post("/api/admin/deleted/{uid}/{cid}/restore")
    async def restore_conversation(uid: str, cid: str, c: Ctx = Depends(admin)):
        try:
            ok = deps.store.restore(uid, cid)
        except ValueError:
            ok = False
        if not ok:
            raise HTTPException(404, "not found or expired")
        return {"ok": True}

    @app.get("/api/admin/status")
    async def admin_status(c: Ctx = Depends(admin)):
        options = deps.options
        settings = settings_store.get()
        return {
            "environments": [await environment_status(cfg, settings) for cfg in settings.environments],
            "options": {"ollama_url": options.ollama_url, "api_key_set": bool(options.ollama_api_key),
                        "default_model": options.default_model, "vision_model": options.vision_model,
                        "queue_enabled": options.queue_enabled,
                        "max_parallel_generations": options.max_parallel_generations},
            "queue": {"running": deps.queue.running, "waiting": deps.queue.waiting},
        }

    # --- static ------------------------------------------------------------

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
