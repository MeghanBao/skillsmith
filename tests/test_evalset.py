from pathlib import Path

from conftest import eval_json

from skillsmith.evalset import GoldenCase, load_golden, run_critic_eval
from skillsmith.evaluate import Verdict
from skillsmith.ir import SkillIR

GOLDEN_DIR = Path(__file__).parents[1] / "evals" / "golden"


def _case(cid: str, verdict: str, weak=None) -> GoldenCase:
    return GoldenCase(
        id=cid,
        description="d",
        source="some source text describing a procedure",
        candidate=SkillIR(
            name="x-skill",
            title="X",
            description="does something useful here",
            triggers=["some trigger"],
            workflow=[{"title": "step", "detail": "do it"}],
        ),
        expected_verdict=verdict,
        expected_weak_dimensions=weak or [],
    )


def test_seed_golden_set_parses_and_is_balanced():
    cases = load_golden(GOLDEN_DIR)
    assert len(cases) == 12
    dist = {v: sum(c.expected_verdict == v for c in cases) for v in Verdict}
    assert dist[Verdict.PASS] == 4
    assert dist[Verdict.REVISE] == 6
    assert dist[Verdict.REJECT] == 2
    # Every revise case isolates at least one weak dimension.
    for c in cases:
        if c.expected_verdict == Verdict.REVISE:
            assert c.expected_weak_dimensions, f"{c.id} has no weak dim"


def test_perfect_agreement_passes(make_completer):
    cases = [_case("a", "pass"), _case("b", "revise", ["faithful"])]
    completer = make_completer([
        eval_json(verdict="pass"),
        eval_json(
            verdict="revise",
            scores={"faithful": 2, "atomic": 5, "actionable": 5, "triggerable": 5, "guarded": 5},
            fix_instructions="fix faithfulness",
        ),
    ])
    report = run_critic_eval(cases, completer=completer, threshold=0.85)

    assert report.verdict_agreement == 1.0
    assert report.weak_dim_recall == 1.0
    assert report.passed is True
    assert report.confusion["pass"]["pass"] == 1
    assert report.confusion["revise"]["revise"] == 1


def test_mismatch_and_missed_weak_dim_flags_regression(make_completer):
    cases = [_case("a", "pass"), _case("b", "revise", ["atomic"])]
    completer = make_completer([
        eval_json(verdict="revise"),   # expected pass -> verdict mismatch
        eval_json(verdict="revise"),   # right verdict but atomic not flagged (all 5s)
    ])
    report = run_critic_eval(cases, completer=completer, threshold=0.85)

    assert report.verdict_agreement == 0.5
    assert report.weak_dim_recall == 0.0   # expected atomic weak, critic scored it fine
    assert report.passed is False
    assert report.confusion["pass"]["revise"] == 1

    missed = [c for c in report.scored if not c.weak_dims_ok]
    assert [c.case_id for c in missed] == ["b"]


def test_case_error_is_isolated(make_completer):
    completer = make_completer([])  # no scripted response -> completer raises
    report = run_critic_eval([_case("boom", "pass")], completer=completer)

    assert report.total == 1
    assert report.scored == []          # errored case excluded from scoring
    assert report.cases[0].error is not None
    assert report.passed is False
