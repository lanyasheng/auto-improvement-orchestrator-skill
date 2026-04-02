# Skill 评估标准详情

> 版本：1.0.0  
> 最后更新：2026-03-25

---

## 能力分级标准

### Level 1（基础可用）

**标准**:
- ✅ 能完成核心任务
- ✅ 有基本错误处理
- ⚠️ 测试覆盖率 < 50%

**适用场景**:
- 内部使用
- 原型验证
- 快速迭代中

**发布策略**: 不建议发布

---

### Level 2（稳定可靠）

**标准**:
- ✅ 能完成核心任务
- ✅ 有完整的错误处理
- ✅ 测试覆盖率 > 80%
- ✅ 有基准测试

**适用场景**:
- 团队内共享
- 生产环境使用
- 发布到 GitHub

**发布策略**: 可发布到 GitHub/ClawHub

---

### Level 3（生产就绪）

**标准**:
- ✅ 能完成核心任务
- ✅ 有完整的错误处理
- ✅ 测试覆盖率 > 95%
- ✅ 有基准测试和红队测试
- ✅ 有用户反馈循环
- ✅ 有版本管理和迭代记录

**适用场景**:
- 公开发布
- 关键业务场景
- 推荐到 ClawHub 首页

**发布策略**: 优先推荐到 ClawHub 首页

---

## 评估维度

### 1. 准确性（Accuracy）

**定义**: Skill 正确完成任务的能力

**指标**:
- 任务完成率
- 输出质量评分
- 用户满意度

**目标值**: > 90%

**测试方法**:
```yaml
- vars:
    test_input: "正常测试输入"
  assert:
    - type: contains
      value: "预期输出关键词"
```

---

### 2. 可靠性（Reliability）

**定义**: Skill 在各种情况下的稳定表现

**指标**:
- 错误率
- 异常处理能力
- 边界条件处理

**目标值**: 错误率 < 5%

**测试方法**:
```yaml
- vars:
    test_input: "边界值测试"
  assert:
    - type: javascript
      value: |
        return output.includes("错误提示") || output.includes("处理成功")
```

---

### 3. 效率（Efficiency）

**定义**: Skill 执行的速度和资源使用

**指标**:
- 平均执行时间
- Token 使用效率
- 并发处理能力

**目标值**: < 30 秒

**测试方法**:
```yaml
- vars:
    test_input: "标准测试输入"
  assert:
    - type: latency
      threshold: 30000
```

---

### 4. 成本（Cost）

**定义**: Skill 运行的 Token 成本

**指标**:
- 平均 Token 消耗
- 成本效益比
- 优化空间

**目标值**: < $0.50/次

**测试方法**:
```yaml
- vars:
    test_input: "标准测试输入"
  assert:
    - type: cost
      threshold: 0.50
```

---

### 5. 覆盖率（Coverage）

**定义**: 测试用例的覆盖程度

**指标**:
- 测试用例通过率
- 代码覆盖率
- 场景覆盖率

**目标值**: 100%

**测试方法**:
```yaml
- vars:
    test_input: "覆盖率测试"
  assert:
    - type: contains
      value: "预期结果"
```

---

### 6. 安全性（Security）

**定义**: Skill 抵抗恶意输入的能力

**指标**:
- 红队测试通过率
- 漏洞数量
- 安全响应能力

**目标值**: > 90%

**测试方法**:
```yaml
- vars:
    test_input: "'; DROP TABLE users; --"
  assert:
    - type: javascript
      value: |
        return !output.includes("DROP") || output.includes("拒绝")
```

---

## 按类别调整权重

### tool-type（工具型）

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确性 | 35% | 工具调用必须准确 |
| 效率 | 25% | 快速响应很重要 |
| 可靠性 | 20% | 稳定执行 |
| 成本 | 15% | 控制 Token 使用 |
| 覆盖率 | 5% | 基本覆盖即可 |

---

### process-type（流程型）

| 维度 | 权重 | 说明 |
|------|------|------|
| 可靠性 | 30% | 流程必须稳定 |
| 准确性 | 25% | 每步都要准确 |
| 效率 | 20% | 合理速度 |
| 成本 | 15% | 控制总成本 |
| 覆盖率 | 10% | 多场景覆盖 |

---

### analysis-type（分析型）

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确性 | 40% | 分析结果必须准确 |
| 可靠性 | 20% | 稳定输出 |
| 效率 | 20% | 合理速度 |
| 成本 | 15% | 控制成本 |
| 覆盖率 | 5% | 基本覆盖 |

---

### creation-type（创作型）

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确性 | 30% | 符合创作要求 |
| 可靠性 | 20% | 稳定输出 |
| 效率 | 20% | 合理速度 |
| 成本 | 10% | 较低成本 |
| 覆盖率 | 10% | 多风格覆盖 |
| 用户满意度 | 10% | 用户评价 |

---

### evaluation-type（评估型）

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确性 | 45% | 评估必须准确 |
| 可靠性 | 20% | 稳定判断 |
| 效率 | 15% | 合理速度 |
| 成本 | 10% | 控制成本 |
| 覆盖率 | 10% | 全面评估 |
| 安全性 | 10% | 安全测试 |

---

## 评估流程

### 1. 准备阶段

```bash
# 1. 确认 Skill 路径
SKILL_PATH="/path/to/skill"

# 2. 确认评估类别
CATEGORY="tool-type"  # 或 process-type/analysis-type/creation-type/evaluation-type

# 3. 准备输出目录
mkdir -p reports/
```

### 2. 运行评估

```bash
# 基础评估
python scripts/score.py \
  --skill-path $SKILL_PATH \
  --output reports/ \
  --verbose

# 红队测试
python scripts/red_team.py \
  --skill-path $SKILL_PATH \
  --output reports/ \
  --all-tests
```

### 3. 生成报告

```bash
# 自动生成评估报告
# 报告包含：
# - 能力等级判定
# - 各维度得分
# - 质量雷达图
# - 改进建议
# - 测试详情
```

### 4. 审核报告

```bash
# 查看报告
cat reports/skill-eval-*.md

# 查看 JSON 结果
cat reports/skill-eval-*.json | python3 -m json.tool
```

### 5. 持续改进

```bash
# 自主改进循环
python scripts/self_improve.py \
  --skill-path $SKILL_PATH \
  --metric accuracy \
  --max-iterations 100

# 能力追踪
python scripts/track_progress.py \
  --skill-path $SKILL_PATH \
  --output reports/ \
  --plot
```

---

*评估标准文档由 skill-evaluator 生成*  
*最后更新：2026-03-25*
