import pytest

from skillsmith.ir import Confidence, SkillIR, WorkflowStep


def _skill(**kw) -> SkillIR:
    defaults = dict(
        name="reset-password",
        title="Reset Password",
        description="Reset a locked-out user's password",
        triggers=["user locked out"],
        workflow=[WorkflowStep(title="do", detail="stuff")],
        confidence=Confidence.HIGH,
    )
    defaults.update(kw)
    return SkillIR(**defaults)


def test_name_normalized_to_kebab():
    assert SkillIR(name="Reset User_Password", title="t", description="x" * 20).name == "reset-user-password"


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        SkillIR(name="reset!password", title="t", description="x" * 20)


def test_shippable_requires_high_confidence_and_content():
    assert _skill().is_shippable() is True
    assert _skill(confidence=Confidence.MEDIUM).is_shippable() is False
    assert _skill(triggers=[]).is_shippable() is False
    assert _skill(description="short").is_shippable() is False
