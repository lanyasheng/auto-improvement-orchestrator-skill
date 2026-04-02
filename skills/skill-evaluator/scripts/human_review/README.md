# Human Review → GitHub PR Integration

**版本**: v0.1 (P2-b First Version)  
**状态**: 最小可行集成

---

## 概述

本集成在 P2-a 已完成的 human review receipt 基础上，实现与 GitHub PR / 审批流的真正互动。

### 核心能力

1. **PR 评论触发 review** - 从 PR 评论/label 读取人工决策
2. **review 结果回写 PR** - 把 human review receipt 作为 PR 评论回写
3. **最小状态机** - `pending_review → reviewed → approved/rejected`

---

## 架构图

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Gate Receipt  │────▶│  PR Integration  │────▶│  GitHub PR #123 │
│  (auto-keep?)   │     │  (create record) │     │  + labels       │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          │ human
                                                          │ review
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Final State    │◀────│  Review Trigger  │◀────│  PR Comment:    │
│  approved/      │     │  (poll decision) │     │  /approve       │
│  rejected       │     │                  │     │  /reject        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 文件结构

```
scripts/human_review/
├── README.md                  # 本文件
├── pr_state.py                # 状态机管理
├── pr_review_trigger.py       # 从 PR 读取决策
├── pr_review_writeback.py     # 回写 receipt 到 PR
└── pr_integration.py          # 集成入口（创建 PR + 记录）
```

---

## 使用流程

### Step 1: Gate 完成后创建 PR

当 `apply_gate.py` 输出 `pending_promote` 决策时：

```bash
# 假设 gate receipt 路径为：
# /Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill/receipts/run-xxx-cand-xxx-gate.json

python scripts/human_review/pr_integration.py \
  --gate-receipt /path/to/gate-receipt.json \
  --repo lanyasheng/auto-improvement-orchestrator-skill
```

**输出**:
- 创建 GitHub PR（或关联现有 PR）
- 创建 human review 记录（状态：`pending_review`）
- 在 PR 上发布初始 review receipt 评论

---

### Step 2: 人工 Review

人类 reviewer 在 PR 上进行审查，然后通过以下方式表达决策：

#### 方式 A: 评论关键词
- `/approve` 或 `LGTM` → 批准
- `/reject` → 拒绝
- `/hold` 或 `needs changes` → 搁置

#### 方式 B: Labels
- 添加 `approved` / `lgtm` / `ready-to-merge` → 批准
- 添加 `rejected` / `do-not-merge` → 拒绝
- 添加 `pending-review` / `needs-changes` → 搁置

---

### Step 3: 触发 Review 处理

```bash
python scripts/human_review/pr_review_trigger.py \
  --repo lanyasheng/auto-improvement-orchestrator-skill \
  --pr-number 123 \
  --run-id run-xxx \
  --candidate-id cand-xxx
```

**行为**:
- 检测 PR 评论/labels 中的决策信号
- 更新 human review 记录状态
- 在 PR 上发布确认评论
- 添加相应 label

---

### Step 4: 回写 Receipt（可选）

```bash
python scripts/human_review/pr_review_writeback.py \
  --repo lanyasheng/auto-improvement-orchestrator-skill \
  --run-id run-xxx \
  --candidate-id cand-xxx
```

**行为**:
- 读取 human review 记录
- 格式化为 Markdown 评论
- 发布到 PR 作为审计记录

---

## 状态机

```
pending_review ──[human decision]──▶ reviewed ──[approve/reject]──▶ approved / rejected
```

### 状态说明

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| `pending_review` | 等待人工审查 | PR 创建后初始状态 |
| `reviewed` | 已审查但未最终决策 | 检测到 `/hold` 或 `needs changes` |
| `approved` | 已批准 | 检测到 `/approve` / `LGTM` / `approved` label |
| `rejected` | 已拒绝 | 检测到 `/reject` / `rejected` label |

---

## 决策信号检测

### Labels（优先级高）

| Label | 决策 |
|-------|------|
| `approved`, `approve`, `lgtm`, `ready-to-merge` | approve |
| `rejected`, `reject`, `do-not-merge` | reject |
| `pending-review`, `needs-changes` | hold |

