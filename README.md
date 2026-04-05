# Auto-Improvement Orchestrator

Closed-loop pipeline that evaluates, improves, and continuously optimizes AI Agent Skills.

**12 pipeline skills + 2 demo targets | 7,800+ lines Python | 390+ tests | pyyaml + pytest only**

Two demo skills (prompt-hardening, deslop) serve as end-to-end evaluation/improvement targets. A session-feedback-analyzer extracts implicit user feedback from Claude Code session logs.

---

## The Problem

AI coding agents (Claude Code, Cursor, Aider, etc.) increasingly rely on SKILL.md files -- structured instruction sets that guide agent behavior for specific tasks like code review, release notes generation, or crash analysis. A mature project might have 30+ skills.

The problem: **there is no way to know if a skill change actually makes the agent work better.**

Consider a typical skill improvement workflow:

1. Engineer edits SKILL.md to add better instructions
2. Engineer subjectively judges "this looks better"
3. The change ships. Maybe it helped, maybe it regressed something else.

Existing tools check document *structure* (does it have a frontmatter? a "When to Use" section?) but not *execution effectiveness* (does an AI agent following this skill actually produce correct output?). You can have a SKILL.md that scores 99% on structural quality metrics and still produces wrong answers on real tasks.

Manual skill iteration does not scale. When you have 28 skills and each needs periodic improvement, you need automation -- and that automation needs a feedback signal stronger than "the document looks well-formatted."

This project solves three problems:

1. **Measurement**: How good is a skill, really? (Not just structurally -- does it actually work?)
2. **Improvement**: Given measurement, can we automatically improve the weakest dimensions?
3. **Continuous optimization**: Can we run this overnight like Karpathy's autoresearch?

---

## Architecture

The system is built as 12 pipeline skills + 2 demo targets that compose into a closed-loop pipeline. Each skill is a standalone CLI tool with its own tests, and the orchestrator chains them together. Three evaluation signals: learner (structural lint, ~$0.5/eval), evaluator (execution via `claude -p`, ~$3/eval), and session-feedback-analyzer (implicit user feedback from session logs, free).

```
                        +-----------+
                        | generator |  (1) Propose improvements
                        +-----+-----+
                              |
                              v
                     +---------------+
                     | discriminator |  (2) Multi-reviewer scoring
                     +-------+-------+
                              |
                              v
                      +-----------+
                      | evaluator |  (3) Run real tasks, measure pass rate
                      +-----+-----+
                              |
                              v
                        +------+
                        | gate |  (4) 6-layer quality gate
                        +--+---+
                              |
                              v
                      +----------+
                      | executor |  (5) Apply with backup + rollback
                      +----+-----+
                              |
                              v
                      +---------+
                      | learner |  (6) Karpathy self-improvement loop
                      +---------+

     +--------------------+         +------------------+
     | autoloop-controller|         | benchmark-store  |
     | (continuous loop)  |         | (Pareto front,   |
     |  - plateau detect  |         |  frozen tests,   |
     |  - cost cap        |         |  quality tiers)  |
     |  - oscillation     |         |                  |
     +--------------------+         +------------------+

     +------------------------+
     | session-feedback-      |  Parse ~/.claude/projects/*.jsonl
     | analyzer               |  Detect corrections/acceptances
     |  -> feedback.jsonl     |  Feed back into generator
     +------------------------+

     Retry on failure (Ralph Wiggum loop):
     gate=revert --> extract trace --> inject into generator --> retry
```

### Why "Ralph Wiggum"?

The retry loop is named after the observation that naive LLM retry loops are like Ralph Wiggum saying "I'm helping!" -- they retry the same thing and fail the same way. Our loop captures a structured failure trace (which dimension regressed, what the diff was, what the gate blocker was) and injects it into the next generator call. The generator reads this trace and skips strategies that have failed 3+ times on the same dimension. This is inspired by the GEPA paper's trace-aware reflection pattern.

---

## Stage Details

### Stage 1: Generator (`improvement-generator`)

Analyzes the target skill's SKILL.md structure, reads feedback signals (user feedback files, memory patterns, previous failure traces), and produces a ranked list of improvement candidates.

