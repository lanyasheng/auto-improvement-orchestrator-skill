# 从蒸馏别人的仓库到让 Skill 自己变好

三个月前我开始折腾 Claude Code 的 Skill 系统，最初只是想把 GitHub 上别人写的好 skill 搬过来用。后来不知不觉越滚越大——写蒸馏工具、写评估器、发现评估器打的分跟实际效果毫无关系（R²=0.00，后面细说）、重新搭评估、搭自动改进管线、搭持续运行控制器、搭用户反馈闭环。

回头看这三个月，最有价值的不是写了多少代码，而是中间几个改变我想法的实验结果。

## 偷师

我想把 GitHub 上别人写得好的 Claude Code Skill 搬到自己项目里用。

Claude Code 的 Skill 就是一个 SKILL.md 文件加几个脚本，告诉 AI 遇到特定任务该怎么干。GitHub 上有人整理了不错的合集：alirezarezvani/claude-skills 有 10 个质量模式，affaan-m/everything-claude-code 搞了 116 个 skill 的架构。我不想从零写，想拿来改改用。

手动抄一两个没问题。但 skill 一多——我陆续看中了三四十个——一个个搬就烦了。我写了个 skill-distill 工具，喂进去 N 个功能有重叠的 skill，它把知识分成交集、独有、冲突、冗余四类，让你确认合并方案，然后吐出一个蒸馏版。

举个具体的蒸馏例子：反 AI 味写作。GitHub 上有两个相关 skill——slopbuster（280 行，英文为主，覆盖学术/代码/散文三种模式）和 humanizer（559 行，偏通用文本去 AI 痕迹）。两个 skill 有大量重叠：都列了 AI 高频词表，都有评分量表，都做模式替换。但 slopbuster 有代码注释专用模式，humanizer 有更细的语气校准。

skill-distill 吃进去这两个再加上我自己写的一份中文写作参考笔记，跑出来一个 deslop skill：221 行 SKILL.md + 561 行 references。交集部分（AI 词汇表、评分标准）合并去重，slopbuster 独有的代码模式保留为"不适用场景"指向原 skill，humanizer 独有的 voice calibration 保留进 references。冲突的地方——比如两个 skill 对 em dash 的容忍度不同——弹出来让我手动选。

蒸馏完的 deslop 比任何一个源 skill 都好用：中英文都覆盖，有明确的两次 pass 流程（先去模式再注灵魂），有中文特有的 AI 模式表（四字堆砌、被动过多、企业套话）。这篇文章本身就是用 deslop 从 7.5 分改到 8.4 分的。

另一个蒸馏案例是 execution-harness。这个的来源更杂：claude-reviews-claude 的 17 篇架构文章、oh-my-claudecode (OMC) 的 npm 源码、ccunpacked.dev 的 Claude Code 拆解、luongnv89/claude-howto 的实践 tips。四个来源讲的都是同一件事——怎么让 dispatched agent 不要半路停下来——但每个的侧重点不同。

OMC 的核心贡献是 Ralph 模式：利用 Claude Code 的 Stop hook，在 agent 试图结束 session 时拦截它，注入"你还没做完"的续航指令。这个模式有个致命的细节——它只在 interactive 模式下工作，headless `-p` 模式的 Stop hook 根本不触发。我在 OMC 源码里花了两个小时才确认这一点，因为文档没写。

claude-reviews-claude 贡献了 Handoff 文档模式——agent 在阶段结束时把 Decided/Rejected/Risks 写到磁盘，这样 context 被压缩后重要决策不会丢。ccunpacked 贡献了 context 估算的具体实现（只读 transcript 最后 4KB 而不是整个文件，因为那东西可以长到 100MB）。claude-howto 贡献了工具错误升级——agent 反复 `cargo build` 但 cargo 没装，第 5 次失败后强制换方案。

蒸馏后是 18 个可组合的 pattern，从"Ralph 持续执行"到"Hook Runtime Profiles"。质量分从 0.63 升到 0.93。但这个蒸馏过程比 deslop 难多了——deslop 的三个源都是同类文档（AI 检测规则），而 execution-harness 的四个源分别是博客文章、npm 包源码、技术拆解网站和 tips 集合，格式和抽象层次完全不同。skill-distill 的"冲突解决"步骤在这里几乎每条知识都要手动介入。

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
    │                                          │ 7层门禁   │     │
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

