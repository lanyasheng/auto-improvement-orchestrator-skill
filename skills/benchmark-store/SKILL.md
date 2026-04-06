---
name: benchmark-store
description: "当需要初始化基准数据库、对比 skill 评分与历史基线、查看 Pareto front 是否有维度回退、或查阅质量分级标准时使用。不用于给候选打分（用 improvement-discriminator）或自动改进（用 improvement-learner）。"
license: MIT
triggers:
  - benchmark data
  - frozen tests
  - pareto front
  - evaluation standards
  - 基准数据
  - 质量分级
version: 0.1.0
author: OpenClaw Team
---

# Benchmark Store

Frozen benchmarks, hidden tests, Pareto front, and evaluation standards.

## When to Use

- 初始化或查询基准数据库
- 对比 skill 评分与冻结基线
- 检查 Pareto front（任何维度回退 >5% 即拒绝）
- 查阅质量分级标准（POWERFUL/SOLID/GENERIC/WEAK）

## When NOT to Use

- **给候选打分** → use `improvement-discriminator`
- **自动改进** → use `improvement-learner`
- **全流程** → use `improvement-orchestrator`

## Quality Tiers

| Tier | Score | Ship? |
|------|-------|-------|
| POWERFUL ⭐ | ≥ 85% | Marketplace ready |
| SOLID | 70–84% | GitHub |
| GENERIC | 55–69% | Needs iteration |
| WEAK | < 55% | Reject or rewrite |

## Pareto Front

```python
ParetoFront.check_regression(new_scores) → {"regressed": bool, "regressions": [...]}
# 5% tolerance — minor fluctuations allowed
```

<example>
正确: 检查 Pareto front 是否有回退
$ python3 -c "from lib.pareto import ParetoFront; pf = ParetoFront('state/pareto.json'); print(pf.check_regression({'accuracy': 0.9, 'coverage': 0.8}))"
→ {"regressed": false, "regressions": []}  # 无回退，可以接受
</example>

<anti-example>
错误: 用 benchmark-store 给候选打分
→ benchmark-store 只存数据，打分用 improvement-discriminator
</anti-example>

## CLI

```bash
# List benchmarks
python3 scripts/benchmark_db.py --action list --db-path benchmarks.db

# Compare skill against baselines
python3 scripts/benchmark_db.py --action compare --skill-path /path/to/skill --category general --db-path benchmarks.db

# Add a benchmark
python3 scripts/benchmark_db.py --action add --category general --test-name "test1" --db-path benchmarks.db
```

## Output Artifacts

| Request | Deliverable |
|---------|------------|
| Init | SQLite database with schema |
| Compare | JSON comparison with per-dimension delta |
| Pareto check | JSON with regressed flag and details |

## Related Skills

- **improvement-learner**: Imports ParetoFront for self-improvement loop
- **improvement-gate**: RegressionGate uses Pareto data
- **improvement-discriminator**: References evaluation standards

## Data Files

- `data/evaluation-standards.md` — Quality tiers, dimensions, weights (v2.0.0)
- `data/fixtures/` — Frozen test fixtures
