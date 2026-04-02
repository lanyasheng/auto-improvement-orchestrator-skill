#!/usr/bin/env python3
"""
Skill Evaluator 端到端演示脚本

P0-3 实现：最小端到端示例命令路径

演示完整流程:
1. evaluate → 评估 Skill
2. self_improve → 自主改进
3. review → 查看改进结果

用法:
    # 演示模式 (不实际修改文件)
    python demo_end_to_end.py --demo
    
    # 真实运行 (会修改目标 Skill)
    python demo_end_to_end.py --skill-path /path/to/skill
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Skill Evaluator 端到端演示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 演示模式 (推荐首次使用)
  python demo_end_to_end.py --demo
  
  # 评估真实 Skill
  python demo_end_to_end.py --skill-path ~/.openclaw/skills/weather --metric accuracy
  
  # 详细输出
  python demo_end_to_end.py --skill-path ~/.openclaw/skills/weather --verbose
        """
    )
    parser.add_argument("--demo", action="store_true", help="演示模式 (使用 mock 数据，不修改文件)")
    parser.add_argument("--skill-path", type=str, help="要评估和改进的 Skill 路径")
    parser.add_argument("--metric", type=str, default="accuracy", 
                        choices=["accuracy", "reliability", "efficiency", "cost", "coverage"],
                        help="优化指标")
    parser.add_argument("--max-iterations", type=int, default=3, help="self_improve 最大迭代次数")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    return parser.parse_args()


