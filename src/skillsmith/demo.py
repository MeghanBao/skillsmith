"""Offline demo forge — a heuristic completer that needs no API key.

Lets anyone try the full pipeline / web workbench without ``ANTHROPIC_API_KEY``:
it fakes the LLM by pulling structure out of the source text with regex (numbered
steps, "never/always" guardrails, a title). The output genuinely reflects what
you upload, so the demo isn't canned — but it is deliberately dumb, not a real
model. Used by ``serve --demo`` / ``forge --demo`` / ``batch --demo`` and in tests.
"""

from __future__ import annotations

import json
import re

_GUARD_RE = re.compile(r"\b(never|always|must not|do not|don't)\b", re.IGNORECASE)


def _extract(tag: str, text: str) -> str:
    m = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.DOTALL)
    return (m.group(1) if m else "").strip()


def _kebab(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "demo-skill"


def _title(source: str) -> str:
    first = next((ln.strip(" #-*") for ln in source.splitlines() if ln.strip()), "")
    words = re.findall(r"[A-Za-z0-9]+", first)[:6]
    return " ".join(w.capitalize() for w in words) or "Demo Skill"


def _steps(source: str) -> list[dict]:
    # Numbered/bulleted items, merging wrapped continuation lines into one step.
    found: list[str] = []
    current: str | None = None
    for line in source.splitlines():
        s = line.strip()
        marker = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)$", s)
        if marker:
            if current is not None:
                found.append(current)
            current = marker.group(1)
        elif current is not None and s:
            current += " " + s
        elif current is not None:
            found.append(current)
            current = None
    if current is not None:
        found.append(current)

    if not found:
        parts = re.split(r"(?:(?<=\s)|^)\d+[.)]\s+", source)
        if len(parts) > 2:
            found = [p.strip() for p in parts[1:]]
    if not found:
        found = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if len(s.strip()) > 20]

    steps: list[dict] = []
    for text in found[:8]:
        code = re.search(r"`([^`]+)`", text)
        words = re.findall(r"[A-Za-z0-9]+", text)[:5]
        steps.append({
            "title": " ".join(words).capitalize() or "Step",
            "detail": text,
            "script": code.group(1) if code else None,
        })
    return steps


def _guardrails(source: str) -> list[str]:
    out = []
    for seg in re.split(r"(?<=[.!?])\s+|\n", source):
        seg = seg.strip(" -*")
        if len(seg) > 8 and _GUARD_RE.search(seg):
            out.append(seg)
    return out[:5]


class DemoCompleter:
    """Prompt-routed heuristic completer (no network, thread-safe)."""

    def complete(self, system: str, user: str) -> str:
        source = _extract("source", user)
        if "critic" in system.lower():
            return self._evaluate(source, _extract("candidate_skill", user))
        return self._generate(source)

    # -- generation ------------------------------------------------------

    def _generate(self, source: str) -> str:
        title = _title(source)
        steps = _steps(source)
        guards = _guardrails(source)
        desc = next((ln.strip() for ln in source.splitlines() if ln.strip()), title)
        if len(desc) < 15:
            desc = f"Skill for {title.lower()} (demo heuristic output)"
        skill = {
            "name": _kebab(title),
            "title": title,
            "description": desc[:160],
            "triggers": [title.lower(), f"handle {title.lower()}"],
            "inputs": [],
            "workflow": steps,
            "guardrails": guards,
            "examples": [],
            "source_refs": ["demo heuristic forge"],
            "confidence": "high" if len(steps) >= 3 else "medium",
        }
        return json.dumps(skill)

    # -- evaluation ------------------------------------------------------

    def _evaluate(self, source: str, candidate_json: str) -> str:
        try:
            cand = json.loads(candidate_json) if candidate_json else {}
        except json.JSONDecodeError:
            cand = {}
        steps = len(cand.get("workflow", []))
        guards = len(cand.get("guardrails", []))

        scores = {d: 4 for d in ("faithful", "atomic", "actionable", "triggerable", "guarded")}
        if len(source) < 60 or steps == 0:
            verdict, conf, fix = "reject", "low", ""
            scores = dict.fromkeys(scores, 2)
        elif steps >= 3 and guards >= 1:
            verdict, conf, fix = "pass", "high", ""
            scores.update(faithful=5, atomic=5, actionable=5)
        else:
            verdict, conf = "revise", "medium"
            fixes = []
            if steps < 3:
                scores["actionable"] = 3
                fixes.append("break the work into more concrete, ordered steps")
            if guards == 0:
                scores["guarded"] = 2
                fixes.append("add the hard rules / guardrails from the source")
            fix = "; ".join(fixes) or "tighten the skill"

        return json.dumps({
            "verdict": verdict,
            "confidence": conf,
            "scores": scores,
            "issues": [],
            "fix_instructions": fix,
        })