15 个 skill 分三层。评估层三个信号源：learner 做结构检查（$0.5/次），evaluator 跑真实任务测执行效果（$3-5/次），session-feedback-analyzer 从用户实际使用中挖隐式反馈（免费，本地 JSONL 解析）。改进层是 generator → discriminator → executor 的流水线，带 trace-aware 重试。控制层是 gate（七层门禁）、autoloop-controller（连续跑 + 收敛检测）和 benchmark-store（Pareto front + 历史基线 + 质量分级）。

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

accuracy 的 12 项检查很朴素——有 YAML frontmatter 吗？有 name/description 吗？有 When to Use 段落吗？有代码示例吗？有 `<example>` 标签吗？每一项就是个 bool，通过得分不通过不得分。这些检查是从 alirezarezvani/claude-skills 的 10 个质量模式里提炼出来的，加了两项我自己觉得重要的（有 `<anti-example>` 标签、示例包含具体 I/O）。

后来觉得纯 checklist 太粗了，加了 LLM-as-Judge 做第二层。让 Claude 当评委，从四个角度给 SKILL.md 打分：clarity（读完你知道该怎么做吗）、specificity（有没有具体到可以复制粘贴的参数）、consistency（命名和接口风格统一吗）、safety（错误处理和回滚有没有到位）。用 `claude -p` 跑，一次大概 $0.5。Mock 模式用于测试时不烧钱——跑 289 个测试的时候不能每次都调 API。

综合分 = 结构评分 × 50% + 语义评分 × 50%。这个比例后来证明可能不太对——语义评分的区分度远高于结构评分，也许应该给语义更多权重。但改权重又会让历史分数不可比，所以一直没动。

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

这组数据让我改变了对 skill 的看法。以前我觉得 skill 是在"教 Claude 新能力"。不是。Claude 本来就懂 MUST/NEVER 模式和反推理模式。Skill 真正贡献的是项目特定知识——`audit.sh` 的路径、P1-P16 编号体系、可靠性百分比。这些是模型训练数据里没有的东西。

但注入知识有代价。skill 改变了 Claude 的注意力分配，输出格式偏好跟着动。修好了 A 任务，B 任务可能就坏了。86% 和 86% 的通过率看着一样，底下的任务分布完全不同。这意味着评估不能只看聚合指标——必须看逐任务对比，跟踪哪些任务因为 skill 变更而从 PASS 变 FAIL 或反过来。

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

### 整合进流水线

generator 通过 `lib/common.py:load_source_paths()` 自动发现 `feedback-store/` 目录。这个函数本来就会自动扫描 target skill 下的 `memory/`、`learnings/`、`.feedback/` 子目录，我只加了一行让它也扫 `feedback-store/`。读到 feedback.jsonl 后，`_find_correction_hotspots()` 按维度聚合纠正次数，返回类似 `{"accuracy": 7, "coverage": 3}` 的热点图。generator 根据这个热点图决定优先改哪个维度。

autoloop-controller 用 correction_rate 是否下降作为额外的收敛信号。具体实现是 `detect_user_feedback_plateau()`: 取最近 3 轮的 correction_rate，如果没有一轮比第一轮低 5% 以上，就判定平台期。这个函数跟 `detect_plateau()` 和 `detect_oscillation()` 并列，三种停止信号用 OR 逻辑——任一个触发就停。

一个微妙的问题：feedback 数据是滞后的。用户的纠正行为发生在 skill 被使用的时候，而 autoloop 改进 skill 是另一个时间。改进后的 skill 需要被用户实际使用一段时间才能产生新的 feedback 数据。所以 feedback plateau 检测在 autoloop 的前几轮基本不起作用——它需要至少一周的使用数据才有信号。目前的做法是在 correction_rate 的计算里设了 `min_invocations=5` 的最低门槛，样本不够就不计算。

### 隐私设计

所有数据都在本地。feedback.jsonl 存在项目目录里，不会发到任何服务器。user_message_snippet 限 200 字符，只用于维度归因的 debug，可以通过 `--no-snippets` 完全禁用。`~/.claude/feedback-config.json` 里写 `{"enabled": false}` 就能关掉整个采集。超过 90 天的事件自动归档到 `archive/` 目录，不参与活跃指标计算。