def run_step(name: str, command: list, demo_mode: bool = False) -> dict:
    """运行一个步骤"""
    logger.info(f"\n{'='*60}")
    logger.info(f"步骤：{name}")
    logger.info(f"命令：{' '.join(command)}")
    
    if demo_mode:
        logger.info("[DEMO] 跳过实际执行")
        return {"status": "skipped", "demo_mode": True}
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        output = {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        
        if result.returncode == 0:
            logger.info(f"✅ {name} 完成")
        else:
            logger.warning(f"⚠️ {name} 失败 (returncode={result.returncode})")
        
        return output
    
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {name} 超时")
        return {"status": "timeout", "error": "Command timed out"}
    except Exception as e:
        logger.error(f"❌ {name} 错误：{e}")
        return {"status": "error", "error": str(e)}


def demo_evaluate(skill_path: str, verbose: bool = False) -> dict:
    """步骤 1: 评估 Skill"""
    scripts_dir = Path(__file__).parent
    evaluate_script = scripts_dir / "evaluate.py"
    
    command = [
        sys.executable, str(evaluate_script),
        "--skill-path", skill_path,
        "--output", "/tmp/skill-eval-demo",
        "--format", "json",
    ]
    
    if verbose:
        command.append("--verbose")
    
    return run_step("1. 评估 Skill", command)


def demo_self_improve(skill_path: str, metric: str, max_iterations: int, verbose: bool = False) -> dict:
    """步骤 2: 自主改进"""
    scripts_dir = Path(__file__).parent
    self_improve_script = scripts_dir / "self_improve.py"
    
    command = [
        sys.executable, str(self_improve_script),
        "--skill-path", skill_path,
        "--metric", metric,
        "--max-iterations", str(max_iterations),
        "--output", "/tmp/skill-eval-demo",
    ]
    
    if verbose:
        command.append("--verbose")
    
    return run_step("2. 自主改进", command)


def demo_review(output_dir: str = "/tmp/skill-eval-demo") -> dict:
    """步骤 3: 查看结果"""
    logger.info(f"\n{'='*60}")
    logger.info(f"步骤：3. 查看结果")
    
    output_path = Path(output_dir)
    
    if not output_path.exists():
        logger.warning(f"输出目录不存在：{output_dir}")
        return {"status": "no_output", "message": "Output directory not found"}
    
    # 查找生成的报告
    reports = list(output_path.glob("*.json")) + list(output_path.glob("*.md"))
    
    if not reports:
        logger.warning("未找到生成的报告")
        return {"status": "no_reports", "message": "No reports found"}
    
    logger.info(f"找到 {len(reports)} 个报告文件:")
    for report in sorted(reports, key=lambda x: x.stat().st_mtime, reverse=True):
        logger.info(f"  - {report.name} ({report.stat().st_size} bytes)")
    
    # 读取最新的 JSON 报告
    json_reports = [r for r in reports if r.suffix == '.json']
    if json_reports:
        latest_report = sorted(json_reports, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        with open(latest_report, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        logger.info(f"\n最新报告摘要 ({latest_report.name}):")
        logger.info(f"  {json.dumps(content, indent=2, ensure_ascii=False)[:500]}...")
        
        return {
            "status": "success",
            "report_path": str(latest_report),
            "report_preview": content,
        }
    
    return {"status": "success", "message": f"Found {len(reports)} reports"}


def run_demo_mode():
    """运行演示模式 (使用 mock 数据)"""
    logger.info("="*60)
    logger.info("Skill Evaluator 端到端演示 (DEMO 模式)")
    logger.info("="*60)
    
    # 模拟流程
    logger.info("\n[DEMO] 步骤 1: 评估 Skill")
    logger.info("  → 使用 mock 评估器")
    logger.info("  → 生成模拟报告")
    
    logger.info("\n[DEMO] 步骤 2: 自主改进")
    logger.info("  → 生成改进候选：prompt, docs, tests")
    logger.info("  → 跳过 stub 类型：workflow, error_handling")
    logger.info("  → 应用改进 (不实际修改文件)")
    
    logger.info("\n[DEMO] 步骤 3: 查看结果")
    logger.info("  → 显示改进报告摘要")
    
    # 生成演示报告
    demo_report = {
        "demo_mode": True,
        "timestamp": datetime.now().isoformat(),
        "workflow": {
            "step1_evaluate": "mock_evaluation",
            "step2_self_improve": "mock_improvement",
            "step3_review": "mock_review",
        },
        "sample_improvements": [
            {"type": "prompt", "description": "优化 SKILL.md 中的 prompt 措辞", "applied": True},
            {"type": "docs", "description": "创建 README.md", "applied": True},
            {"type": "tests", "description": "添加测试用例", "applied": True},
            {"type": "workflow", "description": "优化工作流程", "applied": False, "stub": True},
        ],
        "next_steps": [
            "使用真实 Skill 运行：python demo_end_to_end.py --skill-path /path/to/skill",
            "查看详细文档：cat interfaces/README.md",
            "运行单元测试：python -m pytest tests/",
        ],
    }
    
    os.makedirs("/tmp/skill-eval-demo", exist_ok=True)
    demo_report_path = Path("/tmp/skill-eval-demo") / f"demo-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(demo_report_path, 'w', encoding='utf-8') as f:
        json.dump(demo_report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n演示报告已保存：{demo_report_path}")
    logger.info("\n" + "="*60)
    logger.info("演示完成！")
    logger.info("="*60)
    
    return demo_report


def main():
    args = parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    # 演示模式
    if args.demo or not args.skill_path:
        return run_demo_mode()
    
    # 真实运行
    skill_path = os.path.expanduser(args.skill_path)
    
    if not os.path.exists(skill_path):
        logger.error(f"Skill 路径不存在：{skill_path}")
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("Skill Evaluator 端到端流程")
    logger.info("="*60)
    logger.info(f"目标 Skill: {skill_path}")
    logger.info(f"优化指标：{args.metric}")
    logger.info(f"最大迭代：{args.max_iterations}")
    
    # 步骤 1: 评估
    eval_result = demo_evaluate(skill_path, verbose=args.verbose)
    
    if eval_result.get("status") == "failed":
        logger.warning("评估失败，继续尝试改进...")
    
    # 步骤 2: 自主改进
    improve_result = demo_self_improve(
        skill_path, 
        args.metric, 
        args.max_iterations,
        verbose=args.verbose,
    )
    
    # 步骤 3: 查看结果
    review_result = demo_review()
    
    # 生成汇总报告
    summary = {
        "skill_path": skill_path,
        "metric": args.metric,
        "timestamp": datetime.now().isoformat(),
        "steps": {
            "evaluate": eval_result,
            "self_improve": improve_result,
            "review": review_result,
        },
        "overall_status": "completed" if all(r.get("status") in ["success", "skipped"] for r in [eval_result, improve_result, review_result]) else "partial",
    }
    
    os.makedirs("/tmp/skill-eval-demo", exist_ok=True)
    summary_path = Path("/tmp/skill-eval-demo") / f"e2e-summary-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'='*60}")
    logger.info("端到端流程完成！")
    logger.info(f"汇总报告：{summary_path}")
    logger.info("="*60)
    
    return summary


if __name__ == "__main__":
    main()