**Key design decision**: Candidates are typed by category (`docs`, `reference`, `guardrail`, `prompt`, `workflow`, `tests`) and risk level (`low`, `medium`, `high`). Only `low`-risk document-type candidates are auto-executed. Everything else enters a human review queue.

```
Input:  --target /path/to/skill [--trace failure.json] [--source feedback.md]
Output: candidates.json (array of {id, category, risk_level, execution_plan})
```

### Stage 2: Discriminator (`improvement-discriminator`)

Multi-signal scoring engine with 4 independent scoring modes that can be combined:

| Mode | Flag | What it measures |
|------|------|-----------------|
| Heuristic | (default) | Category bonus + source refs + risk penalty |
| + Evaluator evidence | `--use-evaluator-evidence` | Heuristic 70% + evaluator rubric 30% |
| + LLM Judge | `--llm-judge {claude,openai,mock}` | Heuristic 60% + LLM semantic analysis 40% |
| + Multi-reviewer panel | `--panel` | 2+ independent reviewers with cognitive labels |

The panel produces cognitive consensus labels: `CONSENSUS` (all agree), `VERIFIED` (majority), or `DISPUTED` (disagreement). Disputed candidates are automatically held for human review.

```
Input:  candidates.json [--panel] [--llm-judge mock]
Output: ranking.json ({scored_candidates, recommendations: accept/hold/reject})
```

### Stage 3: Evaluator (`improvement-evaluator`)

**This is the key innovation.** Instead of just scoring the *document*, the evaluator measures whether the skill actually makes an AI agent perform better on real tasks.

It works by running a task suite -- a YAML file defining tasks with prompts and judges -- against the candidate SKILL.md using `claude -p`, then comparing the pass rate against a cached baseline.

