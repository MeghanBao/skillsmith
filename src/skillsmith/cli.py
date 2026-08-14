"""Skillsmith command-line interface.

    skillsmith forge  <source>        # one doc -> one skill, all formats
    skillsmith batch  <folder>        # many docs -> many skills + report
    skillsmith formats                # list export targets
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from .batch import forge_batch, summarize
from .ir import SkillIR
from .pipeline import forge_skill
from .renderers import available_formats, get_renderer

console = Console()


def _write_skill(skill: SkillIR, out_dir: Path, formats: list[str]) -> None:
    for fmt in formats:
        renderer = get_renderer(fmt)
        target = out_dir / fmt / skill.name
        target.mkdir(parents=True, exist_ok=True)
        for rel, contents in renderer.render(skill).items():
            (target / rel).write_text(contents, encoding="utf-8")
        console.print(f"  → [cyan]{fmt}[/cyan]: {target}")


@click.group()
@click.version_option(package_name="skillsmith")
def main() -> None:
    """Forge, test, and ship agent skills from raw company knowledge."""


@main.command()
def formats() -> None:
    """List available export formats."""
    for f in available_formats():
        console.print(f"- {f}")


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("dist"))
@click.option("--format", "-f", "fmts", multiple=True, help="repeatable; default all")
@click.option("--max-iterations", default=3, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="print the SkillIR as JSON")
def forge(source: Path, out: Path, fmts: tuple[str, ...], max_iterations: int, as_json: bool) -> None:
    """Distill ONE source document into a skill and render it."""
    text = source.read_text(encoding="utf-8")
    console.print(f"[bold]Forging[/bold] from {source} …")
    result = forge_skill(text, max_iterations=max_iterations)

    if result.skill is None or result.rejected:
        console.print("[red]Rejected[/red]: source too thin for a real skill.")
        raise SystemExit(1)

    skill = result.skill
    badge = "[green]PASS[/green]" if result.passed else "[yellow]NEEDS REVIEW[/yellow]"
    console.print(
        f"{badge}  {skill.name}  "
        f"(confidence={skill.confidence.value}, iterations={len(result.attempts)})"
    )

    if as_json:
        console.print_json(skill.model_dump_json())

    selected = list(fmts) or available_formats()
    _write_skill(skill, out, selected)


@main.command()
@click.argument("folder", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("dist"))
@click.option("--format", "-f", "fmts", multiple=True, help="repeatable; default all")
@click.option("--max-iterations", default=3, show_default=True)
@click.option("--workers", default=4, show_default=True)
def batch(folder: Path, out: Path, fmts: tuple[str, ...], max_iterations: int, workers: int) -> None:
    """Forge a skill from every document in a folder + write a summary report."""
    console.print(f"[bold]Batch forging[/bold] from {folder} …")
    items = forge_batch(folder, max_iterations=max_iterations, max_workers=workers)

    selected = list(fmts) or available_formats()
    report = {"sources": [], "summary": {}}
    for item in items:
        if item.result and item.result.skill and not item.result.rejected:
            _write_skill(item.result.skill, out, selected)
        report["sources"].append(
            {
                "path": str(item.path),
                "passed": bool(item.result and item.result.passed),
                "rejected": bool(item.result and item.result.rejected),
                "error": item.error,
                "confidence": item.result.final_confidence.value if item.result else None,
            }
        )

    summary_text = summarize(items)
    console.print("\n" + summary_text)
    (out).mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    console.print(f"\nReport → {out / 'report.json'}")


if __name__ == "__main__":
    main()
