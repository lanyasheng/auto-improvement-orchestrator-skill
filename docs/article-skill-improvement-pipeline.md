# 从蒸馏别人的仓库到让 Skill 自己变好

> 15 个 skill、8000 行 Python、409 个测试。从零开始搭了一套 AI agent skill 的自动评估和改进流水线。
> 过程中发现了一个反直觉的事实：结构评分和实际执行效果的相关系数是零。

## 一个结论先放在前面

我花了三周写评估器，给 28 个 skill 跑了六个维度的结构评分。分数从 0.65 到 0.80，看着挺合理。然后我拿真实任务验证——用 `claude -p` 把 SKILL.md 注入上下文，跑预定义测试。

结果是 **R² = 0.00**。

不是接近零。是字面上的零。评分 0.70 的 skill 全部任务通过，评分 0.88 的反而挂了。这意味着我写的那 26 个 checklist 项目——有没有 frontmatter、有没有 When to Use、有没有示例代码——跟 skill 在真实场景下好不好用完全没有关系。

这个发现改变了整个项目的方向。下面讲怎么从这里走到一套可用的自动改进系统。

## 偷师：从蒸馏别人的仓库开始

Claude Code 的 Skill 就是一个 SKILL.md 文件加几个脚本，告诉 AI 遇到特定任务该怎么干。GitHub 上有人整理了不错的合集：alirezarezvani/claude-skills 有 10 个质量模式，affaan-m/everything-claude-code 搞了 116 个 skill 的架构。我不想从零写，想拿来改改用。

手动抄一两个没问题。但 skill 一多——我陆续看中了三四十个——一个个搬就烦了。我写了个 skill-distill 工具，喂进去 N 个功能有重叠的 skill，它把知识分成交集、独有、冲突、冗余四类，让你确认合并方案，然后吐出一个蒸馏版。

### 蒸馏案例：deslop（反 AI 味写作）

GitHub 上有两个相关 skill——slopbuster（280 行，英文为主，覆盖学术/代码/散文三种模式）和 humanizer（559 行，偏通用文本去 AI 痕迹）。两个 skill 有大量重叠：都列了 AI 高频词表，都有评分量表，都做模式替换。但 slopbuster 有代码注释专用模式，humanizer 有更细的语气校准。

```mermaid
graph LR
    A["slopbuster<br/>280 行"] --> D["skill-distill<br/>四类分拣"]
    B["humanizer<br/>559 行"] --> D
    C["中文写作笔记"] --> D
    D --> E["deslop<br/>221 行 SKILL.md<br/>+ 561 行 references"]
    
    style D fill:#f9f,stroke:#333
    style E fill:#9f9,stroke:#333
```

交集部分（AI 词汇表、评分标准）合并去重。slopbuster 独有的代码模式保留为"不适用场景"指向原 skill。humanizer 独有的 voice calibration 保留进 references。冲突的地方——比如两个 skill 对 em dash 的容忍度不同——弹出来让我手动选。

蒸馏完的 deslop 比任何一个源 skill 都好用。这篇文章本身就是用 deslop 从 7.5 分改到 8.4 分的。

### 蒸馏案例：execution-harness（agent 执行可靠性）

这个的来源更杂：claude-reviews-claude 的 17 篇架构文章、oh-my-claudecode (OMC) 的 npm 源码、ccunpacked.dev 的 Claude Code 拆解、luongnv89/claude-howto 的实践 tips。四个来源讲的都是同一件事——怎么让 dispatched agent 不要半路停下来——但每个的侧重点不同。

OMC 的核心贡献是 Ralph 模式：利用 Claude Code 的 Stop hook，在 agent 试图结束 session 时拦截它，注入"你还没做完"的续航指令。这个模式有个致命的细节——**它只在 interactive 模式下工作**，headless `-p` 模式的 Stop hook 根本不触发。我在 OMC 源码里花了两个小时才确认这一点，因为文档没写。

蒸馏后是 21 个可组合的 pattern，质量分从 0.63 升到 0.93。但这个蒸馏过程比 deslop 难多了——deslop 的三个源都是同类文档，而 execution-harness 的四个源分别是博客文章、npm 包源码、技术拆解网站和 tips 集合，格式和抽象层次完全不同。

## 整体架构

