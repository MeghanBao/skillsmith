"""Batch scheduling layer.

Wraps the single-source ``forge_skill`` loop so a whole folder of documents can
be processed in one run, producing many skills plus a summary report that flags
which need human review. This is a thin scheduler on purpose — all the quality
logic lives in ``pipeline``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .llm import Completer
from .pipeline import ForgeResult, forge_skill

# Extensions we treat as forgeable source documents.
SOURCE_SUFFIXES = {".md", ".txt", ".rst"}


@dataclass
class BatchItem:
    path: Path
    result: ForgeResult | None = None
    error: str | None = None


def discover_sources(root: Path) -> list[Path]:
    """Find all forgeable documents under ``root`` (recursive)."""
    if root.is_file():
        return [root]
    return sorted(
        p for p in root.rglob("*") if p.suffix.lower() in SOURCE_SUFFIXES
    )


def forge_batch(
    root: Path,
    max_iterations: int = 3,
    max_workers: int = 4,
    completer: Completer | None = None,
) -> list[BatchItem]:
    """Forge a skill from every source doc under ``root``, in parallel."""
    items = [BatchItem(path=p) for p in discover_sources(root)]

    def _run(item: BatchItem) -> BatchItem:
        try:
            source = item.path.read_text(encoding="utf-8")
            item.result = forge_skill(
                source, max_iterations=max_iterations, completer=completer
            )
        except Exception as exc:  # keep one bad doc from sinking the batch
            item.error = f"{type(exc).__name__}: {exc}"
        return item

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run, it): it for it in items}
        for fut in as_completed(futures):
            fut.result()

    return items


def summarize(items: list[BatchItem]) -> str:
    """Human-readable roll-up: what passed, what needs review, what failed."""
    passed = [i for i in items if i.result and i.result.passed]
    review = [
        i for i in items
        if i.result and not i.result.passed and not i.result.rejected
    ]
    rejected = [i for i in items if i.result and i.result.rejected]
    errored = [i for i in items if i.error]

    lines = [
        f"Forged {len(items)} source(s):",
        f"  ✅ shippable      : {len(passed)}",
        f"  ⚠️  needs review   : {len(review)}",
        f"  ⛔ rejected       : {len(rejected)}",
        f"  💥 errored        : {len(errored)}",
        "",
    ]
    for i in review:
        conf = i.result.final_confidence.value if i.result else "?"
        lines.append(f"  ⚠️  {i.path.name} (confidence={conf})")
    for i in rejected:
        lines.append(f"  ⛔ {i.path.name} — source too thin for a real skill")
    for i in errored:
        lines.append(f"  💥 {i.path.name} — {i.error}")
    return "\n".join(lines)
