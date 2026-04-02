# Improvement Skills Monorepo

**提升/测评类 Skills 统一仓库**

本仓库是一个 monorepo，包含多个专注于技能提升和测评的 OpenClaw skills。

## Skills

### 1. auto-improvement-orchestrator

**统一入口 skill**: 协调 Proposer / Critic / Executor / Gate 四角色，对 skill / macro / workflow 等对象进行自动化改进。

- **路径**: `skills/auto-improvement-orchestrator/`
- **触发条件**: "自动改进", "优化 skill", "运行 critic", "回滚" 等
- **核心流程**: Proposer → Critic → Executor → Gate

### 2. skill-evaluator

**Skill 评估与提升专家**: 提供基准测试、红队测试和自主改进循环（Karpathy Loop）。

- **路径**: `skills/skill-evaluator/`
- **触发条件**: 新 Skill 质量评估、回归测试、能力对比、ClawHub 发布前认证
- **核心流程**: Skill 分析 → 基准测试 → 红队测试 → 生成报告 → 持续改进

## 目录结构

```
.
├── README.md
├── .github/workflows/ci.yml      # Monorepo CI (lint + test + security)
├── .gitignore
├── skills/
│   ├── auto-improvement-orchestrator/
│   │   ├── SKILL.md
│   │   ├── references/            # 架构文档、流程说明
│   │   ├── scripts/               # 执行脚本 (propose/critic/executor/gate/rollback)
│   │   ├── tests/                 # 状态机测试
│   │   └── docs/                  # 文档
│   └── skill-evaluator/
│       ├── SKILL.md
│       ├── README.md              # Skill 详细说明
│       ├── interfaces/            # 评估接口定义 (critic_engine_v2, frozen_benchmark, etc.)
│       ├── scripts/               # 评估脚本 + human_review/ PR 集成
│       ├── tests/                 # 测试套件
│       ├── tests/fixtures/        # 测试用例
│       ├── references/            # 评估标准、测试用例库
│       └── market-research/       # 市场调研
└── ...
```

## 使用方式

每个 skill 都是独立的 OpenClaw skill，通过各自的 `SKILL.md` 触发。

### 安装到 OpenClaw

```bash
# 克隆本仓库到本地
git clone https://github.com/lanyasheng/auto-improvement-orchestrator-skill.git

# 创建软链接到 OpenClaw skills 目录
ln -s $(pwd)/skills/auto-improvement-orchestrator ~/.openclaw/skills/auto-improvement-orchestrator
ln -s $(pwd)/skills/skill-evaluator ~/.openclaw/skills/skill-evaluator
```

## 开发规范

- 每个 skill 保持独立边界（SKILL.md / references / scripts / tests）
- 共享工具/接口可放在 `skills/shared/`（待规划）
- 不要将 benchmark 数据、hidden tests 直接提交到 skill 包
- 清理 `__pycache__`、`.venv`、临时报告等 runtime artifacts

## License

MIT
