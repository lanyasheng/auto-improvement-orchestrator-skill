---
name: improvement-generator
description: "当需要为目标 skill 生成改进候选、把上次失败信息注入下一轮生成、或分析历史记忆模式来避免重复失败时使用。支持 --trace 注入失败上下文。不用于打分（用 improvement-discriminator）或评估（用 improvement-learner）。"
license: MIT
triggers:
  - generate candidates
  - propose improvements
  - 生成候选
  - 改进建议
version: 0.1.0
author: OpenClaw Team
---

# Improvement Generator

Produces ranked improvement candidates from target analysis, feedback signals, and failure traces.

## When to Use

- 为目标 skill 生成结构化改进候选
- 把上次失败的 trace 注入下一轮（GEPA trace-aware）
- 根据 trace 自动降低上次失败类别的候选优先级

## When NOT to Use

- **给候选打分** → use `improvement-discriminator`
- **评估 skill 结构** → use `improvement-learner`
- **全流程** → use `improvement-orchestrator`

## Trace-Aware Generation

```
Previous failure on "accuracy" dimension
  → deprioritize candidates of the same category as the failed one
  → prioritize other dimensions' improvements instead
```

<example>
正确: 第一次失败后注入 trace 重试
$ python3 scripts/propose.py --target /path/to/skill --trace failure_trace.json --output candidates.json
→ 生成的候选会自动避开上次失败的 accuracy 维度策略
</example>

<anti-example>
错误: 失败后不注入 trace 直接重试
→ 没有 trace 信息，generator 无法降低失败类别的优先级，容易重复生成同类候选
→ 失败 ≥3 次的自动跳过逻辑在 improvement-learner 中，不在 generator
</anti-example>

## CLI

```bash
# Basic generation
python3 scripts/propose.py --target /path/to/skill --output candidates.json

# With failure trace (retry loop)
python3 scripts/propose.py --target /path/to/skill --trace failure.json --output candidates.json

# With memory/feedback sources
python3 scripts/propose.py --target /path/to/skill --source memory.json --output candidates.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Generate | JSON array of ranked candidates with category, risk_level, execution_plan |
| With trace | Same format, priorities adjusted based on failure analysis |

## Related Skills

- **improvement-discriminator**: Scores the candidates this skill produces
- **improvement-orchestrator**: Calls generator as stage 1
- **improvement-learner**: Provides evaluation data that informs candidate selection
