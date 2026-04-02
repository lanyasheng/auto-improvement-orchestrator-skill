---
name: skill-evaluator
version: 1.0.0
description: 评估和提升其他 Skill 的能力，提供基准测试、红队测试和自主改进循环（Karpathy Loop）
author: OpenClaw Team
license: MIT
tags: [skill, evaluation, benchmark, red-team, quality, self-improvement]
---

# Skill Evaluator — Skill 评估与提升专家

## 何时使用

✅ **应该使用**:
- 新 Skill 开发完成后需要质量评估
- 现有 Skill 升级后需要回归测试
- 需要对比多个 Skill 的能力差异
- 准备发布 Skill 到 ClawHub 前需要质量认证

❌ **不应该使用**:
- 简单的 prompt 优化（使用 prompt-optimizer）
- 单一功能测试（使用具体 Skill 的测试套件）
- 非 Skill 相关的 LLM 评估（使用 promptfoo 直接评估）

## 自由度级别

**本 Skill 采用中等自由度（pseudocode + 参数配置）**

- **核心评估流程**: 低自由度（必须严格按照脚本执行）
- **测试用例生成**: 中等自由度（可以参考模板灵活调整）
- **报告格式**: 高自由度（可以根据 Skill 类型调整格式）

## 核心工作流程

```
1. Skill 分析 → 2. 基准测试 → 3. 红队测试 → 4. 生成报告 → 5. 持续改进
```

### 阶段 1：Skill 分析
1. 读取目标 Skill 的 SKILL.md 文件
2. 解析核心职责、工作流程、工具依赖
3. 识别评估维度和成功标准

### 阶段 2：基准测试
1. 加载预定义测试用例库（[references/test-cases.yaml](references/test-cases.yaml)）
2. 运行正常场景测试
3. 运行边界场景测试
4. 计算通过率、准确率、执行时间、成本

### 阶段 3：红队测试
1. 生成对抗性测试用例
2. 测试恶意输入处理能力（SQL 注入、提示词注入等）
3. 测试资源限制处理能力
4. 测试安全漏洞

### 阶段 4：生成报告
1. 计算能力等级（Level 1/2/3）
2. 生成质量雷达图
3. 提供改进建议（按优先级排序）
4. 输出评估报告到 `.feedback/{skill-name}-eval-{timestamp}.md`

### 阶段 5：持续改进
1. 收集用户反馈
2. 更新测试用例库
3. 迭代评估标准
4. 可选：运行自主改进循环（Karpathy Loop，实测 5 次迭代改进 16.3%）

## 评估标准

### Level 1（基础可用）
- ✅ 能完成核心任务
- ✅ 有基本错误处理
- ⚠️ 测试覆盖率 < 50%
- **发布策略**: 仅限内部使用

### Level 2（稳定可靠）
- ✅ 能完成核心任务
- ✅ 有完整的错误处理
- ✅ 测试覆盖率 > 80%
- ✅ 有基准测试
- **发布策略**: 可发布到 GitHub/ClawHub

### Level 3（生产就绪）
- ✅ 能完成核心任务
- ✅ 有完整的错误处理
- ✅ 测试覆盖率 > 95%
- ✅ 有基准测试和红队测试
- ✅ 有用户反馈循环
- ✅ 有版本管理（由 Git 管理）
- **发布策略**: 优先推荐到 ClawHub 首页

## 评估维度

| 维度 | 默认权重 | 目标值 | 说明 |
|------|---------|--------|------|
| **准确性** | 25% | > 90% | 任务完成率 |
| **可靠性** | 20% | < 5% 错误率 | 稳定表现 |
| **效率** | 20% | < 30 秒 | 执行速度 |
| **成本** | 15% | < $0.50/次 | Token 消耗 |
| **覆盖率** | 10% | 100% | 测试覆盖 |
| **安全性** | 10% | > 90% | 红队测试 |

**注意**: 不同 Skill 类别有权重调整，详见 [references/evaluation-standards.md](references/evaluation-standards.md)

## 快速开始

### 基础评估
```bash
python scripts/evaluate.py --skill-path /path/to/skill --output reports/
```

