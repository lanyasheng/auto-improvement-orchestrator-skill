---
name: benchmark-store
version: 0.1.0
description: Manages frozen benchmarks, hidden tests, evaluation standards, and historical benchmark data for the improvement pipeline.
author: OpenClaw Team
license: MIT
tags: [benchmark, frozen-tests, hidden-tests, evaluation, data-store]
---

# Benchmark Store

Central store for frozen benchmarks, hidden test suites, and historical evaluation data.

## When to Use
- Manage frozen benchmark test cases for skill evaluation
- Track Pareto-front evolution across improvement runs

## CLI
```bash
python3 scripts/benchmark_db.py --init --db benchmarks.db
python3 scripts/benchmark_db.py --compare --skill /path/to/skill --category general
```
