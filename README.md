# Skillsmith 🔨

**Forge, test, and ship reusable agent skills from raw company knowledge** —
SOPs, internal docs, chat/Slack transcripts, screen-recording notes.

Skillsmith is one pipeline with three layers:

```
Source knowledge (SOP / docs / transcripts)
        │
        ▼
Core engine   ── generate → test → eval → iterate     (skill-creator methodology)
        │
        ▼
Batch layer   ── one run over a whole folder, parallel, with a review report
        │
        ▼
Output layer  ── one skill IR → many target formats (Claude Code, AdaL @skills, …)
```

The insight: these aren't three features, they're three layers of the same
pipeline. The core is a single generation+eval engine. Batch is a scheduler
around it. Cross-format export is a set of renderers over one **intermediate
representation** (`SkillIR`). Adding a target format is adding a renderer — it
never touches generation or eval.

## Install

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...
```

## Use

```bash
# One document → one skill, rendered to every format under ./dist
skillsmith forge examples/reset-password-sop.md

# Only the Claude Code SKILL.md, and print the intermediate representation
skillsmith forge examples/reset-password-sop.md -f claude-code --json

# A whole folder → many skills + a dist/report.json flagging what needs review
skillsmith batch ./sops --workers 8

# What can we export to?
skillsmith formats
```

## How the core loop works

`forge_skill()` (in `pipeline.py`) is the whole methodology:

1. **generate** — distill the source into a candidate `SkillIR` (`generate.py`)
2. **eval** — an LLM critic scores it for faithfulness, atomicity, actionability,
   triggerability, and guardrails (`evaluate.py`)
3. **iterate** — on `revise`, the critic's fix instructions feed the next
   generation pass; loop until `pass` or the iteration budget is spent
4. the final confidence is set by the critic, and the batch report flags
   anything below `high` for human review

## Architecture

| Module | Responsibility |
|--------|----------------|
| `ir.py` | `SkillIR` — the format-agnostic intermediate representation |
| `generate.py` | source → candidate `SkillIR` |
| `evaluate.py` | candidate → structured verdict + fix instructions |
| `pipeline.py` | the generate→eval→iterate loop |
| `batch.py` | scheduler + summary report over a folder |
| `renderers/` | `SkillIR` → target files (`claude-code`, `adal`, …) |
| `llm.py` | the only module that imports the Anthropic SDK |
| `cli.py` | `forge` / `batch` / `formats` commands |

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `ANTHROPIC_API_KEY` | — | required for real runs |
| `SKILLSMITH_MODEL` | `claude-sonnet-4-6` | distillation model; bump to `claude-opus-4-8` for hard sources |

## Adding an export format

1. Subclass `Renderer` in `renderers/`, set `format_id`, implement `render()`.
2. Register the instance in `renderers/__init__.py`.

That's it — the generation and eval engine are untouched.

## Tests

```bash
pytest -v          # fully offline: a fake completer scripts the LLM responses
```

## Roadmap

- [x] Core generate→eval→iterate engine + `SkillIR`
- [x] Batch scheduler with review report
- [x] Renderers: Claude Code `SKILL.md`, AdaL `@skills`
- [ ] More source loaders (PDF, HTML, Slack export, VTT transcripts)
- [ ] OpenCode renderer
- [ ] Golden eval set + regression harness for the critic
- [ ] "Knowledge distillation as a service" packaging for SMEs

## License

MIT
