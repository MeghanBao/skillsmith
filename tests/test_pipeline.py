from conftest import eval_json, skill_json

from skillsmith.pipeline import forge_skill


def test_forge_passes_on_first_try(make_completer):
    completer = make_completer([skill_json(), eval_json()])
    result = forge_skill("some SOP", completer=completer)

    assert result.passed is True
    assert result.skill is not None
    assert result.skill.name == "reset-user-password"
    assert len(result.attempts) == 1


def test_forge_iterates_on_revise_then_passes(make_completer):
    completer = make_completer([
        skill_json(confidence="low"),
        eval_json(verdict="revise", confidence="low", fix_instructions="add guardrails"),
        skill_json(),
        eval_json(),
    ])
    result = forge_skill("some SOP", completer=completer, max_iterations=3)

    assert result.passed is True
    assert len(result.attempts) == 2
    # The critic's fix instructions must reach the second generation call.
    second_generate_user_prompt = completer.calls[2][1]
    assert "add guardrails" in second_generate_user_prompt


def test_forge_stops_on_reject(make_completer):
    completer = make_completer([skill_json(), eval_json(verdict="reject", confidence="low")])
    result = forge_skill("thin source", completer=completer)

    assert result.rejected is True
    assert result.passed is False


def test_forge_exhausts_budget_without_pass(make_completer):
    completer = make_completer([
        skill_json(confidence="medium"),
        eval_json(verdict="revise", confidence="medium", fix_instructions="more detail"),
        skill_json(confidence="medium"),
        eval_json(verdict="revise", confidence="medium", fix_instructions="more detail"),
    ])
    result = forge_skill("borderline", completer=completer, max_iterations=2)

    assert result.passed is False
    assert result.rejected is False
    assert len(result.attempts) == 2
