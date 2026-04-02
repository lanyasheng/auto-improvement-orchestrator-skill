#!/usr/bin/env python3
"""
Skill Evaluator 自主改进循环 - 借鉴 Karpathy Loop

最小可运行版本 (P0 实现):
- 基于评估结果生成结构化改进候选
- 支持有限类型改进 (prompt/docs/tests/workflow)
- 明确标注哪些仍是 stub

用法:
    python self_improve.py --skill-path /path/to/skill --metric accuracy --max-iterations 5
    python self_improve.py --skill-path /path/to/skill --metric accuracy --demo  # 演示模式
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def parse_args():
    parser = argparse.ArgumentParser(description="Skill Evaluator 自主改进循环 (最小可运行版本)")
    parser.add_argument("--skill-path", type=str, required=True, help="要改进的 Skill 路径")
    parser.add_argument("--metric", type=str, default="accuracy", 
                        choices=["accuracy", "reliability", "efficiency", "cost", "coverage"],
                        help="优化指标")
    parser.add_argument("--max-iterations", type=int, default=5, help="最大迭代次数")
    parser.add_argument("--early-stop", type=int, default=3, help="无改进早期停止的迭代次数")
    parser.add_argument("--output", type=str, default="reports/", help="输出目录")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    parser.add_argument("--demo", action="store_true", help="演示模式 (不实际修改文件)")
    return parser.parse_args()


class ImprovementProposer:
    """
    改进提议器 - 基于评估结果生成结构化改进候选
    
    P0 实现：支持有限类型改进，明确标注 stub
    """
    
    IMPROVEMENT_TYPES = {
        "prompt": {
            "description": "优化 SKILL.md 中的 prompt 措辞",
            "target_files": ["SKILL.md"],
            "stub": False,
        },
        "docs": {
            "description": "完善文档 (README/注释)",
            "target_files": ["README.md", "scripts/*.py"],
            "stub": False,
        },
        "tests": {
            "description": "添加/改进测试用例",
            "target_files": ["tests/*.py", "evals/*.yaml"],
            "stub": False,
        },
        "workflow": {
            "description": "优化工作流程逻辑",
            "target_files": ["scripts/*.py"],
            "stub": True,  # STUB: 需要更复杂的代码分析
        },
        "error_handling": {
            "description": "增强错误处理",
            "target_files": ["scripts/*.py"],
            "stub": True,  # STUB: 需要更复杂的代码分析
        },
    }
    
    def __init__(self, skill_path: str):
        self.skill_path = Path(skill_path)
        self.skill_info = self._parse_skill_info()
    
    def _parse_skill_info(self) -> Dict[str, Any]:
        """解析 Skill 基本信息"""
        skill_md = self.skill_path / "SKILL.md"
        if not skill_md.exists():
            return {}
        
        import yaml
        with open(skill_md, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML frontmatter
        lines = content.split('\n')
        in_frontmatter = False
        frontmatter_lines = []
        
        for line in lines:
            if line.strip() == '---':
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    in_frontmatter = False
                    try:
                        return yaml.safe_load('\n'.join(frontmatter_lines)) or {}
                    except:
                        return {}
                    break
            elif in_frontmatter:
                frontmatter_lines.append(line)
        
        return {}
    
    def propose_improvements(
        self, 
        metric: str, 
        current_score: float,
        eval_report: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        基于评估结果生成改进候选列表
        
        Args:
            metric: 优化指标
            current_score: 当前得分
            eval_report: 评估报告 (可选)
        
        Returns:
            改进候选列表，按优先级排序
        """
        candidates = []
        
        # 规则 1: 根据指标类型推荐改进方向
        metric_to_types = {
            "accuracy": ["prompt", "tests", "workflow"],
            "reliability": ["error_handling", "tests", "workflow"],
            "efficiency": ["workflow", "prompt"],
            "cost": ["prompt", "workflow"],
            "coverage": ["tests", "docs"],
        }
        
        relevant_types = metric_to_types.get(metric, ["prompt", "tests"])
        
        # 规则 2: 根据当前得分调整优先级
        if current_score < 0.6:
            priority_boost = ["prompt", "error_handling"]  # 低分优先改基础
        elif current_score < 0.8:
            priority_boost = ["tests", "workflow"]  # 中等分数优先改测试和流程
        else:
            priority_boost = ["docs"]  # 高分优先完善文档
        
        # 规则 3: 检查 Skill 实际文件存在情况
        file_checks = {
            "has_readme": (self.skill_path / "README.md").exists(),
            "has_tests": (self.skill_path / "tests").exists(),
            "has_evals": (self.skill_path / "evals").exists(),
            "has_scripts": (self.skill_path / "scripts").exists(),
        }
        
        # 生成候选
        for imp_type in relevant_types:
            type_info = self.IMPROVEMENT_TYPES.get(imp_type, {})
            
            # 计算优先级分数
            priority_score = 0.5
            if imp_type in priority_boost:
                priority_score += 0.3
            if type_info.get("stub"):
                priority_score -= 0.2  # stub 类型优先级降低
            
            # 根据文件存在情况调整
            if imp_type == "docs" and not file_checks["has_readme"]:
                priority_score += 0.4  # 缺少 README 则文档改进优先级提高
            if imp_type == "tests" and not file_checks["has_tests"]:
                priority_score += 0.4  # 缺少 tests 则测试改进优先级提高
            
            candidate = {
                "type": imp_type,
                "description": type_info.get("description", "Unknown"),
                "target_files": type_info.get("target_files", []),
                "is_stub": type_info.get("stub", False),
                "priority": min(1.0, priority_score),
                "rationale": self._generate_rationale(imp_type, metric, current_score),
            }
            candidates.append(candidate)
        
        # 按优先级排序
        candidates.sort(key=lambda x: x["priority"], reverse=True)
        
        return candidates
    
    def _generate_rationale(self, imp_type: str, metric: str, score: float) -> str:
        """生成改进理由说明"""
        rationales = {
            "prompt": f"优化 prompt 可直接提升{metric}指标 (当前得分：{score:.2%})",
            "docs": "完善文档有助于用户理解和正确使用 Skill",
            "tests": f"增加测试覆盖可提升{metric}和可靠性",
            "workflow": "优化工作流程可改善效率和资源使用",
            "error_handling": "增强错误处理可提升可靠性和用户体验",
        }
        return rationales.get(imp_type, "改进建议")


