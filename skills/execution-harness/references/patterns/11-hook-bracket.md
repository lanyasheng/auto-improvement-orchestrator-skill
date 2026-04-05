# Pattern 11: Hook Pair Bracket（每轮测量框架）

## 问题

无法知道每一轮 agent 交互消耗了多少 context、用了多长时间、调用了哪些工具。

## 原理

用 UserPromptSubmit + Stop 两个 hook 构成一个测量"括号"，在每轮前后采集数据。来自 claude-howto 的 context-tracker 示例——用 session-id 为 key 的临时文件在两个 hook 之间共享状态。

## 实现

**UserPromptSubmit hook（"before"）**：
```bash
# 记录轮次开始状态
jq -n --arg ts "$(date +%s)" --arg ctx "$CONTEXT_USAGE" \
  '{start_ts: $ts, start_ctx: $ctx}' > "$TMPDIR/bracket-${SESSION_ID}.json"
```

**Stop hook（"after"）**：
```bash
# 读取开始状态，计算本轮增量
START=$(cat "$TMPDIR/bracket-${SESSION_ID}.json")
ELAPSED=$(( $(date +%s) - $(echo "$START" | jq -r '.start_ts') ))
CTX_DELTA=$(( CURRENT_CTX - $(echo "$START" | jq -r '.start_ctx') ))
echo "Turn: ${ELAPSED}s, context delta: ${CTX_DELTA} tokens"
```

## 用途

- **Context 预算**：当单轮 context 增量 > 阈值时告警（"这一轮用了 30K token，可能有大文件被读入"）
- **工具统计**：哪些工具被频繁使用/失败
- **进度追踪**：第 N 轮，已用 X% context
- **与 Ralph 叠加**：先 bracket 记录数据，再 ralph 决定是否 block

## 与 Ralph 的关系

Ralph 的 Stop hook 决定"是否阻止停止"。Hook pair bracket 不阻止，只测量和记录。两者可叠加——在 settings.json 的 Stop hooks 数组中，bracket 在前（记录数据），ralph 在后（决定是否 block）。

## 状态文件

临时文件 `$TMPDIR/bracket-${SESSION_ID}.json`（不在 sessions/ 下，因为这是轮次级别的瞬态数据）。

聚合统计可以写入 `sessions/<session-id>/bracket.json`（累计数据，供外部监控读取）。
