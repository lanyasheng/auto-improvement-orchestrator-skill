# Auto-Improvement Orchestrator — Release Readiness Report

**日期**: 2026-04-02  
**执行者**: subagent (release trimming)  
**目标**: 将 repo 整理为 ClawHub-ready 发布候选版

---

## 1. 本次裁掉了什么

### 删除的文件/目录

| 路径 | 类型 | 删除理由 |
|------|------|---------|
| `docs/auto-improvement-orchestrator-design-2026-03-31.md` | 设计稿 | 研发过程文档，非 skill 运行时必需 |
| `docs/auto-improvement-orchestrator-skill-review-2026-04-01.md` | 评审报告 | 研发过程文档，非 skill 运行时必需 |
| `docs/` (整个目录) | 目录 | 空目录清理 |

**删除原则**: 根据 skill-creator 原则，skill 不应包含"auxiliary context about the process that went into creating it"。设计稿和评审报告属于研发历史，不应进入发布包。

---

## 2. 保留了什么

### 核心文件（全部保留）

| 文件 | 用途 | 必要性 |
|------|------|--------|
| `SKILL.md` | 统一入口，触发条件 + 核心流程 | ✅ 必需 |
| `references/architecture.md` | 四角色详细设计 | ✅ 运行时按需加载 |
| `references/adapters.md` | 各 lane adapter 规格 | ✅ 运行时按需加载 |
| `references/guardrails.md` | 质量门/回滚机制 | ✅ 运行时按需加载 |
| `references/phases.md` | 路线图 | ✅ 运行时按需加载 |
| `references/skill-evaluator-adapter.md` | skill-evaluator 集中规格 | ✅ 运行时按需加载 |
| `references/end-to-end-demo.md` | 完整端到端示例 | ✅ 运行时按需加载 |
| `scripts/*.py` (7 个) | 可运行核心功能 | ✅ 必需 |
| `.gitignore` | Git 配置 | ✅ 必需 |

### 保留原则

- **SKILL.md**: 核心入口，符合 skill-creator 原则（简洁，<500 行）
- **references/**: 按需加载的详细文档，符合 progressive disclosure 原则
- **scripts/**: 可运行的 bundled resources，自文档化（--help）

---

## 3. benchmark/hidden tests 归属结论

### 结论：**不属于** skill 发布包

**理由**:

1. **独立性要求**: Frozen benchmark 需要独立于 skill 变更，不应随 skill 版本变化
2. **防过拟合**: Hidden tests 需要对 Proposer 保密，防止候选方案过拟合测试
3. **skill-creator 原则**: skill 只包含 essential files，测试基础设施属于外部依赖
4. **工程最佳实践**: 测试套件应放在独立 repo 或 CI 基础设施

### 正确归属

| 测试类型 | 归属位置 | 说明 |
|---------|---------|------|
| Frozen Benchmark | 独立 repo / 只读快照 | 不随 skill 变更 |
| Hidden Tests | 加密存储 / 运行时注入 | 对 Proposer 保密 |
| External Regression | 现有 CI / 外部 API | 第三方验证 |
| Human Spot-Check | Discord / 审批接口 | 人工抽查 |

### Phase 2 规划

在 `references/phases.md` 和 `references/skill-evaluator-adapter.md` 中已明确规划：
- Phase 2 将实现 full evaluator adapter
- 但 benchmark/hidden tests 仍应留在外部基础设施
- skill 本身只包含调用接口，不包含测试数据

---

## 4. 当前文件树

```
auto-improvement-orchestrator-skill/
├── .gitignore
├── SKILL.md
├── references/
│   ├── adapters.md
│   ├── architecture.md
│   ├── end-to-end-demo.md
│   ├── guardrails.md
│   ├── phases.md
│   └── skill-evaluator-adapter.md
└── scripts/
    ├── apply_gate.py
    ├── evaluator_phase1.py
    ├── lane_common.py
    ├── propose_candidate.py
    ├── rollback.py
    ├── run_critic.py
    └── run_executor.py
```

**文件统计**:
- 核心文件: 1 (SKILL.md)
- References: 6
- Scripts: 7
- 配置: 1 (.gitignore)
- **总计**: 15 个文件

---

## 5. ClawHub 标准检查

### 检查项

| 检查项 | 状态 | 说明 |
|--------|------|------|
| SKILL.md frontmatter | ✅ | 包含 name + description |
| SKILL.md 简洁性 | ✅ | ~150 行，符合 <500 行原则 |
| Progressive Disclosure | ✅ | 详细信息在 references/ 按需加载 |
| 无冗余文档 | ✅ | 已删除 docs/，无 README/CHANGELOG 等噪音 |
| Scripts 自文档化 | ✅ | 所有脚本含 --help |
| 文件结构清晰 | ✅ | SKILL.md / references/ / scripts/ 边界清楚 |
| 无本地绝对路径 | ✅ | 代码中使用相对路径或变量 |
| 无 /tmp 产物 | ✅ | 运行态产物在 .gitignore 中排除 |

### skill-creator 原则对齐

| 原则 | 对齐情况 |
|------|---------|
| Concise is Key | ✅ SKILL.md 精简到核心内容 |
| Set Appropriate Degrees of Freedom | ✅ 明确 Phase 1 边界，不夸大能力 |
| Progressive Disclosure | ✅ 三层加载：metadata → SKILL.md → references |
| No Extraneous Documentation | ✅ 已删除研发过程文档 |
| Scripts as Bundled Resources | ✅ 脚本自包含 + 自文档化 |

---

## 6. ClawHub-ready 候选标准判断

### 结论：**almost** (接近但仍有 1-2 个缺口)

### 已达到的标准 ✅

1. **文件结构简洁**: 15 个文件，无冗余
2. **SKILL.md 规范**: frontmatter + 简洁正文
3. **Progressive Disclosure**: references/按需加载
4. **可运行性**: 7 个脚本可独立执行
5. **自文档化**: scripts 含 --help
6. **边界清晰**: 明确标注 Phase 1/2/3

### 还差的 1-3 个点 ⚠️

| 缺口 | 优先级 | 建议修复方式 |
|------|--------|-------------|
| **缺少 version 字段** | P1 | 在 SKILL.md frontmatter 添加 `version: 0.2.0` |
| **缺少 license 字段** | P1 | 在 SKILL.md frontmatter 添加 `license` 字段 |
| **无自动化测试** | P2 | 添加单元测试/集成测试（可后续补充） |

### 推荐修复（发布前）

在 SKILL.md frontmatter 添加：
```yaml
---
name: auto-improvement-orchestrator
description: ...
version: 0.2.0
license: MIT  # 或项目实际 license
---
```

---

## 7. 最终建议

### 可以发布吗？

**可以发布为 v0.2.0 候选版**，但建议先补充：
1. version 字段
2. license 字段

### 发布后注意事项

1. **Phase 1 能力边界**: 明确告知用户仅 `generic-skill` lane 可运行
2. **Phase 2 规划**: 在 SKILL.md 中已明确标注，避免误导
3. **benchmark/hidden tests**: 不属于发布包，需单独配置

---

## 8. Git 提交记录

### 本次提交

- **Commit**: (待生成)
- **Message**: `chore: trim repo for clawhub-ready release`
- **变更**: 删除 docs/ 目录（2 份研发过程文档）

### 历史提交

- `c5327dc feat: bootstrap auto-improvement-orchestrator skill`

---

**报告路径**: `/Users/study/.openclaw/repos/auto-improvement-orchestrator-skill/docs/release-readiness-2026-04-02.md`

**验证时间**: 2026-04-02 08:36 GMT+8
