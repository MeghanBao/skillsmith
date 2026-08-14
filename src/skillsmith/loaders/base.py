"""Loader contract: a source file/artifact -> clean plain text.

Loaders normalize heterogeneous inputs (PDF, HTML, Slack export, VTT captions)
into the plain-text ``source`` string the generation engine expects. Like
renderers, each loader is isolated and registered by file extension; adding an
input format never touches generation or eval.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class MissingDependencyError(RuntimeError):
    """Raised when a loader's optional third-party dependency isn't installed."""


class Loader(ABC):
    #: file extensions this loader handles, lowercase, incl. leading dot
    suffixes: tuple[str, ...] = ()

    @abstractmethod
    def load(self, path: Path) -> str:
        """Return clean plain text distilled from ``path``."""
