"""Render a SkillIR to an AdaL ``@skills`` JSON descriptor.

NOTE: this is a first-cut mapping. Confirm exact field names against the AdaL
@skills spec before relying on it in production — it is intentionally isolated
here so tweaks never touch the generation/eval engine.
"""

from __future__ import annotations

import json

from ..ir import SkillIR
from .base import Renderer


class AdalRenderer(Renderer):
    format_id = "adal"

    def render(self, skill: SkillIR) -> dict[str, str]:
        descriptor = {
            "name": skill.name,
            "displayName": skill.title,
            "description": skill.description,
            "activation": {"intents": skill.triggers},
            "inputs": skill.inputs,
            "steps": [
                {"name": s.title, "instruction": s.detail, "code": s.script}
                for s in skill.workflow
            ],
            "constraints": skill.guardrails,
            "examples": skill.examples,
            "metadata": {
                "confidence": skill.confidence.value,
                "sourceRefs": skill.source_refs,
                "generatedBy": "skillsmith",
            },
        }
        return {"skill.json": json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n"}
