# Auto-Improvement Orchestrator Skill

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

Automated evaluation and self-improvement pipeline for AI Agent Skills. Evaluates any skill's quality across 6 structural + 4 semantic dimensions, generates improvement candidates, validates through multi-reviewer blind panel and 6-layer mechanical gates, and auto-applies improvements with Pareto front regression protection.

### Why Choose This?

#### The Problem

Most AI skill ecosystems have no quality control. Skills are published without evaluation, improvements are manual, and there's no way to prevent regressions. Existing approaches either:
- **Rely on manual review** — doesn't scale, inconsistent standards
- **Use single-dimension scoring** — misses structural vs semantic gaps
- **Have no regression protection** — fixing one thing breaks another
- **Generate cosmetic improvements** — template READMEs, `assert True` tests

#### What We Do Differently

| Problem | Existing Solutions | Our Approach |
|---------|-------------------|-------------|
| Single evaluator bias | One reviewer scores | **Multi-reviewer blind panel** with cognitive labels (CONSENSUS/VERIFIED/DISPUTED) |
| Rule-only or LLM-only | Pick one | **Blended scoring**: heuristic 60% + LLM-as-Judge 40% (configurable) |
| No regression guard | Accept if score improves | **Pareto front**: reject if ANY dimension regresses >5% |
| Failed retries waste context | Same prompt, same failure | **Ralph Wiggum**: inject failure trace into next attempt |
| Pure-text skills penalized | Require tests/README | **Fair evaluation**: reliability=1.0 for skills without scripts |
| No quality standard | Ad-hoc checks | **15-point accuracy** from skill-creator P0 spec + industry patterns |
| No memory across runs | Start fresh every time | **3-layer memory**: HOT/WARM/COLD with pattern matching |

#### Compared to Alternatives

| Feature | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | **Ours** |
|---------|-------------------|--------------------------|---------|
| Evaluation | External SaaS (Tessl) | None | **Built-in 6+4 dim** |
| Self-improvement | None | None | **Karpathy loop** |
| Multi-reviewer | None | None | **Blind panel** |
| Regression guard | None | None | **Pareto front** |
| LLM-as-Judge | None | None | **Claude/OpenAI/Mock** |
| Mechanical gate | 8-point checklist | None | **6-layer gate** |
| Tests | evals.json | 58 files | **289 pytest** |
| Memory | None | None | **HOT/WARM/COLD** |

### Architecture

```
User → orchestrator → generator (propose candidates)
                    → discriminator (multi-reviewer + LLM Judge)
                    → gate (6-layer: Schema→Compile→Lint→Regression→Review→Human)
                    → executor (apply + backup/rollback)
                    → learner (Karpathy loop + 3-layer memory)
                    ↻ Ralph Wiggum: fail → inject trace → retry (max 3)
```

### 7 Skills

| Skill | Type | Role |
|-------|------|------|
| **improvement-orchestrator** | Orchestration | Full pipeline dispatch + Ralph Wiggum retry |
| **improvement-generator** | Learning | Analyze target + feedback + failure trace → candidates |
| **improvement-discriminator** | Review | Multi-reviewer blind panel + LLM-as-Judge 4-dim semantic |
| **improvement-executor** | Tool | 4 action types + automatic backup + rollback |
| **improvement-gate** | Rule | 6-layer mechanical gate + human review queue |
| **benchmark-store** | Knowledge | Frozen benchmarks + Pareto front + quality tiers |
| **improvement-learner** | Learning | 6-dim evaluation + Karpathy loop + HOT/WARM/COLD memory |

### Quick Start

```bash
git clone https://github.com/lanyasheng/auto-improvement-orchestrator-skill.git
cd auto-improvement-orchestrator-skill
pip install -r requirements.txt
```

**Evaluate a skill:**
```bash
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/skill --max-iterations 1
```

**Self-improvement loop:**
```bash
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/skill --max-iterations 5 --memory-dir /tmp/memory
```

**Multi-reviewer scoring:**
```bash
python3 skills/improvement-discriminator/scripts/score.py \
  --input candidates.json --panel --llm-judge mock --output scored.json
```

**Full pipeline:**
```bash
python3 skills/improvement-orchestrator/scripts/orchestrate.py \
  --target /path/to/skill --state-root /tmp/state --max-retries 3 --out result.json
```

### Accuracy Checks (15 items, v2.0)

