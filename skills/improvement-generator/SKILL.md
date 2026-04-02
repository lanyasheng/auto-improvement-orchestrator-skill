---
name: improvement-generator
version: 0.2.0
description: "Generates structured improvement candidates by analyzing target skill, feedback signals, and failure traces (GEPA trace-aware). Supports trace injection for retry loops. Not for scoring (use improvement-discriminator) or evaluation (use improvement-learner)."
author: OpenClaw Team
license: MIT
tags: [generator, proposer, candidates, self-improvement, trace-aware]
triggers:
  - generate candidates
  - propose improvements
  - create improvement
---

# Improvement Generator

Produces ranked improvement candidates from target analysis, feedback signals, and failure traces.

## When to Use

- Generate structured improvement proposals for a target skill
- Inject failure traces from previous attempts (GEPA trace-aware feedback)
- Analyze memory patterns to avoid previously failed approaches

## When NOT to Use

- **Scoring candidates** → use `improvement-discriminator`
- **Evaluating skill structure** → use `improvement-learner`
- **Full pipeline** → use `improvement-orchestrator`

## Trace-Aware Candidate Generation

When `--trace` is provided, the generator adjusts candidate priorities based on what failed previously:

```
Previous failure on "accuracy" dimension
  → prioritize accuracy-related improvements
  → skip strategies that failed ≥3 times on this dimension
```

## CLI

```bash
# Basic candidate generation
python3 scripts/propose.py \
  --target /path/to/skill \
  --out candidates.json

# With failure trace injection (for retry loops)
python3 scripts/propose.py \
  --target /path/to/skill \
  --trace previous_failure.json \
  --out candidates.json

# With feedback from memory
python3 scripts/propose.py \
  --target /path/to/skill \
  --feedback memory_patterns.json \
  --out candidates.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Generate | JSON array of ranked candidates with category, risk_level, execution_plan |
| With trace | Same format, but priorities adjusted based on failure analysis |

## Related Skills

- **improvement-discriminator**: Scores the candidates this skill produces
- **improvement-orchestrator**: Calls generator as stage 1 in the pipeline
- **improvement-learner**: Provides evaluation data that informs candidate selection
