---
name: improvement-learner
version: 0.2.0
description: "Real Karpathy self-improvement loop with 6-dimension structural evaluation, HOT/WARM/COLD three-layer memory, and Pareto front tracking. Evaluates skills on accuracy (12 checks), coverage, reliability, efficiency, security, and trigger_quality. Not for candidate scoring (use improvement-discriminator) or full pipeline orchestration (use improvement-orchestrator)."
author: OpenClaw Team
license: MIT
tags: [learner, self-improve, progress, evolution, feedback-loop, karpathy, pareto]
triggers:
  - evaluate skill
  - self-improve
  - karpathy loop
  - track progress
  - skill quality check
---

# Improvement Learner

Real Karpathy self-improvement loop: evaluate → modify → re-evaluate → keep/revert → repeat.

## When to Use

- Evaluate a skill's structural quality across 6 dimensions
- Run an autonomous self-improvement loop with Pareto front protection
- Track skill evolution over time with progress metrics

## When NOT to Use

- **Semantic candidate scoring** → use `improvement-discriminator`
- **Full pipeline orchestration** → use `improvement-orchestrator`
- **Applying file changes** → use `improvement-executor`

## 6 Evaluation Dimensions

| Dimension | Checks | Pure-text default |
|-----------|--------|-------------------|
| **accuracy** | 12 items: frontmatter, name/description/version, pushy trigger desc, When to Use, When NOT to Use, code examples, Usage section, no vague language, min length, Related Skills, Output Artifacts | — |
| **coverage** | SKILL.md = 60% base + scripts/references/tests/README bonuses. Penalty if >500 lines without references/ | — |
| **reliability** | pytest pass=1.0, fail=0.5, timeout=0.3 | 1.0 (pure-text) |
| **efficiency** | Line count scoring: ≤200=1.0, ≥1200=0.3 | — |
| **security** | No api_key/password/sk- in SKILL.md, has license, no os.system()/exec() | — |
| **trigger_quality** | Description length, trigger keywords, triggers: field, disambiguation, related refs | — |

## Three-Layer Memory

| Layer | Capacity | Behavior |
|-------|----------|----------|
| **HOT** | ≤100 entries | Always loaded, frequently accessed patterns |
| **WARM** | Unlimited | Overflow from HOT, loaded on demand |
| **COLD** | Archive | >3 months inactive (future) |

## CLI

```bash
# Evaluate a skill (structural dimensions only)
python3 scripts/self_improve.py \
  --skill-path /path/to/skill \
  --max-iterations 1

# Run Karpathy self-improvement loop (5 rounds)
python3 scripts/self_improve.py \
  --skill-path /path/to/skill \
  --max-iterations 5 \
  --memory-dir /path/to/memory \
  --state-root /path/to/state

# Track progress over time
python3 scripts/track_progress.py \
  --skill-path /path/to/skill \
  --output progress.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Evaluate | JSON with 6-dimension scores (0.0-1.0 each) |
| Self-improve | JSON report: iterations, kept/reverted/skipped counts, final_scores, memory stats |
| Track progress | JSON with historical scores and trend data |

## Related Skills

- **improvement-discriminator**: Semantic scoring (LLM judge); learner focuses on structural quality
- **improvement-orchestrator**: Full pipeline; learner can be called standalone or as stage 5
- **benchmark-store**: Pareto front data shared between learner and benchmark-store
