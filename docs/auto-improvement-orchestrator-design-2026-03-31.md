# Auto-Improvement Orchestrator 设计稿

**版本**: v0.1 (Design Draft)  
**日期**: 2026-03-31  
**状态**: 设计稿 + Skeleton，非生产就绪

---

## 1. 为什么不能做"大杂烩 skill"

### 问题
之前的讨论中曾考虑做一个"超级 skill"，把所有 autoresearch / skill-evaluator / producer-critic 逻辑塞进一个超长 SKILL.md。这种设计有严重问题：

1. **不可维护**：SKILL.md 超过 500 行后，人类和 AI 都难以快速定位逻辑
2. **违反 skill-creator 原则**：官方 skill 规范要求 SKILL.md 保持简洁，详细内容拆到 references/
3. **难以测试**：大杂烩逻辑无法分模块验证
4. **复用困难**：其他 skill 无法单独引用其中某个子能力

### 解决方案
采用**统一入口 + 模块化 references**架构：
- `SKILL.md` 只保留触发条件、路由逻辑、核心流程概述（<200 行）
- 详细设计拆到 `references/` 目录
- 执行逻辑下沉到 `scripts/` 可运行骨架

---

## 2. 为什么要用统一入口 + adapter

### 核心洞察
autoresearch / skill-evaluator / macro-ainews 本质上共享同一套**改进循环**：

```
发现改进机会 → 提出候选方案 → 评估/批评 → 执行修改 → 质量门验证 → 回滚/接受
```

但它们操作的对象不同：
- **skill-evaluator**: 评估和修改 skill 文件
- **macro/ainews**: 调整新闻源、筛选规则、推送策略
- **browser workflow**: 优化 selector、重试策略、反爬配置
- **generic skill**: 任意 OpenClaw skill

### Adapter 模式价值
通过 adapter 层抽象差异，实现：
1. **统一状态机**：candidate → ranking → pending → veto → rollback
2. **统一质量门**：frozen benchmark / hidden tests / human spot-check
3. **统一回滚机制**：git-based rollback for all object types

---

## 3. 四角色流程：Proposer / Critic / Executor / Gate

### 角色定义

| 角色 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Proposer** | 发现改进机会，提出候选方案 | 当前状态 + 历史错误日志 | candidate 列表（含优先级） |
| **Critic** | 评估候选方案的风险/收益 | candidate 列表 | 评分 + 风险标记 + 推荐排序 |
| **Executor** | 执行被批准的修改 | 批准的 candidate | 修改后的文件 + 测试报告 |
| **Gate** | 质量门验证，决定接受/回滚 | 修改结果 + 测试报告 | accept / rollback 决策 |

### 流程状态机

```
[Proposer] → candidate_pool
     ↓
[Critic] → ranked_candidates
     ↓
[Gate: Pre-Check] → approved_batch
     ↓
[Executor] → modified_artifacts + test_results
     ↓
[Gate: Post-Check] → accept / rollback
```

### 关键设计点

1. **Proposer 不直接修改**：只提建议，避免"边写边改"导致的不可追溯
2. **Critic 独立于 Executor**：避免"自己评自己"
3. **Gate 有最终否决权**：即使 Executor 认为成功，Gate 也可回滚
4. **状态持久化**：每步写入 status file，支持中断恢复

---

## 4. 复用现有能力

### 4.1 skill-evaluator

**复用内容**：
- 评估维度（correctness / completeness / clarity / safety）
- 红队测试框架
- benchmark 设计思路

**边界**：
- Phase 1：skill-evaluator 作为**外部 judge**，不直接集成
- Phase 2：再做 evaluator adapter，支持统一调用
- **不自举**：第一天不依赖 skill-evaluator 自动修改自身

### 4.2 self-improvement

**复用内容**：
- 错误日志格式
- 教训归档结构
- 触发条件（失败/纠正/缺失能力）

**约束**：
- **最大 1 learning log per user message**：避免链式自改
- 需要 human spot-check 确认教训是否合理

### 4.3 autoresearch-macro 状态机

**复用内容**：
- candidate / ranking / pending / veto / rollback 状态定义
- 状态持久化文件格式
- 回滚机制（git-based）

**扩展**：
- 将 macro 的状态机泛化到 skill / browser workflow

---

## 5. 第一版支持的 Lane

### Lane 定义
Lane = 改进对象类型 + 对应的 adapter

### Phase 1 支持

| Lane | 对象 | Adapter | 状态 |
|------|------|---------|------|
| `generic-skill` | 任意 OpenClaw skill | skill-adapter | 规划 |
| `skill-evaluator` | skill-evaluator 自身 | skill-adapter (frozen benchmark) | 规划 |
| `macro` | macro/ainews 配置 | macro-adapter | 规划 |
| `browser-workflow` | browser ops 配置 | browser-adapter | 规划 |

### Lane 选择逻辑

```python
def select_lane(user_request):
    if "skill" in request and "eval" in request:
        return "skill-evaluator"
    elif "macro" in request or "ainews" in request:
        return "macro"
    elif "browser" in request or "selector" in request:
        return "browser-workflow"
    else:
        return "generic-skill"
```

---

## 6. 明确不做（避免 NIH）

### 不重写现有评估平台
- ❌ 不重写 LangWatch / Braintrust / DeepEval
- ❌ 不自造完整 judge 平台
- ✅ 复用现有 eval / benchmark / red-team 能力

