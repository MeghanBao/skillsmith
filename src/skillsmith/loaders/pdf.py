"""PDF loader — extracts text page by page via pypdf."""

from __future__ import annotations

from pathlib import Path

from .base import Loader, MissingDependencyError


class PdfLoader(Loader):
    suffixes = (".pdf",)

    def load(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover - env-specific
            raise MissingDependencyError(
                "PDF support needs 'pypdf' — install skillsmith with its default "
                "dependencies (pip install -e .)."
            ) from e

        reader = PdfReader(str(path))
        pages: list[str] = []
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[page {i}]\n{text}")
        return "\n\n".join(pages)
