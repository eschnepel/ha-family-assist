from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .agent import Deps, Principal, read_root_agents, run_turn
from .config import Settings, ValidationError, clean_alias, validate_branch, validate_repo_url
from .ghcli import GhError
from .gitenv import BusyError, GitError
from .identity import HAUser, UserDirectory, UserDirectoryError
from .rules import Rules
from .tools import effective_tools, unknown_tool_names

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
INGRESS_ADDRESSES = {"172.30.32.2", "127.0.0.1", "::1"}
MAX_IMAGES = 4
MAX_IMAGE_CHARS = 8_000_000
_IMAGE_RE = re.compile(r"^data:image/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'")


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    images: list[str] = Field(default_factory=list, max_length=MAX_IMAGES)

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


class SettingsIn(BaseModel):
    repo_url: str = Field(max_length=500)
    branch: str = Field(max_length=100)
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
        env.configure(settings.repo_url, settings.branch, token)
        return settings

    async def sync_now() -> None:
        try:
            await asyncio.to_thread(env.sync)
        except GitError as exc:
            log.warning("Sync failed: %s", exc)

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
            gh.on_success = lambda: spawn(sync_now()) if env.configured else None
        if background and env.configured:
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
        return {
            "id": c.eff.id, "alias": c.eff_alias, "is_admin": c.real.is_admin,
            "real_alias": c.real_alias, "acting": c.acting,
            "ready": env.is_cloned(), "can_write": settings_store.get().allow_commits,
        }

    @app.get("/api/conversations")
    async def list_conversations(c: Ctx = Depends(ctx)):
        return deps.store.list(c.eff.id)

    @app.post("/api/conversations")
    async def create_conversation(c: Ctx = Depends(ctx)):
        conv = deps.store.create(c.eff.id)
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
                async for event in run_turn(deps, c.principal, conv, body.text, body.images):
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

    @app.get("/api/family")
    async def family(c: Ctx = Depends(admin)):
        return [{"id": u.id, "name": u.name, "alias": alias_of(u), "is_admin": u.is_admin}
                for u in await state.users.users()]

    # --- admin -----------------------------------------------------------

    def settings_payload() -> dict:
        s = settings_store.get()
        return {"repo_url": s.repo_url, "branch": s.branch, "allow_commits": s.allow_commits,
                "allow_push": s.allow_push, "aliases": s.aliases, "auth_method": s.auth_method,
                "has_token": bool(settings_store.git_token())}

    @app.get("/api/admin/settings")
    async def get_settings(c: Ctx = Depends(admin)):
        return settings_payload()

    @app.put("/api/admin/settings")
    async def put_settings(body: SettingsIn, c: Ctx = Depends(admin)):
        try:
            url, branch = validate_repo_url(body.repo_url), validate_branch(body.branch or "main")
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from None
        old = settings_store.get()
        old_token = settings_store.git_token()
        aliases = {k[:64]: a for k, v in body.aliases.items() if (a := clean_alias(v))}
        settings_store.save(Settings(url, branch, body.allow_commits, body.allow_push, aliases,
                                     auth_method=body.auth_method))
        if body.git_token is not None:
            settings_store.set_git_token(body.git_token)
        new = apply_settings()
        changed = (new.repo_url, new.branch, new.auth_method, settings_store.git_token()) != (
            old.repo_url, old.branch, old.auth_method, old_token)
        if url and changed:
            spawn(sync_now())
        return settings_payload()

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
    async def sync_endpoint(c: Ctx = Depends(admin)):
        try:
            await asyncio.to_thread(env.sync)
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None
        except GitError as exc:
            raise HTTPException(502, str(exc)) from None
        return await asyncio.to_thread(env.status)

    @app.post("/api/admin/push")
    async def push_endpoint(c: Ctx = Depends(admin)):
        try:
            await asyncio.to_thread(env.push)
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None
        except GitError as exc:
            raise HTTPException(502, str(exc)) from None
        return await asyncio.to_thread(env.status)

    @app.get("/api/admin/status")
    async def admin_status(c: Ctx = Depends(admin)):
        options = deps.options
        settings = settings_store.get()
        info: dict = {
            "env": await asyncio.to_thread(env.status),
            "options": {"ollama_url": options.ollama_url, "api_key_set": bool(options.ollama_api_key),
                        "default_model": options.default_model, "vision_model": options.vision_model,
                        "queue_enabled": options.queue_enabled,
                        "max_parallel_generations": options.max_parallel_generations},
            "queue": {"running": deps.queue.running, "waiting": deps.queue.waiting},
            "rules": None, "warnings": [], "model": None,
        }
        model = options.default_model
        if env.is_cloned():
            rules = Rules.load(env.path)
            text, front_model = read_root_agents(env.path)
            model = front_model or model
            info["rules"] = {"hidden": list(rules.hidden_lines), "readonly": list(rules.readonly_lines),
                             "tools": effective_tools(rules, settings.allow_commits)}
            info["warnings"] += list(rules.warnings)
            info["warnings"] += [f"Unknown tool in .agenttools: {n}" for n in unknown_tool_names(rules)]
            if not text:
                info["warnings"].append("The environment has no root AGENTS.md")
        info["model"] = await deps.ollama.check_model(model)
        if info["model"].get("tools") is False:
            info["warnings"].append(f"Model {model} does not report tool support")
        return info

    # --- static ------------------------------------------------------------

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
