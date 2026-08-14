"""Renderer registry. Map a ``--format`` id to a Renderer instance."""

from __future__ import annotations

from .adal import AdalRenderer
from .base import Renderer
from .claude_code import ClaudeCodeRenderer

_RENDERERS: dict[str, Renderer] = {
    r.format_id: r for r in (ClaudeCodeRenderer(), AdalRenderer())
}


def available_formats() -> list[str]:
    return sorted(_RENDERERS)


def get_renderer(format_id: str) -> Renderer:
    try:
        return _RENDERERS[format_id]
    except KeyError:
        raise ValueError(
            f"unknown format {format_id!r}; available: {', '.join(available_formats())}"
        ) from None


__all__ = ["Renderer", "available_formats", "get_renderer"]
