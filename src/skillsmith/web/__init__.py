"""Skillsmith web layer — upload → forge → review/edit → export.

The productization surface: a minimal service that wraps the existing batch
engine and renderers so non-technical users can drop in documents, review the
generated skills, edit the ones that need work, and download an export bundle.
Import ``create_app`` to get a configured FastAPI app.
"""

from .app import create_app

__all__ = ["create_app"]