Detailed explanation in [The Evaluator](#the-evaluator-novel-contribution) section below.

```
Input:  ranking.json + task_suite.yaml + candidate-id
Output: evaluation.json ({execution_pass_rate, baseline_pass_rate, delta, verdict})
```

### Stage 4: Gate (`improvement-gate`)

6-layer mechanical quality gate. Any layer fail = reject. No exceptions.

| Layer | Gate | Pass Condition |
|-------|------|---------------|
| 1 | **SchemaGate** | Execution result has valid JSON structure |
| 2 | **CompileGate** | Target file is syntactically valid after change |
| 3 | **LintGate** | No new lint warnings introduced |
| 4 | **RegressionGate** | No Pareto dimension regressed beyond 5% tolerance |
| 5 | **ReviewGate** | Multi-reviewer consensus is not DISPUTED+reject |
| 6 | **HumanReviewGate** | High-risk candidates require manual approval |

The gate produces one of four decisions:
- `keep` -- Change is accepted and retained
- `pending_promote` -- Valuable but needs human review
- `reject` -- Denied (no file changes made)
- `revert` -- Denied (file changes rolled back from backup)

```
Input:  ranking.json + execution.json
Output: receipt.json ({decision, per_layer_results, rollback_pointer})
```

### Stage 5: Executor (`improvement-executor`)

Applies the accepted candidate to the target file with automatic backup. Supports 4 action types:

| Action | Description |
|--------|-------------|
| `append_markdown_section` | Append a new section to the end |
| `replace_markdown_section` | Replace an existing section by heading match |
| `insert_before_section` | Insert content before a matched heading |
| `update_yaml_frontmatter` | Merge fields into YAML frontmatter |

Every execution creates a backup at `executions/backups/<run-id>/` with a rollback pointer. The executor also supports `--dry-run` for previewing changes.

```
Input:  ranking.json + candidate-id
Output: execution.json ({diff, backup_path, rollback_pointer})
```

### Stage 6: Learner (`improvement-learner`)

The real Karpathy self-improvement loop. Each iteration:

1. Evaluate current state across 6 dimensions (accuracy, coverage, reliability, efficiency, security, trigger_quality)
2. Find the weakest dimension
3. Propose a targeted improvement based on patterns + 3-layer memory
4. Backup + apply
5. Re-evaluate
6. Keep if Pareto-accepted (no dimension regressed), revert otherwise
7. Record outcome in HOT/WARM/COLD memory

**Two-tier evaluation architecture** (learner = lint, evaluator = test):

The accuracy dimension uses **LLM-as-judge** (~$0.5/eval) instead of regex checks. Experiment 5 showed that regex structural checks have R²=0.00 correlation with actual execution effectiveness. The LLM-as-judge scores 5 dimensions via `claude -p`: clarity, specificity, completeness, actionability, differentiation. A `--mock` flag provides regex fallback for testing without API costs.

The learner also supports **multi-role evaluation**: the same skill is scored from 4 perspectives (User, Developer, Security Auditor, Architect) with different dimension weights. This prevents optimizing for one stakeholder at the expense of another.

```
Input:  --skill-path /path/to/skill --max-iterations 5
Output: report.json ({iterations, kept, reverted, final_scores, memory_stats})
```

---

## The Evaluator (Novel Contribution)

### The problem with static checks

The learner scores skills across 6 structural dimensions. This is useful but insufficient. A skill can score 0.85 on accuracy (has frontmatter, "When to Use" section, code examples, etc.) while still producing wrong answers when an AI agent follows it.

Example: a release-notes generator skill might have perfect structure but fail to mention that titles should be in Chinese. Static analysis cannot catch this -- you need to actually run the skill and check the output.

### Task suite format

Task suites are YAML files that define 5-10 tasks with prompts and judges:

```yaml
skill_id: "release-notes-generator"
version: "1.0"
tasks:
  - id: "structure-01"
    description: "Release notes must have standard sections"
    prompt: |
      Based on the following commit data, generate release notes...
      - fix: fixed text click handler
      - feat: added unified template fetch API
    judge:
      type: "contains"
      expected: ["Version Overview", "New Features", "Bug Fixes"]
    timeout_seconds: 120

  - id: "isolation-01"
    description: "iOS release notes must not contain Android keywords"
    prompt: |
      Generate iOS platform release notes...
    judge:
      type: "llm-rubric"
      rubric: |
        Check that the output does NOT contain "Kotlin", "Android",
        "Java" keywords. Score 1.0 if clean, 0.0 if any leakage.
      pass_threshold: 0.8
```

### Three judge types

| Judge | Mechanism | Best for |
|-------|-----------|----------|
| **ContainsJudge** | Checks output contains all expected keywords (case-insensitive) | Deterministic structural checks |
| **PytestJudge** | Writes AI output to temp file, runs pytest with `AI_OUTPUT_FILE` env var | Structured output validation |
| **LLMRubricJudge** | LLM scores output against a rubric (mock mode available) | Semantic quality assessment |

The PytestJudge has a security constraint: `test_file` must start with `fixtures/` to prevent path traversal.

### Baseline comparison with 7-day TTL cache

The evaluator runs the task suite twice: once with the candidate SKILL.md and once with the original (baseline) SKILL.md. The baseline result is cached with a 7-day TTL using a content-hash key (SHA-256 of skill content + suite path).

If the baseline pass rate is below 20%, the evaluator aborts -- the task suite itself is probably broken.

### Conditional evaluation

The evaluator only runs when the discriminator score exceeds a threshold (default: 6.0). This saves 60%+ of evaluation cost on low-quality candidates that would fail the gate anyway.

```python
if candidate_score < args.eval_threshold:
    # Skip evaluation, return verdict="skipped"
    return
```

### Standalone mode

For quick testing without the full pipeline:

```bash
python3 scripts/evaluate.py \
  --task-suite /path/to/task_suite.yaml \
  --state-root /tmp/eval \
  --standalone \
  --mock  # or remove --mock to use real claude -p
```

---

## Autoloop Controller

Wraps the orchestrator in a persistent loop with convergence detection and cost control. Inspired by Karpathy's autoresearch pattern of running improvement overnight.

### 3 modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| `single-run` | CLI / cron | Run iterations until termination, then exit |
| `continuous` | CLI | Loop with configurable cooldown between iterations |
| `scheduled` | system cron | Exit after each iteration, cron triggers next |

### 4 termination conditions (OR logic)

1. **max_iterations** reached (default: 5)
2. **cost_cap** exceeded (default: $50)
3. **score plateau** detected -- N consecutive rounds with no improvement
4. **oscillation** detected -- keep-reject-keep-reject alternating pattern

Plateau detection:

```python
def detect_plateau(score_history, window=3):
    """Returns True if best score in last `window` rounds
    does not exceed the historical best before that window."""
    recent = score_history[-window:]
    earlier = score_history[:-window]
    best_before = max(h["weighted_score"] for h in earlier)
    best_recent = max(h["weighted_score"] for h in recent)
    return best_recent <= best_before
```

Oscillation detection:

```python
def detect_oscillation(score_history, window=4):
    """Detect keep-reject-keep-reject alternating pattern."""
    recent_decisions = [h["decision"] for h in score_history[-window:]]
    return recent_decisions in [
        ["keep", "reject"] * (window // 2),
        ["reject", "keep"] * (window // 2),
    ]
```

### State persistence for cross-session resumption

All state is persisted to `autoloop_state.json` after each iteration. If the process is killed and restarted, it picks up from where it left off:

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

An append-only `iteration_log.jsonl` provides a full audit trail.

---

## Real Experiment Results

These results are from running the system on a real project with 28 AI coding skills.

### Experiment 1: Batch evaluation of 28 project skills

We ran the learner's 6-dimension evaluation on all 28 skills in the project.

**Distribution:**

| Tier | Score Range | Count | Skills |
|------|------------|-------|--------|
| POWERFUL | >= 0.85 | 0 | -- |
| SOLID (high) | 0.79-0.80 | 5 | code-review, crash-analysis, static-analysis, doc-gen, component-dev |
| SOLID | 0.70-0.78 | 18 | cpp-expert, ios-expert, android-expert, etc. |
| GENERIC | 0.65-0.69 | 5 | perf-profiler, component-dev, skill-creator, release-notes, system-maintenance |

Key finding: **zero skills reached POWERFUL tier out of the box.** Even well-maintained skills had accuracy gaps (missing `<example>` tags, vague language, incomplete Output Artifacts sections).

### Experiment 2: Self-improvement loop on lowest-scoring skill

Target: `system-maintenance` skill, starting score 0.653 (GENERIC tier).

**Result: 0.653 --> 0.803 in 3 iterations, 3/3 improvements kept.**

| Iteration | Type | Description | Score Before | Score After | Decision |
|-----------|------|-------------|-------------|-------------|----------|
| 1 | accuracy | Add frontmatter + When to Use/Not sections | 0.653 | 0.715 | keep |
| 2 | reliability | Auto-generate test stubs for scripts/ | 0.715 | 0.770 | keep |
| 3 | accuracy | Add `<example>` and `<anti-example>` tags | 0.770 | 0.803 | keep |

The biggest single-dimension gain: **reliability 0.30 --> 1.00** (from "has scripts but no tests" to "has scripts with passing tests"). The learner auto-generated test stubs that actually passed, which flipped the reliability score.

6-dimension profile before/after:

```
Dimension        Before   After   Delta
accuracy         0.67     0.85    +0.18
coverage         0.60     0.80    +0.20
reliability      0.30     1.00    +0.70
efficiency       0.87     0.85    -0.02 (within 5% tolerance)
security         0.83     0.83     0.00
trigger_quality  0.60     0.80    +0.20
```

### Experiment 3: Execution effectiveness evaluation

We wrote a 7-task suite for a release-notes generator skill and ran it with real `claude -p` execution (not mock mode).

**Result: 86% pass rate (6/7 tasks passed).**

| Task | Type | Verdict |
|------|------|---------|
| Structure check | ContainsJudge | PASS |
| Platform isolation (iOS) | ContainsJudge | PASS |
| Platform leakage detection | LLMRubricJudge | PASS |
| Commit categorization | ContainsJudge | PASS |
| Commit hash references | ContainsJudge | PASS |
| Bad release notes review | ContainsJudge | PASS |
| Module classification | ContainsJudge | **FAIL** |

The 1 failure revealed a real gap: the SKILL.md did not specify how to classify changed files into framework modules. The AI guessed wrong module names because the skill never defined the mapping.

**This is exactly the kind of problem static analysis can never find.** The skill had all the right sections, frontmatter, examples -- but was missing one critical piece of domain knowledge that only shows up when you actually run it against real tasks.

### Experiment 4: Batch improvement of 4 GENERIC-tier skills

We ran the autoloop controller on all 4 skills scoring in the GENERIC tier:

| Skill | Before | After | Kept/Total | Key Improvement |
|-------|--------|-------|------------|----------------|
| perf-profiler | 0.661 | 0.803 | 2/3 | Test stubs + frontmatter |
| component-dev | 0.665 | 0.798 | 1/3 | Accuracy (missing sections) |
| skill-creator | 0.667 | 0.800 | 1/3 | Test stubs |
| release-notes | 0.681 | 0.831 | 3/3 | All dimensions improved |

Average improvement: **+0.138** (from GENERIC to SOLID tier).

Total cost: approximately $15-20 in API calls for all 4 skills combined.

The 2/3 and 1/3 kept/total ratios are healthy -- they mean the gate and Pareto front are working. Candidates that regressed any dimension were correctly reverted.

### Experiment 5: Learner-Evaluator Correlation Analysis (P2)

**Question: Does the learner's structural scoring predict actual execution effectiveness?**

We ran the evaluator's task suites (with real `claude -p` execution and SKILL.md prepended) on 5 skills, then computed Pearson correlation against the learner's dimension scores.

**Data:**

| Skill | Learner Accuracy | Learner WS | Evaluator Pass Rate |
|-------|-----------------|------------|-------------------|
| deslop | 0.88 | 0.754 | 100% (7/7) |
| skill-creator | 0.70 | 0.715 | 100% (7/7) |
| prompt-hardening | 0.88 | 0.802 | 86% (6/7) |
| skill-distill | 0.88 | 0.756 | 86% (6/7) |
| improvement-gate | 0.76 | 0.754 | 71% (5/7) |

**Result: R² = 0.00, Pearson r = -0.0001 (accuracy vs pass rate)**

The learner's accuracy dimension has **zero predictive power** for evaluator pass rate. The overall weighted score fares slightly better at r = -0.40 but in the **wrong direction** (higher learner score → lower pass rate).

**Per-check analysis** (26 original accuracy checks):
- 17/26 checks (65%) had **no variance** — all 5 skills passed, providing zero discrimination
- 3 checks were **anti-predictive** (passing them correlated with *lower* pass rates):
  - `version` in frontmatter (r=-0.76)
  - References files exist (r=-0.54)
  - Examples contain specific I/O (r=-0.54)
- Only 1 check positively predicted pass rate: `Has workflow/steps` (r=+0.80)

**After refactoring** to a two-tier system (5 gate checks + 10 execution-predictive checks), accuracy correlation remained at r = -0.0001. This confirms:

> **Structural analysis of SKILL.md cannot predict execution effectiveness.** A skill with "poor" structure (missing sections, no version field) can still guide Claude perfectly — and a "well-structured" skill can still fail on real tasks.

The fundamental gap is between *document quality* (does the SKILL.md look right?) and *guidance quality* (does the SKILL.md actually change Claude's behavior?). The evaluator's task suites are the only thing that measures guidance quality, but they have their own circularity problem (see Known Limitations below).

**Implication for the pipeline:** The learner's accuracy score should NOT be used as a predictor of evaluator pass rate. Instead:
1. Use evaluator pass rate as the primary quality signal
2. Use learner scores only for structural hygiene (table stakes)
3. Build the user feedback loop (see below) for real-world signal

### Experiment 6: Prompt-hardening three-way comparison

**Question: Does a Skill actually make Claude perform better on real tasks?**

We ran the prompt-hardening task suite (7 tasks) in two configurations using `claude -p` with real LLM execution:

- **Group A**: No skill (bare Claude, no SKILL.md injected)
- **Group B**: v1 prompt-hardening SKILL.md injected as context

| Task | Group A (No Skill) | Group B (v1 Skill) |
|------|----|----|
| P1 triple reinforcement | PASS | PASS |
| P5 anti-reasoning | PASS | PASS |
| Audit output format (/16) | **PASS** | **FAIL** (missing `/16`) |
| CLI reference (audit.sh) | **FAIL** (doesn't know audit.sh) | **PASS** |
| Pattern selection | PASS | PASS |
| Reliability levels | PASS | PASS |
| End-to-end hardening | PASS | PASS |
| **Pass Rate** | **86% (6/7)** | **86% (6/7)** |

**Key finding: same pass rate, different failures.**

The skill adds value where it provides specific knowledge (CLI command path), but changes AI behavior in ways that cause a different failure (output format). This has three implications:

1. **Skill value is in knowledge injection, not general ability uplift.** Claude already knows MUST/NEVER patterns and anti-reasoning blocks. The skill's value is specific: `audit.sh` path, P1-P16 numbering system, reliability percentages.

2. **Skills can introduce new failure modes.** Group B fails on audit output format because the skill shifts Claude's output preferences -- it focuses on patterns but drops the `/16` denominator. Every skill change is a tradeoff.

3. **Pass rate alone is insufficient.** Per-task comparison reveals behavior differences that aggregate metrics hide. Future evaluation should track which tasks improve/regress with each skill version.

### Known Limitations

#### P1: Evaluator Circularity

The evaluator's task suites are created by the same author who writes the SKILL.md. This creates circular reasoning:

```
Author writes SKILL.md → Author writes task_suite.yaml → Evaluator tests SKILL.md against task_suite.yaml
```

A skilled author naturally writes tasks that test what the skill teaches. An unskilled author writes tasks that are too easy or miss real failure modes. The evaluator grade reflects **authoring consistency**, not **absolute quality**.

Evidence from Experiment 5: `skill-creator` has the lowest structural score (0.70) but 100% pass rate. This likely means the task suite is well-aligned with what the skill does — but tells us nothing about whether the skill would handle *unexpected* or *adversarial* inputs.

**Mitigation strategies** (not yet implemented):
1. **Cross-pollination**: Have the generator create adversarial tasks that try to break a skill
2. **User feedback**: Real user corrections are the only independent signal (see User Feedback Loop design)
3. **Held-out tasks**: Split task suites into training (used during improvement) and test (only used for final evaluation)
4. **Community task suites**: Third parties contribute tasks without seeing the SKILL.md

#### P3: Small Sample Size

With N=5 skills, the correlation analysis has low statistical power. A single outlier (skill-creator at 100% pass rate despite low structural score) can dominate the results. More skills need to be evaluated before drawing definitive conclusions.

---

## Design Decisions

### Why Not Git Worktrees?

We initially used `git worktree add` to create an isolated branch for each evaluation run. This was architecturally clean but practically painful:

- Creating/destroying worktrees is slow compared to `tempfile.mkdtemp()`
- Worktree management added 50+ lines of git plumbing code
- Review feedback: "overkill for single-file evaluation"
- The isolated evaluation only needs the SKILL.md content, not a full repo checkout

Current approach: tempdir + prompt injection. Write the candidate SKILL.md content to a temp file, prepend it to the task prompt, run `claude -p`, check the output. 10x faster, same isolation guarantees for our use case.

### Why Default pass@1 Instead of pass@3?

LLM outputs are non-deterministic. Running each task 3 times (pass@3) and taking the best result gives a more stable signal. But:

- Cost: 7 tasks x pass@3 = 21 API calls per evaluation
- Default pass@1 keeps evaluation cost at ~$2.5-5 per run
- pass@3 is available via `--pass-k 3` for high-stakes decisions (e.g., before shipping to a marketplace)

The evaluator supports configurable pass@k, but defaults to 1 for the common case of rapid iteration.

### Why Pareto Front Instead of Single Score?

A single weighted score (0.0-1.0) is convenient but dangerous. Consider:

- Baseline: accuracy=0.85, coverage=0.70
- Candidate: accuracy=0.70, coverage=0.85
- Weighted score: identical (assuming equal weights)

The candidate "improved" coverage by destroying accuracy. A single scalar hides this regression.

The Pareto front enforces: **each dimension must independently not regress beyond 5% tolerance.**

```python
def check_regression(new_scores):
    for dim, new_val in new_scores.items():
        best_val = best_known.get(dim, 0.0)
        if new_val < best_val * 0.95:  # 5% tolerance
            return {"regressed": True, "regressions": [dim]}
    return {"regressed": False}
```

The 5% tolerance prevents rejecting improvements due to minor measurement noise.

### Why Conditional Evaluation?

The evaluator is expensive (it calls `claude -p` for each task). Running it on every candidate wastes money on low-quality proposals that will fail the gate anyway.

The discriminator score acts as a cheap pre-filter. Only candidates scoring above the threshold (default: 6.0) proceed to evaluation. In practice, this saves 60%+ of evaluation cost.

### Why Three-Layer Memory?

The learner maintains a HOT/WARM/COLD memory hierarchy:

| Layer | Capacity | Behavior |
|-------|----------|----------|
| HOT | <= 100 entries | Always loaded. Frequently accessed patterns. |
| WARM | Unlimited | Overflow from HOT when it exceeds 100. Loaded on demand. |
| COLD | Archive | > 3 months inactive (planned, not yet implemented). |

When the HOT layer overflows, entries are ranked by `hit_count` and the least-accessed ones spill to WARM. This prevents unbounded memory growth while keeping recent patterns fast to query.

The memory records both successes and failures. If a strategy has failed 3+ times on the same dimension, the generator skips it entirely -- no more wasting iterations on approaches that do not work for this skill.

---

## Comparison with Existing Approaches

| Approach | What it measures | Feedback loop | Execution test | Multi-dimension |
|----------|-----------------|---------------|----------------|-----------------|
| **This project** | Structure + Execution | Auto-retry with traces | Yes (task suites) | Yes (Pareto front) |
| Aider Benchmark | Code correctness | Manual iteration | Yes (Exercism) | No (single pass rate) |
| Karpathy autoresearch | Single scalar (val_bpb) | Keep/discard loop | Yes (training loss) | No |
| DSPy | User-defined metric | Bayesian optimization | Depends on metric | No (single objective) |
| PromptFoo | Assertion pass rate | Manual | Partial (rubrics) | No |
| ADAS (ICLR 2025) | Meta agent search | Architecture search | Agent benchmarks | No |
| GEPA (ICLR 2026) | LLM reflection quality | Trace injection | Yes | No |

Key differences:
- **Structure + execution measurement**: We measure both document quality (6 dimensions) and execution effectiveness (task suites). Most tools do one or the other.
- **Multi-dimensional Pareto front**: Prevents "fix accuracy by breaking coverage." DSPy, Aider, and autoresearch all use single scalar objectives.
- **Trace-aware retry**: Like GEPA's reflection, but applied to skill improvement rather than code generation. Failed attempts are not wasted -- they inform the next attempt.

---

## Installation

```bash
# Clone
git clone https://github.com/lanyasheng/auto-improvement-orchestrator-skill.git
cd auto-improvement-orchestrator-skill

# Install dependencies (only pyyaml + pytest)
pip install pyyaml pytest

# Run all tests
python3 -m pytest skills/*/tests/ -v
```

### Quick evaluation of a single skill

```bash
# Score a skill across 6 dimensions (no changes made)
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/your/skill \
  --max-iterations 1
```

Output:
```json
{
  "final_scores": {
    "accuracy": 0.83,
    "coverage": 0.80,
    "reliability": 1.00,
    "efficiency": 0.87,
    "security": 0.83,
    "trigger_quality": 0.60
  },
  "iterations": 1,
  "kept": 0,
  "reverted": 0
}
```

### Run task suite evaluation (standalone mode)

```bash
python3 skills/improvement-evaluator/scripts/evaluate.py \
  --task-suite /path/to/task_suite.yaml \
  --state-root /tmp/eval \
  --standalone \
  --mock  # remove for real claude -p execution
```

### Self-improvement loop (5 iterations)

```bash
python3 skills/improvement-learner/scripts/self_improve.py \
  --skill-path /path/to/your/skill \
  --max-iterations 5 \
  --memory-dir /tmp/memory \
  --state-root /tmp/state
```

### Full orchestrator pipeline

```bash
python3 skills/improvement-orchestrator/scripts/orchestrate.py \
  --target /path/to/skill \
  --state-root /tmp/state \
  --max-retries 3 \
  --auto
```

### Continuous improvement (autoloop)

```bash
python3 skills/autoloop-controller/scripts/autoloop.py \
  --target /path/to/skill \
  --state-root /tmp/autoloop \
  --max-iterations 5 \
  --max-cost 50.0 \
  --plateau-window 3 \
  --mode single-run
```

### Writing a task suite

Create a YAML file following this schema:

```yaml
skill_id: "your-skill-name"
version: "1.0"
tasks:
  - id: "unique-task-id"
    description: "Human-readable description of what this tests"
    prompt: "The prompt sent to claude -p with SKILL.md prepended"
    judge:
      type: "contains"  # or "pytest" or "llm-rubric"
      expected: ["keyword1", "keyword2"]
    timeout_seconds: 120
```

See `skills/improvement-evaluator/references/task-format.md` and `skills/improvement-evaluator/references/writing-tasks-guide.md` for the full specification.

---

## Project Structure

```
skills/
  improvement-generator/     # Stage 1: Propose candidates
    scripts/propose.py
    tests/test_propose.py
    SKILL.md

  improvement-discriminator/ # Stage 2: Multi-reviewer scoring
    scripts/score.py
    interfaces/              # LLM judge, assertions, panel
    tests/

  improvement-evaluator/     # Stage 3: Execution effectiveness
    scripts/evaluate.py
    scripts/task_runner.py
    interfaces/judges.py     # ContainsJudge, PytestJudge, LLMRubricJudge
    task_suites/             # Example task suites
    references/              # Task format spec, writing guide
    tests/

  improvement-gate/          # Stage 4: 6-layer quality gate
    scripts/gate.py
    scripts/review.py        # Human review queue management
    tests/

  improvement-executor/      # Stage 5: Apply with backup/rollback
    scripts/execute.py
    scripts/rollback.py
    tests/

  improvement-learner/       # Stage 6: Karpathy self-improvement loop
    scripts/self_improve.py
    scripts/track_progress.py
    tests/

  improvement-orchestrator/  # Pipeline coordinator
    scripts/orchestrate.py
    references/              # Architecture, guardrails, phases, demo
    tests/

  autoloop-controller/       # Continuous loop wrapper
    scripts/autoloop.py
    scripts/convergence.py
    scripts/cost_tracker.py
    references/              # State format, scheduling guide
    tests/

  benchmark-store/           # Frozen benchmarks + Pareto front
    scripts/benchmark_db.py
    data/                    # Evaluation standards, test cases, fixtures
    interfaces/              # Frozen benchmark, hidden tests
    tests/

  session-feedback-analyzer/ # User feedback from session logs
    scripts/analyze.py       # JSONL parser, skill invocation detector, outcome classifier
    scripts/metrics.py       # correction_rate, trend, dimension hotspots
    tests/

lib/
  common.py                  # Shared utilities (read_json, write_json, timestamps)
  pareto.py                  # ParetoFront + ParetoEntry
```

---

## Quality Tiers

The benchmark store defines 4 quality tiers based on weighted score:

| Tier | Score | Ship? |
|------|-------|-------|
| **POWERFUL** | >= 85% | Marketplace ready |
| **SOLID** | 70-84% | GitHub |
| **GENERIC** | 55-69% | Needs iteration |
| **WEAK** | < 55% | Reject or rewrite |

Weights: accuracy 30% + coverage 20% + reliability 20% + efficiency 15% + security 15%.

These weights are adjustable per skill category (tool, knowledge, orchestration, review, rule, learning).

---

## References

- **Karpathy autoresearch** -- The keep/discard loop pattern. "Run overnight, keep improvements, discard regressions."
- **GEPA (ICLR 2026)** -- Trace-aware reflection. Failed attempts are not wasted; their traces inform the next attempt.
- **ADAS (ICLR 2025)** -- Meta Agent Searching. The idea that agents can search over their own architecture.
- **Aider Benchmark** -- Coding agent evaluation using real coding tasks (Exercism). Showed that execution-based evaluation is possible and valuable.
- **Anthropic harness design** -- GAN-style generator/evaluator architecture for self-improving systems.
- **alirezarezvani/claude-skills** -- 10 quality patterns for skill authoring, trigger evaluation with should-trigger/should-not queries.
- **DSPy** -- Bayesian optimization of LLM prompts. Different approach (optimize prompt tokens directly) but same goal (automated prompt improvement).

---

See [docs/design/user-feedback-loop.md](docs/design/user-feedback-loop.md) for the full user feedback loop design document (not yet implemented).

---

## License

MIT
