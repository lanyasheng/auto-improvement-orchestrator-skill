# 从蒸馏别人的仓库到让 Skill 自己变好

## 偷师

我想把 GitHub 上别人写得好的 Claude Code Skill 搬到自己项目里用。

Claude Code 的 Skill 就是一个 SKILL.md 文件加几个脚本，告诉 AI 遇到特定任务该怎么干。GitHub 上有人整理了不错的合集：alirezarezvani/claude-skills 有 10 个质量模式，affaan-m/everything-claude-code 搞了 116 个 skill 的架构。我不想从零写，想拿来改改用。

手动抄一两个没问题。但 skill 一多——我陆续看中了三四十个——一个个搬就烦了。我写了个 skill-distill 工具，喂进去 N 个功能有重叠的 skill，它把知识分成交集、独有、冲突、冗余四类，让你确认合并方案，然后吐出一个蒸馏版。

举个具体的蒸馏例子：反 AI 味写作。GitHub 上有两个相关 skill——slopbuster（280 行，英文为主，覆盖学术/代码/散文三种模式）和 humanizer（559 行，偏通用文本去 AI 痕迹）。两个 skill 有大量重叠：都列了 AI 高频词表，都有评分量表，都做模式替换。但 slopbuster 有代码注释专用模式，humanizer 有更细的语气校准。

skill-distill 吃进去这两个再加上我自己写的一份中文写作参考笔记，跑出来一个 deslop skill：221 行 SKILL.md + 561 行 references。交集部分（AI 词汇表、评分标准）合并去重，slopbuster 独有的代码模式保留为"不适用场景"指向原 skill，humanizer 独有的 voice calibration 保留进 references。冲突的地方——比如两个 skill 对 em dash 的容忍度不同——弹出来让我手动选。

蒸馏完的 deslop 比任何一个源 skill 都好用：中英文都覆盖，有明确的两次 pass 流程（先去模式再注灵魂），有中文特有的 AI 模式表（四字堆砌、被动过多、企业套话）。这篇文章本身就是用 deslop 从 7.5 分改到 8.4 分的。

搞完手上有了二十多个 skill。问题来了：这些 skill 好使吗？

## 整体架构

先上图，下面再逐层拆。

```
                                ┌────────────────────────┐
                                │  session JSONL 日志     │
                                │  ~/.claude/projects/   │
                                └───────────┬────────────┘
                                            │
                                            v
                                ┌────────────────────────┐
                                │  session-feedback-      │
                                │  analyzer               │
                                │  correction/acceptance  │
                                └───────────┬────────────┘
                                            │
                                   feedback.jsonl
                                            │
    ┌───────────────────────────────────────┼────────────────────┐
    │                                       │                    │
    │         ┌─────────────────────────────┘                    │
    │         │                                                  │
    │         v                                                  │
    │   ┌───────────┐     ┌──────────────┐     ┌──────────┐     │
    │   │ generator │────>│discriminator │────>│evaluator │     │
    │   │ 生成候选   │     │ 多信号打分    │     │ 跑真实任务│     │
    │   └───────────┘     └──────────────┘     └────┬─────┘     │
    │         ^                                      │           │
    │         │                                      v           │
    │    traces/                               ┌──────────┐     │
    │    feedback                               │ executor │     │
    │         │                                 │ 应用+备份 │     │
    │         │                                 └────┬─────┘     │
    │         │                                      │           │
    │         │                                      v           │
    │         │                                ┌──────────┐     │
    │         └────────── revert ──────────────│   gate   │     │
    │                                          │ 6层门禁   │     │
    │                                          └────┬─────┘     │
    │                                               │           │
    │                                    keep / pending / reject│
    │                                                           │
    │   ┌─────────────────┐        ┌──────────────────┐        │
    │   │autoloop-        │        │ benchmark-store   │        │
    │   │controller       │        │ Pareto front      │        │
    │   │ 连续跑+收敛检测  │        │ 质量分级          │        │
    │   └─────────────────┘        └──────────────────┘        │
    └──────────────────────────────────────────────────────────┘
```