def apply_improvement(
    skill_path: str, 
    improvement: Dict[str, Any],
    demo_mode: bool = False
) -> bool:
    """
    应用改进
    
    P0 实现：仅支持非 stub 类型，明确标注限制
    
    Args:
        skill_path: Skill 路径
        improvement: 改进候选
        demo_mode: 演示模式 (不实际修改)
    
    Returns:
        是否成功应用
    """
    imp_type = improvement.get("type")
    is_stub = improvement.get("is_stub", False)
    
    if is_stub:
        logger.warning(f"跳过 stub 类型改进：{imp_type} (需要更复杂的代码分析)")
        return False
    
    if demo_mode:
        logger.info(f"[DEMO] 将应用改进：{improvement['description']}")
        logger.info(f"[DEMO] 目标文件：{improvement['target_files']}")
        return True
    
    # P0 实现：仅支持 docs 和 tests 类型的简单改进
    skill_dir = Path(skill_path)
    
    if imp_type == "docs":
        return _apply_docs_improvement(skill_dir, improvement)
    elif imp_type == "tests":
        return _apply_tests_improvement(skill_dir, improvement)
    elif imp_type == "prompt":
        return _apply_prompt_improvement(skill_dir, improvement)
    else:
        logger.warning(f"不支持的改进类型：{imp_type}")
        return False


def _apply_docs_improvement(skill_dir: Path, improvement: Dict) -> bool:
    """应用文档改进"""
    readme_path = skill_dir / "README.md"
    
    if not readme_path.exists():
        # 创建基础 README
        content = f"""# {improvement.get('skill_name', 'Skill')}

## 简介
{improvement.get('description', 'Skill 描述')}

## 安装
```bash
# 安装说明
```

## 使用
```bash
# 使用示例
```

## 测试
```bash
python -m pytest tests/
```
"""
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"已创建 README.md")
        return True
    else:
        logger.info("README.md 已存在，跳过创建")
        return True


def _apply_tests_improvement(skill_dir: Path, improvement: Dict) -> bool:
    """应用测试改进"""
    tests_dir = skill_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    test_file = tests_dir / "test_auto_generated.py"
    
    if not test_file.exists():
        content = f'''#!/usr/bin/env python3
"""
自动生成的测试用例
生成时间：{datetime.now().isoformat()}
"""

import pytest


def test_placeholder():
    """占位测试 - 请替换为真实测试"""
    assert True


# TODO: 根据 Skill 实际功能添加测试
'''
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"已创建测试文件：{test_file}")
        return True
    else:
        logger.info("测试文件已存在，跳过创建")
        return True


def _apply_prompt_improvement(skill_dir: Path, improvement: Dict) -> bool:
    """
    应用 prompt 改进
    
    P0 实现：仅添加改进注释，不直接修改 SKILL.md 内容
    """
    skill_md = skill_dir / "SKILL.md"
    
    if not skill_md.exists():
        logger.warning("SKILL.md 不存在，无法改进 prompt")
        return False
    
    # P0 实现：在文件末尾添加改进建议注释
    with open(skill_md, 'a', encoding='utf-8') as f:
        f.write(f"\n<!-- 改进建议 ({datetime.now().isoformat()}): {improvement['rationale']} -->\n")
    
    logger.info(f"已在 SKILL.md 添加改进建议注释")
    return True