这些约束是参考了 LangSmith 的隐私设计——它也做 trace 采集但允许 PII redaction 和数据保留策略。区别是 LangSmith 是 SaaS（数据上云），我们是纯本地。

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

### Learner 三层记忆

learner 维护一个 HOT/WARM/COLD 记忆层级。HOT 最多 100 条，总是加载；WARM 无上限，按需加载；COLD 是 3 个月不活跃的归档（计划中，还没实现）。

每次改进尝试（不管成功失败）都记录到记忆里。记录的内容包括：哪个策略、作用在哪个维度、结果是 keep 还是 revert、得分变化。HOT 层溢出时，按 `hit_count` 排序，访问最少的条目淘汰到 WARM。

这个记忆系统的实际用途：generator 在生成候选时查 HOT 层，如果发现"加 frontmatter"策略在 accuracy 维度上已经成功了 3 次，它会跳过这个策略去找下一个薄弱点。反过来，如果"改 prompt 措辞"策略在同一个 skill 上连续失败 3 次，generator 就不会再尝试了——这就是 Ralph Wiggum loop 的解法在记忆层面的实现。

我一开始没有加记忆，纯靠 trace 注入。问题是 trace 只在一次 pipeline run 内有效，跨 run 就丢了。第 5 次跑同一个 skill 时，generator 又会提出第 1 次就被拒绝的策略。三层记忆解决了跨 run 的状态保持。

### Gate 七层门禁

Gate 的七层门禁，任一层失败就拒绝，没有例外：

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

### 插曲：从 regex 到 LLM-as-Judge