12 个 skill 分三层。评估层三个信号源：learner 做结构检查（$0.5/次），evaluator 跑真实任务测执行效果（$3-5/次），session-feedback-analyzer 从用户实际使用中挖隐式反馈（免费，本地 JSONL 解析）。改进层是 generator → discriminator → executor 的流水线，带 trace-aware 重试。控制层是 gate（六层门禁）、autoloop-controller（连续跑 + 收敛检测）和 benchmark-store（Pareto front + 历史基线 + 质量分级）。

## 结构检查不管用

先写了个评分器 improvement-learner，六个维度打分：

| 维度 | 权重 | 评估内容 |
|------|------|---------|
| accuracy | 25% | 12 项 SKILL.md 质量检查（frontmatter、When to Use/Not、代码示例等） |
| coverage | 15% | 结构完整性（SKILL.md 60% 基础 + 可选目录加分） |
| reliability | 20% | pytest 测试通过率（纯文本 skill 默认 1.0） |
| efficiency | 15% | SKILL.md 长度合理性（200 行以下满分） |
| security | 15% | 无硬编码密钥、无危险 API 调用 |
| trigger_quality | 10% | frontmatter description 触发路由质量 |

28 个 skill 跑了一遍，分布是这样的：

| 等级 | 分数区间 | 数量 | 代表 |
|------|---------|------|------|
| POWERFUL | >= 0.85 | 0 | — |
| SOLID（高） | 0.79-0.80 | 5 | code-review, crash-analysis, static-analysis |
| SOLID | 0.70-0.78 | 18 | cpp-expert, ios-expert, android-expert 等 |
| GENERIC | 0.65-0.69 | 5 | perf-profiler, skill-creator, release-notes, system-maintenance |

零个达到 POWERFUL。我当时还挺得意——28 个 skill 全量化了嘛。

直到我拿真实任务去验证。用 `claude -p` 把 SKILL.md 注入上下文，跑预定义的测试任务，看输出对不对。

**R² = 0.00。**

零相关。不是接近零，是字面上的零。评分 0.70 的 skill 全部任务通过，评分 0.88 的反而挂了。

| Skill | Learner 准确度 | Learner 加权分 | Evaluator 通过率 |
|-------|---------------|---------------|-----------------|
| deslop | 0.88 | 0.754 | 100% (7/7) |
| skill-creator | 0.70 | 0.715 | 100% (7/7) |
| prompt-hardening | 0.88 | 0.802 | 86% (6/7) |
| skill-distill | 0.88 | 0.756 | 86% (6/7) |
| improvement-gate | 0.76 | 0.754 | 71% (5/7) |

加权分 r = -0.40，方向是反的——learner 分越高，实际执行越差。

为什么？拆开看 26 个检查项：

| 检查项特征 | 数量 | 问题 |
|-----------|------|------|
| 全部 skill 通过 | 17/26 | 零方差，无法区分好坏 |
| 有区分度 | 6/26 | 有正有负 |
| 反向预测 | 3/26 | 通过的 skill 实际执行更差 |

反向预测的三个检查项：frontmatter 有 version 字段（r=-0.76）、有 references 目录（r=-0.54）、示例包含具体 I/O（r=-0.54）。可能的解释：最用心维护 frontmatter 格式的 skill 作者，把精力花在了文档美化而不是指令质量上。

统计上也有问题：N=5 个 skill 的相关性分析，功效很低，一个异常值就能主导。但即便样本量翻倍，17/26 的零方差检查项是结构性问题——这些 checklist 测的是文档卫生，不是指导质量。

重构了一版评估（5 个门槛检查 + 10 个执行预测检查），准确度相关性还是 r = -0.0001。

结论不是"结构不重要"，而是"我们的结构检查测错了东西"。这是整个项目最重要的发现。

