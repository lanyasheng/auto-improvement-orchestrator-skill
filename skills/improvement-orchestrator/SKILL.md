---
name: improvement-orchestrator
version: 0.1.0
description: Unified entry skill for structured self-improvement workflows. Coordinates the Proposer -> Critic -> Executor -> Gate loop across skills, macros, and workflows.
author: OpenClaw Team
license: MIT
tags: [orchestrator, self-improvement, automation, pipeline]
---

# Improvement Orchestrator

Coordinates the full improvement pipeline: Generator -> Discriminator -> Executor -> Gate.

See `references/` for architecture, adapters, guardrails, and phase roadmap.

## When to Use
- Coordinate a full improvement cycle on a skill
- Run the Proposer→Discriminator→Gate→Executor pipeline
- Retry failed improvements with trace-aware feedback


## When NOT to Use

- [Define exclusion conditions here]

## Pipeline
```text
propose → discriminate → gate → execute → learn
         ↻ Ralph Wiggum: fail → inject trace → retry (max 3)
```

## CLI
```bash
python3 scripts/orchestrate.py --target /path/to/skill --auto
```
