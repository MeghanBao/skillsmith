"""Skillsmith command-line interface.

    skillsmith forge  <source>        # one doc -> one skill, all formats
    skillsmith batch  <folder>        # many docs -> many skills + report
    skillsmith formats                # list export targets
    skillsmith inputs                 # list supported source formats
    skillsmith eval-critic            # regression-test the critic vs golden set
    skillsmith serve                  # web review workbench (upload/review/export)
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from .batch import forge_batch, summarize
from .evalset import format_report, load_golden, run_critic_eval
from .ir import SkillIR
from .loaders import load_source, supported_suffixes
from .pipeline import forge_skill
from .renderers import available_formats, get_renderer

console = Console()

_DEMO_OPTION = click.option(
    "--demo",
    is_flag=True,
    help="offline heuristic forge — no ANTHROPIC_API_KEY needed (for trying it out)",
)


def _demo_completer(demo: bool):
    """Return a DemoCompleter when --demo is set, else None (real Anthropic)."""
    if not demo:
        return None
    from .demo import DemoCompleter

    console.print("[yellow]DEMO MODE[/yellow] — heuristic offline forge, no API key used")
    return DemoCompleter()


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
def inputs() -> None:
    """List supported source formats (file extensions)."""
    for suffix in sorted(supported_suffixes()):
        console.print(f"- {suffix}")


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("dist"))
@click.option("--format", "-f", "fmts", multiple=True, help="repeatable; default all")
@click.option("--max-iterations", default=3, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="print the SkillIR as JSON")
@_DEMO_OPTION
def forge(source: Path, out: Path, fmts: tuple[str, ...], max_iterations: int, as_json: bool, demo: bool) -> None:
    """Distill ONE source document into a skill and render it."""
    text = load_source(source)
    console.print(f"[bold]Forging[/bold] from {source} …")
    result = forge_skill(text, max_iterations=max_iterations, completer=_demo_completer(demo))

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
@_DEMO_OPTION
def batch(folder: Path, out: Path, fmts: tuple[str, ...], max_iterations: int, workers: int, demo: bool) -> None:
    """Forge a skill from every document in a folder + write a summary report."""
    console.print(f"[bold]Batch forging[/bold] from {folder} …")
    items = forge_batch(
        folder, max_iterations=max_iterations, max_workers=workers, completer=_demo_completer(demo)
    )

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


@main.command(name="eval-critic")
@click.option(
    "--golden-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path("evals/golden"),
    show_default=True,
    help="file or directory of golden cases",
)
@click.option("--threshold", default=0.85, show_default=True, help="min verdict agreement to pass")
def eval_critic(golden_dir: Path, threshold: float) -> None:
    """Regression-test the critic against the human-labelled golden set.

    Runs the real critic on every golden case and reports verdict agreement,
    weak-dimension recall, and a confusion matrix. Exits non-zero on regression
    so it can gate CI. Requires ANTHROPIC_API_KEY.
    """
    cases = load_golden(golden_dir)
    console.print(f"[bold]Evaluating critic[/bold] on {len(cases)} golden case(s) …")
    report = run_critic_eval(cases, threshold=threshold)
    console.print("\n" + format_report(report))
    if not report.passed:
        raise SystemExit(1)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--forge-workers", default=4, show_default=True, help="parallel forges per job")
@_DEMO_OPTION
def serve(host: str, port: int, forge_workers: int, demo: bool) -> None:
    """Launch the web review workbench (upload → review → export)."""
    try:
        import uvicorn

        from .web import create_app
    except ImportError:
        raise SystemExit(
            "web dependencies missing — install them with: pip install 'skillsmith[web]'"
        ) from None
    console.print(f"[bold]Skillsmith[/bold] workbench → http://{host}:{port}")
    uvicorn.run(
        create_app(completer=_demo_completer(demo), forge_workers=forge_workers),
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
