"""The core loop: generate -> test -> eval -> iterate.

This is the methodology Skillsmith is built around (mirroring the official
skill-creator approach). Everything else — batch scheduling, format rendering —
wraps this single function.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evaluate import Evaluation, Verdict, evaluate_skill
from .generate import generate_skill
from .ir import Confidence, SkillIR
from .llm import Completer


@dataclass
class Attempt:
    skill: SkillIR
    evaluation: Evaluation


@dataclass
class ForgeResult:
    """Outcome of forging one skill from one source."""

    skill: SkillIR | None
    passed: bool
    attempts: list[Attempt] = field(default_factory=list)
    rejected: bool = False

    @property
    def final_confidence(self) -> Confidence:
        if self.skill is None:
            return Confidence.LOW
        return self.skill.confidence


def forge_skill(
    source: str,
    max_iterations: int = 3,
    completer: Completer | None = None,
) -> ForgeResult:
    """Run the generate->eval->iterate loop until pass or budget exhausted.

    Returns the best skill produced. On ``revise`` the critic's fix_instructions
    are fed back into the next generation pass.
    """
    result = ForgeResult(skill=None, passed=False)
    fix_instructions: str | None = None

    for _ in range(max_iterations):
        skill = generate_skill(
            source, completer=completer, fix_instructions=fix_instructions
        )
        evaluation = evaluate_skill(source, skill, completer=completer)
        # Reflect the critic's judgement onto the artifact we ship.
        skill.confidence = evaluation.confidence
        result.attempts.append(Attempt(skill=skill, evaluation=evaluation))
        result.skill = skill  # keep latest as best-so-far

        if evaluation.verdict == Verdict.PASS:
            result.passed = True
            return result
        if evaluation.verdict == Verdict.REJECT:
            result.rejected = True
            return result

        fix_instructions = evaluation.fix_instructions

    return result
