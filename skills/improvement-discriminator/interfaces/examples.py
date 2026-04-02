#!/usr/bin/env python3
"""
Critic Phase 2 - 使用示例

展示如何使用 Frozen Benchmark 和 Hidden Tests 接口。

DEPRECATED: This examples file references legacy CriticEngine (now CriticEngineV2).
It is retained for reference only.
"""

try:
    from interfaces import (
        CriticConfig,
        CriticEngineV2 as CriticEngine,
        BenchmarkCase,
        BenchmarkSuite,
        ScoringCriteria,
        MetricType,
        FrozenBenchmark,
        HiddenTestSuite,
        TestType,
        create_hidden_test,
    )
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    try:
        from interfaces import (
            CriticConfig,
            CriticEngineV2 as CriticEngine,
            BenchmarkCase,
            BenchmarkSuite,
            ScoringCriteria,
            MetricType,
            FrozenBenchmark,
            HiddenTestSuite,
            TestType,
            create_hidden_test,
        )
    except ImportError:
        pass  # Module may not be available in all environments


def example_1_basic_usage():
    """示例 1: 基础用法"""
    print("\n" + "=" * 60)
    print("示例 1: 基础用法 - 运行标准基准测试")
    print("=" * 60)

    # 创建配置
    config = CriticConfig(
        enable_frozen_benchmark=True,
        enable_hidden_tests=False,  # 先不运行隐藏测试
        verbose=True,
    )

    # 创建引擎
    engine = CriticEngine(config)

    # 加载标准基准测试套件
    engine.load_benchmark_suite()

    # 运行评估
    score = engine.evaluate()

    # 输出结果
    print(f"\n评估完成!")
    print(f"  总体得分: {score.overall:.4f}")
    print(f"  等级: Level {score.level}")
    print(f"  结论: {score.verdict}")

    return score


def example_2_custom_benchmark():
    """示例 2: 自定义基准测试套件"""
    print("\n" + "=" * 60)
    print("示例 2: 创建和运行自定义基准测试")
    print("=" * 60)

    # 创建自定义测试用例
    custom_cases = [
        BenchmarkCase(
            id="custom-001",
            name="Custom Functionality Test",
            input_data={"task": "custom_operation", "value": 42},
            expected_output={"result": 42},
            category="functionality",
            difficulty=2,
            tags=("custom", "demo"),
        ),
        BenchmarkCase(
            id="custom-002",
            name="Custom Edge Case",
            input_data={"task": "edge_operation", "value": None},
            expected_output={"error": "invalid_input"},
            category="reliability",
            difficulty=4,
            tags=("edge-case", "error-handling"),
        ),
    ]

    # 创建自定义评分标准
    custom_criteria = [
        ScoringCriteria(MetricType.ACCURACY, weight=0.5, threshold=0.7, target=0.95),
        ScoringCriteria(MetricType.RELIABILITY, weight=0.3, threshold=0.6, target=0.9),
        ScoringCriteria(MetricType.EFFICIENCY, weight=0.2, threshold=0.5, target=0.8),
    ]

    # 创建自定义套件
    custom_suite = BenchmarkSuite(
        id="custom-benchmark-v1",
        name="Custom Benchmark Suite",
        version="1.0.0",
        description="Custom benchmark for demonstration",
        cases=tuple(custom_cases),
        criteria=tuple(custom_criteria),
    )

    print(f"\n创建自定义套件:")
    print(f"  名称: {custom_suite.name}")
    print(f"  用例数: {len(custom_suite.cases)}")
    print(f"  签名验证: {custom_suite.verify()}")

    # 运行评估
    config = CriticConfig(
        enable_frozen_benchmark=True,
        enable_hidden_tests=False,
        verbose=False,
    )

    engine = CriticEngine(config)
    engine.load_benchmark_suite(custom_suite)

    score = engine.evaluate()

    print(f"\n评估结果:")
    print(f"  总体得分: {score.overall:.4f}")
    print(f"  通过率: {score.pass_rate:.2%}")

    return score


def example_3_hidden_tests():
    """示例 3: 使用隐藏测试"""
    print("\n" + "=" * 60)
    print("示例 3: 创建和运行隐藏测试")
    print("=" * 60)

    # 创建隐藏测试套件
    suite = HiddenTestSuite(
        suite_id="hidden-demo-v1",
        name="Demo Hidden Tests",
        version="1.0.0",
    )

    # 添加隐藏测试用例
    password = "my_secret_key_123"

    hidden_tests = [
        {
            "id": "hidden-func-001",
            "type": TestType.FUNCTIONAL,
            "category": "core",
            "difficulty": 2,
            "input": {"operation": "add", "a": 10, "b": 20},
            "expected": {"result": 30},
            "validator": {"type": "exact"},
        },
        {
            "id": "hidden-edge-001",
            "type": TestType.EDGE_CASE,
            "category": "edge",
            "difficulty": 4,
            "input": {"operation": "divide", "a": 10, "b": 0},
            "expected": {"error": "division_by_zero"},
            "validator": {"type": "contains", "keywords": ["error", "zero"], "threshold": 1.0},
        },
        {
            "id": "hidden-sec-001",
            "type": TestType.SECURITY,
            "category": "security",
            "difficulty": 5,
            "input": "'; DROP TABLE users; --",
            "expected": {"blocked": True},
            "validator": {"type": "contains", "keywords": ["blocked", "invalid", "rejected"], "threshold": 0.5},
        },
    ]

    for test_data in hidden_tests:
        test = create_hidden_test(
            test_id=test_data["id"],
            input_data=test_data["input"],
            expected_output=test_data["expected"],
            validator=test_data["validator"],
            password=password,
            test_type=test_data["type"],
            category=test_data["category"],
            difficulty=test_data["difficulty"],
        )
        suite.add_test(test)

    print(f"\n创建隐藏测试套件:")
    print(f"  名称: {suite.name}")
    print(f"  测试数: {len(suite._tests)}")

    # 保存到文件
    suite.save_to_file("/tmp/hidden_tests_demo.json")
    print(f"  已保存到: /tmp/hidden_tests_demo.json")

    # 重新加载并运行
    new_suite = HiddenTestSuite(
        suite_id="loaded",
        name="Loaded",
        version="1.0.0",
    )
    new_suite.load_from_file("/tmp/hidden_tests_demo.json")

    # 解锁 (使用正确的密码)
    unlocked = new_suite.unlock(password)
    print(f"  解锁状态: {unlocked}")

    if unlocked:
        # 运行测试
        from interfaces.critic_engine import MockSkillUnderTest
        skill = MockSkillUnderTest("TestSkill", success_rate=0.75)

        results = new_suite.run_all(skill)

        print(f"\n测试结果:")
        print(f"  总测试数: {results['summary']['total_tests']}")
        print(f"  通过数: {results['summary']['passed']}")
        print(f"  失败数: {results['summary']['failed']}")
        print(f"  通过率: {results['summary']['pass_rate']:.2%}")

    return results


