import json

from skillsmith.ir import Confidence, SkillIR, WorkflowStep
from skillsmith.renderers import available_formats, get_renderer


def _skill() -> SkillIR:
    return SkillIR(
        name="reset-password",
        title="Reset Password",
        description="Reset a locked-out user's password following policy",
        triggers=["user locked out"],
        inputs=["user email"],
        workflow=[WorkflowStep(title="Reset", detail="run tool", script="idm reset $EMAIL")],
        guardrails=["Never reset without a ticket"],
        examples=["reset alice@corp.de"],
        source_refs=["SOP §3"],
        confidence=Confidence.HIGH,
    )


def test_all_formats_registered():
    assert "claude-code" in available_formats()
    assert "adal" in available_formats()


def test_claude_code_renders_valid_skill_md():
    files = get_renderer("claude-code").render(_skill())
    md = files["SKILL.md"]
    assert md.startswith("---\n")
    assert "name: reset-password" in md
    assert "# Reset Password" in md
    assert "idm reset $EMAIL" in md
    assert "## Guardrails" in md


def test_adal_renders_valid_json():
    files = get_renderer("adal").render(_skill())
    descriptor = json.loads(files["skill.json"])
    assert descriptor["name"] == "reset-password"
    assert descriptor["activation"]["intents"] == ["user locked out"]
    assert descriptor["metadata"]["generatedBy"] == "skillsmith"


def test_unknown_format_raises():
    try:
        get_renderer("nope")
    except ValueError as e:
        assert "unknown format" in str(e)
    else:
        raise AssertionError("expected ValueError")
