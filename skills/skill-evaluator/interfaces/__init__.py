"""
Skill Evaluator Critic Phase 2 Interfaces

Frozen Benchmark + Hidden Tests + External Regression + Human Review 接口定义
"""

from .frozen_benchmark import FrozenBenchmark, BenchmarkResult, BenchmarkSuite
from .hidden_tests import (
    HiddenTest,
    HiddenTestSuite,
    TestResult,
    TestType,
    TestVisibility,
    create_hidden_test,
    DictHiddenTestDataSource,
    FileHiddenTestDataSource,
)
from .critic_engine import CriticEngine, CriticConfig
from .critic_engine_v2 import CriticEngineV2, CriticConfig as CriticConfigV2
from .external_regression import (
    ExternalRegressionHook,
    RegressionSuiteResult,
    RegressionSourceType,
    create_regression_result,
)
from .human_review import (
    HumanReviewManager,
    HumanReviewReceipt,
    ReviewDecision,
    ReviewSeverity,
    create_review_finding,
)

__all__ = [
    # Frozen Benchmark
    "FrozenBenchmark",
    "BenchmarkResult",
    "BenchmarkSuite",
    # Hidden Tests
    "HiddenTest",
    "HiddenTestSuite",
    "TestResult",
    "TestType",
    "TestVisibility",
    "create_hidden_test",
    "DictHiddenTestDataSource",
    "FileHiddenTestDataSource",
    # Critic Engine
    "CriticEngine",
    "CriticConfig",
    "CriticEngineV2",
    "CriticConfigV2",
    # External Regression (P2-a)
    "ExternalRegressionHook",
    "RegressionSuiteResult",
    "RegressionSourceType",
    "create_regression_result",
    # Human Review (P2-a)
    "HumanReviewManager",
    "HumanReviewReceipt",
    "ReviewDecision",
    "ReviewSeverity",
    "create_review_finding",
]
