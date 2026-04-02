---
name: improvement-executor
version: 0.2.0
description: "Executes approved improvement candidates with 4 action types (append/replace/insert_before/update_yaml). Automatic backup before every change and full rollback support via receipts. Not for scoring (use improvement-discriminator) or gate decisions (use improvement-gate)."
author: OpenClaw Team
license: MIT
tags: [executor, apply, rollback, safe-execution, backup]
triggers:
  - apply improvement
  - execute candidate
  - rollback change
---

# Improvement Executor

Applies accepted candidates with automatic backup and rollback capability.

## When to Use

- Apply an approved improvement candidate to its target file
- Rollback a previously applied change using a receipt
- Preview changes with dry-run before applying

## When NOT to Use

- **Scoring candidates** → use `improvement-discriminator`
- **Gate validation** → use `improvement-gate`
- **Full pipeline orchestration** → use `improvement-orchestrator`

## 4 Action Types

| Action | Description |
|--------|------------|
| `append_markdown_section` | Append a new section to the end of a Markdown file |
| `replace_markdown_section` | Replace an existing section by heading match |
| `insert_before_section` | Insert content before a matched section heading |
| `update_yaml_frontmatter` | Merge fields into YAML frontmatter |

## CLI

```bash
# Apply a candidate
python3 scripts/execute.py \
  --candidate candidate.json \
  --state-root /path/to/state \
  --out result.json

# Rollback using receipt
python3 scripts/rollback.py \
  --receipt receipt.json

# Dry-run (preview only)
python3 scripts/rollback.py \
  --receipt receipt.json \
  --dry-run
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Execute | JSON result with rollback_pointer (original content, backup path) |
| Rollback | Restored file + confirmation JSON |

## Related Skills

- **improvement-discriminator**: Scores candidates before execution
- **improvement-gate**: Validates execution results after this skill runs
- **improvement-orchestrator**: Calls executor as stage 4 in the pipeline
