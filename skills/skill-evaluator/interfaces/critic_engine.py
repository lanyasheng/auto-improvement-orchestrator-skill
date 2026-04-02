#!/usr/bin/env python3
"""
Critic Engine Phase 2 - Minimal Implementation

整合 Frozen Benchmark 和 Hidden Tests 的核心评估引擎。
提供统一的评估接口和可运行的最小实现。
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import json
import time

try:
    from .frozen_benchmark import (
        BenchmarkCase,
        BenchmarkResult,
        BenchmarkSuite,
        FrozenBenchmark,
        MetricType,
        ScoringCriteria,
        STANDARD_BENCHMARK_SUITE,
    )
    from .hidden_tests import (
        HiddenTest,
        HiddenTestSuite,
        TestResult,
        TestType,
        TestVisibility,
        create_hidden_test,
    )
except ImportError:
    from frozen_benchmark import (
        BenchmarkCase,
        BenchmarkResult,
        BenchmarkSuite,
        FrozenBenchmark,
        MetricType,
        ScoringCriteria,
        STANDARD_BENCHMARK_SUITE,
    )
    from hidden_tests import (
        HiddenTest,
        HiddenTestSuite,
        TestResult,
        TestType,
        TestVisibility,
        create_hidden_test,
    )


@dataclass
class CriticConfig:
    """
    Critic 评估配置

    Attributes:
        enable_frozen_benchmark: 启用冻结基准测试
        enable_hidden_tests: 启用隐藏测试
        benchmark_weight: 基准测试权重 (0.0 - 1.0)
        hidden_test_weight: 隐藏测试权重 (0.0 - 1.0)
        min_pass_rate: 最低通过率要求
        timeout_seconds: 单测试超时时间
        verbose: 详细输出模式
    """
    enable_frozen_benchmark: bool = True
    enable_hidden_tests: bool = True
    benchmark_weight: float = 0.5
    hidden_test_weight: float = 0.5
    min_pass_rate: float = 0.6
    timeout_seconds: float = 30.0
    verbose: bool = False

    def __post_init__(self):
        assert abs(self.benchmark_weight + self.hidden_test_weight - 1.0) < 0.001, \
            "Benchmark weight + hidden test weight must equal 1.0"


@dataclass
class CriticScore:
    """
    Critic 评估得分

    Attributes:
        overall: 总体得分 (0.0 - 1.0)
        benchmark_score: 基准测试得分
        hidden_test_score: 隐藏测试得分
        pass_rate: 通过率
        by_metric: 各指标得分
        level: 等级 (1/2/3)
        verdict: 评审结论
    """
    overall: float = 0.0
    benchmark_score: float = 0.0
    hidden_test_score: float = 0.0
    pass_rate: float = 0.0
    by_metric: Dict[str, float] = field(default_factory=dict)
    level: int = 1
    verdict: str = "pending"

    def __post_init__(self):
        assert 0.0 <= self.overall <= 1.0, "Overall score must be in [0, 1]"

    @classmethod
    def from_results(
        cls,
        benchmark_results: Optional[Dict],
        hidden_test_results: Optional[Dict],
        config: CriticConfig,
    ) -> "CriticScore":
        """从测试结果计算得分"""
        benchmark_score = 0.0
        hidden_test_score = 0.0
        by_metric = {}

        # 计算基准测试得分
        if benchmark_results:
            summary = benchmark_results.get("summary", {})
            benchmark_score = summary.get("weighted_score", summary.get("avg_score", 0.0))
            pass_rate = summary.get("pass_rate", 0.0)
            by_metric["accuracy"] = benchmark_score
            by_metric["reliability"] = pass_rate

        # 计算隐藏测试得分
        if hidden_test_results:
            summary = hidden_test_results.get("summary", {})
            hidden_test_score = summary.get("avg_score", 0.0)
            pass_rate = summary.get("pass_rate", 0.0)
            by_metric["hidden_accuracy"] = hidden_test_score

        # 加权总分
        overall = (
            benchmark_score * config.benchmark_weight +
            hidden_test_score * config.hidden_test_weight
        )

        # 综合通过率
        total_passed = 0
        total_cases = 0
        if benchmark_results:
            summary = benchmark_results.get("summary", {})
            total_passed += summary.get("passed_cases", 0)
            total_cases += summary.get("total_cases", 0)
        if hidden_test_results:
            summary = hidden_test_results.get("summary", {})
            total_passed += summary.get("passed", 0)
            total_cases += summary.get("total_tests", 0)

        pass_rate = total_passed / total_cases if total_cases > 0 else 0.0

        # 判定等级
        level = 1
        verdict = "needs_improvement"
        if overall >= 0.9 and pass_rate >= 0.95:
            level = 3
            verdict = "production_ready"
        elif overall >= 0.75 and pass_rate >= 0.8:
            level = 2
            verdict = "stable"
        elif overall >= 0.6:
            level = 1
            verdict = "basic"

        return cls(
            overall=round(overall, 4),
            benchmark_score=round(benchmark_score, 4),
            hidden_test_score=round(hidden_test_score, 4),
            pass_rate=round(pass_rate, 4),
            by_metric=by_metric,
            level=level,
            verdict=verdict,
        )


class MockSkillEvaluator:
    """
    模拟 Skill 评估器 (用于演示)

    实际使用时替换为真实的 Skill 评估逻辑。
    """

    def __init__(self, success_rate: float = 0.85, avg_time_ms: float = 500):
        self.success_rate = success_rate
        self.avg_time_ms = avg_time_ms
        self.token_usage = 0

    def evaluate(self, case: BenchmarkCase) -> BenchmarkResult:
        """评估单个基准测试用例"""
        import random

        # 模拟执行时间
        execution_time = random.gauss(self.avg_time_ms, self.avg_time_ms * 0.2)
        execution_time = max(100, execution_time)  # 最小 100ms

        # 模拟成功率
        passed = random.random() < self.success_rate
        score = 1.0 if passed else random.uniform(0.0, 0.5)

        # 模拟 token 使用量
        token_usage = random.randint(500, 2000)

        return BenchmarkResult(
            case_id=case.id,
            passed=passed,
            score=score,
            actual_output={"result": "mock_output"} if passed else None,
            execution_time_ms=execution_time,
            token_usage=token_usage,
            error_message=None if passed else "Mock failure",
        )


class MockSkillUnderTest:
    """
    模拟被测 Skill (用于演示)
    """

    def __init__(self, name: str = "MockSkill", success_rate: float = 0.8):
        self.name = name
        self.success_rate = success_rate

    def execute(self, input_data: Any) -> Any:
        """执行 Skill"""
        import random
        if random.random() < self.success_rate:
            return {"status": "success", "output": f"Processed: {input_data}"}
        else:
            return {"status": "error", "output": "Failed to process"}

    def get_name(self) -> str:
        return self.name


class CriticEngine:
    """
    Critic Phase 2 评估引擎

    整合冻结基准测试和隐藏测试的统一评估引擎。
    提供完整的评估流程和报告生成功能。
    """

    def __init__(self, config: Optional[CriticConfig] = None):
        """
        初始化 Critic 引擎

        Args:
            config: 评估配置，使用默认配置如果未提供
        """
        self.config = config or CriticConfig()
        self._frozen_benchmark: Optional[FrozenBenchmark] = None
        self._hidden_suite: Optional[HiddenTestSuite] = None
        self._results: Dict[str, Any] = {}

    def load_benchmark_suite(self, suite: Optional[BenchmarkSuite] = None) -> None:
        """
        加载基准测试套件

        Args:
            suite: 测试套件，使用标准套件如果未提供
        """
        suite = suite or STANDARD_BENCHMARK_SUITE
        self._frozen_benchmark = FrozenBenchmark(suite)

        if self.config.verbose:
            print(f"Loaded benchmark suite: {suite.name} (v{suite.version})")
            print(f"  - Cases: {len(suite.cases)}")
            print(f"  - Criteria: {[c.metric.value for c in suite.criteria]}")
            print(f"  - Signature verified: {suite.verify()}")

    def load_hidden_tests(
        self,
        suite_path: Optional[Union[str, Path]] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        加载隐藏测试套件

        Args:
            suite_path: 测试套件文件路径
            password: 解锁密码
        """
        if suite_path:
            self._hidden_suite = HiddenTestSuite(
                suite_id="loaded_suite",
                name="Loaded Hidden Tests",
                version="1.0.0",
            )
            self._hidden_suite.load_from_file(suite_path)
        else:
            # 创建演示用的隐藏测试套件
            self._hidden_suite = self._create_demo_hidden_suite()

        # 解锁
        if password:
            self._hidden_suite.unlock(password)
        else:
            # 使用演示密码
            self._hidden_suite.unlock("demo_password_123")

        if self.config.verbose:
            metadata = self._hidden_suite.get_metadata()
            print(f"Loaded hidden test suite: {metadata['name']}")
            print(f"  - Tests: {metadata['test_count']}")

    def _create_demo_hidden_suite(self) -> HiddenTestSuite:
        """创建演示用的隐藏测试套件"""
        suite = HiddenTestSuite(
            suite_id="demo-hidden-v1",
            name="Demo Hidden Test Suite",
            version="1.0.0",
        )

        # 添加一些演示用例
        test_cases = [
            ("func-001", TestType.FUNCTIONAL, "general", 2),
            ("edge-001", TestType.EDGE_CASE, "edge", 3),
            ("sec-001", TestType.SECURITY, "security", 4),
        ]

        for test_id, test_type, category, difficulty in test_cases:
            test = create_hidden_test(
                test_id=test_id,
                input_data={"task": f"test_{test_id}", "data": [1, 2, 3]},
                expected_output={"status": "success"},
                validator={"type": "contains", "threshold": 0.8, "keywords": ["success"]},
                password="demo_password_123",
                test_type=test_type,
                category=category,
                difficulty=difficulty,
            )
            suite.add_test(test)

        return suite

    def evaluate(
        self,
        skill_evaluator: Optional[MockSkillEvaluator] = None,
        skill_under_test: Optional[MockSkillUnderTest] = None,
        progress_callback: Optional[Callable] = None,
    ) -> CriticScore:
        """
        执行完整评估

        Args:
            skill_evaluator: Skill 评估器 (用于基准测试)
            skill_under_test: 被测 Skill (用于隐藏测试)
            progress_callback: 进度回调

        Returns:
            评估得分
        """
        benchmark_results = None
        hidden_test_results = None

        # 1. 运行冻结基准测试
        if self.config.enable_frozen_benchmark and self._frozen_benchmark:
            if self.config.verbose:
                print("\n=== Running Frozen Benchmark ===")

            evaluator = skill_evaluator or MockSkillEvaluator()
            benchmark_results = self._frozen_benchmark.run(evaluator, progress_callback)

            if self.config.verbose:
                summary = benchmark_results.get("summary", {})
                print(f"Pass rate: {summary.get('pass_rate', 0):.2%}")
                print(f"Avg score: {summary.get('avg_score', 0):.4f}")

        # 2. 运行隐藏测试
        if self.config.enable_hidden_tests and self._hidden_suite:
            if self.config.verbose:
                print("\n=== Running Hidden Tests ===")

            skill = skill_under_test or MockSkillUnderTest()
            hidden_test_results = self._hidden_suite.run_all(skill)

            if self.config.verbose:
                summary = hidden_test_results.get("summary", {})
                print(f"Pass rate: {summary.get('pass_rate', 0):.2%}")
                print(f"Avg score: {summary.get('avg_score', 0):.4f}")

        # 3. 计算最终得分
        score = CriticScore.from_results(
            benchmark_results,
            hidden_test_results,
            self.config,
        )

        # 4. 存储结果
        self._results = {
            "score": score,
            "benchmark": benchmark_results,
            "hidden_tests": hidden_test_results,
            "config": self.config,
            "timestamp": datetime.now().isoformat(),
        }

        return score

    def generate_report(self, output_path: Optional[Union[str, Path]] = None) -> str:
        """
        生成评估报告

        Args:
            output_path: 输出文件路径

        Returns:
            报告内容 (Markdown 格式)
        """
        if not self._results:
            return "# Error\n\nNo evaluation results available. Run evaluate() first."

        score = self._results["score"]
        benchmark = self._results.get("benchmark", {})
        hidden = self._results.get("hidden_tests", {})

        report = f"""# Critic Phase 2 评估报告

**评估时间**: {self._results.get('timestamp', 'N/A')}

---

## 总体评分

| 指标 | 值 |
|------|-----|
| 总体得分 | {score.overall:.4f} |
| 等级 | **Level {score.level}** |
| 结论 | {score.verdict} |
| 通过率 | {score.pass_rate:.2%} |

---

## 详细得分

### 基准测试 ({self.config.benchmark_weight * 100:.0f}%)

| 指标 | 得分 |
|------|-----|
| 基准测试得分 | {score.benchmark_score:.4f} |

{benchmark.get('summary', {}).get('total_cases', 0)} 个测试用例，{benchmark.get('summary', {}).get('passed_cases', 0)} 个通过

### 隐藏测试 ({self.config.hidden_test_weight * 100:.0f}%)

| 指标 | 得分 |
|------|-----|
| 隐藏测试得分 | {score.hidden_test_score:.4f} |

{hidden.get('summary', {}).get('total_tests', 0)} 个测试用例，{hidden.get('summary', {}).get('passed', 0)} 个通过

---

## 按指标分析

"""
        for metric, value in score.by_metric.items():
            report += f"- **{metric}**: {value:.4f}\n"

        report += """
---

## 分类统计

### 基准测试分类

"""
        for category, stats in benchmark.get("by_category", {}).items():
            report += f"- **{category}**: {stats.get('pass_rate', 0):.1%} 通过率, {stats.get('avg_score', 0):.4f} 平均分\n"

        report += """
### 隐藏测试分类

"""
        for test_type, stats in hidden.get("by_type", {}).items():
            report += f"- **{test_type}**: {stats.get('pass_rate', 0):.1%} 通过率, {stats.get('avg_score', 0):.4f} 平均分\n"

        report += """
---

## 改进建议

"""
        if score.level == 3:
            report += """
✅ **恭喜！** Skill 已达到生产就绪标准 (Level 3)。

建议：
- 继续保持当前质量
- 定期进行回归测试
- 关注用户反馈
"""
        elif score.level == 2:
            report += f"""
⚠️ **良好。** Skill 已达到稳定标准 (Level 2)，但还有提升空间。

建议：
- 目标：将总体得分从 {score.overall:.4f} 提升到 0.90
- 重点改进：隐藏测试得分 ({score.hidden_test_score:.4f})
- 增加边界条件和安全性测试覆盖
"""
        else:
            report += f"""
❌ **需要改进。** Skill 仅达到基础标准 (Level 1)。

建议：
- 优先修复失败的核心功能测试
- 增加错误处理和边界条件处理
- 提高测试通过率到 80% 以上
- 参考 Level 2 标准进行改进
"""

        # 保存报告
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report saved to: {output_path}")

        return report

    def export_results(self, path: Union[str, Path]) -> Path:
        """导出完整结果为 JSON"""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self._results, f, indent=2, default=str)

        return output_path