## 两层评估架构

```
┌──────────────────────────────────────────────────────┐
│                     评估三信号                        │
│                                                      │
│  ┌─────────────────┐      ┌─────────────────────┐   │
│  │ learner         │      │ evaluator            │   │
│  │ 结构检查 = lint  │      │ 执行测试 = test      │   │
│  │ $0.5/次         │      │ $3-5/次              │   │
│  │ 6维 checklist   │      │ task suite + judge   │   │
│  │ R²=0.00 vs 执行 │      │ 真实 claude -p 调用  │   │
│  └─────────────────┘      └─────────────────────┘   │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ session-feedback-analyzer                    │    │
│  │ 用户隐式反馈 = production monitoring        │    │
│  │ 免费（本地 JSONL 解析）                       │    │
│  │ correction_rate + dimension hotspots         │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

结构层当 lint：通过了不代表好，但不通过的肯定有基础问题（缺 frontmatter、没 When to Use）。

执行层是真金白银。task suite 格式长这样：

```yaml
skill_id: "release-notes-generator"
version: "1.0"
tasks:
  - id: "isolation-01"
    description: "iOS release notes must not contain Android keywords"
    prompt: |
      Generate iOS platform release notes for these commits:
      - fix: fixed text click handler
      - feat: added unified template fetch API
    judge:
      type: "contains"
      expected: ["Version Overview", "New Features", "Bug Fixes"]
    timeout_seconds: 120

  - id: "leakage-01"
    description: "No Android keyword leakage in iOS notes"
    judge:
      type: "llm-rubric"
      rubric: |
        Check output does NOT contain "Kotlin", "Android", "Java".
        Score 1.0 if clean, 0.0 if any leakage.
      pass_threshold: 0.8
