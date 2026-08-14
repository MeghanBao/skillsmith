"""Skill Intermediate Representation (IR).

The IR is the heart of Skillsmith. Every source document is distilled into a
single, format-agnostic ``SkillIR`` object. Renderers then project that IR onto
concrete target formats (Claude Code ``SKILL.md``, AdaL ``@skills``, OpenCode,
...). Adding a new export target means adding a renderer, not touching the
generation or eval engine.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Confidence(str, Enum):
    """How much the pipeline trusts a generated skill without human review."""

    HIGH = "high"      # ship it
    MEDIUM = "medium"  # spot-check recommended
    LOW = "low"        # needs human review before use


class WorkflowStep(BaseModel):
    """A single ordered step in the skill's workflow."""

    title: str
    detail: str
    # Optional shell/code the agent may run for this step.
    script: str | None = None


class SkillIR(BaseModel):
    """Format-agnostic representation of one skill.

    This is deliberately a superset of what any single target format needs;
    renderers pick the fields they care about.
    """

    name: str = Field(description="kebab-case unique identifier")
    title: str = Field(description="human-readable name")
    description: str = Field(
        description="one-line summary used by agents to decide relevance"
    )
    triggers: list[str] = Field(
        default_factory=list,
        description="phrases/intents that should activate this skill",
    )
    inputs: list[str] = Field(
        default_factory=list, description="what the skill needs to run"
    )
    workflow: list[WorkflowStep] = Field(default_factory=list)
    guardrails: list[str] = Field(
        default_factory=list, description="hard rules / things to never do"
    )
    examples: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(
        default_factory=list,
        description="provenance: which source docs this was distilled from",
    )
    confidence: Confidence = Confidence.MEDIUM

    @field_validator("name")
    @classmethod
    def _kebab(cls, v: str) -> str:
        norm = v.strip().lower().replace(" ", "-").replace("_", "-")
        if not norm or not all(c.isalnum() or c == "-" for c in norm):
            raise ValueError(f"name must be kebab-case alphanumerics: got {v!r}")
        return norm

    def is_shippable(self) -> bool:
        """A skill is shippable if it clears the minimum quality bar."""
        return (
            self.confidence == Confidence.HIGH
            and bool(self.workflow)
            and bool(self.triggers)
            and len(self.description) >= 15
        )
