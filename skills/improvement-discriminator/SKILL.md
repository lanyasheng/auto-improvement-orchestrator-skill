---
name: improvement-discriminator
version: 0.2.0
description: "Multi-signal scoring engine for improvement candidates. Combines heuristic rules, evaluator rubrics, LLM-as-Judge (4-dim semantic), and multi-reviewer blind panel with cognitive labels (CONSENSUS/VERIFIED/DISPUTED). Not for structural evaluation (use improvement-learner) or gate decisions (use improvement-gate)."
author: OpenClaw Team
license: MIT
tags: [discriminator, critic, evaluator, scoring, assertions, llm-judge]
triggers:
  - score candidate
  - evaluate improvement
  - run critic
  - multi-reviewer panel
  - LLM judge
---

# Improvement Discriminator

Multi-signal scoring engine combining heuristic rules, evaluator rubrics, LLM-as-Judge, and multi-reviewer blind panel.

## When to Use

- Score and rank improvement candidates before execution
- Run multi-reviewer blind panel with cognitive labels (CONSENSUS/VERIFIED/DISPUTED)
- Evaluate candidates with LLM-as-Judge on 4 semantic dimensions (clarity, specificity, consistency, safety)
- Blend heuristic + evaluator + LLM scores (weights: 0.5/0.2/0.3 when all three active)

## When NOT to Use

- **Structural evaluation of a skill directory** → use `improvement-learner`
- **Keep/revert/reject decisions** → use `improvement-gate`
- **Applying changes to files** → use `improvement-executor`

## Scoring Modes

| Mode | Flag | Scoring |
|------|------|---------|
| Heuristic only | (default) | Rule-based: category bonus + source refs + risk penalty |
| + Evaluator evidence | `--use-evaluator-evidence` | Heuristic 70% + evaluator 30% |
| + LLM Judge | `--llm-judge {claude,openai,mock}` | Heuristic 60% + LLM 40% |
| + Panel | `--panel` | 2+ reviewers score independently, cognitive label determines consensus |
| All combined | `--panel --llm-judge mock --use-evaluator-evidence` | Full pipeline |

## CLI

```bash
# Basic scoring
python3 scripts/score.py --input candidates.json --output scored.json

# Multi-reviewer panel with LLM judge
python3 scripts/score.py \
  --input candidates.json \
  --panel \
  --llm-judge mock \
  --output scored.json

# With evaluator evidence
python3 scripts/score.py \
  --input candidates.json \
  --use-evaluator-evidence \
  --llm-judge claude \
  --output scored.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Score candidates | JSON with per-candidate scores, blockers, recommendations, judge_notes |
| Panel scoring | JSON with panel_reviews[], cognitive_label, aggregated_score |
| LLM judge | JSON with llm_verdict (score, decision, dimensions, confidence, suggestions) |

## Related Skills

- **improvement-generator**: Produces the candidates that this skill scores
- **improvement-gate**: Consumes scored candidates for keep/revert/reject decisions
- **improvement-learner**: Structural evaluation (6-dim); discriminator focuses on semantic quality
- **benchmark-store**: Provides frozen benchmarks for regression checking