```mermaid
graph TB
    subgraph 素材获取
        GH["GitHub 仓库"] --> SD["skill-distill<br/>蒸馏合并"]
        CH["ClawHub 市场"] --> SD
        HW["手写"] --> SD
    end

    subgraph 评估层
        L["learner<br/>结构 lint $0.5"]
        EV["evaluator<br/>执行测试 $3-5"]
        SF["session-feedback<br/>用户隐式反馈 $0"]
    end

    subgraph 改进层
        G["generator"] --> DIS["discriminator"]
        DIS --> EV2["evaluator*"]
        EV2 --> EX["executor"]
        EX --> GATE["gate<br/>7层门禁"]
        GATE -->|"revert + trace"| G
    end

    subgraph 控制层
        AL["autoloop<br/>连续跑+收敛检测"]
        BS["benchmark-store<br/>Pareto front"]
        EH["execution-harness<br/>21 patterns"]
    end

    SD --> L
    L --> G
    SF --> G
    GATE -->|"keep"| BS

    style GATE fill:#f99,stroke:#333
    style EV fill:#9cf,stroke:#333
    style SF fill:#9f9,stroke:#333
```

15 个 skill 分三层：

- **评估层**：learner 做结构检查（$0.5/次），evaluator 跑真实任务测执行效果（$3-5/次），session-feedback-analyzer 从用户实际使用中挖隐式反馈（免费）
- **改进层**：generator → discriminator → evaluator → executor → gate，带 trace-aware 重试
- **控制层**：gate（七层门禁）、autoloop-controller（连续跑 + 收敛检测）、benchmark-store（Pareto front + 质量分级）

## R² = 0.00 的故事

先写了个评分器 improvement-learner，六个维度打分，每个维度按 skill 类别差异化权重：

```mermaid
pie title 评估维度权重（Tool 类 skill）
    "accuracy" : 25
    "coverage" : 15
    "reliability" : 30
    "efficiency" : 15
    "security" : 15
```

| 类别 | accuracy | coverage | reliability | efficiency | security |
|------|----------|----------|-------------|------------|----------|
| Tool（工具型） | 25% | 15% | 30% | 15% | 15% |
| Knowledge（知识型） | 40% | 20% | 10% | 20% | 10% |
| Orchestration（编排型） | 30% | 20% | 25% | 10% | 15% |
| Review（评审型） | 35% | 15% | 25% | 10% | 15% |

28 个 skill 跑了一遍，零个达到 POWERFUL（>= 85%）。我当时还挺得意——可以量化了嘛。

然后拿真实任务验证。5 个 skill 的结构评分 vs 实际执行通过率：

```mermaid
xychart-beta
    title "结构评分 vs 执行通过率（R² = 0.00）"
    x-axis "Learner 加权分" [0.71, 0.75, 0.76, 0.80, 0.80]
    y-axis "Evaluator 通过率" 60 --> 105
    bar [100, 86, 71, 86, 100]
```

加权分 r = -0.40，方向是反的——learner 分越高，实际执行越差。

为什么？拆开看 26 个检查项：17 个在所有 skill 上都通过（零方差，无区分度），3 个是**反向预测**——通过的 skill 实际表现更差。比如"frontmatter 里有 version 字段"这项，通过它跟执行效果的相关系数是 r=-0.76。

可能的解释：最用心维护 frontmatter 格式的 skill 作者，把精力花在了文档美化而不是指令质量上。

结论不是"结构不重要"，而是"我们的结构检查测错了东西"。

### 从 regex 到 LLM-as-Judge

最早的 accuracy 评估用 regex 做。检查"有没有代码示例"就是 grep 一下有没有 ``` 代码块。这个做法的问题：一个 skill 可以有 10 个代码块但全是语法展示（`python3 script.py --flag`），没有一个展示输入→输出的完整示例。regex 检查通过，但质量其实很差。

换成 LLM-as-Judge 后，accuracy 检查变成了把 SKILL.md 发给 Claude，让它从 5 个维度打分：clarity、specificity、completeness、actionability、differentiation。

成本从 $0（regex）涨到 ~$0.5/eval，但区分度大幅提升。原来 17/26 检查项零方差的问题消失了。

但 R² 还是 0.00。因为问题不在评估方法上——是"文档质量"和"指导质量"本就是两件事。这个认知是我花了两个月才接受的。

## 两层评估 + 用户反馈闭环

```mermaid
graph LR
    subgraph "评估三信号"
        L["learner<br/>结构 lint<br/>$0.5/次<br/>R²=0.00 vs 执行"]
        E["evaluator<br/>执行测试<br/>$3-5/次<br/>claude -p 真实调用"]
        S["session-feedback<br/>用户隐式反馈<br/>$0<br/>correction_rate"]
    end

    L --> |"gate check"| P["Pareto front"]
    E --> |"pass rate"| P
    S --> |"correction hotspot"| G["generator"]
