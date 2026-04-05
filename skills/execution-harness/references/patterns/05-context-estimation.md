# Pattern 5: 轻量 Context 使用量估算

## 问题

需要知道 agent 的 context window 用了多少，但 transcript JSONL 文件可能 100MB+，不能全部读取。

## 原理

Claude Code 的 transcript 是 append-only JSONL。最新的 API 响应总在文件末尾，包含 `context_window` 和 `input_tokens` 字段。只读最后 4KB 足以提取这些值。

来自 Claude Code 内部的 HUD 实现和 OMC 的 `context-guard-stop.mjs`。

## 实现

```bash
transcript="$1"
if [ -f "$transcript" ]; then
  size=$(stat -f%z "$transcript" 2>/dev/null || stat -c%s "$transcript")
  if [ "$size" -gt 4096 ]; then
    input=$(tail -c 4096 "$transcript" | grep -o '"input_tokens":[0-9]*' | tail -1 | grep -o '[0-9]*')
    window=$(tail -c 4096 "$transcript" | grep -o '"context_window":[0-9]*' | tail -1 | grep -o '[0-9]*')
    if [ -n "$input" ] && [ -n "$window" ] && [ "$window" -gt 0 ]; then
      usage=$(( input * 100 / window ))
      echo "Context usage: ${usage}% (${input}/${window} tokens)"
    fi
  fi
fi
```

## 用途

1. **Stop hook 中的安全阀**：当 usage >= 95% 时，Ralph MUST 放行 stop（见 Pattern 1 安全阀 #1）
2. **Hook pair bracket 中的预算追踪**：每轮记录 context 增量（见 Pattern 11）
3. **外部监控**：周期性检查所有运行中 session 的 context 使用率

## Claude Code 的 token 估算精度

Claude Code 内部使用 3 级精度估算：

- **粗估**：bytes / 4（零成本，毫秒级）
- **代理**：Haiku input count（便宜但需要 API 调用）
- **精确**：countTokens API（慢但准确）

粗估还加 33% 保守缓冲：`Math.ceil(totalTokens * (4/3))`。transcript 尾部读取得到的是 API 返回的实际值，精度等同于精确级。
