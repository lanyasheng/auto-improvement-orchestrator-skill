---
name: improvement-gate
version: 0.1.0
description: Quality gate that decides keep/pending/revert/reject for executed candidates based on risk, category, and execution outcome.
author: OpenClaw Team
license: MIT
tags: [gate, quality, decision, keep, revert, reject]
---

# Improvement Gate

Conservative gate: only auto-keeps low-risk docs/reference/guardrail edits; everything else goes to pending or reject.

## When to Use
- Decide whether to keep, pend, revert, or reject an executed candidate
- Run mechanical validation (5-layer) before the decision


## When NOT to Use

- [Define exclusion conditions here]

## CLI
```bash
python3 scripts/gate.py --execution result.json --out receipt.json
```
