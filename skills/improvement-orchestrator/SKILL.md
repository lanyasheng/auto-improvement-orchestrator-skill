---
name: improvement-orchestrator
version: 0.2.0
description: "Unified entry for structured self-improvement workflows. Coordinates Generator→Discriminator→Gate→Executor→Learner pipeline with Ralph Wiggum retry. Not for single-skill evaluation (use improvement-learner) or manual scoring (use improvement-discriminator)."
author: OpenClaw Team
license: MIT
tags: [orchestrator, self-improvement, automation, pipeline]
triggers:
  - improve skill
  - run improvement pipeline
  - self-improvement loop
  - orchestrate improvement
---

# Improvement Orchestrator

Coordinates the full improvement pipeline: Generator → Discriminator → Gate → Executor → Learner.

## When to Use

- Run a full improvement cycle on one or more skills
- Coordinate the Generator→Discriminator→Gate→Executor pipeline end-to-end
- Retry failed improvements with trace-aware feedback (Ralph Wiggum loop)

## When NOT to Use

- **Single-skill evaluation only** → use `improvement-learner` directly
- **Manual candidate scoring** → use `improvement-discriminator` directly
- **One-off file edits** → use `improvement-executor` directly
- **Benchmark data management** → use `benchmark-store` directly

## Pipeline

```
propose → discriminate → gate → execute → learn
         ↻ Ralph Wiggum: fail → inject trace → retry (max 3)
```

## CLI

```bash
# Full pipeline run
python3 scripts/orchestrate.py \
  --target /path/to/skill \
  --state-root /path/to/state \
  --out result.json

# With custom retry limit
python3 scripts/orchestrate.py \
  --target /path/to/skill \
  --max-retries 3 \
  --out result.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Full pipeline run | JSON with all stage outputs, final scores, and execution trace |
| Retry cycle | Updated candidates with injected failure traces |

## Related Skills

- **improvement-generator**: Produces candidate proposals (stage 1)
- **improvement-discriminator**: Scores candidates via multi-reviewer panel (stage 2)
- **improvement-gate**: 6-layer quality gate (stage 3)
- **improvement-executor**: Applies changes with backup/rollback (stage 4)
- **improvement-learner**: Karpathy self-improvement loop and progress tracking (stage 5)
- **benchmark-store**: Frozen benchmarks and Pareto front data

## References

- [Architecture](references/architecture.md) — System design and data flow
- [Guardrails](references/guardrails.md) — Safety rules and protected targets
- [Phases](references/phases.md) — Roadmap and phase definitions
- [End-to-End Demo](references/end-to-end-demo.md) — Complete walkthrough