最早的 accuracy 评估用 regex 做。检查"有没有代码示例"就是 grep 一下有没有 ``` 代码块。检查"示例是否包含具体 I/O"就是看代码块里有没有 `→` 或 `Output:` 字样。

这个做法有个明显的问题：一个 skill 可以有 10 个代码块但全是语法展示（`python3 script.py --flag`），没有一个展示输入→输出的完整示例。regex 检查通过，但质量其实很差。

换成 LLM-as-Judge 后，accuracy 检查变成了把 SKILL.md 发给 Claude，让它从 5 个维度打分：clarity（"读完你知道该怎么做吗"）、specificity（"有没有具体到可以复制粘贴的参数"）、completeness（"有没有关键场景被遗漏"）、actionability（"新手读完能不能立刻上手"）、differentiation（"跟相关 skill 的区别说清楚了吗"）。

成本从 $0（regex）涨到 ~$0.5/eval（一次 `claude -p` 调用），但区分度大幅提升。原来 17/26 检查项零方差的问题消失了——LLM 给不同 skill 的 clarity 打分从 0.65 到 0.90 不等，能看出差异。

但 R² 还是 0.00。LLM-as-Judge 的分数和 evaluator pass rate 依然零相关。因为问题不在评估方法上——是"文档质量"和"指导质量"本就是两件事。一个 SKILL.md 可以写得非常清楚但缺一条关键的领域知识（比如模块分类规则），也可以写得一团糟但恰好包含了 Claude 需要的那条信息。

这个认知是我花了两个月才接受的。一开始我一直想优化 accuracy 检查让 R² 变大，直到最终承认：结构评估和执行评估就是两个正交的信号，不能互相替代，只能叠加。

### 自评报告的发现

我用同样的评估管线给自己的 15 个流水线 skill 打了分。经过几轮 SKILL.md 充实后，均分从 83.3% 升到了 91.2%，13/15 达到 POWERFUL。

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

我一开始以为 DSPy 跟我做的事差不多。仔细看了之后发现不是。DSPy 的 MIPROv2 optimizer 在 token 粒度上做贝叶斯搜索——它直接改 prompt 里的 few-shot 示例和措辞，输出一个你不一定看得懂的"优化后 prompt"。我操作的粒度粗得多：候选改的是 SKILL.md 里的段落、示例标签、frontmatter 字段。diff 人能读，代价是搜索空间小。对 skill 来说这是个合理的取舍——你不需要逐字调 prompt，你需要的是"加一个 module mapping 表"或"补一个 anti-example"这种段落级的改动。

TextGrad 的思路我很喜欢——用 LLM 生成的文字反馈当"梯度"来迭代优化文本。但它假设目标函数是连续可微的。accuracy 和 coverage 之间不存在连续的梯度关系——accuracy 从 0.83 到 0.84 不会"推动" coverage 往任何方向移动。六个维度是独立的。

LangSmith 和 Langfuse 我用过。它们做 trace、做 monitoring、生成 dashboard。有用，但止步于此——告诉你"这里出了问题"然后你去手动修。我的 session-feedback-analyzer 在采集端跟 LangSmith 很像（都是从 agent 日志里提取信号），差别在下游：LangSmith 输出到 dashboard 给人看，我输出到 feedback.jsonl 给 generator 读。人看 dashboard 做决策 vs 机器读 JSONL 做决策，这是闭环和开环的区别。

GEPA 的 trace-aware reflection 几乎是照搬的。失败追踪注入下一轮 prompt，在代码生成领域已经验证过。搬到 skill 改进上的改动很小——两边的失败结构一样：改了什么、被哪个 gate 拦住了、哪个维度退步了。

有一个方向目前是空白的：从用户会话日志挖隐式反馈来优化 agent 指令。我没有在任何开源项目里看到这件事的实现。RLHF 的偏好信号在模型训练层面做类似的事，但那需要大量标注数据和重新训练模型的基础设施。在 prompt/skill 层面做隐式反馈采集和闭环改进——技术上简单得多（就是解析 JSONL + 关键词分类），但好像没人做过。也许是因为大多数 agent 框架没有 Claude Code 这种"所有会话都存成 JSONL"的机制。

### 质量分级体系

benchmark-store 定义了四个质量等级：

| 等级 | 综合分 | 含义 |
|------|--------|------|
| POWERFUL | >= 85% | 可发布到 marketplace |
| SOLID | 70-84% | 可发布到 GitHub |
| GENERIC | 55-69% | 需要迭代改进 |
| WEAK | < 55% | 拒绝或重写 |

权重分配：accuracy 30% + coverage 20% + reliability 20% + efficiency 15% + security 15%。这套权重可以按 skill 类别调整——tool 类 skill 的 reliability 权重更高（要有测试），knowledge 类 skill 的 accuracy 权重更高（要有正确的知识）。

这套分级不是拍脑袋定的。我跑了一遍对标：alirezarezvani/claude-skills 的 220+ skill 平均结构质量对应 SOLID 上沿；DesignToken AgentSkills 的 9 个 skill 均分 74%，也在 SOLID 区间。POWERFUL 的门槛设在 85% 是因为——根据我的观察——低于这个分数的 skill 大概率有至少一个维度的明显短板（通常是 accuracy 或 trigger_quality），在实际使用中会表现为"某些场景不触发"或"触发了但输出不对"。

Pareto front 跟质量等级的关系：等级决定的是"你现在在哪里"，Pareto front 决定的是"你能不能往前走"。一个 SOLID 的 skill 想升到 POWERFUL，每一步改进都必须在 Pareto front 上——不能退步任何一个维度。这比单看综合分严格得多。综合分可以通过提升一个维度来弥补另一个维度的退步，Pareto front 不允许这样做。

### 评估标准的来源

evaluation-standards.md v2.0.0 参考了五个外部仓库的质量模式：

| 仓库 | 贡献 |
|------|------|
| alirezarezvani/claude-skills | 10 个质量模式、SKILL_PIPELINE、质量分级 |
| affaan-m/everything-claude-code | 116-skill 架构、多 harness 支持 |
| anthropics/claude-plugins-official | 官方 plugin.json 标准 |
| sbroenne/pytest-skill-engineering | pytest 测试框架 for skills |
| jensoppermann/agent-skill-scanner | 安全扫描模式 |

这些仓库我都手动审阅过。alirezarezvani 的贡献最大——它的 10 个质量模式（有 frontmatter、有 triggers、有 When to Use、有 examples……）直接成了我 accuracy 维度的 12 项检查的基础。anthropics 的 plugin.json 标准定义了 frontmatter 的格式规范。sbroenne 的测试框架影响了 reliability 维度的评估方式——它证明了 skill 的测试可以结构化为 pytest cases，而不只是手动验证。

## 执行可靠性：agent 为什么老停

到这里有个问题还没说——这些自动改进任务谁来跑？答案是 dispatched agent，丢进 tmux session 让它自己干。但 Claude Code agent 有个毛病：它经常觉得自己"做完了"然后停下来，实际上只改了一半。

这不是偶发的。我在批量改进 28 个 skill 的时候，大概有 40% 的 session 是 agent 跑到一半自己停了——改了 2 个文件里的 1 个，或者跑了 7 个测试里的 4 个。Claude Code 的 `end_turn` 机制不是 bug，而是模型在"做完了"和"还没做完"之间做了一个概率判断，而这个判断经常是错的。

### Ralph：拦住不让停

Ralph 利用 Claude Code 的 Stop hook。agent 试图结束 session 时，`ralph-stop-hook.sh` 拦截它，检查任务状态，如果没做完就返回 `{"decision":"block","reason":"[RALPH LOOP 3/10] Task is NOT done..."}`，注入续航指令。

实现很简单——一个 shell 脚本读 `sessions/<session-id>/ralph.json` 状态文件：

```bash
# ralph-stop-hook.sh 核心逻辑
state=$(cat "sessions/$SESSION_ID/ralph.json")
iteration=$(echo "$state" | jq .iteration)
max=$(echo "$state" | jq .max_iterations)

