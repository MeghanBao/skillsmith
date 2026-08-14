"""Generation engine: source document -> SkillIR."""

from __future__ import annotations

from .ir import SkillIR
from .llm import AnthropicCompleter, Completer, extract_json, load_prompt


def generate_skill(
    source: str,
    completer: Completer | None = None,
    fix_instructions: str | None = None,
) -> SkillIR:
    """Distill one source document into a candidate SkillIR.

    ``fix_instructions`` is appended on revision passes so the generator can act
    on the critic's feedback (the iterate half of generate->test->eval->iterate).
    """
    completer = completer or AnthropicCompleter()
    system = load_prompt("generate_skill")

    user = f"<source>\n{source}\n</source>"
    if fix_instructions:
        user += (
            "\n\nA previous attempt was reviewed. Apply this feedback and "
            f"regenerate the full JSON:\n{fix_instructions}"
        )

    raw = completer.complete(system, user)
    return SkillIR.model_validate(extract_json(raw))
