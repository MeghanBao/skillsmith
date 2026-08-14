"""WebVTT / SRT caption loader — returns the spoken transcript as plain prose.

Handles the two things that make raw captions unusable as source: cue timing
metadata, and the rolling-duplicate lines auto-generated captions emit (each cue
repeats the tail of the previous one). Pure stdlib, no dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import Loader

_TIMING = re.compile(r"-->")
_INLINE_TAG = re.compile(r"<[^>]+>")          # <c>, <v Author>, <00:00:01.000>


class VttLoader(Loader):
    suffixes = (".vtt", ".srt")

    def load(self, path: Path) -> str:
        raw = path.read_text(encoding="utf-8-sig")
        out: list[str] = []
        in_note = False

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                in_note = False
                continue
            if stripped.startswith(("WEBVTT", "NOTE", "STYLE")):
                in_note = True
                continue
            if in_note or _TIMING.search(stripped):
                continue
            # Drop bare sequence numbers (SRT indices / numeric VTT cue ids).
            if stripped.isdigit():
                continue

            text = _INLINE_TAG.sub("", stripped).strip()
            if not text:
                continue
            # Drop consecutive duplicates from rolling auto-captions.
            if out and out[-1] == text:
                continue
            out.append(text)

        return "\n".join(out)