| # | Check | Source |
|---|-------|--------|
| 1 | YAML frontmatter exists | Basic |
| 2 | `name:` field | skill-creator |
| 3 | `description:` field | skill-creator |
| 4 | Description >40 chars with trigger keywords | Quality pattern |
| 5 | **Symptom-driven description ("use when...")** | **skill-creator P0** |
| 6 | When to Use section | Quality pattern |
| 7 | When NOT to Use section | Quality pattern |
| 8 | Code examples (```) | Quality pattern |
| 9 | Usage/CLI section | Quality pattern |
| 10 | **Few-shot examples (`<example>`/`<anti-example>`)** | **skill-creator P0** |
| 11 | No vague language (etc./and so on) | Quality pattern |
| 12 | Minimum length (≥15 lines) | Basic |
| 13 | Related Skills section | Quality pattern |
| 14 | Output Artifacts section | Quality pattern |
| 15 | **Atomicity (no @skill/references/ path coupling)** | **skill-creator P0** |

### Quality Tiers

| Tier | Score | Meaning |
|------|-------|---------|
| **POWERFUL** ⭐ | ≥ 85% | Marketplace ready |
| **SOLID** | 70–84% | Publishable to GitHub |
| **GENERIC** | 55–69% | Needs iteration |
| **WEAK** | < 55% | Reject or rewrite |

### Install Globally

```bash
# Claude Code
for skill in skills/*/; do
  rsync -a --exclude='__pycache__' "$skill" ~/.claude/skills/$(basename "$skill")/
done
ln -sfn ~/.claude/skills/_auto-improvement-lib/lib ~/.claude/lib

# OpenClaw
for skill in skills/*/; do
  rsync -a --exclude='__pycache__' "$skill" ~/.openclaw/skills/$(basename "$skill")/
done
cp -r lib/ ~/.openclaw/lib/
```

### Tests

```bash
python3 -m pytest skills/ -v           # All 289 tests
python3 -m pytest skills/improvement-learner/tests/ -v  # Single skill
```

### Design References

| Source | Pattern Adopted |
|--------|----------------|
| [Karpathy autoresearch](https://github.com/karpathy) | evaluate→modify→re-evaluate→keep/revert loop |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 10 quality patterns, POWERFUL/SOLID/GENERIC/WEAK tiers |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | plugin.json standard |
| GEPA (ICLR 2026) | Trace-aware feedback (failure injection into next round) |
| SoK (2025) | Curated > auto-generated skills |
| Princeton/ETH contextual drag | Context cleanup to prevent 10-20% performance drops |

---

<a name="中文"></a>

## 中文

AI Agent Skill 自动评估与自改进管线。评估任意 skill 的质量（6 维结构 + 4 维语义），生成改进候选，通过多审阅者盲审和 6 层机械门禁验证，自动应用改进并用 Pareto front 防止任何维度回退。

### 为什么选择我们？

#### 现有方案的问题

大多数 AI skill 生态没有质量控制。Skill 发布无评估、改进靠手动、回退无防护。现有方案要么：
- **依赖人工审查** — 不可扩展，标准不一致
- **单维度打分** — 看不到结构 vs 语义的差距
- **无回退保护** — 修了 A 坏了 B
- **生成表面改进** — 模板 README、`assert True` 测试

#### 我们的差异化

| 问题 | 现有方案 | 我们的做法 |
|------|---------|-----------|
| 单一评审偏差 | 一个人打分 | **多审阅者盲审**，CONSENSUS/VERIFIED/DISPUTED 认知标签 |
| 规则 or LLM 二选一 | 只用一种 | **混合评分**: 启发式 60% + LLM-as-Judge 40%（可配置） |
| 无回退防护 | 分数涨了就接受 | **Pareto front**: 任何维度回退 >5% 即拒绝 |
| 失败重试浪费 | 同样的 prompt 同样的错 | **Ralph Wiggum**: 把失败 trace 注入下一轮 |
| 惩罚纯文本 skill | 要求 tests/README | **公平评估**: 无 scripts 的 skill reliability=1.0 |
| 无质量标准 | 随意检查 | **15 项 accuracy**: 来自 skill-creator P0 规范 + 业界模式 |
| 跨次运行无记忆 | 每次从零开始 | **三层记忆**: HOT/WARM/COLD，模式匹配 |

#### 与市面同类对比

| 能力 | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | [everything-claude-code](https://github.com/affaan-m/everything-claude-code) | **我们** |
|------|-------------------|--------------------------|---------|
| 评估 | 外部 SaaS (Tessl) | 无 | **内置 6+4 维** |
| 自改进 | 无 | 无 | **Karpathy 循环** |
| 多审阅者 | 无 | 无 | **盲审面板** |
| 回退防护 | 无 | 无 | **Pareto front** |
| LLM 评审 | 无 | 无 | **Claude/OpenAI/Mock** |
| 机械门禁 | 8 点检查 | 无 | **6 层门禁** |
| 测试 | evals.json | 58 文件 | **289 个 pytest** |
| 记忆 | 无 | 无 | **HOT/WARM/COLD** |

### 架构

```
用户 → orchestrator → generator (候选生成)
                    → discriminator (多审阅者盲审 + LLM Judge)
                    → gate (6 层门禁: Schema→Compile→Lint→Regression→Review→Human)
                    → executor (变更执行 + 备份/回滚)
                    → learner (Karpathy 循环 + 三层记忆)
                    ↻ Ralph Wiggum: 失败 → 注入 trace → 重试 (max 3)
```

### 7 个 Skill

| Skill | 类型 | 职责 |
|-------|------|------|
| **improvement-orchestrator** | 编排 | 全流程调度 + Ralph Wiggum 重试循环 |
| **improvement-generator** | 学习 | 分析目标 + 反馈 + 失败 trace → 生成候选 |
| **improvement-discriminator** | 审查 | 多审阅者盲审 + LLM-as-Judge 4 维语义 + 混合评分 |
| **improvement-executor** | 工具 | 4 种 action 类型 + 自动备份 + 回滚 |
| **improvement-gate** | 规则 | 6 层机械门禁 + 人工审核队列 |
| **benchmark-store** | 知识 | 冻结基准 + Pareto front + 质量分级标准 |
| **improvement-learner** | 学习 | 6 维评估 + Karpathy 循环 + HOT/WARM/COLD 记忆 |

### 快速开始

```bash
git clone https://github.com/lanyasheng/auto-improvement-orchestrator-skill.git
cd auto-improvement-orchestrator-skill
pip install -r requirements.txt
```

**评估一个 skill:**
```bash
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/skill --max-iterations 1
```

**自改进循环:**
```bash
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/skill --max-iterations 5 --memory-dir /tmp/memory
```

**多审阅者打分:**
```bash
python3 skills/improvement-discriminator/scripts/score.py \
  --input candidates.json --panel --llm-judge mock --output scored.json
```

**全流程编排:**
```bash
python3 skills/improvement-orchestrator/scripts/orchestrate.py \
  --target /path/to/skill --state-root /tmp/state --max-retries 3 --out result.json
```

### Accuracy 15 项检查（v2.0）

| # | 检查项 | 来源 |
|---|--------|------|
| 1 | YAML frontmatter 存在 | 基础 |
| 2 | name: 字段 | skill-creator |
| 3 | description: 字段 | skill-creator |
| 4 | description > 40 字符（含触发关键词） | 质量模式 |
| 5 | **症状驱动 description（"当...时使用"）** | **skill-creator P0** |
| 6 | When to Use 区块 | 质量模式 |
| 7 | When NOT to Use 区块 | 质量模式 |
| 8 | 代码示例（```） | 质量模式 |
| 9 | Usage/CLI 区块 | 质量模式 |
| 10 | **Few-shot 示例（`<example>`/`<anti-example>`）** | **skill-creator P0** |
| 11 | 无模糊语言（etc./and so on） | 质量模式 |
| 12 | 最小长度（≥15 行） | 基础 |
| 13 | Related Skills 区块 | 质量模式 |
| 14 | Output Artifacts 区块 | 质量模式 |
| 15 | **原子性（无 @skill/references/ 路径耦合）** | **skill-creator P0** |

### 质量分级

| 等级 | 分数 | 含义 |
|------|------|------|
| **POWERFUL** ⭐ | ≥ 85% | 可发布到 Marketplace |
| **SOLID** | 70–84% | 可发布到 GitHub |
| **GENERIC** | 55–69% | 需迭代改进 |
| **WEAK** | < 55% | 拒绝或重写 |

### 全局安装

```bash
# Claude Code
for skill in skills/*/; do
  rsync -a --exclude='__pycache__' "$skill" ~/.claude/skills/$(basename "$skill")/
done
ln -sfn ~/.claude/skills/_auto-improvement-lib/lib ~/.claude/lib

# OpenClaw（大龙虾）
for skill in skills/*/; do
  rsync -a --exclude='__pycache__' "$skill" ~/.openclaw/skills/$(basename "$skill")/
done
cp -r lib/ ~/.openclaw/lib/
```

### 测试

```bash
python3 -m pytest skills/ -v                              # 全部 289 个测试
python3 -m pytest skills/improvement-learner/tests/ -v    # 单个 skill
```

### 目录结构

```
├── lib/                              # 共享库
│   ├── common.py                     # I/O、时间戳、分类常量
│   └── state_machine.py              # 状态机、阶段转换
├── skills/
│   ├── improvement-orchestrator/     # 全流程编排
│   ├── improvement-generator/        # 候选生成
│   ├── improvement-discriminator/    # 多审阅者 + LLM Judge
│   │   └── interfaces/              # llm_judge, critic_engine, assertions...
│   ├── improvement-executor/         # 变更执行 + 回滚
│   ├── improvement-gate/             # 6 层门禁 + 人工审核
│   ├── benchmark-store/              # Pareto front + 评估标准
│   │   └── data/                     # evaluation-standards.md v2.0
│   └── improvement-learner/          # Karpathy 循环 + 三层记忆
│       └── memory/                   # HOT/WARM/COLD JSON
├── EVALUATION_REPORT.md              # 自测评报告
├── .github/workflows/ci.yml          # CI: lint + test + security
├── pyproject.toml
└── requirements.txt                  # pyyaml + pytest
```

### 设计参考

| 来源 | 采纳的模式 |
|------|-----------|
| [Karpathy autoresearch](https://github.com/karpathy) | evaluate→modify→re-evaluate→keep/revert 循环 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 10 个质量模式、POWERFUL/SOLID/GENERIC/WEAK 分级 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | plugin.json 标准 |
| GEPA (ICLR 2026) | trace-aware feedback（失败信息注入下一轮） |
| SoK (2025) | curated > auto-generated skills |
| Princeton/ETH contextual drag | 失败上下文清理，防止 10-20% 性能下降 |

---

## License

MIT
