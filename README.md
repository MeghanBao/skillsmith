# Skillsmith 🔨

**English** · [中文](README.zh-CN.md)

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
| `loaders/` | source file → clean plain text (`.md`, `.pdf`, `.html`, `.vtt`/`.srt`, Slack `.json`) |
| `renderers/` | `SkillIR` → target files (`claude-code`, `adal`, …) |
| `evalset.py` | golden regression harness for the critic |
| `llm.py` | the only module that imports the Anthropic SDK |
| `cli.py` | `forge` / `batch` / `formats` / `inputs` / `eval-critic` commands |

## Source formats

Loaders normalize each input into plain text before distillation. Run
`skillsmith inputs` to list them.

| Loader | Extensions | Notes |
|--------|-----------|-------|
| text | `.md` `.markdown` `.txt` `.rst` | passthrough |
| pdf | `.pdf` | per-page text extraction (pypdf) |
| html | `.html` `.htm` | strips script/style/nav boilerplate (BeautifulSoup) |
| vtt | `.vtt` `.srt` | caption → prose; drops timings and rolling auto-caption dupes |
| slack | `.json` | Slack export → `Name: message` transcript; resolves `@mentions` via a sibling `users.json`; non-Slack JSON falls through untouched |

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `ANTHROPIC_API_KEY` | — | required for real runs |
| `SKILLSMITH_MODEL` | `claude-sonnet-4-6` | distillation model; bump to `claude-opus-4-8` for hard sources |

## Adding an export format

1. Subclass `Renderer` in `renderers/`, set `format_id`, implement `render()`.
2. Register the instance in `renderers/__init__.py`.

That's it — the generation and eval engine are untouched.

## Adding a source format

1. Subclass `Loader` in `loaders/`, set `suffixes`, implement `load()`.
2. Register the instance in `loaders/__init__.py`.

Same principle as renderers — generation and eval never change.

## Testing the critic (golden regression set)

The critic is itself an LLM, so its judgement can silently drift when you change
`prompts/eval_skill.md` or the model. `evals/golden/` holds human-labelled cases
— each a `(source, candidate skill, expected verdict)` plus the dimensions that
*should* score low — and `eval-critic` runs the real critic against them:

```bash
skillsmith eval-critic                      # needs ANTHROPIC_API_KEY
skillsmith eval-critic --threshold 0.9      # stricter gate
```

It reports verdict agreement, weak-dimension recall, and a confusion matrix, and
exits non-zero on regression so it can gate CI:

```
Critic golden eval — 12 case(s)
  verdict agreement : 92% (threshold 85%)  ✅ PASS
  weak-dim recall   : 100%

  confusion (rows=expected, cols=actual):
                 pass   revise   reject
       pass         3        1        0
     revise         0        6        0
     reject         0        0        2
```

Add cases by dropping a JSON object (or list) into `evals/golden/`. The seed set
covers faithful/atomic/actionable/triggerable/guarded failure modes plus
too-thin and off-topic rejects.

## Tests

```bash
pytest -v          # fully offline: a fake completer scripts the LLM responses
```

## Roadmap

- [x] Core generate→eval→iterate engine + `SkillIR`
- [x] Batch scheduler with review report
- [x] Renderers: Claude Code `SKILL.md`, AdaL `@skills`
- [x] Source loaders: PDF, HTML, Slack export, VTT/SRT transcripts
- [x] Golden eval set + regression harness for the critic
- [ ] OpenCode renderer
- [ ] "Knowledge distillation as a service" packaging for SMEs

## License

MIT