```

三种 judge：ContainsJudge（关键词检查）、PytestJudge（pytest 结构验证）、LLMRubricJudge（语义评分）。PytestJudge 有路径安全约束：`test_file` 必须以 `fixtures/` 开头防止目录穿越。

### 实验 3：release-notes skill 执行测试

7 个任务，用真实 `claude -p` 跑（不是 mock），结果 86% 通过率（6/7）：

| 任务 | Judge 类型 | 结果 |
|------|-----------|------|
| 结构检查 | ContainsJudge | PASS |
| 平台隔离（iOS） | ContainsJudge | PASS |
| 平台泄露检测 | LLMRubricJudge | PASS |
| Commit 分类 | ContainsJudge | PASS |
| Commit hash 引用 | ContainsJudge | PASS |
| 坏 release notes 审查 | ContainsJudge | PASS |
| 模块分类 | ContainsJudge | **FAIL** |

挂在模块分类上。SKILL.md 没指定怎么把改动文件归到框架模块里，Claude 猜错了模块名。这个 skill 的 frontmatter 完整、段落齐全、示例丰富——结构评分 0.83。但它缺了一条关键的领域知识，这条知识只有在你真正跑任务的时候才会暴露。

结构检查永远找不到这种问题。

### 实验 6：Skill 到底有没有用？

一个更根本的问题：加载 Skill 和不加载 Skill，Claude 表现有区别吗？

prompt-hardening skill 的 7 个任务，分两组跑——Group A 裸跑 Claude，Group B 注入 SKILL.md：

| 任务 | 裸跑 Claude | 加载 Skill |
|------|------------|-----------|
| P1 三重强化 | PASS | PASS |
| P5 反推理 | PASS | PASS |
| 审计输出格式（/16 后缀） | **PASS** | **FAIL** |
| CLI 路径（audit.sh） | **FAIL** | **PASS** |
| 模式选择 | PASS | PASS |
| 可靠性等级 | PASS | PASS |
| 端到端硬化 | PASS | PASS |
| **通过率** | **86%** | **86%** |

通过率一模一样。但挂的任务不同。

裸跑时 Claude 不知道 `audit.sh` 这个工具的路径——FAIL。加了 skill 后它知道了——PASS。但 skill 改变了 Claude 的输出偏好，它开始省略 `/16` 后缀——FAIL。

三个结论：

Skill 的价值在知识注入。Claude 本来就懂 MUST/NEVER 模式和反推理模式。Skill 真正贡献的是项目特定知识：`audit.sh` 的路径、P1-P16 编号体系、可靠性百分比。

Skill 会引入新的失败模式。每次 skill 变更本质上是 tradeoff——你修好了 A 任务，B 任务可能就坏了。

单看通过率看不出问题。86% 和 86% 看起来一样，但底下的任务分布完全不同。评估必须看逐任务对比，不能只看聚合指标。

### 设计决策：为什么默认 pass@1 而不是 pass@3？

LLM 输出不确定。同一个 prompt 跑三次取最好结果（pass@3）信号更稳。但成本翻了三倍：7 个任务 × pass@3 = 21 次 API 调用，一次评估从 $3 涨到 $9。

默认 pass@1 保持快速迭代的成本可控。pass@3 通过 `--pass-k 3` 开放给高风险决策（比如发布到 marketplace 之前）。

### 设计决策：为什么不用 Git Worktree？

最初用 `git worktree add` 给每次评估创建隔离分支。架构上干净，但实际很痛——创建销毁 worktree 比 `tempfile.mkdtemp()` 慢得多，worktree 管理加了 50 多行 git 管道代码，而实际上评估只需要 SKILL.md 的内容，不需要整个 repo checkout。

现在的做法：临时目录 + prompt 注入。把候选 SKILL.md 写到临时文件，拼到 task prompt 前面，跑 `claude -p`，检查输出。快 10 倍，对 single-file 评估来说隔离保证一样。

## 用户反馈闭环

task suite 测的是作者预设的场景。用户在真实使用中遇到的问题，task suite 未必覆盖。我实现了一个 session-feedback-analyzer，从 Claude Code 的会话日志里挖隐式反馈信号。

工作流程：

```
~/.claude/projects/**/*.jsonl
         │
         v
  detect_skill_invocations()     ── 找 Skill tool_use / slash command
         │
         v
  classify_outcome()             ── 3-turn 影响窗口内分类
         │                          correction / acceptance / partial
         v
  feedback-store/feedback.jsonl  ── 追加写入，SHA256 去重
         │
         v
  correction_rate per skill      ── (corrections + 0.5*partials) / total
```

Skill 调用检测走两条路径。一是 assistant 消息里的 `tool_use`，`name == "Skill"` 时提取 `input.skill` 作为 skill_id。二是 system 消息里的 `<command-name>` 标签（用户敲 `/deslop` 这种 slash command）。内置命令（help、clear、resume）跳过。

纠正信号的检测规则：

| 信号类型 | 检测方式 | 置信度 |
|---------|---------|--------|
| 明确否定 | "不对"/"错了"/"wrong" 等关键词 | 0.9 |
| 撤销操作 | 窗口内出现 git checkout/restore | 0.9 |
| 重做请求 | "重新来"/"redo"/"try again" | 0.9 |
| 部分纠正 | 接受词 + 转折词同时出现（"可以但是"） | 0.7 |
| 静默继续 | 用户换话题，未纠正前一个输出 | 0.6 |

部分纠正计 0.5 个纠正。比如用户说"这个可以，但是命名应该用 camelCase"——skill 大方向对了，但某个细节不对。这比完全否定轻，但仍然是改进信号。

每个纠正事件还做维度归因——通过关键词匹配把纠正归到 accuracy（"命名"/"格式"）、coverage（"漏了"/"缺少"）、reliability（"又"/"重复"）、efficiency（"太慢"/"太长"）、security（"密钥"/"token"）、trigger_quality（"不该触发"）六个维度。归不上的留 null。

在我自己的 session 数据上跑了一遍：

```
Analyzed 28 feedback events
  Outcomes: {'correction': 9, 'partial': 19}
  Top skills: [('code-review-enhanced', 9), ('deslop', 5),
               ('read', 3), ('prompt-hardening', 2)]
