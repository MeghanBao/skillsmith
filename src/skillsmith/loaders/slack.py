"""Slack export loader — turns exported channel JSON into a readable transcript.

A Slack workspace export is a directory of channel folders, each holding dated
``YYYY-MM-DD.json`` files (a list of message objects), plus a top-level
``users.json`` mapping user ids to names. This loader handles one such message
file, resolving ``<@U…>`` mentions and human names where possible.

``.json`` is generic, so if a file isn't Slack-shaped we fall back to returning
the pretty-printed JSON as-is rather than guessing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .base import Loader

# Subtypes that are noise for skill distillation (joins, topic changes, ...).
_SKIP_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic", "channel_purpose",
    "channel_name", "bot_add", "bot_remove",
}
_MENTION = re.compile(r"<@([UW][A-Z0-9]+)>")
_LINK = re.compile(r"<(https?://[^>|]+)(?:\|([^>]+))?>")


class SlackLoader(Loader):
    suffixes = (".json",)

    def load(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages") if isinstance(data, dict) else data
        if not isinstance(messages, list) or not self._looks_like_slack(messages):
            # Not a Slack export — hand back the raw JSON so nothing is lost.
            return json.dumps(data, indent=2, ensure_ascii=False)

        users = self._load_user_map(path)
        lines: list[str] = []
        for msg in messages:
            if not isinstance(msg, dict) or msg.get("subtype") in _SKIP_SUBTYPES:
                continue
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            name = self._resolve_name(msg, users)
            stamp = self._fmt_ts(msg.get("ts"))
            clean = self._clean_text(text, users)
            prefix = f"[{stamp}] " if stamp else ""
            lines.append(f"{prefix}{name}: {clean}")

        return "\n".join(lines)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _looks_like_slack(messages: list) -> bool:
        head = next((m for m in messages if isinstance(m, dict)), None)
        return bool(head) and ("ts" in head or "user" in head or head.get("type") == "message")

    @staticmethod
    def _load_user_map(path: Path) -> dict[str, str]:
        for candidate in (path.parent / "users.json", path.parent.parent / "users.json"):
            if candidate.exists():
                try:
                    users = json.loads(candidate.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                mapping: dict[str, str] = {}
                for u in users if isinstance(users, list) else []:
                    profile = u.get("profile", {}) if isinstance(u, dict) else {}
                    name = (
                        profile.get("real_name")
                        or profile.get("display_name")
                        or u.get("real_name")
                        or u.get("name")
                    )
                    if u.get("id") and name:
                        mapping[u["id"]] = name
                return mapping
        return {}

    @staticmethod
    def _resolve_name(msg: dict, users: dict[str, str]) -> str:
        profile = msg.get("user_profile") or {}
        return (
            profile.get("real_name")
            or profile.get("display_name")
            or users.get(msg.get("user", ""))
            or msg.get("user")
            or msg.get("username")
            or "unknown"
        )

    @staticmethod
    def _fmt_ts(ts: str | None) -> str:
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _clean_text(text: str, users: dict[str, str]) -> str:
        text = _MENTION.sub(lambda m: "@" + users.get(m.group(1), m.group(1)), text)
        text = _LINK.sub(lambda m: m.group(2) or m.group(1), text)
        return text.replace("\n", " ").strip()
