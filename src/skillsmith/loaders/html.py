"""HTML loader — strips boilerplate and returns readable text via BeautifulSoup."""

from __future__ import annotations

import re
from pathlib import Path

from .base import Loader, MissingDependencyError

# Tags whose contents are never useful as skill source material.
_DROP_TAGS = ("script", "style", "head", "nav", "footer", "aside", "noscript", "svg")


class HtmlLoader(Loader):
    suffixes = (".html", ".htm")

    def load(self, path: Path) -> str:
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:  # pragma: no cover - env-specific
            raise MissingDependencyError(
                "HTML support needs 'beautifulsoup4' — install skillsmith with "
                "its default dependencies (pip install -e .)."
            ) from e

        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for tag in soup(_DROP_TAGS):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        body = soup.get_text(separator="\n")

        # Collapse the ragged whitespace bs4 leaves behind.
        lines = [ln.strip() for ln in body.splitlines()]
        text = "\n".join(ln for ln in lines if ln)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return f"# {title}\n\n{text}" if title else text
