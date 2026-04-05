# Session-Scoped State Layout

所有状态统一在一个 session 目录下，清理只需 `rm -rf` 一个目录。

## 目录结构

```
sessions/<session-id>/
  ralph.json              ← Pattern 1 状态
  cancel.json             ← Pattern 7 取消信号
  handoffs/               ← Pattern 2/8 handoff 文档
    stage-1-plan.md
    pre-compact.md
  tool-errors.json        ← Pattern 3 工具错误追踪
  denials.json            ← Pattern 9 权限否决追踪
  bracket.json            ← Pattern 11 累计测量数据
  learnings.jsonl         ← Subagent 发现的持久化知识
```

## 为什么不用多个散落目录

OMC 使用 `sessions/<sessionId>/` 为根的隔离方案。好处：

1. **清理简单**：一个 session 的所有状态一个 `rm -rf` 搞定
2. **无跨 session 污染**：不可能读到其他 session 的状态
3. **Crash 恢复简单**：检查目录是否存在就知道有没有残留状态
4. **Staleness 检查**：目录的 mtime 反映最后活动时间

## OMC 的状态读取策略

OMC 的 `readStateFileWithSession()` 使用 4 级 fallback：
1. Session-scoped path：`sessions/<sessionId>/<file>`
2. 扫描其他 session 目录找匹配的 `session_id`
3. Legacy 非 session 路径（向后兼容）
4. 全局 `~/.omc/state/`（最后的 fallback）

对于新实现，建议只用第 1 级——严格 session-scoped，不做 fallback。
