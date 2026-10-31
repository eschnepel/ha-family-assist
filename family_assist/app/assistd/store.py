from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .config import write_json_atomic

_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CID_RE = re.compile(r"^[0-9a-f]{32}$")


class ConversationStore:
    """Conversations as JSON files, one folder per family member."""

    def __init__(self, root: Path):
        self.root = root

    def _dir(self, uid: str) -> Path:
        if not _UID_RE.match(uid):
            raise ValueError("invalid user id")
        return self.root / uid

    def create(self, uid: str) -> dict:
        now = time.time()
        conv = {"id": uuid.uuid4().hex, "user_id": uid, "title": "", "created": now, "updated": now,
                "messages": [], "loaded_agents": []}
        self.save(conv)
        return conv

    def load(self, uid: str, cid: str) -> dict | None:
        if not _CID_RE.match(cid):
            return None
        try:
            return json.loads((self._dir(uid) / f"{cid}.json").read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, conv: dict) -> None:
        write_json_atomic(self._dir(conv["user_id"]) / f"{conv['id']}.json", conv)

    def list(self, uid: str) -> list[dict]:
        folder = self._dir(uid)
        items = []
        if folder.is_dir():
            for path in folder.glob("*.json"):
                try:
                    conv = json.loads(path.read_text("utf-8"))
                    items.append({"id": conv["id"], "title": conv.get("title", ""), "updated": conv.get("updated", 0)})
                except (OSError, ValueError, KeyError):
                    continue
        return sorted(items, key=lambda c: c["updated"], reverse=True)
