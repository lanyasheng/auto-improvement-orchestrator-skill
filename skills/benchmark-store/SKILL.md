---
name: benchmark-store
category: tool
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

Frozen benchmarks, hidden tests, Pareto front, and evaluation standards for the skill improvement pipeline. Provides immutable test suites with SHA-256 integrity verification, encrypted hidden tests to prevent overfitting, and a SQLite-backed benchmark database.

## When to Use / NOT to Use

- Init/query benchmark database, compare skill scores against frozen baselines, check Pareto front for regression (>5% drop = reject), look up quality tiers and per-dimension weights
- **NOT** for scoring candidates (improvement-discriminator), structural evaluation (improvement-learner), or full loop (improvement-orchestrator)

## CLI

```
python3 scripts/benchmark_db.py --db-path benchmarks.db \
  --action {add,compare,leaderboard,list,delete} \
  [--category CAT] [--test-name NAME] [--input INPUT] \
  [--expected-output OUT] [--metrics JSON] [--skill-path PATH]
```

`--db-path`: SQLite path (default: benchmarks.db). `--action`: required. `--category`: required for add/compare/leaderboard/delete. `--test-name`: required for add/delete. `--input`: required for add. `--expected-output`, `--metrics`: optional for add. `--skill-path`: required for compare (compare also needs a Python API evaluator callable).

## Quality Tiers (from `data/evaluation-standards.md` v2.0.0)

Composite: `accuracy*0.3 + coverage*0.2 + reliability*0.2 + efficiency*0.15 + security*0.15`

| Tier | Score | Ship Policy |
|------|-------|-------------|
| POWERFUL | >= 85% | Marketplace ready |
| SOLID | 70-84% | GitHub publishable |
| GENERIC | 55-69% | Internal, needs iteration |
| WEAK | < 55% | Reject or rewrite |

## Per-Dimension Weight Table

| Dimension | Weight | Threshold | Target |
|-----------|--------|-----------|--------|
| Accuracy (SKILL.md quality, 12 checks) | 0.30 | 0.80 | 0.95 |
| Coverage (structural completeness) | 0.20 | 0.70 | 0.90 |
| Reliability (execution consistency) | 0.20 | 0.60 | 0.85 |
| Efficiency (time performance) | 0.15 | 0.50 | 0.80 |
| Security (safety checks) | 0.15 | 0.50 | 0.80 |

## Frozen Benchmark Suites

Immutable test suites with checksum verification. Tampering detected via `suite.verify()`.

```python
from interfaces.frozen_benchmark import FrozenBenchmark, STANDARD_BENCHMARK_SUITE
fb = FrozenBenchmark(STANDARD_BENCHMARK_SUITE)  # ValueError if integrity fails
report = fb.run(evaluator)  # -> {summary: {pass_rate, avg_score, weighted_score}, by_category, results}
```

Standard suite: functionality (difficulty 1), reliability (difficulty 2), efficiency (difficulty 3).

## Hidden Tests

Encrypted test cases that stay hidden until execution. Prevents overfitting.
Types: functional, edge_case, adversarial, security, performance, distribution.
Visibility boundaries: evaluator / proposer / both.

```python
from interfaces.hidden_tests import HiddenTestSuite, create_hidden_test, TestType
suite = HiddenTestSuite(suite_id="s1", name="Tests", version="1.0.0")
suite.unlock("password")
results = suite.run_all(skill)  # -> {summary: {total_tests, passed, pass_rate, avg_score}, by_type}
```

## Pareto Front

```python
from lib.pareto import ParetoFront
pf = ParetoFront("state/pareto.json")
pf.check_regression({"accuracy": 0.9, "coverage": 0.8})
# -> {"regressed": false, "regressions": []}  # 5% tolerance
```

<example>
$ python3 scripts/benchmark_db.py --db-path bench.db --action add --category tool-type \
    --test-name "file-search" --input "Search for error in .py files"
$ python3 scripts/benchmark_db.py --db-path bench.db --action leaderboard --category tool-type
$ python3 scripts/benchmark_db.py --db-path bench.db --action list
</example>

<anti-example>
benchmark-store stores baselines and runs frozen tests. To score improvement candidates, use improvement-discriminator.
</anti-example>

## Output Artifacts

| Request | Deliverable |
|---------|-------------|
| `--action list` | Benchmarks grouped by category |
| `--action leaderboard` | Top-N skills by best score |
| Frozen benchmark `run()` | JSON: summary, by_category, per-case results, verified flag |
| Hidden test `run_all()` | JSON: summary, by_type stats, per-test scores |
| Pareto `check_regression()` | `{regressed: bool, regressions: [...]}` |

## Data Files

`data/evaluation-standards.md` (v2.0.0), `data/fixtures/`, `interfaces/frozen_benchmark.py`, `interfaces/hidden_tests.py`

## Related Skills

- **improvement-learner** -- imports ParetoFront | **improvement-gate** -- RegressionGate uses Pareto
- **improvement-discriminator** -- references evaluation standards for scoring
