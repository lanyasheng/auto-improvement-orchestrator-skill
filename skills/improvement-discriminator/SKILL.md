---
name: improvement-discriminator
description: "当需要对改进候选多人盲审打分、用 LLM 做语义评估、判断候选是否应被接受、或打分结果全是 hold 想知道为什么时使用。支持 --panel 多审阅者盲审和 --llm-judge 语义评估。不用于结构评估（用 improvement-learner）或门禁决策（用 improvement-gate）。"
license: MIT
triggers:
  - score candidate
  - evaluate improvement
  - multi-reviewer panel
  - LLM judge
  - 候选打分
  - 盲审
version: 0.1.0
author: OpenClaw Team
---

# Improvement Discriminator

Multi-signal scoring engine: heuristic rules + evaluator rubrics + LLM-as-Judge + multi-reviewer blind panel.

## When to Use

- 对改进候选打分和排序
- 运行多审阅者盲审（CONSENSUS/VERIFIED/DISPUTED 认知标签）
- 用 LLM-as-Judge 评估 4 个语义维度（clarity, specificity, consistency, safety）

## When NOT to Use

- **评估 skill 目录结构** → use `improvement-learner`
- **keep/revert/reject 决策** → use `improvement-gate`
- **执行文件变更** → use `improvement-executor`

## Scoring Modes

| Mode | Flag | Scoring |
|------|------|---------|
| Heuristic only | (default) | category bonus + source refs + risk penalty |
| + Evaluator | `--use-evaluator-evidence` | Heuristic 70% + evaluator 30% |
| + LLM Judge | `--llm-judge {claude,openai,mock}` | Heuristic 60% + LLM 40% |
| + Panel | `--panel` | 2+ reviewers independently, cognitive label decides |
| All combined | `--panel --llm-judge mock --use-evaluator-evidence` | Full |

<example>
正确用法: 多审阅者盲审 + LLM 语义打分
$ python3 scripts/score.py --input candidates.json --panel --llm-judge mock --output scored.json
→ 输出包含:
  panel_reviews: [{reviewer: "structural", score: 7.5}, {reviewer: "conservative", score: 5.0}]
  cognitive_label: "VERIFIED"  (2人同意)
  llm_verdict: {score: 0.78, decision: "conditional", dimensions: {clarity: 0.85, ...}}
</example>

<anti-example>
常见误解: --panel 和 --llm-judge 互斥
→ 错！两者可以同时使用。每个审阅者独立调用 LLM judge，得到独立的语义分数。
→ 如果只用 --panel 不加 --llm-judge，panel 只做启发式评分，不做语义评估。
</anti-example>

## CLI

```bash
# Basic scoring
python3 scripts/score.py --input candidates.json --output scored.json

# Full pipeline: panel + LLM judge
python3 scripts/score.py \
  --input candidates.json --panel --llm-judge mock --output scored.json
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Score | JSON: per-candidate scores, blockers, recommendations, judge_notes |
| Panel | JSON: panel_reviews[], cognitive_label, aggregated_score |
| LLM judge | JSON: llm_verdict (score, decision, dimensions, confidence) |

## Related Skills

- **improvement-generator**: Produces the candidates that this skill scores
- **improvement-gate**: Consumes scored candidates for keep/revert/reject
- **improvement-learner**: Structural evaluation (6-dim); discriminator focuses on semantic
- **benchmark-store**: Frozen benchmarks for regression checking
