from __future__ import annotations

import logging
import os

import uvicorn
from fastapi import FastAPI

from .agent import Deps
from .config import DATA_DIR, SettingsStore, load_options
from .genqueue import GenerationQueue
from .ghcli import GitHubCli
from .gitenv import AgentEnvironment
from .identity import HAUser, StaticUsers, SupervisorUsers, UserDirectory
from .ollama import OllamaClient
from .store import ConversationStore
from .web import create_app


def build_app() -> FastAPI:
    options = load_options()
    dev = os.environ.get("FA_DEV") == "1"
    deps = Deps(
        options=options,
        settings=SettingsStore(DATA_DIR),
        env=AgentEnvironment(DATA_DIR / "env" / "repo"),
        ollama=OllamaClient(options.ollama_url, options.ollama_api_key),
        store=ConversationStore(DATA_DIR / "conversations"),
        queue=GenerationQueue(options.queue_enabled, options.max_parallel_generations),
        gh=GitHubCli(DATA_DIR / "gh"),
    )
    users: UserDirectory
    if dev:
        users = StaticUsers(
            [HAUser("dev-admin", "Dev Admin", True), HAUser("dev-kid", "Dev Kid", False)]
        )
    else:
        users = SupervisorUsers(os.environ.get("SUPERVISOR_TOKEN", ""))
    return create_app(deps, users, dev=dev, dev_user="dev-admin" if dev else "")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    uvicorn.run(
        build_app(),
        host="0.0.0.0",
        port=int(os.environ.get("FA_PORT", "8099")),
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
