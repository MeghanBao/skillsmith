"""Shared test fixtures: an offline fake completer that scripts LLM responses."""

from __future__ import annotations

import json

import pytest


class FakeCompleter:
    """Returns queued responses in order. Records the prompts it was given.

    Lets us exercise the full generate->eval->iterate loop with zero network.
    """

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self._responses:
            raise AssertionError("FakeCompleter ran out of scripted responses")
        return self._responses.pop(0)


def skill_json(**overrides) -> str:
    base = {
        "name": "reset-user-password",
        "title": "Reset User Password",
        "description": "Reset a locked-out user's password following IT policy",
        "triggers": ["user is locked out", "password reset request"],
        "inputs": ["user email", "ticket id"],
        "workflow": [
            {"title": "Verify identity", "detail": "Confirm via ticket", "script": None},
            {"title": "Trigger reset", "detail": "Run reset tool", "script": "idm reset $EMAIL"},
        ],
        "guardrails": ["Never reset without a verified ticket"],
        "examples": ["Ticket #123: reset alice@corp.de"],
        "source_refs": ["IT onboarding SOP §3"],
        "confidence": "high",
    }
    base.update(overrides)
    return json.dumps(base)


def eval_json(**overrides) -> str:
    base = {
        "verdict": "pass",
        "confidence": "high",
        "scores": {"faithful": 5, "atomic": 5, "actionable": 5, "triggerable": 4, "guarded": 4},
        "issues": [],
        "fix_instructions": "",
    }
    base.update(overrides)
    return json.dumps(base)


class StubCompleter:
    """Order-independent completer for parallel/batch tests.

    Chooses its reply from the *prompt* rather than a queue, so it is safe under
    the thread pool that ``forge_batch`` uses. Returns a skill for generation
    calls and an evaluation for critic calls.
    """

    def __init__(self, skill: str | None = None, evaluation: str | None = None):
        self._skill = skill or skill_json()
        self._eval = evaluation or eval_json()

    def complete(self, system: str, user: str) -> str:
        return self._eval if "critic" in system.lower() else self._skill


@pytest.fixture
def make_completer():
    return FakeCompleter


@pytest.fixture
def stub_completer():
    return StubCompleter
