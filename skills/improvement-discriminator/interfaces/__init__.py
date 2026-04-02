"""
Improvement Discriminator Interfaces

Frozen Benchmark + Hidden Tests + External Regression + Human Review + Assertions
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
from .critic_engine import CriticEngineV2, CriticConfig
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
    # Critic Engine V2
    "CriticEngineV2",
    "CriticConfig",
    # External Regression
    "ExternalRegressionHook",
    "RegressionSuiteResult",
    "RegressionSourceType",
    "create_regression_result",
    # Human Review
    "HumanReviewManager",
    "HumanReviewReceipt",
    "ReviewDecision",
    "ReviewSeverity",
    "create_review_finding",
]
