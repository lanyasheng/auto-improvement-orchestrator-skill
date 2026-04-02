# Auto-Improvement Orchestrator Skill

AI Agent Skill 自动评估与自改进管线。评估任意 skill 的质量，生成改进候选，通过多审阅者盲审和 6 层机械门禁验证，自动应用改进并用 Pareto front 防止任何维度回退。

## 核心能力

| 能力 | 说明 | 市面独有? |
|------|------|----------|
| **6 维结构评估** | accuracy(15项) + coverage + reliability + efficiency + security + trigger_quality | 市面最多维度 |
| **LLM-as-Judge** | 4 维语义评估（clarity/specificity/consistency/safety），支持 Claude/OpenAI/Mock | 是 |
| **多审阅者盲审** | 2+ 审阅者独立评分，CONSENSUS/VERIFIED/DISPUTED 认知标签 | 是 |
| **6 层机械门禁** | Schema→Compile→Lint→Regression→Review→HumanReview | 是 |
| **Pareto front** | 多维度回退保护，任何维度回退 >5% 即拒绝改进 | 是 |
| **Karpathy 自改进循环** | evaluate→modify→re-evaluate→keep/revert→repeat | 是 |
| **三层记忆** | HOT(≤100)/WARM/COLD，自动溢出和模式匹配 | 是 |
| **Ralph Wiggum 重试** | 失败 trace 注入下一轮候选生成，最多 3 次 | 是 |
| **纯文本 skill 公平评估** | reliability 默认 1.0，不惩罚无 scripts/tests 的 skill | 是 |
| **skill-creator P0 规范检查** | 症状驱动 description、few-shot 示例、原子性 | 按我们的规范 |

## 架构

```
User → orchestrator → generator (候选生成)
                    → discriminator (多审阅者盲审 + LLM Judge)
                    → gate (6 层机械门禁)
                    → executor (变更执行 + 回滚)
                    → learner (Karpathy 循环 + 三层记忆)
                    ↻ Ralph Wiggum: 失败 → 注入 trace → 重试 (max 3)
```

## 7 个 Skill

| Skill | 类型 | 职责 |
|-------|------|------|
| **improvement-orchestrator** | 编排 | 全流程调度 + Ralph Wiggum 重试循环 |
| **improvement-generator** | 学习 | 分析目标 + 反馈 + 失败 trace → 生成候选 |
| **improvement-discriminator** | 审查 | 多审阅者盲审 + LLM-as-Judge 4 维语义 + 混合评分 |
| **improvement-executor** | 工具 | 4 种 action 类型 + 自动备份 + 回滚 |
| **improvement-gate** | 规则 | 6 层机械门禁 + 人工审核队列 |
| **benchmark-store** | 知识 | 冻结基准 + Pareto front + 质量分级标准 |
| **improvement-learner** | 学习 | 6 维评估 + Karpathy 循环 + HOT/WARM/COLD 记忆 |

## 快速开始

### 安装依赖

```bash
git clone https://github.com/lanyasheng/auto-improvement-orchestrator-skill.git
cd auto-improvement-orchestrator-skill
pip install -r requirements.txt  # pyyaml + pytest
```

### 评估一个 skill

```bash
# 结构评估（6 维度，15 项 accuracy 检查）
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/your/skill \
  --max-iterations 1

# 输出:
# {"final_scores": {"accuracy": 0.87, "coverage": 1.0, "reliability": 1.0, ...}}
```

### 自动改进循环

```bash
# Karpathy 循环: 评估 → 修改 → 重评估 → 保留/回滚 → 重复
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/your/skill \
  --max-iterations 5 \
  --memory-dir /tmp/memory
```

### 多审阅者打分

```bash
# 候选打分（panel + LLM judge）
python3 skills/improvement-discriminator/scripts/score.py \
  --input candidates.json \
  --panel \
  --llm-judge mock \
  --output scored.json
```

### 门禁验证

```bash
# 6 层机械验证
python3 skills/improvement-gate/scripts/gate.py --state-root /tmp/state

# 人工审核队列
python3 skills/improvement-gate/scripts/review.py --list --state-root /tmp/state
```

### 全流程编排

```bash
python3 skills/improvement-orchestrator/scripts/orchestrate.py \
  --target /path/to/skill \
  --state-root /tmp/state \
  --max-retries 3 \
  --out result.json
```

## Accuracy 15 项检查（v2.0）

| # | 检查项 | 来源 |
|---|--------|------|
| 1 | YAML frontmatter 存在 | 基础 |
| 2 | name: 字段 | skill-creator |
| 3 | description: 字段 | skill-creator |
| 4 | description > 40 字符（含触发关键词） | 质量模式 |
| 5 | **症状驱动 description（"当...时使用"）** | skill-creator P0 |
| 6 | When to Use 区块 | 质量模式 |
| 7 | When NOT to Use 区块 | 质量模式 |
| 8 | 代码示例（```） | 质量模式 |
| 9 | Usage/CLI 区块 | 质量模式 |
| 10 | **Few-shot 示例（`<example>`/`<anti-example>`）** | skill-creator P0 |
| 11 | 无模糊语言（etc./and so on） | 质量模式 |
| 12 | 最小长度（≥15 行） | 基础 |
| 13 | Related Skills 区块 | 质量模式 |
| 14 | Output Artifacts 区块 | 质量模式 |
| 15 | **原子性（无 @skill/references/ 路径耦合）** | skill-creator P0 |

## 质量分级

| 等级 | 分数 | 含义 |
|------|------|------|
| **POWERFUL** ⭐ | ≥ 85% | Marketplace ready |
| **SOLID** | 70–84% | 可发布 GitHub |
| **GENERIC** | 55–69% | 需迭代 |
| **WEAK** | < 55% | 拒绝 |

## 测试

```bash
# 全部 289 个测试
python3 -m pytest skills/ -v

# 单个 skill
python3 -m pytest skills/improvement-learner/tests/ -v

# 验证无 mock 残留
grep -rn "random\.uniform\|\"score\": 0.85" skills/*/scripts/*.py
```

## 全局安装

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

## 目录结构

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

## 设计参考

| 来源 | 采纳的模式 |
|------|-----------|
| [Karpathy autoresearch](https://github.com/karpathy) | evaluate→modify→re-evaluate→keep/revert 循环 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 10 个质量模式、POWERFUL/SOLID/GENERIC/WEAK 分级 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | plugin.json 标准 |
| GEPA (ICLR 2026) | trace-aware feedback（失败信息注入下一轮） |
| SoK (2025) | curated > auto-generated skills |
| Princeton/ETH contextual drag | 失败上下文清理，防止 10-20% 性能下降 |

## License

MIT
