from pathlib import Path

from skillsmith.demo import DemoCompleter
from skillsmith.ir import SkillIR
from skillsmith.loaders import load_source
from skillsmith.pipeline import forge_skill

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_demo_generates_valid_skill_from_real_sop():
    source = load_source(EXAMPLES / "reset-password-sop.md")
    result = forge_skill(source, completer=DemoCompleter())

    assert result.passed is True
    skill = result.skill
    assert skill is not None
    SkillIR.model_validate(skill.model_dump())          # structurally valid
    assert len(skill.workflow) >= 3                       # steps pulled from the SOP
    assert skill.guardrails                                # "never reset without..." caught
    # A real command from the source made it into a step script.
    assert any("idm reset" in (s.script or "") for s in skill.workflow)


def test_demo_output_reflects_the_input_not_canned():
    a = forge_skill(load_source(EXAMPLES / "reset-password-sop.md"), completer=DemoCompleter())
    b = forge_skill(load_source(EXAMPLES / "onboarding-call.vtt"), completer=DemoCompleter())
    assert a.skill.name != b.skill.name   # different sources -> different skills


def test_demo_rejects_thin_source():
    result = forge_skill("hi there", completer=DemoCompleter())
    assert result.rejected is True
    assert result.passed is False


def test_demo_completer_routes_by_prompt():
    d = DemoCompleter()
    gen = d.complete("You are Skillsmith's distillation engine.", "<source>\n1. do a thing\n2. do another\n</source>")
    ev = d.complete("You are Skillsmith's critic.", "<source>\nx\n</source>\n<candidate_skill>\n{}\n</candidate_skill>")
    assert '"workflow"' in gen
    assert '"verdict"' in ev