if [ "$iteration" -ge "$max" ]; then
  echo '{"decision":"allow"}'  # 到达上限，放行
else
  # 递增迭代计数，继续
  echo "{\"decision\":\"block\",\"reason\":\"[RALPH LOOP $iteration/$max] ...\"}"
fi
```

但不能让 Ralph 把 agent 永远困住。五个安全阀保证这一点：context 用量 >= 95%（防止 context overflow 崩溃）、认证错误 401/403（token 过期没意义继续）、cancel 信号（Pattern 7 的 TTL 机制）、闲置超过 2 小时（state 判定）、达到最大迭代次数。

Ralph 有一个我踩了很久的坑：**它只在 interactive 模式下工作**。headless `-p` 模式的 Stop hook 不触发。我在 OMC 源码里翻了两个小时才确认这件事——文档没有一个地方提到这个限制。evaluator 用 `claude -p` 跑任务，所以它用不了 Ralph，得用 `--max-turns` 代替。但 autoloop-controller 跑在 tmux 里是 interactive 模式，可以用。

### Handoff：context 压缩了怎么办

Claude Code 有四级 context 压缩：MicroCompact、Session Memory、Full Compact、Reactive Compact。压缩时，设计决策、被否决的方案、已知风险这些东西会被丢掉——因为它们在 token 计数里占大，但压缩算法不知道它们重要。

Handoff 文档解决这个问题。agent 在阶段结束时（比如 plan 阶段结束、进入 implement 阶段）写一个 `handoffs/stage-N.md`：

```markdown
## Decided
- 用 Pareto front 而不是单一加权分数
- 5% 容差而不是 0%

## Rejected
- Git worktree 隔离方案（太慢）
- pass@3 作为默认（太贵）