def run_minimal_demo():
    """
    运行最小演示

    展示 Critic Phase 2 的核心功能。
    """
    print("=" * 60)
    print("Critic Phase 2 - Minimal Demo")
    print("=" * 60)

    # 创建配置
    config = CriticConfig(
        enable_frozen_benchmark=True,
        enable_hidden_tests=True,
        benchmark_weight=0.5,
        hidden_test_weight=0.5,
        verbose=True,
    )

    # 创建引擎
    engine = CriticEngine(config)

    # 加载测试套件
    engine.load_benchmark_suite()
    engine.load_hidden_tests()

    # 创建模拟 Skill
    skill_evaluator = MockSkillEvaluator(success_rate=0.85, avg_time_ms=500)
    skill_under_test = MockSkillUnderTest("DemoSkill", success_rate=0.80)

    # 运行评估
    print("\n" + "=" * 60)
    print("Running Evaluation...")
    print("=" * 60)

    score = engine.evaluate(skill_evaluator, skill_under_test)

    # 输出结果
    print("\n" + "=" * 60)
    print("Evaluation Results")
    print("=" * 60)
    print(f"Overall Score: {score.overall:.4f}")
    print(f"Benchmark Score: {score.benchmark_score:.4f}")
    print(f"Hidden Test Score: {score.hidden_test_score:.4f}")
    print(f"Pass Rate: {score.pass_rate:.2%}")
    print(f"Level: {score.level}")
    print(f"Verdict: {score.verdict}")

    # 生成报告
    print("\n" + "=" * 60)
    print("Generating Report...")
    print("=" * 60)

    report = engine.generate_report("/tmp/critic_phase2_report.md")
    print("\nReport Preview:")
    print(report[:1500] + "...")

    # 导出 JSON 结果
    engine.export_results("/tmp/critic_phase2_results.json")
    print("\nResults exported to /tmp/critic_phase2_results.json")

    return score


if __name__ == "__main__":
    run_minimal_demo()