```

### Task Suite 执行测试

执行层是真金白银。task suite 格式：

```yaml
skill_id: "release-notes-generator"
tasks:
  - id: "leakage-01"
    description: "iOS notes must not contain Android keywords"
    judge:
      type: "llm-rubric"
      rubric: |
        Check output does NOT contain "Kotlin", "Android", "Java".
        Score 1.0 if clean, 0.0 if any leakage.
      pass_threshold: 0.8
```

三种 judge：ContainsJudge（关键词检查）、PytestJudge（pytest 验证）、LLMRubricJudge（语义评分）。

### Skill 到底有没有用？

prompt-hardening skill 的 7 个任务，加载 skill 和裸跑 Claude 的通过率一样——都是 86%。但挂的任务不同：

```mermaid
xychart-beta
    title "加载 Skill vs 裸跑 Claude（通过率都是 86%）"
    x-axis ["P1三重强化", "P5反推理", "审计格式", "CLI路径", "模式选择", "可靠性", "端到端"]
    y-axis "PASS=1 / FAIL=0" 0 --> 1.2
    bar "裸跑" [1, 1, 1, 0, 1, 1, 1]
    bar "加载Skill" [1, 1, 0, 1, 1, 1, 1]
```

Skill 的价值在注入特定知识（audit.sh 路径），不是让 Claude 变聪明。但注入知识有代价——输出格式偏好变了，造成新的失败模式。

### 用户反馈闭环

task suite 测的是作者预设的场景。用户在真实使用中遇到的问题，task suite 未必覆盖。session-feedback-analyzer 从 Claude Code 的会话日志里挖隐式反馈：

```mermaid
flowchart TD
    A["~/.claude/projects/**/*.jsonl"] --> B["detect_skill_invocations()"]
    B --> C{"Skill tool_use?<br/>slash command?"}
    C -->|yes| D["classify_outcome()<br/>3-turn 影响窗口"]
    C -->|no| X["skip"]
    D --> E{"correction?<br/>acceptance?<br/>partial?"}
    E -->|correction| F["feedback.jsonl"]
    E -->|partial| F
    E -->|acceptance| G["计入 total"]
    F --> H["correction_rate<br/>per skill"]
    H --> I["generator<br/>优先改纠正最多的维度"]
```

纠正信号检测规则：

| 信号 | 检测方式 | 置信度 |
|------|---------|--------|
| 明确否定 | "不对"/"错了"/"wrong" | 0.9 |
| 撤销操作 | git checkout/restore | 0.9 |
| 部分纠正 | 接受词 + 转折词（"可以但是"） | 0.7 |
| 静默继续 | 用户换话题，未纠正 | 0.6 |

在我的 session 数据上跑了一遍：28 个反馈事件，code-review-enhanced 被纠正最多（9 次）。这跟我的体感一致——它生成的 review 评论经常需要我手动调整措辞和优先级。

## 自动改进流水线

直接重试不行。LLM 容易翻来覆去犯同一个错——我们叫它 "Ralph Wiggum loop"，说着 "I'm helping!" 然后帮倒忙。

```mermaid
flowchart LR
    G["generator<br/>生成候选"] --> D["discriminator<br/>4种打分模式"]
    D --> E["evaluator<br/>跑真实任务"]
    E --> EX["executor<br/>应用+备份"]
    EX --> GATE["gate<br/>7层门禁"]
    GATE -->|"keep"| DONE["✅ 保留"]
    GATE -->|"revert"| T["extract_failure_trace()"]
    T -->|"注入 trace"| G
    GATE -->|"pending"| HR["👤 人工审核"]
    GATE -->|"reject"| REJ["❌ 拒绝"]

    style T fill:#ff9,stroke:#333
    style GATE fill:#f99,stroke:#333
```

失败追踪的数据结构：

```json
{
  "type": "failure_trace",
  "candidate_id": "docs-accuracy-001",
  "decision": "revert",
  "reason": "accuracy regressed 12%",
  "gate_blockers": ["RegressionGate: accuracy 0.85 -> 0.75"]
}
```

generator 读到"docs-accuracy 策略在 accuracy 维度上失败了 3 次"，就跳过这个策略。思路来自 GEPA 论文（ICLR 2026）的 trace-aware reflection。

### Gate 七层门禁

```mermaid
flowchart TD
    S["SchemaGate<br/>JSON 结构"] --> C["CompileGate<br/>语法检查"]
    C --> LI["LintGate<br/>风格检查"]
    LI --> R["RegressionGate<br/>Pareto 维度无退步"]
    R --> RE["ReviewGate<br/>盲审共识"]
    RE --> DG["DoubtGate<br/>投机语言检测"]
    DG --> H["HumanReviewGate<br/>高风险人工审批"]
    
    R -.->|"security: 2% 容差<br/>efficiency: 10% 容差<br/>其他: 5% 容差"| R
    DG -.->|"docs: 阈值2<br/>prompt: 阈值4<br/>其他: 阈值3"| DG
