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
- 根据记忆模式避开已经失败过 ≥3 次的策略

## When NOT to Use

- **给候选打分** → use `improvement-discriminator`
- **评估 skill 结构** → use `improvement-learner`
- **全流程** → use `improvement-orchestrator`

## Trace-Aware Generation

```
Previous failure on "accuracy" dimension
  → prioritize accuracy-related improvements
  → skip strategies that failed ≥3 times on this dimension
```

<example>
正确: 第一次失败后注入 trace 重试
$ python3 scripts/propose.py --target /path/to/skill --trace failure_trace.json --output candidates.json
→ 生成的候选会自动避开上次失败的 accuracy 维度策略
</example>

<anti-example>
错误: 同一个维度失败 3 次后还继续重试
→ generator 会自动跳过失败 ≥3 次的策略，返回 None。此时应换维度或停止
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
