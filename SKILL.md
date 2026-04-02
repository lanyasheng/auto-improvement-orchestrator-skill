# Auto-Improvement Orchestrator

**统一入口 skill**:协调 Proposer / Critic / Executor / Gate 四角色,对 skill / macro / workflow 等对象进行自动化改进。

---

## 触发条件

当用户提到以下关键词时触发:
- "自动改进" / "auto-improve" / "self-improve"
- "优化 skill" / "优化 macro" / "优化 workflow"
- "提出改进建议" / "评估当前实现"
- "运行 critic" / "运行 evaluator"
- "回滚" / "rollback"(配合 Gate)

---

## 核心流程

```text
1. 识别 lane(skill / macro / browser-workflow)
2. 读取对应 references/ 文档
3. 按四角色流程执行:
   Proposer → Critic → Executor → Gate
4. 输出结论 + 证据 + 动作
```

---

## Lane 选择

| 用户请求包含 | Lane | Adapter | 状态 |
|-------------|------|---------|------|
| skill / 优化 skill | `generic-skill` | skill-adapter | ✅ 已落地 (Phase 1) |
| skill-evaluator 自身评估 | `skill-evaluator` | skill-evaluator-adapter | 🟡 规划中 (Phase 2) |
| macro / ainews / 新闻 | `macro` | macro-adapter | 📝 规划中 (Phase 2) |
| browser / selector / 抓取 | `browser-workflow` | browser-adapter | 📝 规划中 (Phase 3) |
| 其他 | `generic-skill` | skill-adapter | ✅ 已落地 (Phase 1) |

**说明**:
- `generic-skill` 是当前唯一可运行的 lane
- `skill-evaluator` / `macro` / `browser-workflow` 仍是规划,详见 `references/phases.md`

---

## 何时读取 References

| 需求 | 文件 |
|------|------|
| 架构设计 | `references/architecture.md` |
| Adapter 规格 | `references/adapters.md` |
| skill-evaluator 详细规格 | `references/skill-evaluator-adapter.md` |
| 质量门/回滚 | `references/guardrails.md` |
| 路线图 | `references/phases.md` |
| 完整端到端示例 | `references/end-to-end-demo.md` |

---

## 当前支持程度(v0.2 - Phase 1)

### 已可运行:`generic-skill` lane

当前版本已从 skeleton 推进到 **first runnable version**,可在本地真实跑通:

**Proposer** → **Critic** → **Executor** → **Gate** 四角色完整流程。

#### 各角色能力

| 角色 | 能力 | 状态 |
|------|------|------|
| Proposer | 读取目标路径 + feedback,输出结构化 candidate | ✅ |
| Critic | 规则 + Phase 1 evaluator evidence 混合打分 | ✅ |
| Executor | 低风险文档类修改(docs/reference/guardrail) | ✅ |
| Gate | keep/pending_promote/revert/reject 决策 | ✅ |

**详细说明**: 见 `references/end-to-end-demo.md`

---

## 持久化状态机(generic-skill lane)

所有 artifact 均为 machine-readable JSON,包含 `stage` / `status` / `next_step` / `next_owner` / `truth_anchor` 字段,支持控制面自动推进。

**详细结构**: 见 `references/end-to-end-demo.md#完整文件树执行后`

---

## 快速使用

```bash
# 1) propose
python scripts/propose_candidate.py \
  --target /path/to/skill \
  --source /path/to/demo.feedback.md

# 2) critic
python scripts/run_critic.py \
  --input <candidate.json> \
  --use-evaluator-evidence  # Phase 1 minimal evaluator evidence

# 3) executor
python scripts/run_executor.py \
  --input <ranking.json> \
  --candidate-id <candidate-id>

# 4) gate
python scripts/apply_gate.py \
  --ranking <ranking.json> \
  --execution <execution.json>

# 5) rollback(如需要)
python scripts/rollback.py --receipt <receipt.json> --execute
```

**详细示例**: 见 `references/end-to-end-demo.md`

---

## 约束

- 当前仅 `generic-skill` lane 可运行(Phase 1)
- `skill-evaluator` / `macro` / `browser-workflow` 仍是规划(Phase 2/3)
- 仅自动执行低风险文档类修改(docs/reference/guardrail)
- 默认保守 gate,优先可回退

---

## 仍在规划中的部分(Phase 2/3)

以下仍是**规划中**,不是当前版本能力:

### Phase 2(下一步)
- `skill-evaluator` full adapter(真实调用 CLI / benchmark / hidden tests)
- frozen benchmark / hidden tests / external regression
- human spot-check interface

### Phase 3(远期)
- `macro` lane 真正自动执行
- `browser-workflow` lane 真正自动执行
- 复杂 prompt / workflow / tests / code 级自动修改
- 控制面主动调度与多 run 并发仲裁

详见 `references/phases.md` 和 `references/skill-evaluator-adapter.md`。

---

## 下一步

**P1（Phase 2）**: 升级 Critic 从 rubric-assisted 到 full evaluator runtime
- 真实调用 `skill-evaluator` CLI
- 运行 frozen benchmark / hidden tests
- 接入 external regression callback

详见 `references/phases.md` 和 `references/skill-evaluator-adapter.md`。
