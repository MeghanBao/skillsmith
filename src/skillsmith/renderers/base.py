"""Renderer contract: SkillIR -> files for a concrete target format."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..ir import SkillIR


class Renderer(ABC):
    """Projects a format-agnostic SkillIR onto one target format.

    A renderer returns a mapping of ``relative_path -> file_contents``. The CLI
    writes those under ``<out_dir>/<format>/<skill_name>/``. Adding a new export
    target is: subclass, implement ``render``, register in ``__init__.py``.
    """

    #: short id used on the CLI (e.g. ``--format claude-code``)
    format_id: str = ""

    @abstractmethod
    def render(self, skill: SkillIR) -> dict[str, str]:
        ...