def example_4_full_evaluation():
    """示例 4: 完整评估流程"""
    print("\n" + "=" * 60)
    print("示例 4: 完整评估流程 (基准测试 + 隐藏测试)")
    print("=" * 60)

    # 创建配置
    config = CriticConfig(
        enable_frozen_benchmark=True,
        enable_hidden_tests=True,
        benchmark_weight=0.6,  # 基准测试权重 60%
        hidden_test_weight=0.4,  # 隐藏测试权重 40%
        verbose=True,
    )

    # 创建引擎
    engine = CriticEngine(config)

    # 加载套件
    engine.load_benchmark_suite()
    engine.load_hidden_tests()

    # 定义进度回调
    def progress_callback(current: int, total: int, result):
        if current == 1 or current == total or current % 5 == 0:
            print(f"  进度: {current}/{total} ({current/total*100:.0f}%)")

    # 运行评估
    score = engine.evaluate(progress_callback=progress_callback)

    # 生成报告
    print("\n" + "=" * 60)
    print("生成评估报告...")
    print("=" * 60)

    report = engine.generate_report("/tmp/full_evaluation_report.md")

    # 打印关键信息
    print(f"\n评估完成!")
    print(f"  总体得分: {score.overall:.4f}")
    print(f"  基准测试得分: {score.benchmark_score:.4f}")
    print(f"  隐藏测试得分: {score.hidden_test_score:.4f}")
    print(f"  通过率: {score.pass_rate:.2%}")
    print(f"  等级: Level {score.level}")
    print(f"  结论: {score.verdict}")

    print(f"\n报告已保存到: /tmp/full_evaluation_report.md")

    return score


def example_5_level_comparison():
    """示例 5: 不同等级 Skill 对比"""
    print("\n" + "=" * 60)
    print("示例 5: 不同质量 Skill 的评估对比")
    print("=" * 60)

    # 定义不同质量的 Skill
    skill_configs = [
        ("LowQuality", 0.5, 0.4),   # Level 1 水平
        ("MediumQuality", 0.75, 0.7),  # Level 2 水平
        ("HighQuality", 0.95, 0.9),   # Level 3 水平
    ]

    results = []

    for name, benchmark_sr, hidden_sr in skill_configs:
        print(f"\n评估 {name}:")
        print(f"  基准测试成功率: {benchmark_sr:.0%}")
        print(f"  隐藏测试成功率: {hidden_sr:.0%}")

        config = CriticConfig(
            enable_frozen_benchmark=True,
            enable_hidden_tests=True,
            benchmark_weight=0.5,
            hidden_test_weight=0.5,
            verbose=False,
        )

        engine = CriticEngine(config)
        engine.load_benchmark_suite()
        engine.load_hidden_tests()

        from interfaces.critic_engine import MockSkillEvaluator, MockSkillUnderTest

        evaluator = MockSkillEvaluator(success_rate=benchmark_sr)
        skill = MockSkillUnderTest(name, success_rate=hidden_sr)

        score = engine.evaluate(evaluator, skill)

        print(f"  -> 等级: Level {score.level}, 总体得分: {score.overall:.4f}")

        results.append({
            "name": name,
            "level": score.level,
            "overall": score.overall,
        })

    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    for r in results:
        print(f"{r['name']}: Level {r['level']} ({r['overall']:.4f})")

    return results


def main():
    """运行所有示例"""
    print("=" * 60)
    print("Critic Phase 2 - 使用示例集")
    print("=" * 60)
    print("\n本示例展示 Frozen Benchmark 和 Hidden Tests 接口的使用方法。")
    print("每个示例可以独立运行，也可以一起运行。\n")

    # 运行示例
    try:
        example_1_basic_usage()
    except Exception as e:
        print(f"示例 1 出错: {e}")

    try:
        example_2_custom_benchmark()
    except Exception as e:
        print(f"示例 2 出错: {e}")

    try:
        example_3_hidden_tests()
    except Exception as e:
        print(f"示例 3 出错: {e}")

    try:
        example_4_full_evaluation()
    except Exception as e:
        print(f"示例 4 出错: {e}")

    try:
        example_5_level_comparison()
    except Exception as e:
        print(f"示例 5 出错: {e}")

    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
