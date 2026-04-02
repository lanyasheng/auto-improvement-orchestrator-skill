#!/bin/bash
# Human Review PR Integration Demo Script
# 演示从 gate receipt 到 PR 审批的完整流程

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
STATE_ROOT="/Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill"
REPO="lanyasheng/auto-improvement-orchestrator-skill"

echo "========================================"
echo "Human Review PR Integration Demo"
echo "========================================"
echo ""

# Step 0: 准备测试数据
echo "Step 0: 准备测试数据..."

# 创建模拟的 gate receipt
mkdir -p "$STATE_ROOT/receipts"
cat > "$STATE_ROOT/receipts/run-demo-$(date +%Y%m%d-%H%M%S)-gate.json" << 'EOF'
{
  "schema_version": "v1",
  "lane": "generic-skill",
  "run_id": "run-demo-20260402",
  "candidate_id": "cand-demo-001",
  "decision": "pending_promote",
  "reason": "Critic marked candidate as hold; requires human review before promotion",
  "candidate_category": "reference",
  "created_at": "2026-04-02T10:00:00+00:00"
}
EOF

GATE_RECEIPT="$STATE_ROOT/receipts/run-demo-20260402-gate.json"
echo "✓ 创建模拟 gate receipt: $GATE_RECEIPT"
echo ""

# Step 1: 创建 PR 和 review 记录
echo "Step 1: 创建 PR 和 human review 记录..."
echo "命令:"
echo "  python $SCRIPT_DIR/pr_integration.py \\"
echo "    --gate-receipt $GATE_RECEIPT \\"
echo "    --repo $REPO"
echo ""

# Step 2: 说明人工 review 步骤
echo "Step 2: 人工 Review（手动操作）"
echo "  在 PR 上评论以下任一内容:"
echo "    - /approve 或 LGTM  → 批准"
echo "    - /reject           → 拒绝"
echo "    - /hold             → 搁置"
echo ""

# Step 3: 触发 review 处理
echo "Step 3: 触发 review 处理（人工 review 后执行）"
echo "命令:"
echo "  python $SCRIPT_DIR/pr_review_trigger.py \\"
echo "    --repo $REPO \\"
echo "    --pr-number <PR_NUMBER> \\"
echo "    --run-id run-demo-20260402 \\"
echo "    --candidate-id cand-demo-001"
echo ""

# Step 4: 回写 receipt
echo "Step 4: 回写 receipt 到 PR（可选）"
echo "命令:"
echo "  python $SCRIPT_DIR/pr_review_writeback.py \\"
echo "    --repo $REPO \\"
echo "    --run-id run-demo-20260402 \\"
echo "    --candidate-id cand-demo-001"
echo ""

# Step 5: 查看状态
echo "Step 5: 查看最终状态"
echo "命令:"
echo "  python $SCRIPT_DIR/pr_state.py \\"
echo "    --action show \\"
echo "    --run-id run-demo-20260402 \\"
echo "    --candidate-id cand-demo-001"
echo ""

echo "========================================"
echo "Demo 脚本结束"
echo "========================================"
echo ""
echo "真实运行请按上述步骤执行，或使用以下一键命令（如果有真实 PR）："
echo ""
echo "  # 创建 PR + review 记录"
echo "  python $SCRIPT_DIR/pr_integration.py --gate-receipt $GATE_RECEIPT --repo $REPO"
echo ""
echo "  # 人工 review 后触发处理"
echo "  python $SCRIPT_DIR/pr_review_trigger.py --repo $REPO --pr-number <PR_NUM> --run-id run-demo-20260402 --candidate-id cand-demo-001"
echo ""
