---
name: improvement-gate
description: "当执行完变更需要验证是否应保留、候选被标记 pending 需要人工审批、或想查看待审队列时使用。6 层机械门禁: Schema→Compile→Lint→Regression→Review→HumanReview，任一层失败即拒绝。不用于打分（用 improvement-discriminator）或执行变更（用 improvement-executor）。"
license: MIT
triggers:
  - quality gate
  - validate candidate
  - gate check
  - human review
  - 门禁验证
  - 待审批
---

# Improvement Gate

6-layer mechanical quality gate: any layer fail = reject.

## When to Use

- 验证已执行的候选是否应保留
- 管理人工审核队列（高风险候选）
- 查看/完成待审批项

## When NOT to Use

- **给候选打分** → use `improvement-discriminator`
- **执行文件变更** → use `improvement-executor`
- **评估 skill 结构** → use `improvement-learner`

## 6-Layer Gate

| Layer | Gate | Pass Condition |
|-------|------|---------------|
| 1 | **SchemaGate** | Execution result has valid JSON structure |
| 2 | **CompileGate** | Target file is syntactically valid after change |
| 3 | **LintGate** | No new lint warnings introduced |
| 4 | **RegressionGate** | No Pareto dimension regressed beyond 5% |
| 5 | **ReviewGate** | Multi-reviewer consensus is not DISPUTED+reject |
| 6 | **HumanReviewGate** | High-risk candidates require manual approval |

## CLI

```bash
# Run gate validation
python3 scripts/gate.py --state-root /path/to/state

# List pending human reviews
python3 scripts/review.py --list --state-root /path/to/state

# Complete a review
python3 scripts/review.py --complete REVIEW_ID --decision approve --comment "LGTM"
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Gate check | JSON receipt: gate_decision, per-layer results |
| Review list | JSON array of pending reviews |
| Review complete | Updated receipt with human decision |

## Related Skills

- **improvement-discriminator**: Scores candidates before gate
- **improvement-executor**: Applies changes before gate validates
- **improvement-orchestrator**: Calls gate as stage 3
- **benchmark-store**: Pareto front data for RegressionGate