```

code-review-enhanced 被纠正最多（9 次）。这跟我的体感一致——它生成的 review 评论经常需要我手动调整措辞和优先级。

这个信号整合进改进流水线的方式：generator 自动发现 `feedback-store/` 目录（通过 `lib/common.py:load_source_paths()` 的自动发现机制），读取 feedback.jsonl，按维度聚合纠正热点，优先改进被用户纠正最多的维度。autoloop-controller 用 correction_rate 是否下降作为额外的收敛信号——如果改了三轮用户还是在纠正同样的问题，说明改进方向不对，停下来。

## 自动改进流水线

能测了，就想让它自动变好。

直接重试不行。LLM 容易翻来覆去犯同一个错——我们叫它 "Ralph Wiggum loop"，说着 "I'm helping!" 然后帮倒忙。原版 Simpsons 梗，但这个问题真的存在：给 LLM 说"你上次做错了，再来一次"，它会换个方式犯同样的错。

解法是带记忆的重试（trace-aware retry）。失败追踪的数据结构：

```json
{
  "type": "failure_trace",
  "candidate_id": "docs-accuracy-001",
  "decision": "revert",
  "reason": "accuracy regressed 12%",
  "gate_blockers": ["RegressionGate: accuracy 0.85 -> 0.75"],
  "diff": "- ## When to Use\n+ ## Usage Scenarios\n..."
}
```

这个追踪注入到下一轮的 generator prompt 里。generator 读到"docs-accuracy 策略在 accuracy 维度上失败了 3 次"，就跳过这个策略。思路来自 GEPA 论文（ICLR 2026）的 trace-aware reflection——失败不是白失败，追踪信息喂回去让下一轮避开同样的坑。

### Generator 怎么读反馈

generator 通过 `--source` 接收反馈文件。`lib/common.py` 的 `load_source_paths()` 自动发现 target skill 目录下的 `memory/`、`learnings/`、`.feedback/` 和 `feedback-store/`。每个源文件被 `expand_source()` 展开为 `{path, kind, characters, snippet}` 格式，然后 `classify_feedback()` 按关键词分桶：limitations、examples、workflow、tests、guardrails、prompt。

对于 evaluator 的失败数据，generator 有专门的 `_find_evaluator_failures()` 函数去读 baseline-failures JSON。对于用户反馈数据，新加的 `_find_correction_hotspots()` 读 feedback.jsonl，按维度聚合纠正次数。两个信号一起决定候选的优先级：evaluator 失败的任务优先修、用户纠正最多的维度优先改。

### Discriminator 多信号打分

候选生成后要打分。discriminator 支持四种打分模式叠加：

| 模式 | 开关 | 测量内容 |
|------|------|---------|
| 启发式规则 | 默认 | 类别加分 + 来源引用 + 风险惩罚 |
| + Evaluator 证据 | `--use-evaluator-evidence` | 启发式 70% + evaluator rubric 30% |
| + LLM Judge | `--llm-judge {claude,openai,mock}` | 启发式 60% + LLM 语义分析 40% |
| + 盲审 Panel | `--panel` | 2+ 独立审阅者，认知标签输出 |

盲审 panel 里，structural 审阅者和 conservative 审阅者独立评分，产出三种认知标签：CONSENSUS（全同意）、VERIFIED（多数同意）、DISPUTED（有分歧）。DISPUTED 的候选自动进入人工审核队列。

### Gate 六层门禁

Gate 的六层门禁，任一层失败就拒绝，没有例外：

| 层 | 门禁 | 通过条件 |
|----|------|---------
| 1 | SchemaGate | 执行结果 JSON 结构合法 |
| 2 | CompileGate | 目标文件语法正确 |
| 3 | LintGate | 无新增 lint 告警 |
| 4 | RegressionGate | Pareto 每个维度无退步（5% 容差） |
| 5 | ReviewGate | 盲审共识非 DISPUTED+reject |
| 6 | HumanReviewGate | 高风险候选需人工确认 |

第 4 层是核心。RegressionGate 用的 Pareto front 回归检测，代码（`lib/pareto.py`）：

```python
def check_regression(self, scores: dict[str, float]) -> dict:
    best_per_dim: dict[str, float] = {}
    for entry in self.entries:
        for dim, score in entry.scores.items():
            if dim not in best_per_dim or score > best_per_dim[dim]:
                best_per_dim[dim] = score

    regressions = []
    for dim, best in best_per_dim.items():
        new_score = scores.get(dim, 0)
        if new_score < best * 0.95:  # 5% tolerance
            regressions.append({"dimension": dim, "best": best, "new": new_score})

    return {"regressed": len(regressions) > 0, "regressions": regressions}
