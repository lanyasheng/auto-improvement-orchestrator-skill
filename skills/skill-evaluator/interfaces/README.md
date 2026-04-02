# Skill Evaluator - Critic Phase 2

Phase 2 增强版本，提供 Frozen Benchmark 和 Hidden Tests 的完整接口定义和最小实现。

## 文件结构

```
interfaces/
├── __init__.py           # 接口导出
├── frozen_benchmark.py   # 冻结基准测试接口 (530+ 行)
├── hidden_tests.py       # 隐藏测试接口 (480+ 行)
├── critic_engine.py      # Critic 引擎最小实现 (520+ 行)
├── examples.py           # 使用示例 (280+ 行)
└── README.md             # 本文档
```

## 核心特性

### 1. Frozen Benchmark (冻结基准测试)

**设计目标**: 确保评估的一致性和可比性

**关键特性**:
- **不可变性**: 测试用例一旦创建即冻结，防止篡改
- **完整性校验**: 每个用例和套件都有数字签名
- **版本控制**: 语义化版本管理，支持套件演进
- **多维度评分**: 准确性、可靠性、效率、成本、覆盖率、安全性

**核心类**:
| 类名 | 用途 |
|------|------|
| `BenchmarkCase` | 单个测试用例 (frozen) |
| `BenchmarkSuite` | 测试套件 (frozen) |
| `BenchmarkResult` | 测试结果 |
| `ScoringCriteria` | 评分标准 (frozen) |
| `FrozenBenchmark` | 基准测试执行器 |

### 2. Hidden Tests (隐藏测试)

**设计目标**: 防止测试污染和过度拟合

**关键特性**:
- **加密存储**: 测试内容加密，执行时解密
- **访问控制**: 需要密码解锁才能运行
- **分级可见**: public/protected/hidden 三级可见性
- **类型多样**: 功能、边界、对抗、安全、性能、分布外测试

**核心类**:
| 类名 | 用途 |
|------|------|
| `HiddenTest` | 单个隐藏测试 (加密存储) |
| `HiddenTestSuite` | 隐藏测试套件管理 |
| `TestResult` | 测试结果 |
| `TestMetadata` | 公开元数据 |
| `create_hidden_test()` | 隐藏测试工厂函数 |

### 3. Critic Engine (评估引擎)

**设计目标**: 整合两种测试类型的统一评估

**关键特性**:
- **加权评分**: 基准测试和隐藏测试权重可配置
- **等级判定**: Level 1/2/3 自动判定
- **综合报告**: Markdown + JSON 双格式输出
- **可扩展**: 协议/接口设计，易于扩展

**核心类**:
| 类名 | 用途 |
|------|------|
| `CriticConfig` | 评估配置 |
| `CriticScore` | 评分结果 |
| `CriticEngine` | 主评估引擎 |

## 快速开始

### 运行演示

```bash
cd ~/.openclaw/skills/skill-evaluator
python3 interfaces/critic_engine.py
```

### 运行示例

```bash
python3 interfaces/examples.py
```

### 基础用法

```python
from interfaces import CriticEngine, CriticConfig

# 创建配置
config = CriticConfig(
    enable_frozen_benchmark=True,
    enable_hidden_tests=True,
    benchmark_weight=0.5,
    hidden_test_weight=0.5,
)

# 创建引擎
engine = CriticEngine(config)

# 加载测试套件
engine.load_benchmark_suite()  # 标准套件
engine.load_hidden_tests()       # 演示套件

# 运行评估
score = engine.evaluate()

# 生成报告
print(f"Level: {score.level}")
print(f"Overall: {score.overall:.4f}")
engine.generate_report("report.md")
```

## 等级标准

### Level 1 (基础可用)
- 总体得分 ≥ 0.60
- 通过率 ≥ 60%
- 有基本功能实现

### Level 2 (稳定可靠)
- 总体得分 ≥ 0.75
- 通过率 ≥ 80%
- 有完整错误处理
- 有基准测试覆盖

### Level 3 (生产就绪)
- 总体得分 ≥ 0.90
- 通过率 ≥ 95%
- 有基准测试 + 隐藏测试
- 有安全测试覆盖

## 接口定义摘要

### Frozen Benchmark Interface

```python
@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    name: str
    input_data: Any
    expected_output: Any
    category: str
    difficulty: int
    tags: tuple
    checksum: str  # 数据完整性校验

    def verify_integrity(self) -> bool:
        """验证数据未被篡改"""
```

```python
class FrozenBenchmark:
    def __init__(self, suite: BenchmarkSuite):
        """初始化，验证套件完整性"""

    def run(self, evaluator: Evaluator) -> Dict[str, Any]:
        """运行基准测试，返回完整报告"""
```

### Hidden Tests Interface

```python
@dataclass(frozen=True)
class HiddenTest:
    metadata: TestMetadata      # 公开信息
    encrypted_input: bytes      # 加密输入
    encrypted_expected: bytes   # 加密期望输出
    encrypted_validator: bytes  # 加密验证逻辑
    salt: bytes
    visibility: TestVisibility

    def verify_hash(self, input_data, expected_output) -> bool:
        """验证解密后的数据完整性"""
```

```python
class HiddenTestSuite:
    def unlock(self, password: str) -> bool:
        """解锁测试套件"""

    def run_all(self, skill: SkillUnderTest) -> Dict[str, Any]:
        """运行所有隐藏测试"""
```

## 与 Phase 1 对比

| 特性 | Phase 1 | Phase 2 |
|------|---------|---------|
| 基准测试 | 基础 Promptfoo 集成 | Frozen Benchmark (不可变) |
| 隐藏测试 | 无 | 完整实现 (加密/解锁) |
| 评分 | 简单百分比 | 多维度加权评分 |
| 等级判定 | 基于目录结构 | 基于量化评分 |
| 报告 | Markdown 基础 | Markdown + JSON + 改进建议 |
| 完整性校验 | 无 | SHA256 签名验证 |

## 后续扩展

1. **真实加密**: 当前使用简单 XOR，生产环境应使用 AES-GCM 或 ChaCha20-Poly1305
2. **沙箱执行**: 隐藏测试验证器应在沙箱中执行
3. **密钥管理**: 集成 KMS 或 HSM 进行密钥管理
4. **分布式评估**: 支持多节点并行评估
5. **可视化**: 添加评估结果可视化仪表板

## 验收检查

- [x] 明确的接口定义 (可执行/可验证)
- [x] 最小实现代码 (不只是文档)
- [x] 可以实际运行并产出评分结果
- [x] 围绕 frozen benchmark / hidden tests，不是空写大文档
