# Auto-Improvement Skills

A 7-skill pipeline for autonomous skill improvement. An AI agent evaluates a target skill, generates improvement candidates, scores them through multi-reviewer consensus, applies changes through a gated executor, and learns from outcomes via a 3-layer memory system backed by Pareto front tracking.

## Architecture

```
  Orchestrator ──► Generator ──► Discriminator ──► Executor ──► Gate
       │               ▲              │                           │
       │               │              ▼                           ▼
       │            Learner ◄── Benchmark-Store ◄─────────── (keep/revert)
       │               │
       └───── retry with failure trace
```

**Pipeline flow**: The orchestrator dispatches a run. The generator proposes improvement candidates (docs, references, guardrails). The discriminator scores each candidate through a multi-reviewer blind panel. The executor applies the top candidate and captures an execution trace. The gate validates the result through 5 layers (schema, compile, lint, regression, review). The learner records outcomes in 3-layer memory and drives self-improvement loops with Pareto front regression detection.

## Skills

| Skill | Role | Description |
|-------|------|-------------|
| `improvement-orchestrator` | Coordinator | State machine + retry loop; dispatches generate/score/execute/gate pipeline |
| `improvement-generator` | Generator | Proposes improvement candidates; adjusts priority from prior failure traces |
| `improvement-discriminator` | Discriminator | Multi-reviewer blind panel with configurable weights and risk sensitivity |
| `improvement-executor` | Executor | Applies candidate changes; captures structured execution traces |
| `improvement-gate` | Gate | 5-layer validation (schema, compile, lint, regression, review) with keep/revert decisions |
| `benchmark-store` | Data | Pareto front tracking with persistence; regression detection within tolerance |
| `improvement-learner` | Learner | 3-layer memory (hot/warm/cold), skill dimension evaluation, self-improvement loop |

## Shared Library

`lib/` contains code extracted from the original monolith:

- `common.py` -- shared utilities (timestamps, slugify, classification)
- `state_machine.py` -- improvement pipeline state machine (stages, transitions, persistence)

## Directory Structure

```
.
├── lib/                          # Shared library
│   ├── common.py
│   └── state_machine.py
├── skills/
│   ├── improvement-orchestrator/ # Pipeline coordinator
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── tests/
│   ├── improvement-generator/    # Candidate proposer
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── tests/
│   ├── improvement-discriminator/# Multi-reviewer scorer
│   │   ├── SKILL.md
│   │   ├── interfaces/
│   │   ├── scripts/
│   │   └── tests/
│   ├── improvement-executor/     # Change applier
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── tests/
│   ├── improvement-gate/         # 5-layer validator
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── tests/
│   ├── benchmark-store/          # Pareto front tracking
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── tests/
│   └── improvement-learner/      # Memory + self-improvement
│       ├── SKILL.md
│       ├── scripts/
│       └── tests/
├── .github/workflows/ci.yml     # CI: lint + test + security
└── pyproject.toml
```

## Quick Start

```bash
git clone <repo-url>
cd auto-improvement-skill
pip install pytest
python -m pytest skills/ -v
```

## Development

### Run all tests

```bash
python -m pytest skills/ -v --tb=short
```

### Run tests for a single skill

```bash
python -m pytest skills/improvement-gate/tests/ -v
```

### Add a new skill

1. Create `skills/<name>/` with `SKILL.md`, `scripts/`, `tests/`
2. Add the skill to the lint loop in `.github/workflows/ci.yml`
3. Import shared code from `lib/` as needed

### Verify no mock remnants

```bash
grep -rn "random\.uniform\|\"score\": 0.85" skills/*/scripts/*.py
```

This should return no results. All scores flow through real evaluator functions.

## License

MIT