## Risks
- evaluator 循环依赖
- R²=0.00 可能是样本量问题
```

这个文件在磁盘上，不在 context window 里，所以不管 context 怎么压缩它都在。下一个阶段的 agent 通过 UserPromptSubmit hook（带 `once: true`，只在 session 启动时注入一次）读取 handoff 文档。

我在 autoloop-controller 里用了这个模式。每轮改进结束时写 `iteration-N.md`，记录这轮改了什么、分数怎么变化、哪些候选被拒了。这样第 5 轮的 agent 不需要重新分析前 4 轮的所有 artifact——handoff 已经把关键信息浓缩好了。

### 工具错误升级

agent 反复用同一个失败的命令是另一个常见问题。比如 `cargo build` 失败因为没装 cargo，agent 换个参数再试一次，再试一次，进入死循环。

Pattern 3 用 PostToolUseFailure hook 追踪连续失败次数，按 `tool_name + input_hash` 聚合。1-2 次沉默记录，3-4 次在 PreToolUse 里注入软提示（"考虑换个方案"），5 次以上注入硬指令（"MUST use an alternative approach"）。状态存在 `sessions/<session-id>/tool-errors.json`。

### Pattern 组合

这些 pattern 不是独立使用的。后来加的 6 个 pattern（13-18）进一步扩展了覆盖面——Doubt Gate（Pattern 13）拦截 agent 用投机语言声称"完成"但实际没有证据的情况；三种委托模式（Pattern 14）给多 agent 场景提供 Coordinator/Fork/Swarm 选型指南；Post-Edit Diagnostics（Pattern 15）在每次文件编辑后即时跑 linter；Adaptive Complexity（Pattern 16）根据任务复杂度自动选执行模式，避免简单任务背负全套 hook 的开销。

常用组合：

| 场景 | 组合 |
|------|------|
| 多文件 bugfix | Ralph + Context 估算做安全阀 |
| 多阶段任务 | Handoff + Compaction 提取 |
| Agent 在陌生环境跑 | 工具错误升级 + 权限否决追踪 |
| 批量 dispatch 到 tmux | Rate Limit 恢复 + Hook Bracket 监控 |
| 高价值任务 | Agent-type Stop hook + Scoped hooks + Doubt Gate |
| 多 agent 并行 | 委托模式选型 + Handoff + Hook Bracket |
| 快速实验，最小开销 | Hook Profile = minimal + Adaptive Complexity = trivial |

跟改进流水线怎么配合？evaluator 跑长 task suite 时用 Ralph 保证跑完所有任务——我遇到过一次 evaluator 跑了 5/7 个任务就停了，通过率算出来是 80%，实际应该是 71%（剩下 2 个任务有 1 个会 FAIL）。加了 Ralph 后这个问题消失了。

autoloop-controller 跑多轮改进时用 Handoff 保证跨轮次的上下文存活。每轮结束时写 `iteration-N.md`：这轮改了什么、分数怎么变、哪些候选被拒了。第 5 轮的 agent 不用重新读前 4 轮的 100MB+ transcript，直接读 5 个 handoff 文件就够了。

improvement-gate 可以加一个 agent-type Stop hook 做语义验证——不只是机械地检查 schema 和 lint，而是让一个 subagent 实际读原文件和改后文件，判断变更是不是真的有价值。这相当于第 8 层门禁。比现有的 7 层重得多（要额外调一次 LLM），所以只在高价值任务（安全修复、生产配置变更）时才开。

Ralph 还有一个设计上的权衡我一直在想。OMC 的默认 max_iterations 是 200，我设的是 50。200 次迭代意味着 agent 可以跑很久——如果每次迭代 30 秒，200 次就是接近 2 小时。对长任务来说这是好事，但如果 agent 陷入了某种无效循环（不是工具错误，而是策略层面的重复），200 次迭代就是在烧钱。我的 50 次上限更保守，代价是有些确实需要更多迭代的任务会被截断。目前没有好的自适应方案——理想情况下 max_iterations 应该根据任务复杂度动态调整，但"任务复杂度"本身就很难量化。

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

状态持久化到 `autoloop_state.json`，每轮结束写一次。格式长这样：

```json
{
  "schema_version": "1.0",
  "target": "/path/to/skill",
  "iterations_completed": 3,
  "max_iterations": 5,
  "total_cost_usd": 12.50,
  "current_scores": {"clarity": 0.85, "coverage": 0.72},
  "score_history": [
    {"iteration": 1, "weighted_score": 0.78, "decision": "keep"},
    {"iteration": 2, "weighted_score": 0.80, "decision": "keep"},
    {"iteration": 3, "weighted_score": 0.82, "decision": "keep"}
  ],
  "plateau_counter": 0,
  "status": "running"
}
```

进程挂了重启读状态接着跑——不用从头开始。另外有一个 append-only 的 `iteration_log.jsonl` 做完整审计追踪，每轮写一行，方便事后分析哪些改进被保留了、哪些被拒了。

三种运行模式：`single-run`（跑到终止条件就退出）、`continuous`（带 cooldown 的循环）、`scheduled`（配合系统 cron，每次只跑一轮然后退出）。我日常用 single-run，设 `max_iterations=5` 和 `max_cost=50.0`，睡前跑，第二天早上看结果。

Karpathy 用 700 次自主实验在两天里提升了 11%。我的情况麻烦一些——他优化的是一个数 val_bpb，我得看六个维度，accuracy 升了但 coverage 降了算好还是算坏？所以才需要 Pareto front。但核心模式一样：修改→测量→保留或回滚→重复。

## 吃自己狗粮

我用这套评估管线给自己的流水线 skill 打了分。均分 83.3%，14 个 skill 里只有 benchmark-store 够上了 POWERFUL（86.2%）。最讽刺的发现：

discriminator 有 620 行的 score.py，实现了多审阅者盲审 panel、CONSENSUS/VERIFIED/DISPUTED 认知标签、heuristic+LLM 三路 blending——SKILL.md 只有 26 行，连 `--panel` 和 `--llm-judge` 这两个关键 flag 都没提。learner 有 878 行的核心引擎（6 维评估 + 12 项 accuracy check + 三层记忆 + Pareto front），SKILL.md 27 行，CLI 参数名跟实际都对不上（文档写 `--target --rounds`，代码里是 `--skill-path --max-iterations`）。

7 个 skill 的 "When NOT to Use" 段落全是占位符 `[Define exclusion conditions here]`。全部缺 `triggers:` 字段。trigger_quality 被锁死在 0.40。

做评估框架的项目，自己的文档是最差的。这个发现让我重新理解了 R²=0.00——不是"结构不重要"，是结构评分太容易通过了。17/26 的检查项全部 skill 都过，等于没检查。真正应该检查的是"SKILL.md 有没有记录它最重要的三个参数"，而不是"有没有 frontmatter"。

这也是为什么后来加了 execution-harness 之后，我立刻给它写了完整的 SKILL.md——18 个 pattern 的一句话描述、常见场景选型表、条件判断规则。从 0.63 分的骨架升到 0.93。吃了一次自己狗粮之后老实了。

## 蒸馏的真正难点

写到这里可能给人一个印象：蒸馏就是把几个文件喂进去跑一下。实际不是。

skill-distill 的自动合并在"同类文档合并"场景下工作得不错——deslop 的三个源都是 AI 检测规则列表，格式接近，知识粒度一致。但 execution-harness 的四个源包括博客文章、npm 包源码、网站技术拆解和 tips 集合。格式不同，抽象层次不同，甚至同一个概念的叫法都不同（OMC 叫它 "persistent loop"，claude-reviews-claude 叫它 "stop hook pattern"，ccunpacked 叫它 "continuation harness"）。

skill-distill 的"分析"阶段把这些全标成了"冲突"，一条条弹出来让我选。实际上不是冲突，是同一件事的不同描述。这说明 distill 的冲突检测粒度太粗——它比较的是文字表面，不是语义。

另一个问题：源文件的质量差异很大。OMC 的源码是可执行的、可测试的——我能直接跑它的 Ralph 实现看行为。claude-reviews-claude 的文章是分析性的——它描述了 Claude Code 的 Stop hook 机制但没有给可运行的代码。ccunpacked 介于两者之间。把这三个来源的信息合并到一个一致的 SKILL.md 里，实际上是在做知识层次的对齐——把"分析"、"实现"、"配方"统一到"可操作的指令"这个层次上。

这件事目前还是手动的。我不确定它能不能完全自动化。

## 还没解的

循环依赖仍然是最大的问题。task suite 和 SKILL.md 通常一个人写。你写了 skill 教 Claude 怎么做 X，然后你写测试检查 Claude 有没有做 X。当然能通过——你测的就是你教的。

已经做了两件事。session-feedback-analyzer 从用户实际使用中挖信号——用户改了 AI 的输出，这个动作本身就是 skill 有问题的证据，独立于 task suite。null-skill calibration 在 skill-forge 里——生成 task suite 时过滤掉裸跑 Claude 就能通过的任务，如果不加载 skill 也能过，那它测的不是 skill 的贡献。

但这两件事加起来仍然不够。更好的方案也许是：让 generator 自动造对抗性测试（"找一个能让这个 skill 失败的输入"），引入社区贡献的 task suite（写 suite 的人没看过 SKILL.md），或者做 held-out 拆分——一半任务用于改进迭代，一半只用于最终评估，不参与优化循环。但这些都还没实现。

Skill 副作用是另一个我反复想的问题。加载 prompt-hardening skill 后，通过率跟裸跑一样是 86%，但是不同的 86%。你修好了 A 任务，B 任务可能就坏了。这不是 bug——你往 Claude 的上下文里注入了新的指令，它的注意力分配就变了。这是 skill 工作方式的固有属性。量化这个 tradeoff 需要把通过率拆到逐任务级别，跟踪每个任务跨 skill 版本的 pass/fail 变化。现在的 evaluator 已经能做到，但没人写这个分析脚本。

execution-harness 里还有一个没解的问题：Ralph 的 block 消息设计。block 消息需要足够强硬让 Claude 不要合理化"剩下的工作可以后续做"，但又不能太强硬导致 Claude 对所有"完成"信号都变得麻木。prompt-hardening 的 P5（三重强化模式）可以强化 block 消息，但我还没有数据说明什么强度的措辞在 Ralph 场景下最有效。这可能需要一个专门的 A/B 测试——同一个多文件任务，用不同强度的 block 消息跑，看完成率和质量。

还有成本问题。整个改进管线跑一轮大约 $3-5（主要是 evaluator 的 `claude -p` 调用）。四个 skill 批量改，$15-20。如果 autoloop 跑 10 轮，接近 $50。对个人项目来说这个价格可以接受，但如果要在有 100+ skill 的团队里用，成本控制会变成核心问题。autoloop-controller 的 cost_cap 参数就是为这个设计的，但当前的成本估算不够精确——它只计算 evaluator 调用次数，没算 LLM judge 和 generator 的 token 消耗。

## 回头看

做了三个多月，踩了不少坑。

最大的弯路是顺序。先写了 generator 和 executor——"先让它能改，再想怎么评"。改完之后不知道好不好，只能凭感觉觉得"看起来不错"。掉头先做 learner 和 evaluator 之后一切才顺起来。"没有测量就没有改进"，说出来像废话，做起来真的会忘。

然后在 accuracy 检查上花了大量时间。调 checklist、加检查项、改权重，断断续续搞了三周。R²=0.00 出来之后全白费了。如果重来，learner 最多做个 30 分钟就能写完的快速 lint，剩下的精力全部投到 evaluator 上。结构评估的价值上限比我以为的低得多——它能告诉你"这个 SKILL.md 缺 frontmatter"，但不能告诉你"这个 skill 在真实任务上会不会出错"。两者之间的鸿沟，不是优化 checklist 能弥合的。

Pareto front 是做对了的事。有一次一个候选把 accuracy 从 0.83 拉到 0.91，trigger_quality 从 0.80 掉到 0.55。算加权得分——还涨了 0.02。如果用单一分数，这个候选就会被应用，这个 skill 在触发路由时就废了。这种"一个维度暴涨遮盖另一个维度暴跌"的情况我后来又遇到过两次。每次都是 Pareto front 拦住的。它在我整个设计里大概是 ROI 最高的一个组件——实现只有 98 行 Python，但救了至少三个 skill 不被搞坏。

关于 Ralph，花的时间比预期多一倍，不是因为逻辑复杂（就是个 shell 脚本读 JSON），而是因为 Claude Code 的 Stop hook 行为在文档里描述得不够精确。headless 模式不触发这件事我是从 OMC 源码里翻出来的。没有任何官方文档提到这个限制。我理解这是因为 hooks 还算比较新的功能，文档会慢慢补全。但对于在生产环境依赖 hooks 的人来说，这种"文档没写的行为差异"是很痛的。

execution-harness 的 18 个 pattern 本质上都是在补 Claude Code 作为 agent runtime 的基础设施缺失。如果 Claude Code 原生支持任务完成检测和跨 session 状态恢复，其中至少一半 pattern 不需要存在。我写它们不是因为想写，是因为没有它们 agent 跑不稳。

成本的问题是第三个月才想起来的。evaluator 一次 $3-5，autoloop 跑 10 轮 $50。对个人项目来说没什么。但有一天我算了一下：如果团队里有 100 个 skill，每个每月跑一次 autoloop（5 轮），一个月光自动改进就要 $5000。这个数字让我加了 conditional evaluation——discriminator 分数低于 6.0 的候选直接跳过 evaluator，不花那 $3-5。省了 60% 的 evaluation 成本。但这是补丁，不是设计。应该从第一天就把 cost_per_eval 当一个显式约束。

## 代码

15 个 skill（13 个 pipeline + execution-harness + 2 个 demo target），8000+ 行 Python，409 个测试，依赖只有 pyyaml 和 pytest。

[github.com/lanyasheng/auto-improvement-orchestrator-skill](https://github.com/lanyasheng/auto-improvement-orchestrator-skill)

几个我还在想的问题，如果你在做类似的事，我想听听你的做法：

task suite 怎么写才能不陷入循环依赖？held-out 拆分在 5-7 个任务的小 suite 上可行吗，还是样本量太小没意义？

Skill 副作用怎么量化？有没有比逐任务 diff 更高效的方式来检测 skill 变更引入的 regression？

从用户会话日志挖隐式反馈，除了关键词匹配还有什么更好的 correction 检测方法？LLM 对 200 字片段做分类的成本能接受吗？
