"""Skillsmith — forge, test, and ship agent skills from raw company knowledge."""

from .evalset import CriticReport, GoldenCase, load_golden, run_critic_eval
from .evaluate import Evaluation, Verdict, evaluate_skill
from .generate import generate_skill
from .ir import Confidence, SkillIR, WorkflowStep
from .pipeline import ForgeResult, forge_skill

__version__ = "0.1.0"

__all__ = [
    "Confidence",
    "CriticReport",
    "Evaluation",
    "ForgeResult",
    "GoldenCase",
    "SkillIR",
    "Verdict",
    "WorkflowStep",
    "evaluate_skill",
    "forge_skill",
    "generate_skill",
    "load_golden",
    "run_critic_eval",
]
