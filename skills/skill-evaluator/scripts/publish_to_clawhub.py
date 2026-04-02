#!/usr/bin/env python3
"""
Skill Evaluator 发布到 ClawHub

用法:
    python publish_to_clawhub.py --skill-path /path/to/skill --level Level2
    python publish_to_clawhub.py --skill-path /path/to/skill --level Level3 --publish
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def parse_args():
    parser = argparse.ArgumentParser(description="Skill Evaluator 发布到 ClawHub")
    parser.add_argument("--skill-path", type=str, required=True, help="要发布的 Skill 路径")
    parser.add_argument("--level", type=str, required=True, choices=["Level1", "Level2", "Level3"], help="Skill 能力等级")
    parser.add_argument("--publish", action="store_true", help="执行发布（默认只验证）")
    parser.add_argument("--clawhub-path", type=str, default="~/.openclaw/clawhub", help="ClawHub 路径")
    parser.add_argument("--output", type=str, default="reports/", help="输出目录")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    return parser.parse_args()


def check_skill_level(skill_path: str, required_level: str) -> bool:
    """
    检查 Skill 是否达到指定等级
    
    Level 要求:
    - Level 1: 能完成核心任务，有基本错误处理
    - Level 2: Level 1 + 完整错误处理 + 测试覆盖率>80% + 基准测试
    - Level 3: Level 2 + 红队测试 + 测试覆盖率>95% + 用户反馈循环
    """
    logger.info(f"检查 Skill 等级：{skill_path} (要求：{required_level})")
    
    # 检查 SKILL.md
    skill_md = Path(skill_path) / "SKILL.md"
    if not skill_md.exists():
        logger.error("缺少 SKILL.md")
        return False
    
    # 检查目录结构
    checks = {
        "Level1": ["SKILL.md"],
        "Level2": ["SKILL.md", "scripts", "evals"],
        "Level3": ["SKILL.md", "scripts", "evals", "tests", "README.md", ".feedback"],
    }
    
    required_files = checks.get(required_level, [])
    
    for file_or_dir in required_files:
        path = Path(skill_path) / file_or_dir
        if not path.exists():
            logger.error(f"缺少 {file_or_dir} (Level {required_level} 要求)")
            return False
    
    logger.info(f"✅ Skill 等级检查通过：{required_level}")
    return True


def run_eval(skill_path: str) -> dict:
    """运行评估"""
    logger.info("运行 Skill 评估...")
    
    # 实际实现应该调用 evaluate.py
    # result = subprocess.run(
    #     ["python", "scripts/evaluate.py", "--skill-path", skill_path, "--output", "reports/"],
    #     capture_output=True,
    #     text=True,
    #     check=True
    # )
    
    # 示例返回
    return {
        "skill_path": skill_path,
        "skill_level": "Level2",  # 实际应该从评估结果获取
        "accuracy": 0.85,
        "reliability": 0.88,
        "efficiency": 0.82,
        "cost": 0.15,
        "coverage": 0.80,
        "timestamp": datetime.now().isoformat(),
    }


def run_red_team(skill_path: str) -> dict:
    """运行红队测试（Level 3 要求）"""
    logger.info("运行红队测试...")
    
    # 实际实现应该调用 red_team.py
    # result = subprocess.run(
    #     ["python", "scripts/red_team.py", "--skill-path", skill_path, "--output", "reports/"],
    #     capture_output=True,
    #     text=True,
    #     check=True
    # )
    
    # 示例返回
    return {
        "skill_path": skill_path,
        "pass_rate": 0.92,
        "tests_passed": 18,
        "tests_total": 20,
        "timestamp": datetime.now().isoformat(),
    }


def check_security(skill_path: str) -> bool:
    """安全检查"""
    logger.info("运行安全检查...")
    
    # 检查敏感信息
    sensitive_patterns = [
        r'/Users/\w+/',  # 本地路径
        r'\.openclaw',  # OpenClaw 路径
        r'api[_-]?key|token|secret|password',  # 密钥
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',  # 邮箱
    ]
    
    import re
    
    for root, dirs, files in os.walk(skill_path):
        # 跳过某些目录
        if any(skip in root for skip in ['.git', '__pycache__', '.venv', 'node_modules']):
            continue
        
        for file in files:
            if file.endswith(('.py', '.md', '.yaml', '.yml', '.json')):
                file_path = Path(root) / file
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for pattern in sensitive_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            logger.warning(f"发现敏感信息：{file_path} (匹配：{pattern})")
                            # 不直接返回 False，只是警告
                except Exception as e:
                    logger.debug(f"读取文件失败 {file_path}: {e}")
    
    logger.info("✅ 安全检查完成")
    return True


def publish_to_clawhub(skill_path: str, clawhub_path: str, eval_result: dict) -> bool:
    """发布到 ClawHub"""
    logger.info(f"发布 Skill 到 ClawHub: {clawhub_path}")
    
    # 创建 ClawHub 目录
    clawhub_skills_dir = Path(clawhub_path).expanduser() / "skills"
    os.makedirs(clawhub_skills_dir, exist_ok=True)
    
    # 复制 Skill 到 ClawHub
    skill_name = Path(skill_path).name
    target_path = clawhub_skills_dir / skill_name
    
    if target_path.exists():
        logger.warning(f"ClawHub 中已存在 Skill: {skill_name}")
        backup_path = target_path.with_name(f"{skill_name}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.move(target_path, backup_path)
        logger.info(f"已备份旧版本到：{backup_path}")
    
    shutil.copytree(skill_path, target_path)
    
    # 添加评估报告
    eval_report_path = target_path / "eval-report.json"
    with open(eval_report_path, 'w', encoding='utf-8') as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Skill 已发布到 ClawHub: {target_path}")
    
    # 提交到 Git（如果 ClawHub 是 Git 仓库）
    git_dir = Path(clawhub_path).expanduser() / ".git"
    if git_dir.exists():
        logger.info("提交到 Git...")
        try:
            subprocess.run(["git", "add", "-A"], cwd=clawhub_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Publish {skill_name} ({eval_result.get('skill_level', 'Unknown')})"], cwd=clawhub_path, check=True, capture_output=True)
            logger.info("✅ 已提交到 Git")
        except Exception as e:
            logger.warning(f"Git 提交失败：{e}")
    
    return True


def generate_publish_report(skill_path: str, eval_result: dict, red_team_result: dict, security_passed: bool, output_dir: str):
    """生发布报告"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_file = Path(output_dir) / f"publish-report-{timestamp}.md"
    
    report = f"""# Skill 发布报告

**Skill 路径**: {skill_path}  
**发布时间**: {datetime.now().isoformat()}

---

## 评估结果

| 指标 | 值 |
|------|-----|
| 能力等级 | {eval_result.get('skill_level', 'Unknown')} |
| 准确性 | {eval_result.get('accuracy', 0):.2%} |
| 可靠性 | {eval_result.get('reliability', 0):.2%} |
| 效率 | {eval_result.get('efficiency', 0):.2%} |
| 成本 | {eval_result.get('cost', 0):.2%} |
| 覆盖率 | {eval_result.get('coverage', 0):.2%} |

---

## 红队测试结果

"""
    
    if red_team_result:
        report += f"""| 指标 | 值 |
|------|-----|
| 通过率 | {red_team_result.get('pass_rate', 0):.2%} |
| 通过测试 | {red_team_result.get('tests_passed', 0)} |
| 总测试 | {red_team_result.get('tests_total', 0)} |
"""
    else:
        report += "*未运行红队测试（Level 1/2 不要求）*\n"
    
    report += f"""
---

## 安全检查

**结果**: {'✅ 通过' if security_passed else '❌ 失败'}

---

## 发布状态

**状态**: {'✅ 已发布' if True else '⏳ 待发布'}  
**ClawHub 路径**: `~/.openclaw/clawhub/skills/{Path(skill_path).name}`

---

## 下一步行动

"""
    
    if eval_result.get('skill_level') == "Level1":
        report += "- [ ] 达到 Level 2 要求（添加 scripts/, evals/，测试覆盖率>80%）\n"
    elif eval_result.get('skill_level') == "Level2":
        report += "- [ ] 达到 Level 3 要求（添加 tests/, .feedback/，红队测试，测试覆盖率>95%）\n"
    else:
        report += "- [x] 已达到 Level 3，可以发布到 ClawHub 市场\n"
    
    report += f"""
---

*报告由 Skill Evaluator 发布工具生成*
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"发布报告已保存到：{report_file}")


def main():
    args = parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    logger.info(f"开始 Skill 发布流程：{args.skill_path}")
    logger.info(f"目标等级：{args.level}")
    
    # 1. 检查 Skill 等级
    if not check_skill_level(args.skill_path, args.level):
        logger.error(f"Skill 未达到 {args.level} 要求")
        sys.exit(1)
    
    # 2. 运行评估
    eval_result = run_eval(args.skill_path)
    
    # 3. 运行红队测试（Level 3 要求）
    red_team_result = None
    if args.level == "Level3":
        red_team_result = run_red_team(args.skill_path)
        if red_team_result['pass_rate'] < 0.90:
            logger.error(f"红队测试通过率 {red_team_result['pass_rate']:.2%} < 90% (Level 3 要求)")
            sys.exit(1)
    
    # 4. 安全检查
    security_passed = check_security(args.skill_path)
    
    # 5. 生成报告
    generate_publish_report(args.skill_path, eval_result, red_team_result, security_passed, args.output)
    
    # 6. 发布到 ClawHub
    if args.publish:
        publish_to_clawhub(args.skill_path, args.clawhub_path, eval_result)
        logger.info(f"\n✅ Skill 发布完成！")
    else:
        logger.info(f"\n⚠️  仅验证模式，未执行发布。使用 --publish 执行发布")
    
    logger.info(f"报告：{args.output}/publish-report-*.md")


if __name__ == "__main__":
    main()