### 评论关键词

| 关键词 | 决策 |
|--------|------|
| `/approve`, `approved`, `LGTM`, `looks good to me` | approve |
| `/reject`, `rejected` | reject |
| `/hold`, `needs changes`, `request changes` | hold |

**规则**: 最新评论覆盖早期评论。

---

## 持久化路径

所有 human review 记录存储在：

```
/Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill/pr_reviews/
└── {run_id}-{candidate_id}-review.json
```

**示例内容**:
```json
{
  "schema_version": "v1",
  "lane": "generic-skill",
  "run_id": "run-20260402-123456",
  "candidate_id": "cand-001",
  "pr_number": 123,
  "pr_url": "https://github.com/lanyasheng/auto-improvement-orchestrator-skill/pull/123",
  "state": "approved",
  "decision": "approved",
  "decision_source": "comment",
  "reviewer": "lanyasheng",
  "created_at": "2026-04-02T10:00:00+00:00",
  "updated_at": "2026-04-02T11:30:00+00:00",
  "gate_receipt_path": "/path/to/gate-receipt.json",
  "truth_anchor": "pr:123"
}
```

---

## Demo 命令

### 完整流程演示

```bash
# 1. 假设已有 gate receipt（pending_promote 决策）
GATE_RECEIPT="/Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill/receipts/run-demo-cand-demo-gate.json"

# 2. 创建 PR 和 review 记录
python scripts/human_review/pr_integration.py \
  --gate-receipt "$GATE_RECEIPT" \
  --repo lanyasheng/auto-improvement-orchestrator-skill

# 3. 人工在 PR 上评论 /approve

# 4. 触发 review 处理
python scripts/human_review/pr_review_trigger.py \
  --repo lanyasheng/auto-improvement-orchestrator-skill \
  --pr-number <PR_NUMBER> \
  --run-id run-demo \
  --candidate-id cand-demo

# 5. 查看最终状态
python scripts/human_review/pr_state.py \
  --action show \
  --run-id run-demo \
  --candidate-id cand-demo
```

---

## 与现有流程集成

### 在 apply_gate.py 后自动调用

修改 gate 流程，在 `pending_promote` 决策后自动调用 `pr_integration.py`：

```bash
# apply_gate.py 完成后
if [ "$DECISION" = "pending_promote" ]; then
  python scripts/human_review/pr_integration.py \
    --gate-receipt "$RECEIPT_PATH" \
    --repo lanyasheng/auto-improvement-orchestrator-skill
fi
```

---

## 约束与边界

### 当前支持

- ✅ 从 PR 评论读取决策
- ✅ 从 PR labels 读取决策
- ✅ 状态机持久化
- ✅ Receipt 回写 PR
- ✅ 与 gate receipt 关联

### 当前不支持

- ❌ 自动创建分支/commit（需手动准备 PR）
- ❌ 多轮 review 迭代（仅单次决策）
- ❌ 批量 review 处理
- ❌ 外部审批系统集成（如 Slack/邮件）

---

## 故障排查

### PR 创建失败

**症状**: `Failed to create PR: ...`

**原因**: 没有未提交的更改或功能分支

**解决**:
```bash
# 确保有未提交的更改
git status
git add -A
git commit -m "Auto-improvement candidate: <candidate-id>"
git push -u origin <branch>
```

### gh CLI 未认证

**症状**: `gh command failed: To re-authenticate, please run: gh auth login`

**解决**:
```bash
gh auth login
```

### 状态记录找不到

**症状**: `No review record found for ...`

**解决**: 使用 `--create-if-missing` 参数：
```bash
python pr_review_trigger.py --create-if-missing ...
```

---

## 下一步（Phase 3）

- [ ] 自动创建功能分支和 commit
- [ ] 多轮 review 支持（评论 → 修改 → 再审查）
- [ ] 与 control-plane 集成（自动推进状态机）
- [ ] Slack/邮件通知
- [ ] Review 超时自动提醒

---

## 报告路径

集成测试报告：`/tmp/human-review-pr-integration-2026-04-02.md`
