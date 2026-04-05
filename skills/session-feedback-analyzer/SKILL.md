---
name: session-feedback-analyzer
category: tool
description: |
  Parse Claude Code session JSONL to extract implicit user feedback signals.
  Detects skill invocations, classifies user responses as correction/acceptance/partial,
  and computes per-skill correction_rate metrics for the improvement pipeline.
license: MIT
triggers:
  - feedback
  - correction_rate
  - session.*analyz
  - user.*feedback
  - skill.*feedback
---

# Session Feedback Analyzer

Mines Claude Code session logs for implicit feedback: when a user corrects, redoes, or reverts AI output after a skill was invoked, that is evidence the skill has a gap.

## When to Use

- Computing per-skill correction rates from real usage data
- Finding which skills get corrected most often (and on which dimensions)
- Generating feedback.jsonl that the improvement-generator consumes via `--source`
- Checking if autoloop improvements actually reduce user corrections

## When NOT to Use

- Evaluating skill execution with synthetic tasks (use improvement-evaluator)
- Scoring skill document structure (use improvement-learner)

## Usage

```bash
# Analyze all sessions
python3 scripts/analyze.py \
  --session-dir ~/.claude/projects/ \
  --output feedback-store/feedback.jsonl

# Filter to a specific skill
python3 scripts/analyze.py \
  --skill-filter cpp-expert \
  --output feedback-store/feedback.jsonl

# Privacy mode: omit user message snippets
python3 scripts/analyze.py --no-snippets
```

## Metrics

```bash
python3 -c "
from scripts.metrics import load_feedback_events, compute_all_skill_metrics, format_metrics_report
events = load_feedback_events(Path('feedback-store/feedback.jsonl'))
print(format_metrics_report(compute_all_skill_metrics(events)))
"
```

## Output Schema

Each line of `feedback.jsonl` is a JSON object:

```json
{
  "event_id": "sha256-hash",
  "timestamp": "2026-04-05T10:00:00Z",
  "session_id": "uuid",
  "skill_id": "cpp-expert",
  "outcome": "correction",
  "confidence": 0.9,
  "correction_type": "rejection",
  "user_message_snippet": "不对，应该用...",
  "turns_to_feedback": 1,
  "ai_tools_used": ["Read", "Edit"],
  "dimension_hint": "accuracy"
}
```

## Integration

The generator auto-discovers `feedback-store/` under the target skill directory via `lib/common.py:load_source_paths()`. Correction hotspots inform which dimensions to prioritize for improvement.

## Related

- `improvement-generator` — consumes feedback.jsonl as `--source`
- `improvement-evaluator` — synthetic task evaluation (complementary signal)
- `autoloop-controller` — uses correction_rate plateau as termination condition
