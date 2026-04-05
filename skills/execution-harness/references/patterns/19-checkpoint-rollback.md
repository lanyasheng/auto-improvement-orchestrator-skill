# Pattern 19: Git Checkpoint + Auto Rollback（快照与回滚）

## 问题

Agent 执行 Bash 命令可能造成不可逆的破坏——`rm -rf`、`git reset --hard`、`docker rm`。Claude Code 内置的 checkpoint 只追踪 Write/Edit 工具的文件变更，不覆盖 Bash 的副作用。

来源：Claude Code 官方文档 Checkpointing + PostToolUseFailure hook

## 原理

在 Bash 执行破坏性命令前，PreToolUse hook 创建 git 快照。如果命令失败（PostToolUseFailure），自动回滚到快照。

## 实现

### PreToolUse hook（Bash 命令快照）

```bash
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
# 检测破坏性命令
if echo "$CMD" | grep -qE 'rm -rf|git reset --hard|git checkout --|docker rm|kubectl delete'; then
  # 创建快照
  CHECKPOINT=$(git stash create 2>/dev/null)
  if [ -n "$CHECKPOINT" ]; then
    echo "$CHECKPOINT" > "sessions/${SESSION_ID}/checkpoint"
    echo '{"hookSpecificOutput":{"additionalContext":"Checkpoint created before destructive command."}}'
  fi
fi
echo '{"continue":true}'
```

### PostToolUseFailure hook（自动回滚）

```bash
INPUT=$(cat)
CHECKPOINT_FILE="sessions/${SESSION_ID}/checkpoint"
[ -f "$CHECKPOINT_FILE" ] || exit 0

CHECKPOINT=$(cat "$CHECKPOINT_FILE")
git stash apply "$CHECKPOINT" 2>/dev/null
rm -f "$CHECKPOINT_FILE"
echo '{"hookSpecificOutput":{"additionalContext":"Auto-rolled back to checkpoint after tool failure."}}'
```

## 与 Claude Code 内置 checkpoint 的区别

| | 内置 Checkpoint | 本 Pattern |
|---|---|---|
| 覆盖范围 | Write/Edit 工具 | Bash 破坏性命令 |
| 恢复方式 | Esc+Esc 或 /rewind（用户手动） | PostToolUseFailure hook（自动） |
| 存储方式 | Claude Code 内部 | git stash |

## Tradeoff

- git stash 只覆盖 git tracked 文件——untracked 文件的删除无法恢复
- 每个破坏性命令前都 stash 会有 I/O 开销
- 命令匹配是 regex——可能误判（`rm -rf` 在代码注释里也会触发）
