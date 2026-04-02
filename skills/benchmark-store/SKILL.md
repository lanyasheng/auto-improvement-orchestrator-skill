---
name: benchmark-store
version: 0.2.0
description: "Central store for frozen benchmarks, hidden test suites, Pareto front tracking, and evaluation standards. Provides immutable reference data for the improvement pipeline. Not for scoring candidates (use improvement-discriminator) or running improvements (use improvement-learner)."
author: OpenClaw Team
license: MIT
tags: [benchmark, frozen-tests, hidden-tests, evaluation, data-store, pareto]
triggers:
  - benchmark data
  - frozen tests
  - pareto front
  - evaluation standards
---

# Benchmark Store

Central store for frozen benchmarks, hidden test suites, Pareto front tracking, and evaluation standards.

## When to Use

- Initialize or query the benchmark database
- Compare a skill's scores against frozen baselines
- Track Pareto front evolution (no dimension may regress beyond 5% tolerance)
- Reference evaluation standards and quality tiers

## When NOT to Use

- **Scoring candidates** → use `improvement-discriminator`
- **Running self-improvement** → use `improvement-learner`
- **Full pipeline** → use `improvement-orchestrator`

## Pareto Front

The Pareto front ensures multi-dimensional quality: a new entry is accepted only if it does not cause any dimension to regress more than 5%.

```python
# ParetoEntry.dominates(other) → True if all dimensions ≥ other
# ParetoFront.check_regression(new_scores) → {"regressed": bool, "regressions": [...]}
```

## CLI

```bash
# Initialize benchmark database
python3 scripts/benchmark_db.py --init --db benchmarks.db

# Compare a skill against baselines
python3 scripts/benchmark_db.py \
  --compare \
  --skill /path/to/skill \
  --category general
```

## Quality Tiers (from evaluation-standards.md)

| Tier | Score | Ship? |
|------|-------|-------|
| POWERFUL ⭐ | ≥ 85% | Yes — Marketplace ready |
| SOLID | 70–84% | Yes — GitHub |
| GENERIC | 55–69% | No — needs iteration |
| WEAK | < 55% | No — reject or rewrite |

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Init | SQLite database with schema |
| Compare | JSON comparison report with per-dimension delta |
| Pareto check | JSON with regressed flag and dimension-level details |

## Related Skills

- **improvement-learner**: Imports ParetoFront/ParetoEntry for self-improvement loop
- **improvement-gate**: RegressionGate uses Pareto data to check for regressions
- **improvement-discriminator**: References evaluation standards for scoring context

## Data Files

- `data/evaluation-standards.md` — Quality tiers, evaluation dimensions, category weights (v2.0.0)
- `data/fixtures/` — Frozen test fixtures for benchmark validation