```

为什么不用一个总分？accuracy=0.85/coverage=0.70 改成 accuracy=0.70/coverage=0.85，加权得分完全相同。但准确度被毁了。单一标量把这件事藏起来了。Pareto front 要求每个维度独立不退步，5% 容差是为了排除测量噪声——LLM-as-Judge 的评分每次跑会有小波动，不能因为波动就拒绝本来好的改进。

### Executor 怎么改文件

executor 支持四种操作：`append_markdown_section`（追加段落）、`replace_markdown_section`（按标题匹配替换段落）、`insert_before_section`（在某标题前插入）、`update_yaml_frontmatter`（合并 YAML 字段）。

每次执行前自动备份到 `executions/backups/<run-id>/`，生成一个 receipt JSON 记录原始内容和 rollback 指针。`--dry-run` 可以预览变更而不实际写入。rollback.py 读 receipt 恢复原始状态。

目前只有 low-risk 的文档类候选（docs/reference/guardrail 类别）自动执行。prompt 类、workflow 类、code 类候选进 pending 队列等人工审核。这个限制是故意的——无人值守运行时不能让 AI 随便改 prompt 措辞。

## 实验数据

### 实验 2：单 Skill 自改进

目标：system-maintenance skill，起始分 0.653（GENERIC 级别）。

| 轮次 | 维度 | 做了什么 | 改前分 | 改后分 | 决策 |
|------|------|---------|--------|--------|------|
| 1 | accuracy | 加 frontmatter + When to Use/Not | 0.653 | 0.715 | keep |
| 2 | reliability | 自动生成测试桩 | 0.715 | 0.770 | keep |
| 3 | accuracy | 加 `<example>` 和 `<anti-example>` 标签 | 0.770 | 0.803 | keep |

3 轮全部保留。六维度变化：

```
维度             改前     改后     变化
accuracy         0.67     0.85    +0.18
coverage         0.60     0.80    +0.20
reliability      0.30     1.00    +0.70
efficiency       0.87     0.85    -0.02 (在 5% 容差内)
security         0.83     0.83     0.00
trigger_quality  0.60     0.80    +0.20
```

最大跳跃是 reliability：0.30 到 1.00。原因很直接——learner 发现 skill 有脚本但没测试，自动生成了测试桩，测试跑过了。"有脚本无测试"得 0.30，"有脚本有测试且通过"得 1.00。

efficiency 从 0.87 降到 0.85。加了 frontmatter 和 example 段落后文档变长了，但降幅在 5% 容差内，RegressionGate 放行。

### 实验 4：批量改进 4 个 GENERIC Skill

| Skill | 改进前 | 改进后 | 保留/总尝试 | 关键改进 |
|-------|--------|--------|------------|---------|
| system-maintenance | 0.653 | 0.803 | 3/3 | frontmatter + 示例 + 测试桩 |
| perf-profiler | 0.661 | 0.803 | 2/3 | 测试桩 + frontmatter |
| component-dev | 0.665 | 0.798 | 1/3 | 补缺失段落 |
| release-notes | 0.681 | 0.831 | 3/3 | 全维度改进 |

平均 +0.138，从 GENERIC 全部升到 SOLID。

保留率在 1/3 到 3/3 之间。perf-profiler 的 2/3 意思是跑了 3 个候选，其中 1 个被 gate 拦住（某个维度退步了，revert），另外 2 个保留。component-dev 的 1/3 更保守——3 个候选里 2 个在 gate 被拒，只有 1 个活下来。这说明门禁在工作。

四个 skill 一起改，API 费用 $15-20。

最管用的改进不是改措辞，是补结构。加 frontmatter，加 `<example>` 标签，加测试。这些东西缺失时分数低，补上后提升大，而且 learner 能稳定检测到。

### 自评报告的发现

我用同样的评估管线给自己的 12 个流水线 skill 打了分。综合均分 83.3%，只有 benchmark-store 达到了 POWERFUL（86.2%）。

一个系统性问题：7 个 skill 的 SKILL.md 全是自动生成骨架，每个都缺 "When NOT to Use" 段落（全是占位符 `[Define exclusion conditions here]`），全部缺 `triggers:` 字段（trigger_quality 被限在 0.40）。代码实现和测试远超文档——discriminator 有 620 行的 score.py 实现了多审阅者盲审 panel，SKILL.md 只有 26 行。learner 有 878 行的核心引擎，SKILL.md 只有 27 行。

这是自己项目的"鞋匠没鞋穿"问题：评估框架本身的 SKILL.md 文档恰恰是文档质量最差的。

## 行业对比

| 系统 | 优化对象 | 粒度 | diff 可读？ | 多维度？ | 反馈来源 |
|------|---------|------|-----------|---------|---------
| 本项目 | SKILL.md 结构化文档 | 段落/section | 是 | 6维 Pareto | task suite + 用户隐式反馈 |
| DSPy | prompt token | token 级 | 否（贝叶斯搜索） | 单目标 | 用户定义 metric |
| TextGrad | LLM 输出变量 | token 级 | 否 | 单目标 | LLM 生成的"梯度" |
| ADAS | agent 架构 | 组件级 | 部分 | 单目标 | benchmark |
| GEPA | 代码生成 | 函数级 | 是 | 单目标 | trace reflection |
| PromptFoo | prompt assertion | prompt 级 | 是 | 单维（pass rate） | assertion suite |
| DeepEval | LLM 输出 | 输出级 | N/A | 多 metric | rubric |
| LangSmith | agent trace | trace 级 | N/A | 多 metric | 可观测性平台 |
| Karpathy autoresearch | train.py | 文件级 | 是 | 单标量 val_bpb | 训练 loss |

DSPy 做的事表面上很像——自动优化 prompt。但它是在 token 粒度上用贝叶斯搜索（MIPROv2 optimizer），改完你未必看得懂改了什么。我操作的是 SKILL.md 这个有结构的文档，diff 是人能读的。代价是搜索空间小得多，但对 skill 来说够用——候选改的是段落、示例、frontmatter 字段，不是逐字调 prompt。

TextGrad 把自动微分的概念搬到了文本上——用 LLM 生成的文字反馈当"梯度"来迭代优化。概念漂亮，但需要一个可微的目标函数。skill 的六个质量维度不满足这个条件——accuracy 和 coverage 之间没有连续的梯度关系。

LangSmith 和 Langfuse 是可观测性平台，做 trace、做 monitoring，但不关闭改进循环。它们告诉你"这里出了问题"，但不自动修。session-feedback-analyzer 和 LangSmith 的 trace 采集思路接近，但下游直接对接 generator 形成闭环，而不是生成一个 dashboard 给人看。

GEPA 的 trace-aware reflection 我直接借用了。它在代码生成领域已经验证过——失败追踪注入下一轮 prompt 能显著减少重复失败。搬到 skill 改进上没什么障碍，因为失败结构是类似的：都是"改了什么、为什么被拒、哪个检查没过"。

目前没有看到其他开源项目做"从用户会话日志挖隐式反馈来优化 agent 指令"这件事。最接近的是 RLHF 的偏好信号，但那是在模型训练层面，不是 prompt/skill 层面。

## 连续跑

改一次不够。autoloop-controller 包了个外层循环，设最大轮次和花费上限。它检测三种停止信号：

```python
# 分数平台期：最近 N 轮没超过历史最好
def detect_plateau(score_history, window=3):
    recent = score_history[-window:]
    earlier = score_history[:-window]
    return max(h["weighted_score"] for h in recent) <= \
           max(h["weighted_score"] for h in earlier)

