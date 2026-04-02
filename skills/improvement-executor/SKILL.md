---
name: improvement-executor
description: "当需要把已批准的改进候选应用到目标文件、回滚之前的变更、或预览变更效果时使用。支持 4 种 action（append/replace/insert_before/update_yaml），每次变更前自动备份。不用于打分（用 improvement-discriminator）或门禁验证（用 improvement-gate）。"
license: MIT
triggers:
  - apply improvement
  - execute candidate
  - rollback change
  - 执行变更
  - 回滚
---

# Improvement Executor

Applies accepted candidates with automatic backup and rollback.

## When to Use

- 把已批准的改进候选应用到目标文件
- 回滚之前的变更（通过 receipt）
- 用 `--dry-run` 预览变更

## When NOT to Use

- **给候选打分** → use `improvement-discriminator`
- **门禁验证** → use `improvement-gate`
- **全流程编排** → use `improvement-orchestrator`

## 4 Action Types

| Action | Description |
|--------|------------|
| `append_markdown_section` | Append a new section to the end |
| `replace_markdown_section` | Replace an existing section by heading match |
| `insert_before_section` | Insert content before a matched heading |
| `update_yaml_frontmatter` | Merge fields into YAML frontmatter |

## CLI

```bash
# Apply
python3 scripts/execute.py --candidate candidate.json --state-root /path/to/state --out result.json

# Rollback
python3 scripts/rollback.py --receipt receipt.json

# Dry-run
python3 scripts/rollback.py --receipt receipt.json --dry-run
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Execute | JSON with rollback_pointer (original content, backup path) |
| Rollback | Restored file + confirmation JSON |

## Related Skills

- **improvement-discriminator**: Scores candidates before execution
- **improvement-gate**: Validates results after execution
- **improvement-orchestrator**: Calls executor as stage 4