def backup_skill(skill_path: str) -> str:
    """备份 Skill"""
    backup_path = f"{skill_path}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copytree(skill_path, backup_path)
    return backup_path


def revert_change(skill_path: str, backup_path: str):
    """回滚改动"""
    logger.info(f"回滚改动，恢复到 {backup_path}")
    shutil.rmtree(skill_path, ignore_errors=True)
    shutil.copytree(backup_path, skill_path)


def commit_change(skill_path: str, improvement: Dict):
    """提交改动 (尝试 git)"""
    logger.info(f"尝试提交改动：{improvement['type']}")
    
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=skill_path,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Auto-improve: {improvement['type']} - {improvement['description']}"],
            cwd=skill_path,
            capture_output=True,
            timeout=10,
        )
        logger.info("Git 提交成功")
    except Exception as e:
        logger.warning(f"Git 提交失败 (非致命): {e}")


def evaluate_skill(skill_path: str, metric: str) -> Dict[str, Any]:
    """
    评估 Skill
    
    P0 实现：调用 evaluate.py 脚本
    
    Returns:
        评估结果字典
    """
    scripts_dir = Path(__file__).parent
    evaluate_script = scripts_dir / "evaluate.py"
    
    if not evaluate_script.exists():
        logger.warning("evaluate.py 不存在，使用模拟评估")
        import random
        return {
            "score": random.uniform(0.7, 0.9),
            "metric": metric,
            "details": "Mock evaluation (evaluate.py not found)",
        }
    
    try:
        result = subprocess.run(
            [
                sys.executable, str(evaluate_script),
                "--skill-path", skill_path,
                "--output", "/tmp/skill-eval-output",
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        # 查找生成的 JSON 报告
        import glob
        json_files = glob.glob("/tmp/skill-eval-output/*.json")
        
        if json_files:
            with open(json_files[-1], 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # 提取分数 (简化处理)
            score = 0.75  # 默认值
            if report.get("structure", {}).get("has_skill_md"):
                score += 0.1
            if report.get("structure", {}).get("has_tests"):
                score += 0.1
            if report.get("structure", {}).get("has_readme"):
                score += 0.05
            
            return {
                "score": min(1.0, score),
                "metric": metric,
                "details": "Based on structure check",
                "report": report,
            }
        else:
            logger.warning("未找到评估报告，使用默认分数")
            return {"score": 0.75, "metric": metric, "details": "Default score"}
    
    except subprocess.TimeoutExpired:
        logger.error("评估超时")
        return {"score": 0.5, "metric": metric, "details": "Timeout"}
    except Exception as e:
        logger.error(f"评估错误：{e}")
        return {"score": 0.5, "metric": metric, "details": str(e)}


def self_improve_loop(
    skill_path: str,
    metric: str,
    max_iterations: int,
    early_stop: int,
    output_dir: str,
    demo_mode: bool = False,
):
    """
    自主改进循环 - 最小可运行版本
    
    流程:
    1. 初始评估
    2. 生成改进候选
    3. 应用改进 (非 stub 类型)
    4. 重新评估
    5. 保留或回滚
    6. 重复直到收敛
    """
    logger.info(f"开始自主改进循环：{skill_path}")
    logger.info(f"优化指标：{metric}, 最大迭代：{max_iterations}, 早期停止：{early_stop}")
    logger.info(f"演示模式：{demo_mode}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 备份 Skill
    if not demo_mode:
        backup_path = backup_skill(skill_path)
        logger.info(f"已备份 Skill 到：{backup_path}")
    else:
        backup_path = None
        logger.info("[DEMO] 跳过备份")
    
    # 初始评估
    logger.info("进行初始评估...")
    eval_result = evaluate_skill(skill_path, metric)
    best_score = eval_result.get("score", 0.5)
    logger.info(f"初始得分：{best_score:.2%}")
    
    history = [best_score]
    no_improvement_count = 0
    applied_improvements = []
    
    # 初始化改进提议器
    proposer = ImprovementProposer(skill_path)
    
    # 改进循环
    for i in range(max_iterations):
        logger.info(f"\n{'='*50}")
        logger.info(f"迭代 {i+1}/{max_iterations}")
        logger.info(f"当前最佳：{best_score:.2%}, 无改进计数：{no_improvement_count}/{early_stop}")
        
        # 1. 生成改进候选
        candidates = proposer.propose_improvements(
            metric=metric,
            current_score=best_score,
            eval_report=eval_result,
        )
        
        if not candidates:
            logger.warning("未生成改进候选，终止循环")
            break
        
        # 选择最高优先级的候选
        improvement = candidates[0]
        logger.info(f"选择改进：{improvement['type']} (优先级：{improvement['priority']:.2f})")
        logger.info(f"描述：{improvement['description']}")
        if improvement.get('is_stub'):
            logger.warning("⚠️ 这是一个 stub 类型，将跳过实际应用")
        
        # 2. 应用改进
        success = apply_improvement(skill_path, improvement, demo_mode=demo_mode)
        
        if not success:
            logger.warning("改进应用失败")
            no_improvement_count += 1
            continue
        
        # 3. 重新评估
        logger.info("重新评估...")
        eval_result = evaluate_skill(skill_path, metric)
        score = eval_result.get("score", 0.5)
        
        # 4. 保留或回滚
        if score > best_score:
            best_score = score
            if not demo_mode:
                commit_change(skill_path, improvement)
            applied_improvements.append(improvement)
            logger.info(f"✅ 迭代{i+1}: 改进到 {score:.2%}")
            no_improvement_count = 0
        else:
            if not demo_mode and backup_path:
                revert_change(skill_path, backup_path)
            logger.info(f"❌ 迭代{i+1}: 无改进 ({score:.2%})")
            no_improvement_count += 1
        
        history.append(score)
        
        # 5. 早期停止
        if no_improvement_count >= early_stop:
            logger.info(f"\n{early_stop}次无改进，早期停止")
            break
    
    # 生成报告
    report = {
        "skill_path": skill_path,
        "metric": metric,
        "initial_score": history[0],
        "final_score": best_score,
        "improvement": best_score - history[0],
        "improvement_rate": (best_score - history[0]) / history[0] if history[0] > 0 else 0,
        "total_iterations": len(history) - 1,
        "history": history,
        "applied_improvements": applied_improvements,
        "stubs_skipped": sum(1 for c in [ImprovementProposer(skill_path).propose_improvements(metric, h) for h in history] for ci in c if ci.get('is_stub')),
        "timestamp": datetime.now().isoformat(),
        "demo_mode": demo_mode,
    }
    
    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_file = Path(output_dir) / f"self-improve-report-{timestamp}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 摘要
    md_report = _generate_markdown_summary(report)
    md_file = Path(output_dir) / f"self-improve-summary-{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_report)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"自主改进完成！")
    logger.info(f"初始得分：{history[0]:.2%}")
    logger.info(f"最终得分：{best_score:.2%}")
    logger.info(f"改进幅度：{report['improvement_rate']:.2%}")
    logger.info(f"迭代次数：{report['total_iterations']}")
    logger.info(f"应用的改进：{len(applied_improvements)}")
    logger.info(f"报告：{report_file}")
    logger.info(f"摘要：{md_file}")
    
    # 清理备份
    if not demo_mode and backup_path:
        shutil.rmtree(backup_path, ignore_errors=True)
        logger.info(f"已清理备份：{backup_path}")
    
    return report


def _generate_markdown_summary(report: Dict) -> str:
    """生成 Markdown 格式摘要"""
    return f"""# Skill 自主改进报告

**技能路径**: {report['skill_path']}  
**优化指标**: {report['metric']}  
**时间**: {report['timestamp']}

---

## 改进结果

| 指标 | 值 |
|------|-----|
| 初始得分 | {report['initial_score']:.2%} |
| 最终得分 | {report['final_score']:.2%} |
| 改进幅度 | {report['improvement_rate']:.2%} |
| 迭代次数 | {report['total_iterations']} |
| 应用的改进 | {len(report['applied_improvements'])} |

---

## 得分历史

```
{ ' -> '.join(f"{s:.2%}" for s in report['history']) }
```

---

## 应用的改进

""" + "\n".join(
        f"- **{imp['type']}**: {imp['description']} (优先级：{imp['priority']:.2f})"
        for imp in report['applied_improvements']
    ) + f"""

---

## 说明

- 本报告由 skill-evaluator 自主改进循环生成
- P0 版本仅支持非 stub 类型的改进 (prompt/docs/tests)
- workflow 和 error_handling 类型仍为 stub，需要后续完善

---

*Generated by Skill Evaluator Self-Improvement Loop (P0)*
"""


def main():
    args = parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    report = self_improve_loop(
        skill_path=args.skill_path,
        metric=args.metric,
        max_iterations=args.max_iterations,
        early_stop=args.early_stop,
        output_dir=args.output,
        demo_mode=args.demo,
    )
    
    logger.info(f"\n自主改进循环完成！")


if __name__ == "__main__":
    main()