# 震荡：keep-reject 交替出现
def detect_oscillation(score_history, window=4):
    decisions = [h["decision"] for h in score_history[-window:]]
    return decisions in [["keep","reject"]*2, ["reject","keep"]*2]

# 用户反馈平台期：correction_rate 没下降
def detect_user_feedback_plateau(correction_rates, window=3):
    recent = correction_rates[-window:]
    return all(r >= recent[0] * 0.95 for r in recent[1:])
```

第三个是新加的。如果改了三轮，用户还是在纠正同样的问题（correction_rate 没有下降 5% 以上），说明改进方向不对，停下来换个思路。

状态持久化到 `autoloop_state.json`，每轮结束写一次。进程挂了重启读状态接着跑。另外有一个 append-only 的 `iteration_log.jsonl` 做完整审计追踪。

Karpathy 用 700 次自主实验在两天里提升了 11%。我的情况麻烦一些——他优化的是一个数 val_bpb，我得看六个维度，accuracy 升了但 coverage 降了算好还是算坏？所以才需要 Pareto front。但核心模式一样：修改→测量→保留或回滚→重复。

## 还没解的

最困扰我的是循环依赖。task suite 和 SKILL.md 通常一个人写。你写了 skill 教 Claude 怎么做 X，然后你写测试检查 Claude 有没有做 X。当然能通过——你测的就是你教的。这像是考试出题人自己做自己的卷子。

已经做了两件事来缓解。第一个是 session-feedback-analyzer——从用户实际使用中挖信号。用户改了 AI 的输出，这个动作本身就是 skill 有问题的证据。这是独立于 task suite 的信号来源。第二个是 null-skill calibration（在 skill-forge 里）——生成 task suite 时过滤掉裸跑 Claude 就能通过的任务。如果一个测试不加载 skill 也能过，那它测的不是 skill 的贡献，是模型的通用能力。

还不够。更好的方案可能是：让 generator 自动造对抗性测试（"找一个能让这个 skill 失败的输入"），引入社区贡献的 task suite（写 suite 的人没看过 SKILL.md），或者做 held-out 拆分（一半任务用于改进迭代，一半只用于最终评估，不参与优化循环）。

另一个更深的问题：skill 本身可能是有副作用的。加载 prompt-hardening skill 后，通过率跟裸跑一样是 86%，但是不同的 86%。你修好了 A 任务，B 任务可能就坏了。这不是 bug，是 skill 工作方式的固有属性——你往 Claude 的上下文里注入了新的指令，它的注意力分配就变了。怎么量化这个 tradeoff，我还没想到好办法。

## 代码

12 个 skill，共享 Python 库，353 个测试，依赖只有 pyyaml 和 pytest。

[github.com/lanyasheng/auto-improvement-orchestrator-skill](https://github.com/lanyasheng/auto-improvement-orchestrator-skill)

task suite 怎么写才能不陷入循环依赖，这个问题我反复想了几周还是没有满意的答案。如果你在做类似的事，我想听听你的做法。
