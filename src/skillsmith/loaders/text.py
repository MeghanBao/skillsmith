"""Plain-text / Markdown / reStructuredText loader (passthrough)."""

from __future__ import annotations

from pathlib import Path

from .base import Loader


class TextLoader(Loader):
    suffixes = (".md", ".txt", ".rst", ".markdown")

    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")
