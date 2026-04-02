#!/usr/bin/env python3
"""
Skill Evaluator 多 Agent 并行评估

用法:
    python parallel_eval.py --skill-paths /path/to/skill1 /path/to/skill2 --max-workers 10
    python parallel_eval.py --skill-paths /path/to/skill1 /path/to/skill2 --output reports/ --max-workers 10
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def parse_args():
    parser = argparse.ArgumentParser(description="Skill Evaluator 多 Agent 并行评估")
    parser.add_argument("--skill-paths", type=str, nargs='+', required=True, help="要评估的 Skill 路径列表")
    parser.add_argument("--output", type=str, default="reports/", help="输出目录")
    parser.add_argument("--max-workers", type=int, default=10, help="最大并发数")
    parser.add_argument("--metric", type=str, default="accuracy", help="优化指标")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    return parser.parse_args()


def evaluate_single_skill(skill_path: str, metric: str) -> dict:
    """
    评估单个 Skill
    
    实际实现应该调用 evaluate.py
    这里只是示例
    """
    logger.info(f"评估 Skill: {skill_path}")
    
    # 实际实现:
    # result = subprocess.run(
    #     ["python", "scripts/evaluate.py", "--skill-path", skill_path, "--output", "reports/"],
    #     capture_output=True,
    #     text=True,
    #     check=True
    # )
    
    # 示例返回
    import random
    return {
        "skill_path": skill_path,
        "metric": metric,
        "score": random.uniform(0.7, 0.95),
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
    }


def parallel_eval_skills(skill_paths: list, max_workers: int, metric: str, output_dir: str) -> list:
    """
    多 Agent 并行评估
    
    Args:
        skill_paths: Skill 路径列表
        max_workers: 最大并发数
        metric: 评估指标
        output_dir: 输出目录
    
    Returns:
        评估结果列表
    """
    logger.info(f"开始并行评估 {len(skill_paths)} 个 Skill")
    logger.info(f"最大并发数：{max_workers}")
    logger.info(f"评估指标：{metric}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_skill = {
            executor.submit(evaluate_single_skill, skill_path, metric): skill_path
            for skill_path in skill_paths
        }
        
        # 收集结果
        for future in as_completed(future_to_skill):
            skill_path = future_to_skill[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(f"✅ {skill_path}: {result['score']:.2%}")
            except Exception as e:
                logger.error(f"❌ {skill_path} 评估失败：{e}")
                results.append({
                    "skill_path": skill_path,
                    "metric": metric,
                    "score": 0,
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": str(e),
                })
    
    # 生成报告
    generate_parallel_eval_report(results, output_dir)
    
    return results


def generate_parallel_eval_report(results: list, output_dir: str):
    """生成并行评估报告"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_file = Path(output_dir) / f"parallel-eval-report-{timestamp}.md"
    
    # 计算统计
    total = len(results)
    completed = sum(1 for r in r if r["status"] == "completed")
    failed = sum(1 for r in r if r["status"] == "failed")
    avg_score = sum(r["score"] for r in r if r["status"] == "completed") / completed if completed > 0 else 0
    
    # 排序
    sorted_results = sorted(
        [r for r in r if r["status"] == "completed"],
        key=lambda x: x["score"],
        reverse=True
    )
    
    report = f"""# 并行评估报告

**评估时间**: {datetime.now().isoformat()}  
**评估 Skill 数**: {total}  
**成功**: {completed}  
**失败**: {failed}  
**平均得分**: {avg_score:.2%}

---

## 总体统计

| 指标 | 值 |
|------|-----|
| 总 Skill 数 | {total} |
| 成功 | {completed} |
| 失败 | {failed} |
| 成功率 | {completed/total:.2%} if total > 0 else 0 |
| 平均得分 | {avg_score:.2%} |

---

## 排行榜 (Top {len(sorted_results)})

| 排名 | Skill 路径 | 得分 | 评估时间 |
|------|-----------|------|---------|
"""
    
    for i, result in enumerate(sorted_results, 1):
        report += f"| {i} | {result['skill_path']} | {result['score']:.2%} | {result['timestamp']} |\n"
    
    report += f"""
---

## 失败列表

"""
    
    failed_results = [r for r in r if r["status"] == "failed"]
    if failed_results:
        for result in failed_results:
            report += f"- **{result['skill_path']}**: {result.get('error', 'Unknown error')}\n"
    else:
        report += "无失败\n"
    
    report += f"""
---

## 详细结果

"""
    
    for result in r:
        report += f"""### {result['skill_path']}

- **状态**: {result['status']}
- **得分**: {result['score']:.2%}
- **时间**: {result['timestamp']}
"""
        if result.get('error'):
            report += f"- **错误**: {result['error']}\n"
        report += "\n"
    
    report += f"""
---

*报告由 Skill Evaluator 并行评估工具生成*
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"评估报告已保存到：{report_file}")
    
    # 保存 JSON 结果
    json_file = Path(output_dir) / f"parallel-eval-results-{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    
    logger.info(f"评估结果已保存到：{json_file}")


def main():
    args = parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    results = parallel_eval_skills(
        skill_paths=args.skill_paths,
        max_workers=args.max_workers,
        metric=args.metric,
        output_dir=args.output,
    )
    
    logger.info(f"\n并行评估完成！")
    logger.info(f"评估 Skill 数：{len(results)}")
    logger.info(f"成功：{sum(1 for r in r if r['status'] == 'completed')}")
    logger.info(f"失败：{sum(1 for r in r if r['status'] == 'failed')}")


if __name__ == "__main__":
    main()
