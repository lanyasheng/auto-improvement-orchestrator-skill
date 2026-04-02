#!/usr/bin/env python3
"""
Skill Evaluator P1 示例命令

演示 P1 新增功能:
1. 使用 Critic Engine V2 进行评估
2. 整合 assertions 断言系统
3. 支持真实 Skill 调用

用法:
    # 评估 skill-evaluator 自身
    python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/skill-evaluator
    
    # 评估其他 Skill
    python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/weather
    
    # 详细输出
    python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/skill-evaluator --verbose
"""

import argparse
import sys
from pathlib import Path

# 添加 scripts 和 interfaces 到 path
scripts_dir = Path(__file__).parent
interfaces_dir = scripts_dir.parent / "interfaces"
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(interfaces_dir))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Skill Evaluator P1 示例命令",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 评估 skill-evaluator 自身
  python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/skill-evaluator
  
  # 评估其他 Skill
  python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/weather
  
  # 详细输出
  python scripts/run_p1_eval.py --skill-path ~/.openclaw/skills/skill-evaluator --verbose
        """
    )
    parser.add_argument("--skill-path", type=str, required=True, help="要评估的 Skill 路径")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--output", type=str, default="/tmp/skill-eval-p1", help="输出目录")
    return parser.parse_args()


def run_p1_eval(skill_path: str, verbose: bool = False, output_dir: str = "/tmp/skill-eval-p1"):
    """运行 P1 评估"""
    from evaluate import run_critic_engine_eval
    
    logger.info(f"开始 P1 评估：{skill_path}")
    logger.info(f"使用 Critic Engine V2 (assertions + real skill evaluator)")
    
    # 运行评估
    result = run_critic_engine_eval(skill_path, verbose=verbose, use_v2=True)
    
    # 输出结果
    logger.info("\n" + "=" * 60)
    logger.info("评估结果")
    logger.info("=" * 60)
    
    if "error" in result:
        logger.error(f"评估失败：{result['error']}")
        return result
    
    logger.info(f"引擎：{result['engine']}")
    logger.info(f"等级：{result['level']}")
    logger.info(f"结论：{result['verdict']}")
    logger.info(f"总体得分：{result['score']:.2%}")
    logger.info(f"基准测试：{result['benchmark_score']:.2%}")
    logger.info(f"隐藏测试：{result['hidden_test_score']:.2%}")
    logger.info(f"断言检查：{result['assertion_score']:.2%} (P1 新增)")
    logger.info(f"通过率：{result['pass_rate']:.2%}")
    logger.info(f"\n报告：{result['report_path']}")
    
    # 输出按指标分析
    if result.get('by_metric'):
        logger.info("\n按指标分析:")
        for metric, value in result['by_metric'].items():
            logger.info(f"  {metric}: {value:.4f}")
    
    return result


def main():
    args = parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    result = run_p1_eval(args.skill_path, verbose=args.verbose, output_dir=args.output)
    
    if "error" not in result:
        logger.info("\n✅ P1 评估完成！")
    else:
        logger.warning("\n⚠️ P1 评估完成但有错误")
    
    return result


if __name__ == "__main__":
    main()