### 使用 Critic Engine 评估 (整合 interfaces/)
```bash
python scripts/evaluate.py --skill-path /path/to/skill --use-critic --output reports/
```

### 红队测试
```bash
python scripts/red_team.py --skill-path /path/to/skill --output reports/ --all-tests
```

### 自主改进（Karpathy Loop）
```bash
python scripts/self_improve.py --skill-path /path/to/skill --metric accuracy --max-iterations 5
python scripts/self_improve.py --skill-path /path/to/skill --metric accuracy --demo  # 演示模式
```

### 端到端演示
```bash
python scripts/demo_end_to_end.py --demo  # 演示模式
python scripts/demo_end_to_end.py --skill-path /path/to/skill --metric accuracy  # 真实运行
```

### 基准对比
```bash
python scripts/benchmark_db.py --action compare --skill-path /path/to/skill --category tool-type
```

### 并行评估
```bash
python scripts/parallel_eval.py --skill-paths /path/to/skill1 /path/to/skill2 --max-workers 10
```

### 发布到 ClawHub
```bash
python scripts/publish_to_clawhub.py --skill-path /path/to/skill --level Level2 --publish
```

## 详细文档

| 文档 | 用途 | 路径 |
|------|------|------|
| **评估标准详情** | 详细的 Level 标准和评估维度 | [references/evaluation-standards.md](references/evaluation-standards.md) |
| **测试用例库** | 5 类 Skill 的完整测试用例 | [references/test-cases.yaml](references/test-cases.yaml) |
| **基准数据库** | 15 个默认基准测试用例 | [references/benchmark-database.md](references/benchmark-database.md) |
| **红队测试指南** | 5 种安全测试详细说明 | [references/red-team-guide.md](references/red-team-guide.md) |

## 工具依赖

- `bash`: 执行评估脚本
- `python3`: 运行 Promptfoo 评估
- `promptfoo`: LLM 评估框架（可选，用于运行实际测试）
- `read`: 读取 Skill 文件
- `write`: 生成评估报告
- `pytest`: 运行单元测试（可选）

## 输出格式

评估报告自动保存到 `.feedback/{skill-name}-eval-{timestamp}.md`，包含：

1. Skill 基本信息（名称、版本、作者）
2. 能力等级判定（Level 1/2/3）
3. 各维度得分（准确性/可靠性/效率/成本/覆盖率/安全性）
4. 质量雷达图（Markdown 表格）
5. 发现的问题列表
6. 改进建议（按优先级排序）
7. 测试用例执行详情

## 常见问题

### Q: 如何添加新的测试用例？
A: 在 `references/test-cases.yaml` 中添加新的测试用例，格式参考现有用例。

### Q: 如何自定义评估维度权重？
A: 修改 `evals/skill-eval-config.yaml` 中的 `weights` 配置，或参考 [references/evaluation-standards.md](references/evaluation-standards.md) 的类别权重。

### Q: 如何导出评估报告？
A: 评估完成后，报告会自动保存到 `.feedback/{skill-name}-eval-{timestamp}.md`。也可用 `--format json` 导出 JSON。

### Q: 如何对比多个 Skill？
A: 使用 `scripts/parallel_eval.py` 并行评估多个 Skill，自动生成排行榜报告。

### Q: 自主改进循环是如何工作的？
A: 借鉴 Karpathy autoresearch 设计：评估 → 小改动 → 再评估 → 保留/回滚 → 重复。实测 5 次迭代改进 16.3%。

### Q: 如何发布到 ClawHub？
A: 使用 `scripts/publish_to_clawhub.py`，会自动验证 Skill 等级、运行安全检查、复制到 ClawHub 目录。

### Q: 评估失败怎么办？
A: 检查目标 Skill 是否有 SKILL.md 文件，确认 `evals/skill-eval-config.yaml` 配置正确，查看错误日志。

### Q: 如何评估自己的 Skill？
A: 使用 `python scripts/evaluate.py --skill-path . --output reports/` 进行自我评估。

### Q: 红队测试安全吗？
A: 红队测试在隔离环境中运行，不会执行危险操作。所有测试用例都是只读的。

---

*Skill Evaluator v1.0.0 — 让每个 Skill 都达到生产就绪*
