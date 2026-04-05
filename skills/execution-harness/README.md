# Execution Harness Patterns

Claude Code agent 执行可靠性增强。21 个可组合模式，解决 agent 提前停止、上下文丢失、重试死循环、限速挂死、crash 状态丢失。

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](../../LICENSE)

蒸馏自 Claude Code 内部架构和 [oh-my-claudecode (OMC)](https://github.com/anthropics/oh-my-claudecode) 生产实践。

## Quick Start

```bash
# 初始化 Ralph 持续执行（最多 50 轮迭代，crash 后自动恢复）
bash scripts/ralph-init.sh my-session

# 取消执行（30s TTL 安全窗口）
bash scripts/ralph-cancel.sh my-session "任务已完成"
```

Ralph Stop Hook 通过 Claude Code hooks 机制自动拦截 agent 停止行为，无需手动干预。

## 核心问题

| 失败类型 | 症状 | 对应模式 |
|----------|------|----------|
| **提前停止** | 多文件修改只改了一部分就停了 | Ralph (P01) |
| **上下文丢失** | context 压缩后 agent 忘了设计决策 | Handoff (P02), Compaction Extract (P08) |
| **重试死循环** | 工具调用反复失败，agent 一直试同一个命令 | Tool Error Escalation (P03) |
| **限速挂死** | API 限速后 tmux session 无响应 | Rate Limit Recovery (P04) |
| **crash 状态丢失** | 需要从头开始而不是断点恢复 | Checkpoint Rollback (P19), Session State |

## 21 Patterns

| # | Pattern | 分类 | 一句话 |
|---|---------|------|--------|
| 01 | **Ralph** | 持续执行 | Stop hook 拦截提前停止，5 个安全不变量 |
| 02 | **Handoff** | 上下文存活 | 5 节文档在 compaction 后注入恢复决策 |
| 03 | **Tool Error** | 错误处理 | 3 层升级：日志 → 提示 → 强制替代 |
| 04 | **Rate Limit** | 恢复 | 指数退避 + 自动 provider 切换 |
| 05 | **Context Estimation** | 预算 | 预估 token 消耗，提前触发 compaction |
| 06 | **Atomic Write** | 可靠性 | write-then-rename 防止写入中断 |
| 07 | **Cancel TTL** | 安全 | 30s 过期的取消信号，防止残留信号误杀 |
| 08 | **Compaction Extract** | 上下文存活 | compaction 前提取关键决策到持久化文件 |
| 09 | **Denial Tracking** | 可观测 | 记录用户拒绝工具调用的模式 |
| 10 | **Memory Consolidation** | 记忆 | HOT/WARM/COLD 三层记忆合并 |
| 11 | **Hook Bracket** | 生命周期 | setup/teardown 括号，确保清理 |
| 12 | **Scoped Hooks** | 隔离 | 按任务类型加载不同 hook 集 |
| 13 | **Doubt Gate** | 安全 | 不确定时询问而非猜测 |
| 14 | **Delegation Modes** | 调度 | 选择 subagent / tmux worker / sequential |
| 15 | **Post-Edit Diagnostics** | 质量 | 编辑后自动跑 lint/test 验证 |
| 16 | **Adaptive Complexity** | 效率 | 按任务复杂度调整 agent 行为 |
| 17 | **Stale Session Daemon** | 清理 | 自动清理过期 session 状态 |
| 18 | **Hook Profiles** | 配置 | 预设 hook 组合（dev/ci/review） |
| 19 | **Checkpoint Rollback** | 恢复 | 失败时回滚到上一个 checkpoint |
| 20 | **Token Budget** | 预算 | 跟踪和限制 token 消耗 |
| 21 | **Model Fallback** | 恢复 | 主模型失败时降级到备用模型 |

每个模式的完整实现细节见 `references/patterns/01-ralph.md` ~ `21-model-fallback.md`。

## 常见场景选型

| 场景 | 推荐组合 |
|------|----------|
| 多文件重构（怕停） | Ralph + Handoff + Post-Edit Diagnostics |
| 长任务（怕丢上下文） | Handoff + Compaction Extract + Context Estimation |
| 不稳定 API（怕挂） | Tool Error + Rate Limit + Model Fallback |
| CI 流水线 | Hook Profiles(ci) + Scoped Hooks + Hook Bracket |
| crash 恢复 | Checkpoint Rollback + Ralph(crash recovery) |

## Scripts

| 脚本 | 用途 | 用法 |
|------|------|------|
| `ralph-init.sh` | 初始化 Ralph 状态 | `bash scripts/ralph-init.sh <session-id> [max-iter]` |
| `ralph-stop-hook.sh` | Stop hook（读 stdin 输出 JSON） | Claude Code hooks 自动调用 |
| `ralph-cancel.sh` | 发送 30s TTL 取消信号 | `bash scripts/ralph-cancel.sh <session-id> [reason]` |

## Session State

所有状态统一在 `~/.openclaw/shared-context/sessions/<session-id>/` 下：

```
sessions/my-session/
├── ralph.json          # Ralph 迭代状态
├── cancel.json         # 取消信号（带 TTL）
├── handoffs/           # Handoff 文档
├── tool-errors.json    # 工具错误升级记录
├── denials.json        # 用户拒绝记录
├── bracket.json        # Hook 生命周期状态
└── learnings.jsonl     # 累积学习记录
```

详见 `references/session-state-layout.md`。

## Project Structure

```
execution-harness/
├── SKILL.md                # AI 消费的模式指南（核心）
├── task_suite.yaml          # 10 个评估任务
├── scripts/                 # Ralph 相关 shell 脚本
├── references/
│   ├── patterns/            # 21 个模式的完整文档
│   ├── session-state-layout.md
│   └── quality-pipeline-integration.md
└── tests/
    └── test_ralph.py        # Ralph 脚本的 pytest 测试
```

## Related Skills

| Skill | 关系 |
|-------|------|
| improvement-evaluator | Ralph 为评估运行提供持续执行保障 |
| autoloop-controller | Handoff 文档为迭代间提供上下文存活 |
| improvement-gate | Hook bracket 为门禁提供 setup/teardown |
| prompt-hardening | 硬化后的 prompt 配合 Ralph 更可靠 |

## License

[MIT](../../LICENSE)
