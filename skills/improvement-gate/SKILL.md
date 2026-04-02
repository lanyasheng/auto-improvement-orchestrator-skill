---
name: improvement-gate
version: 0.2.0
description: "6-layer mechanical quality gate: Schema→Compile→Lint→Regression→Review→HumanReview. Decides keep/pending/revert/reject for executed candidates. Not for scoring (use improvement-discriminator) or applying changes (use improvement-executor)."
author: OpenClaw Team
license: MIT
tags: [gate, quality, decision, keep, revert, reject, validation]
triggers:
  - quality gate
  - validate candidate
  - gate check
  - human review
---

# Improvement Gate

6-layer mechanical quality gate that decides keep/pending/revert/reject for executed candidates.

## When to Use

- Validate an executed candidate before keeping the change
- Run 6-layer mechanical checks (any layer fail = reject)
- Manage human review queue for high-risk candidates

## When NOT to Use

- **Scoring candidates** → use `improvement-discriminator`
- **Applying changes** → use `improvement-executor`
- **Evaluating skill structure** → use `improvement-learner`

## 6-Layer Gate

| Layer | Gate | Pass Condition |
|-------|------|---------------|
| 1 | **SchemaGate** | Execution result has valid JSON structure |
| 2 | **CompileGate** | Target file is syntactically valid after change |
| 3 | **LintGate** | No new lint warnings introduced |
| 4 | **RegressionGate** | No Pareto dimension regressed beyond 5% tolerance |
| 5 | **ReviewGate** | Multi-reviewer consensus is not DISPUTED+reject |
| 6 | **HumanReviewGate** | High-risk candidates require manual approval |

## CLI

```bash
# Run gate validation
python3 scripts/gate.py \
  --state-root /path/to/state

# List pending human reviews
python3 scripts/review.py --list --state-root /path/to/state

# Complete a human review
python3 scripts/review.py \
  --complete REVIEW_ID \
  --decision approve \
  --comment "Looks good"
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Gate check | JSON receipt: gate_decision (keep/pending/revert/reject), layer results |
| Review list | JSON array of pending human reviews with metadata |
| Review completion | Updated receipt with human decision |

## Related Skills

- **improvement-discriminator**: Scores candidates before gate; gate consumes scored results
- **improvement-executor**: Applies changes before gate validates them
- **improvement-orchestrator**: Calls gate as stage 3 in the full pipeline
- **benchmark-store**: Provides Pareto front data for RegressionGate
