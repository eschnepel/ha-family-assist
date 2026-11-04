from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .config import DEFAULT_ENV_ID, write_json_atomic

_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CID_RE = re.compile(r"^[0-9a-f]{32}$")
RETENTION_SECONDS = 7 * 24 * 3600


class ConversationStore:
    """Conversations as JSON files, one folder per family member."""

    def __init__(self, root: Path):
        self.root = root

    def _dir(self, uid: str) -> Path:
        if not _UID_RE.match(uid):
            raise ValueError("invalid user id")
        return self.root / uid

    def create(self, uid: str, env_id: str = DEFAULT_ENV_ID) -> dict[str, Any]:
        now = time.time()
        conv: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "user_id": uid,
            "env_id": env_id,
            "title": "",
            "created": now,
            "updated": now,
            "messages": [],
            "loaded_agents": [],
        }
        self.save(conv)
        return conv

    def load(self, uid: str, cid: str, include_deleted: bool = False) -> dict[str, Any] | None:
        if not _CID_RE.match(cid):
            return None
        try:
            conv: dict[str, Any] = json.loads((self._dir(uid) / f"{cid}.json").read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if conv.get("deleted_at") and not include_deleted:
            return None
        return conv

    def soft_delete(self, conv: dict[str, Any]) -> None:
        conv["deleted_at"] = time.time()
        self.save(conv)

    def restore(self, uid: str, cid: str) -> bool:
        conv = self.load(uid, cid, include_deleted=True)
        if conv is None or not conv.get("deleted_at"):
            return False
        if time.time() - conv["deleted_at"] > RETENTION_SECONDS:
            return False
        conv.pop("deleted_at")
        self.save(conv)
        return True

    def list_deleted(self) -> list[dict[str, Any]]:
        """Soft-deleted conversations still inside the retention period; expired ones are purged."""
        now = time.time()
        items: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return items
        for path in self.root.glob("*/*.json"):
            try:
                conv = json.loads(path.read_text("utf-8"))
                deleted_at = conv.get("deleted_at")
                if not deleted_at:
                    continue
                if now - deleted_at > RETENTION_SECONDS:
                    path.unlink(missing_ok=True)
                    continue
                items.append(
                    {
                        "id": conv["id"],
                        "user_id": conv["user_id"],
                        "title": conv.get("title", ""),
                        "env_id": conv.get("env_id", DEFAULT_ENV_ID),
                        "deleted_at": deleted_at,
                        "messages": len(conv.get("messages", [])),
                    }
                )
            except (OSError, ValueError, KeyError):
                continue
        return sorted(items, key=lambda c: c["deleted_at"], reverse=True)

    def save(self, conv: dict[str, Any]) -> None:
        write_json_atomic(self._dir(conv["user_id"]) / f"{conv['id']}.json", conv)

    def list(self, uid: str, env_id: str | None = None) -> list[dict[str, Any]]:
        folder = self._dir(uid)
        items: list[dict[str, Any]] = []
        if folder.is_dir():
            for path in folder.glob("*.json"):
                try:
                    conv = json.loads(path.read_text("utf-8"))
                    if conv.get("deleted_at"):
                        continue
                    if env_id is not None and conv.get("env_id", DEFAULT_ENV_ID) != env_id:
                        continue
                    items.append(
                        {
                            "id": conv["id"],
                            "title": conv.get("title", ""),
                            "updated": conv.get("updated", 0),
                        }
                    )
                except (OSError, ValueError, KeyError):
                    continue
        return sorted(items, key=lambda c: c["updated"], reverse=True)
