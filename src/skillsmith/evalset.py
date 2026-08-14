"""Golden eval regression harness for the critic.

The critic (``evaluate.py``) is itself an LLM, so its judgement can silently
drift when we tweak ``prompts/eval_skill.md`` or change models. This module runs
the critic against a set of human-labelled *golden cases* — each a
``(source, candidate skill, expected verdict)`` with the dimensions that should
score low — and reports how well the critic still agrees with the humans.

It answers: "did my last prompt/model change make the judge better or worse?"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from .evaluate import Verdict, evaluate_skill
from .ir import SkillIR
from .llm import Completer

# A dimension is "flagged weak" when it scores below this (matches the critic's
# own rule: pass requires every dimension >= 4).
WEAK_THRESHOLD = 4
DIMENSIONS = ("faithful", "atomic", "actionable", "triggerable", "guarded")


class GoldenCase(BaseModel):
    """One human-labelled exam question for the critic."""

    id: str
    description: str
    source: str
    candidate: SkillIR
    expected_verdict: Verdict
    # For revise/reject cases: dimensions that SHOULD score low. Empty for pass.
    expected_weak_dimensions: list[str] = []
    rationale: str = ""


@dataclass
class CaseResult:
    case_id: str
    expected_verdict: Verdict
    actual_verdict: Verdict
    verdict_match: bool
    expected_weak: list[str]
    actual_weak: list[str]
    weak_caught: list[str]   # expected_weak ∩ actual_weak
    weak_dims_ok: bool       # every expected weak dim was flagged
    error: str | None = None


@dataclass
class CriticReport:
    cases: list[CaseResult] = field(default_factory=list)
    threshold: float = 0.85

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def scored(self) -> list[CaseResult]:
        return [c for c in self.cases if c.error is None]

    @property
    def verdict_agreement(self) -> float:
        scored = self.scored
        if not scored:
            return 0.0
        return sum(c.verdict_match for c in scored) / len(scored)

    @property
    def weak_dim_recall(self) -> float:
        """Fraction of expected weak-dimension flags the critic actually caught."""
        expected = sum(len(c.expected_weak) for c in self.scored)
        if not expected:
            return 1.0
        caught = sum(len(c.weak_caught) for c in self.scored)
        return caught / expected

    @property
    def confusion(self) -> dict[str, dict[str, int]]:
        """confusion[expected][actual] = count."""
        verdicts = [v.value for v in Verdict]
        matrix = {e: {a: 0 for a in verdicts} for e in verdicts}
        for c in self.scored:
            matrix[c.expected_verdict.value][c.actual_verdict.value] += 1
        return matrix

    @property
    def passed(self) -> bool:
        return bool(self.scored) and self.verdict_agreement >= self.threshold


def load_golden(path: Path) -> list[GoldenCase]:
    """Load golden cases from a file or a directory of ``*.json``.

    Each JSON file may hold a single case object or a list of cases, so a whole
    suite can live in one file or be split one-case-per-file for contribution.
    """
    files = [path] if path.is_file() else sorted(path.glob("*.json"))
    cases: list[GoldenCase] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else [data]
        cases.extend(GoldenCase.model_validate(r) for r in records)
    return cases


def _run_case(case: GoldenCase, completer: Completer | None) -> CaseResult:
    try:
        evaluation = evaluate_skill(case.source, case.candidate, completer=completer)
    except Exception as exc:  # noqa: BLE001 - one bad case shouldn't sink the run
        return CaseResult(
            case_id=case.id,
            expected_verdict=case.expected_verdict,
            actual_verdict=case.expected_verdict,
            verdict_match=False,
            expected_weak=case.expected_weak_dimensions,
            actual_weak=[],
            weak_caught=[],
            weak_dims_ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    actual_weak = [
        d for d in DIMENSIONS if evaluation.scores.get(d, 5) < WEAK_THRESHOLD
    ]
    caught = [d for d in case.expected_weak_dimensions if d in actual_weak]
    return CaseResult(
        case_id=case.id,
        expected_verdict=case.expected_verdict,
        actual_verdict=evaluation.verdict,
        verdict_match=evaluation.verdict == case.expected_verdict,
        expected_weak=case.expected_weak_dimensions,
        actual_weak=actual_weak,
        weak_caught=caught,
        weak_dims_ok=set(case.expected_weak_dimensions) <= set(actual_weak),
    )


def run_critic_eval(
    cases: list[GoldenCase],
    completer: Completer | None = None,
    threshold: float = 0.85,
) -> CriticReport:
    """Run the critic over every golden case and aggregate the results."""
    report = CriticReport(threshold=threshold)
    for case in cases:
        report.cases.append(_run_case(case, completer))
    return report


def format_report(report: CriticReport) -> str:
    """Plain-text summary suitable for CI logs."""
    verdicts = [v.value for v in Verdict]
    status = "✅ PASS" if report.passed else "❌ REGRESSION"
    lines = [
        f"Critic golden eval — {report.total} case(s)",
        (
            f"  verdict agreement : {report.verdict_agreement:.0%} "
            f"(threshold {report.threshold:.0%})  {status}"
        ),
        f"  weak-dim recall   : {report.weak_dim_recall:.0%}",
        "",
        "  confusion (rows=expected, cols=actual):",
        "            " + "".join(f"{a:>9}" for a in verdicts),
    ]
    conf = report.confusion
    for e in verdicts:
        lines.append(f"    {e:>7} " + "".join(f"{conf[e][a]:>9}" for a in verdicts))

    mismatches = [c for c in report.scored if not c.verdict_match]
    errors = [c for c in report.cases if c.error]
    if mismatches:
        lines += ["", "  Verdict mismatches:"]
        for c in mismatches:
            lines.append(
                f"    ✗ {c.case_id}: expected {c.expected_verdict.value}, "
                f"got {c.actual_verdict.value}"
            )
    missed = [c for c in report.scored if not c.weak_dims_ok]
    if missed:
        lines += ["", "  Missed weak dimensions:"]
        for c in missed:
            gap = sorted(set(c.expected_weak) - set(c.actual_weak))
            lines.append(f"    ✗ {c.case_id}: expected weak {gap}, not flagged")
    if errors:
        lines += ["", "  Errors:"]
        for c in errors:
            lines.append(f"    💥 {c.case_id}: {c.error}")
    return "\n".join(lines)
