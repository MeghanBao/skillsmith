"""Eval engine: judge a candidate SkillIR against its source."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .ir import Confidence, SkillIR
from .llm import AnthropicCompleter, Completer, extract_json, load_prompt


class Verdict(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    REJECT = "reject"


class Evaluation(BaseModel):
    verdict: Verdict
    confidence: Confidence
    scores: dict[str, int]
    issues: list[str] = []
    fix_instructions: str = ""


def evaluate_skill(
    source: str, skill: SkillIR, completer: Completer | None = None
) -> Evaluation:
    """Score a candidate skill; returns a structured verdict + fix guidance."""
    completer = completer or AnthropicCompleter()
    system = load_prompt("eval_skill")
    user = (
        f"<source>\n{source}\n</source>\n\n"
        f"<candidate_skill>\n{skill.model_dump_json(indent=2)}\n</candidate_skill>"
    )
    raw = completer.complete(system, user)
    return Evaluation.model_validate(extract_json(raw))
