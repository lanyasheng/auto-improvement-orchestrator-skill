---
name: session-feedback-analyzer
category: tool
description: |
  Parse Claude Code session JSONL to extract implicit user feedback signals.
  Detects skill invocations (tool_use blocks with name="Skill" or /slash-commands),
  classifies user responses as correction/acceptance/partial within a 3-turn
  influence window, and computes per-skill correction_rate metrics.
  Not for synthetic evaluation (use improvement-evaluator) or structural
  scoring (use improvement-learner). Use this when you need to find which
  skills users correct most often, or generate feedback.jsonl for the
  improvement-generator.
license: MIT
triggers:
  - feedback
  - correction_rate
  - session.*analyz
  - user.*feedback
  - skill.*feedback
  - which skills get corrected
  - implicit feedback
---

# Session Feedback Analyzer

Mines Claude Code session JSONL for implicit user feedback. When a user corrects, redoes, reverts, or partially accepts AI output after a skill invocation, that signals a skill gap. Outputs structured `feedback.jsonl` with per-event dimension attribution for the improvement pipeline.

## When to Use / NOT to Use

- Compute per-skill correction rates, find which skills users correct most, generate feedback.jsonl for the generator, track correction trends over time
- **NOT** for synthetic task evaluation (improvement-evaluator), structural scoring (improvement-learner), or candidate scoring (improvement-discriminator)

## CLI

```
python3 scripts/analyze.py [--session-dir DIR] [--output PATH]
  [--no-snippets] [--skill-filter SKILL_ID] [--min-invocations N]
```

| Param | Default | Description |
|-------|---------|-------------|
| `--session-dir` | `~/.claude/projects/` | Root directory for session JSONL files |
| `--output` | `feedback-store/feedback.jsonl` | Output path for feedback JSONL |
| `--no-snippets` | off | Omit user message snippets (privacy mode) |
| `--skill-filter` | none | Only analyze this specific skill's invocations |
| `--min-invocations` | 5 | Minimum invocations before computing metrics |

## Detection Rules

| Path | Condition |
|------|-----------|
| Tool use | Assistant message with `tool_use` block, `name == "Skill"`, skill_id from `input.skill` |
| Slash command | System `subtype == "local_command"` with `<command-name>` tag (excludes help/clear/resume/compact/config) |

## Outcome Classification (3-turn influence window)

| Outcome | Type | Confidence | Trigger |
|---------|------|-----------|---------|
| correction | rejection | 0.9 | Keywords: "wrong", "incorrect", "no," (zh: "不对", "错了") |
| correction | revert | 0.9 | Git revert commands in assistant tool_use (`git checkout/restore/reset`) |
| correction | redo | 0.9 | Keywords: "try again", "redo" (zh: "重新来", "换个方案") |
| partial | partial | 0.7 | Qualifier ("but", "however", "但是") + correction or acceptance keyword |
| acceptance | explicit | 0.8 | Keywords: "lgtm", "looks good", "correct" (zh: "好", "可以", "对的") |
| acceptance | implicit | 0.6 | User message >20 chars, no question marks, no correction keywords |

## Dimension Attribution

Each correction/partial gets a `dimension_hint` from keyword matching:

| Dimension | Keywords |
|-----------|----------|
| accuracy | naming, format, style, typo, 命名, 格式, 拼写 |
| coverage | missing, forgot, incomplete, 缺少, 漏了 |
| reliability | again, inconsistent, 重复, 不稳定 |
| efficiency | slow, verbose, 太慢, 冗余 |
| security | security, secret, token, credential, 密钥 |
| trigger_quality | "wrong skill", "shouldn't trigger", "不该触发" -- wrong skill invoked entirely (distinct from accuracy which is correct skill, wrong output) |

## correction_rate Formula

`correction_rate = (corrections + 0.5 * partials) / total_invocations`. Returns `sufficient_data: false` when sample_size < `--min-invocations`. Trend: last 30d vs prior 30d. Positive = worsening, negative = improving, |delta| <= 0.05 = stable.

## Privacy Controls

`--no-snippets` strips user message snippets. `~/.claude/feedback-config.json` with `{"enabled": false}` disables all collection. Skips `pytest/`, `/tmp/`, `/subagents/` dirs. Auto-archives events >90 days old to `feedback-store/archive/`.

## Output Schema (feedback.jsonl, one JSON per line)

```json
{
  "event_id": "a1b2c3d4...", "timestamp": "2026-04-05T10:00:00Z",
  "session_id": "uuid", "skill_id": "cpp-expert", "invocation_uuid": "msg-uuid",
  "outcome": "correction", "confidence": 0.9, "correction_type": "rejection",
  "user_message_snippet": "not right, should use const ref...",
  "turns_to_feedback": 1, "ai_tools_used": ["Read", "Edit"],
  "dimension_hint": "accuracy"
}
```

## Metrics API (scripts/metrics.py)

```python
from scripts.metrics import load_feedback_events, compute_correction_rate, \
    compute_correction_trend, compute_hotspot_dimensions, format_metrics_report
events = load_feedback_events(Path("feedback-store/feedback.jsonl"))
compute_correction_rate(events, "cpp-expert")
# -> {correction_rate: 0.35, sample_size: 20, sufficient_data: true, corrections: 5, partials: 4}
compute_correction_trend(events, "cpp-expert")
# -> {trend: -0.08, direction: "improving", recent_rate: 0.30, prior_rate: 0.38}
compute_hotspot_dimensions(events, "cpp-expert")  # -> {"accuracy": 5, "coverage": 3}
```

## Integration & Related Skills

Generator auto-discovers `feedback-store/` via `lib/common.py:load_source_paths()`. Hotspots inform prioritization. autoloop-controller uses correction_rate plateau as termination condition.

- **improvement-generator** -- consumes feedback.jsonl via `--source`
- **improvement-evaluator** -- synthetic evaluation (complementary) | **autoloop-controller** -- plateau termination
