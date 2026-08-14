"""Thin wrapper around the Anthropic SDK.

Isolated here so the rest of the codebase never imports ``anthropic`` directly.
That keeps generation/eval logic testable (swap in a fake client) and makes the
model choice a single-point configuration.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol

# Default model. Configurable via SKILLSMITH_MODEL. Sonnet is the cost/quality
# sweet spot for structured distillation; bump to claude-opus-4-8 for the
# hardest sources.
DEFAULT_MODEL = os.environ.get("SKILLSMITH_MODEL", "claude-sonnet-4-6")

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt by filename (without extension) from prompts/."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


class Completer(Protocol):
    """Anything that can turn (system, user) -> text. Enables test fakes."""

    def complete(self, system: str, user: str) -> str: ...


class AnthropicCompleter:
    """Real completer backed by the Anthropic Messages API."""

    def __init__(self, model: str | None = None, max_tokens: int = 4096):
        from anthropic import Anthropic  # imported lazily so tests stay offline

        self._client = Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in resp.content if block.type == "text"
        )


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response.

    Models sometimes wrap JSON in ```json fences or add stray prose; be lenient.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in response: {text[:200]!r}")
    # Walk braces to find the matching close so trailing prose is ignored.
    depth = 0
    for i, ch in enumerate(candidate[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(candidate[start : i + 1])
    raise ValueError(f"unbalanced JSON in response: {text[:200]!r}")