### 不自造代码修改引擎
- ❌ 不从零实现代码 diff/patch 引擎
- ✅ 复用 git / edit tool / coding agent

### 不追求全自动
- ❌ 不声称"自动修改一切"
- ✅ Phase 1 需要 human spot-check
- ✅ Gate 可配置为"需人工确认"

### 不重复造轮子
- ❌ 不重写 skill-evaluator 已有逻辑
- ❌ 不重写 self-improvement 日志系统
- ✅ 通过 adapter 调用现有能力

---

## 7. Phase 路线图

### Phase 1: 设计验证 (2026-03-31 ~ 2026-04-07)
- [x] 设计稿 + skeleton 创建
- [ ] 实现 `generic-skill` lane 的 Proposer stub
- [ ] 实现 Gate 的 git-based rollback 原型
- [ ] 手动跑通 1 个完整流程（人工执行各步骤）

**成功标准**：能手动演示"提出候选 → 评估 → 执行 → 回滚"全流程

### Phase 2: 单 Lane 自动化 (2026-04-08 ~ 2026-04-21)
- [ ] 实现 `skill-evaluator` adapter
- [ ] 集成 frozen benchmark / hidden tests
- [ ] 实现 Critic 自动评分
- [ ] Gate 支持自动 accept（低风险修改）

**成功标准**：skill-evaluator 能自动提出并执行低风险改进（如文档修正）

### Phase 3: 多 Lane 扩展 (2026-04-22 ~)
- [ ] 实现 `macro` adapter
- [ ] 实现 `browser-workflow` adapter
- [ ] 支持并发多 candidate 评估
- [ ] 集成 external regression tests

**成功标准**：至少 3 个 lane 可稳定运行，支持每周自动改进报告

---

## 8. skill-evaluator 边界详细说明

### 为什么不能第一天完全自举

1. **评估标准未冻结**：skill-evaluator 自身的 benchmark 还在演进
2. **循环依赖风险**：用 skill-evaluator 改进 skill-evaluator 需要外部基准
3. **人类校准需求**：需要 human spot-check 确认评估维度是否合理

### Phase 1 接入方式

```
auto-improvement-orchestrator
    ↓ (调用)
skill-evaluator (作为外部 judge)
    ↓ (输出)
评估报告 → Gate 决策
```

**关键**：skill-evaluator 此时是"被调用工具"，不是"自举系统"

### Phase 2 Evaluator Adapter

```python
class EvaluatorAdapter:
    def run_benchmark(self, skill_path):
        # 运行 frozen benchmark
        pass
    
    def run_hidden_tests(self, skill_path):
        # 运行 hidden tests（不暴露给 Proposer）
        pass
    
    def external_regression(self, skill_path):
        # 调用外部回归测试
        pass
```

### 需要的保障

| 保障类型 | 说明 | 实现方式 |
|---------|------|---------|
| Frozen Benchmark | 不随 skill 变更而变化的测试集 | 独立 repo / 只读快照 |
| Hidden Tests | Proposer 看不到的测试（防止过拟合） | 加密 / 运行时注入 |
| External Regression | 第三方验证 | 调用现有 CI / 外部 API |
| Human Spot-Check | 人工抽查 | Gate 配置 + Discord 通知 |

---

## 9. Producer-Critic / GAN-like 利用方式

### 借鉴的是什么

**借鉴**：角色分工（Generator → Discriminator）  
**不借鉴**：零和博弈 / 对抗训练 / 梯度更新

### 推荐结构

```
Proposer (Generator) → 提出尽可能多的候选方案
       ↓
Critic (Discriminator) → 筛选出真正有价值的方案
       ↓
Executor → 执行通过的方案
       ↓
Gate → 最终质量门
```

### 与 GAN 的区别

| GAN | Auto-Improvement Orchestrator |
|-----|------------------------------|
| 连续参数空间 | 离散决策空间（文件修改） |
| 梯度反向传播 | 基于规则的反馈（评分/标记） |
| 零和博弈 | 共同目标（改进质量） |
| 自动收敛 | 需要 Gate 人工/自动验收 |

### 为什么不用真正 GAN

1. **代码修改不可微**：无法计算梯度
2. **评估成本高**：跑一次测试可能需要秒级/分钟级
3. **需要可解释性**：人类需要理解"为什么这个修改好"

---

## 10. 文件结构

```
skills/auto-improvement-orchestrator/
├── SKILL.md                    # 统一入口（<200 行）
├── references/
│   ├── architecture.md         # 四角色详细设计
│   ├── adapters.md             # 各 lane adapter 规格
│   ├── guardrails.md           # 质量门/回滚机制
│   └── phases.md               # Phase 路线图
└── scripts/
    ├── propose_candidate.py    # Proposer stub
    ├── run_critic.py           # Critic stub
    ├── run_executor.py         # Executor stub
    └── apply_gate.py           # Gate stub
```

---

## 11. 验证清单

- [x] 设计稿创建
- [x] SKILL.md skeleton
- [x] references/ 骨架
- [x] scripts/ stub
- [ ] 手动跑通 1 个完整流程
- [ ] 编写 Phase 1 测试用例

---

**备注**：本设计稿是 v0.1，后续根据实际落地情况迭代更新。