```

RegressionGate 用的 Pareto front，代码（`lib/pareto.py`）：

```python
def check_regression(self, scores, tolerances=None):
    for dim, best in best_per_dim.items():
        tol = tolerances.get(dim, 0.05)  # per-dimension tolerance
        if new_score < best * (1 - tol):
            regressions.append({"dimension": dim, "best": best, "new": new_score})
    return {"regressed": len(regressions) > 0, "regressions": regressions}
```

为什么不用一个总分？accuracy=0.85/coverage=0.70 改成 accuracy=0.70/coverage=0.85，加权得分完全相同。但准确度被毁了。Pareto front 要求每个维度独立不退步。

## 执行可靠性：agent 为什么老停

这些自动改进任务丢进 tmux session 让 dispatched agent 跑。但 Claude Code agent 有个毛病：它经常觉得自己"做完了"然后停下来，实际上只改了一半。我在批量改进 28 个 skill 的时候，大概有 40% 的 session 是 agent 跑到一半自己停了。

### Ralph：拦住不让停

```mermaid
sequenceDiagram
    participant A as Agent
    participant H as ralph-stop-hook.sh
    participant S as ralph.json

    A->>H: end_turn (试图停止)
    H->>S: 读取状态
    S-->>H: active=true, iteration=3/10
    H-->>A: {"decision":"block", "reason":"[RALPH LOOP 3/10] NOT DONE"}
    Note over A: 继续执行
    A->>H: end_turn (再次试图停止)
    H->>S: 读取状态
    S-->>H: active=true, iteration=10/10
    H-->>A: {"decision":"allow"}
    Note over A: 正常结束
```

五个安全阀防止 Ralph 把 agent 永远困住：context >= 95%、认证错误 401/403、cancel 信号（30s TTL）、闲置 > 2 小时、达到上限。

### Handoff：context 压缩了怎么办

Claude Code 压缩 context 时，设计决策、被否决的方案、已知风险会被丢掉。Handoff 文档解决这个问题——agent 在阶段结束时写 `handoffs/stage-N.md`，包含 Decided/Rejected/Risks/Remaining。文件在磁盘上，不受 context 压缩影响。

## 实验数据

### 批量改进 4 个 GENERIC Skill

```mermaid
xychart-beta
    title "改进前后对比（GENERIC → SOLID）"
    x-axis ["system-maintenance", "perf-profiler", "component-dev", "release-notes"]
    y-axis "加权分" 0.6 --> 0.9
    bar "改进前" [0.653, 0.661, 0.665, 0.681]
    bar "改进后" [0.803, 0.803, 0.798, 0.831]
```

平均 +0.138，从 GENERIC 全部升到 SOLID。API 费用 $15-20。

最大的单项跳跃是 reliability：0.30 到 1.00——learner 发现 skill 有脚本但没测试，自动生成了测试桩，测试跑过了。

### 自评：均分 83.3% → 91.2%

用同样的评估管线给自己的 15 个流水线 skill 打分。经过几轮 SKILL.md 充实后：

```mermaid
xychart-beta
    title "15 个 Skill 评分分布（真实 LLM judge）"
    x-axis ["gate", "discrim", "autoloop", "harness", "distill", "feedback", "bench", "eval", "learner", "gen", "prompt", "executor", "orch"]
    y-axis "加权分" 0.8 --> 1.0
    bar [0.928, 0.899, 0.917, 0.889, 0.902, 0.928, 0.919, 0.937, 0.885, 0.916, 0.918, 0.940, 0.948]
