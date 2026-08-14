"""Loader registry. Map a file extension to a Loader that yields plain text."""

from __future__ import annotations

from pathlib import Path

from .base import Loader, MissingDependencyError
from .html import HtmlLoader
from .pdf import PdfLoader
from .slack import SlackLoader
from .text import TextLoader
from .vtt import VttLoader

_LOADERS: tuple[Loader, ...] = (
    TextLoader(),
    PdfLoader(),
    HtmlLoader(),
    VttLoader(),
    SlackLoader(),
)

# extension -> loader
_BY_SUFFIX: dict[str, Loader] = {
    suffix: loader for loader in _LOADERS for suffix in loader.suffixes
}


def supported_suffixes() -> set[str]:
    return set(_BY_SUFFIX)


def can_load(path: Path) -> bool:
    return path.suffix.lower() in _BY_SUFFIX


def get_loader(path: Path) -> Loader:
    try:
        return _BY_SUFFIX[path.suffix.lower()]
    except KeyError:
        raise ValueError(
            f"no loader for {path.suffix!r}; supported: "
            f"{', '.join(sorted(_BY_SUFFIX))}"
        ) from None


def load_source(path: Path) -> str:
    """Load ``path`` and return clean plain-text source for the pipeline."""
    return get_loader(path).load(path)


__all__ = [
    "Loader",
    "MissingDependencyError",
    "can_load",
    "get_loader",
    "load_source",
    "supported_suffixes",
]
