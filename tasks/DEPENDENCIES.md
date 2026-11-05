# Project Dependencies

> Maintained by the Lead Agent. Workers append entries; never edit existing ones
> without Lead approval. One entry per library, no duplicates.
> Versions are the lower bounds pinned in `family_assist/requirements.txt` / `requirements-dev.txt`; the App image installs them into `/opt/venv`.

## fastapi >=0.115

- **Install:** `pip install "fastapi>=0.115"` (already in `family_assist/requirements.txt`)
- **Import:** `from fastapi import Depends, FastAPI, HTTPException, Request`; `from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse`; `from fastapi.staticfiles import StaticFiles`
- **Added by task:** pre-existing
- **Purpose:** web framework for the ingress API and SSE streaming

## pydantic (bundled with FastAPI)

- **Install:** already installed as a FastAPI dependency; do not install separately
- **Import:** `from pydantic import BaseModel, Field, field_validator`
- **Added by task:** pre-existing
- **Purpose:** request body models and validation

## uvicorn >=0.30

- **Install:** `pip install "uvicorn>=0.30"` (already in `requirements.txt`)
- **Import:** `import uvicorn`
- **Added by task:** pre-existing
- **Purpose:** ASGI server started from `__main__.py`

## httpx >=0.27

- **Install:** `pip install "httpx>=0.27"` (already in `requirements.txt`)
- **Import:** `import httpx`
- **Added by task:** pre-existing
- **Purpose:** async HTTP for the Ollama client and `load_skill`; the canonical HTTP client, do not add `requests`

## aiohttp >=3.9

- **Install:** `pip install "aiohttp>=3.9"` (already in `requirements.txt`)
- **Import:** `import aiohttp`
- **Added by task:** pre-existing
- **Purpose:** Home Assistant user lookup in `identity.py`; do not use it elsewhere, prefer `httpx`

## pathspec >=0.12

- **Install:** `pip install "pathspec>=0.12"` (already in `requirements.txt`)
- **Import:** `import pathspec` (`pathspec.GitIgnoreSpec`)
- **Added by task:** pre-existing
- **Purpose:** `.gitignore`-syntax matching for Hidden and Read-only Paths

## regex >=2024.5

- **Install:** `pip install "regex>=2024.5"` (already in `requirements.txt`)
- **Import:** `import regex`
- **Added by task:** pre-existing
- **Purpose:** the `grep` Tool's pattern matching

## PyYAML >=6.0

- **Install:** `pip install "PyYAML>=6.0"` (already in `requirements.txt`)
- **Import:** `import yaml` (`yaml.safe_load` only)
- **Added by task:** pre-existing
- **Purpose:** `.family_assist.yaml`, AGENTS.md front matter and translation files

## git and github-cli (system packages)

- **Install:** already installed in the image: `apk add --no-cache python3 py3-pip git github-cli`; do not install separately
- **Import:** not applicable; invoked as the `git` and `gh` command line tools
- **Added by task:** pre-existing
- **Purpose:** Checkout management; GitHub sign-in (device flow)

## KaTeX and Mermaid (vendored front-end libraries)

- **Install:** already vendored under `family_assist/app/assistd/static/vendor/`; no network, no build step
- **Import:** loaded on demand by `static/app.js`
- **Added by task:** pre-existing
- **Purpose:** math typesetting and diagram rendering in Chats

## Development tools (`requirements-dev.txt`)

- **Install:** `pip install -r requirements-dev.txt` (pytest>=8, pytest-cov, mypy, pre-commit, ruff==0.16.4, types-PyYAML)
- **Import:** `import pytest` in tests
- **Added by task:** pre-existing
- **Purpose:** the CI check is `pre-commit run --all-files` followed by `pytest`