```

13/15 达到 POWERFUL（>= 85%）。讽刺的发现：做评估框架的项目，自己的文档曾经是最差的——discriminator 有 620 行 score.py，SKILL.md 只有 26 行。

## 行业对比

| 系统 | 优化对象 | 粒度 | diff 可读？ | 多维度？ | 反馈来源 |
|------|---------|------|:-----------:|:-------:|---------|
| **本项目** | SKILL.md 文档 | 段落 | ✅ | 6维 Pareto | task suite + 用户隐式反馈 |
| DSPy | prompt token | token | ❌ | 单目标 | 用户定义 metric |
| TextGrad | LLM 输出变量 | token | ❌ | 单目标 | LLM "梯度" |
| GEPA | 代码生成 | 函数 | ✅ | 单目标 | trace reflection |
| PromptFoo | prompt assertion | prompt | ✅ | 单维 | assertion suite |
| LangSmith | agent trace | trace | N/A | 多 metric | 可观测性平台 |
| Karpathy autoresearch | train.py | 文件 | ✅ | 单标量 | 训练 loss |

DSPy 在 token 粒度上做贝叶斯搜索，改完你未必看得懂改了什么。我操作的是 SKILL.md——候选改的是段落、示例、frontmatter 字段，diff 人能读。

LangSmith 和 Langfuse 做 trace、做 monitoring，但不关闭改进循环。session-feedback-analyzer 的 trace 采集思路跟 LangSmith 接近，但下游直接对接 generator，不是给人看 dashboard。

有一件事我在这些系统里都没看到：从用户会话日志挖隐式反馈来优化 agent 指令。RLHF 做偏好学习，但那是模型训练层面。在 prompt/skill 层面，用户纠正 AI 输出这个动作被浪费了——没人把它收集起来反馈给 skill 改进流程。

## 连续跑

autoloop-controller 包了个外层循环，检测三种停止信号：

```mermaid
flowchart TD
    START["开始迭代"] --> RUN["run_pipeline()"]
    RUN --> CHECK{"检查终止条件"}
    CHECK -->|"max_iterations 到了"| STOP["停止"]
    CHECK -->|"cost_cap 超了"| STOP
    CHECK -->|"分数平台期"| STOP
    CHECK -->|"震荡 keep-reject-keep-reject"| STOP
    CHECK -->|"correction_rate 没下降"| STOP
    CHECK -->|"都没触发"| HANDOFF["写 handoff 文档"]
    HANDOFF --> RUN
```

状态持久化到 JSON，进程挂了重启接着跑。每轮写 `handoffs/iteration-N.md` 记录 Decided/Rejected/Scores/Remaining，保证跨迭代上下文存活。

## 回头看

最大的弯路是顺序。先写了 generator 和 executor——"先让它能改，再想怎么评"。改完之后不知道好不好，只能凭感觉。掉头先做 learner 和 evaluator 之后一切才顺起来。

然后在 accuracy 检查上花了大量时间。调 checklist、加检查项、改权重，断断续续搞了三周。R²=0.00 出来之后全白费了。结构评估的价值上限比我以为的低得多。

Pareto front 是做对了的事。有一次一个候选把 accuracy 从 0.83 拉到 0.91，trigger_quality 从 0.80 掉到 0.55。算加权得分——还涨了 0.02。如果用单一分数，这个候选就会被应用。Pareto front 拦住了它。98 行 Python，救了至少三个 skill 不被搞坏。

成本的问题是第三个月才想起来的。evaluator 一次 $3-5，autoloop 跑 10 轮 $50。对个人项目来说没什么。但 100 个 skill 的团队一个月光自动改进就要 $5000。conditional evaluation（discriminator 分数低于阈值就跳过 evaluator）省了 60%，但这是补丁。应该从第一天就把 cost_per_eval 当约束。

## 还没解的

循环依赖仍然是最大的问题。task suite 和 SKILL.md 通常一个人写。你写了 skill 教 Claude 怎么做 X，然后你写测试检查 Claude 有没有做 X。当然能通过——你测的就是你教的。

已经做了两件事：session-feedback-analyzer（独立于 task suite 的信号来源）和 null-skill calibration（过滤掉裸跑 Claude 就能通过的任务）。但还不够。更好的方案可能是对抗性测试生成、社区贡献的 task suite、或 held-out 拆分。

另一个问题：skill 本身有副作用。加载 prompt-hardening skill 后，通过率跟裸跑一样是 86%，但是不同的 86%。你修好了 A 任务，B 任务可能就坏了。怎么量化这个 tradeoff，我还没想到好办法。

## 代码

15 个 skill，8000+ 行 Python，409 个测试，依赖只有 pyyaml 和 pytest。已发布到 ClawHub。

- GitHub: [lanyasheng/auto-improvement-orchestrator-skill](https://github.com/lanyasheng/auto-improvement-orchestrator-skill)
- ClawHub: 搜索 `auto-improvement`

几个我还在想的问题：task suite 怎么写才能不陷入循环依赖？Skill 副作用怎么量化？从用户会话日志挖隐式反馈，除了关键词匹配还有什么更好的 correction 检测方法？
