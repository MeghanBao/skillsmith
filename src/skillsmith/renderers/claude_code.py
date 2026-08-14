"""Render a SkillIR to Claude Code's ``SKILL.md`` format."""

from __future__ import annotations

import yaml

from ..ir import SkillIR
from .base import Renderer


class ClaudeCodeRenderer(Renderer):
    format_id = "claude-code"

    def render(self, skill: SkillIR) -> dict[str, str]:
        frontmatter = yaml.safe_dump(
            {"name": skill.name, "description": skill.description},
            sort_keys=False,
            allow_unicode=True,
        ).strip()

        lines: list[str] = [f"---\n{frontmatter}\n---", "", f"# {skill.title}", ""]

        if skill.triggers:
            lines += ["## When to use", ""]
            lines += [f"- {t}" for t in skill.triggers]
            lines.append("")

        if skill.inputs:
            lines += ["## Inputs", ""]
            lines += [f"- {i}" for i in skill.inputs]
            lines.append("")

        if skill.workflow:
            lines += ["## Workflow", ""]
            for n, step in enumerate(skill.workflow, 1):
                lines.append(f"{n}. **{step.title}** — {step.detail}")
                if step.script:
                    lines += ["", "   ```bash", *(
                        f"   {ln}" for ln in step.script.splitlines()
                    ), "   ```"]
            lines.append("")

        if skill.guardrails:
            lines += ["## Guardrails", ""]
            lines += [f"- {g}" for g in skill.guardrails]
            lines.append("")

        if skill.examples:
            lines += ["## Examples", ""]
            lines += [f"- {e}" for e in skill.examples]
            lines.append("")

        if skill.source_refs:
            lines += ["## Provenance", ""]
            lines += [f"- {r}" for r in skill.source_refs]
            lines.append("")

        return {"SKILL.md": "\n".join(lines).rstrip() + "\n"}
