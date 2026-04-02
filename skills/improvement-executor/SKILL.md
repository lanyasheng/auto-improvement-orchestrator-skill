---
name: improvement-executor
version: 0.1.0
description: Executes approved improvement candidates by applying low-risk document changes with backup and rollback support.
author: OpenClaw Team
license: MIT
tags: [executor, apply, rollback, safe-execution]
---

# Improvement Executor

Applies accepted candidates (docs/reference/guardrail) with automatic backup and rollback capability.

## When to Use
- Apply an approved improvement candidate to its target file
- Rollback a previously applied change using backup or receipt


## When NOT to Use

- [Define exclusion conditions here]

## CLI
```bash
python3 scripts/execute.py --candidate candidate.json --out result.json
python3 scripts/rollback.py --receipt receipt.json --dry-run
```
