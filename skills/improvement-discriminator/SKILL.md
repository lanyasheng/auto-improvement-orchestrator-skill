---
name: improvement-discriminator
version: 0.1.0
description: Scores and validates improvement candidates using heuristics, rubric evidence, assertions, benchmarks, and human review.
author: OpenClaw Team
license: MIT
tags: [discriminator, critic, evaluator, scoring, assertions]
---

# Improvement Discriminator

Multi-signal scoring engine combining heuristic rules, evaluator rubrics, frozen benchmarks, hidden tests, external regression, and human review.

## When to Use
- Score and validate improvement candidates before execution
- Run the full Critic Engine V2 evaluation pipeline

## CLI
```bash
python3 scripts/score.py --candidate candidate.json --out scored.json
```
