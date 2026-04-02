#!/usr/bin/env python3
"""
Skill Evaluator 单元测试 - 核心功能测试

运行方式:
    pytest tests/test_evaluator.py -v --cov=scripts --cov-report=term-missing
"""

import pytest
import os
import tempfile
from pathlib import Path

# 导入被测试的函数
from scripts.evaluate import (
    check_skill_structure,
    parse_skill_md,
    calculate_skill_level,
    generate_markdown_report
)


class TestCheckSkillStructure:
    """测试 Skill 结构检查功能"""
    
    def test_level3_skill_structure(self):
        """测试 Level 3 Skill 结构检查"""
        # 创建临时 Level 3 Skill 目录
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n")
            (skill_dir / "scripts").mkdir()
            (skill_dir / "evals").mkdir()
            (skill_dir / "tests").mkdir()
            (skill_dir / "README.md").write_text("# Test")
            
            result = check_skill_structure(str(skill_dir))
            
            assert result["has_skill_md"] == True
            assert result["has_scripts"] == True
            assert result["has_evals"] == True
            assert result["has_tests"] == True
            assert result["has_readme"] == True
    
    def test_level2_skill_structure(self):
        """测试 Level 2 Skill 结构检查"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n")
            (skill_dir / "scripts").mkdir()
            (skill_dir / "evals").mkdir()
            
            result = check_skill_structure(str(skill_dir))
            
            assert result["has_skill_md"] == True
            assert result["has_scripts"] == True
            assert result["has_evals"] == True
            assert result["has_tests"] == False
            assert result["has_readme"] == False
    
    def test_level1_skill_structure(self):
        """测试 Level 1 Skill 结构检查"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n")
            
            result = check_skill_structure(str(skill_dir))
            
            assert result["has_skill_md"] == True
            assert result["has_scripts"] == False
            assert result["has_evals"] == False
            assert result["has_tests"] == False
            assert result["has_readme"] == False
    
    def test_no_skill_md(self):
        """测试缺少 SKILL.md 的情况"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "README.md").write_text("# Test")
            
            result = check_skill_structure(str(skill_dir))
            
            assert result["has_skill_md"] == False
    
    def test_nonexistent_directory(self):
        """测试不存在的目录"""
        result = check_skill_structure("/nonexistent/path")
        
        assert result["has_skill_md"] == False
        assert result["has_scripts"] == False
        assert result["has_evals"] == False
        assert result["has_tests"] == False
        assert result["has_readme"] == False


class TestParseSkillMd:
    """测试 SKILL.md 解析功能"""
    
    def test_parse_complete_skill_md(self):
        """测试解析完整的 SKILL.md"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
version: 1.0.0
description: Test skill description
author: Test Author
tags: [test, evaluation]
---

# Test Skill

## Core Responsibilities
- Responsibility 1
- Responsibility 2
""")
            
            result = parse_skill_md(str(skill_dir))
            
            assert result["name"] == "test-skill"
            assert result["version"] == "1.0.0"
            assert result["description"] == "Test skill description"
            assert result["author"] == "Test Author"
            assert result["tags"] == ["test", "evaluation"]
    
    def test_parse_minimal_skill_md(self):
        """测试解析最小 SKILL.md"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("""---
name: minimal-skill
---
""")
            
            result = parse_skill_md(str(skill_dir))
            
            assert result["name"] == "minimal-skill"
    
    def test_parse_no_frontmatter(self):
        """测试解析没有 frontmatter 的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("# Test Skill\n\nNo frontmatter here.")
            
            result = parse_skill_md(str(skill_dir))
            
            assert result == {}
    
    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        result = parse_skill_md("/nonexistent/path")
        
        assert result == {}
    
    def test_parse_invalid_yaml(self):
        """测试解析 YAML 格式错误的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
  invalid: yaml: format:
---
""")
            
            result = parse_skill_md(str(skill_dir))
            
            # 应该返回空字典而不是抛出异常
            assert isinstance(result, dict)


class TestCalculateSkillLevel:
    """测试 Skill 能力等级计算功能"""
    
    def test_level3_all_requirements(self):
        """测试 Level 3 - 满足所有要求"""
        structure = {
            "has_skill_md": True,
            "has_scripts": True,
            "has_evals": True,
            "has_tests": True,
            "has_readme": True
        }
        
        result = calculate_skill_level(structure, {})
        
        assert result == "Level 3"
    
    def test_level2_missing_tests(self):
        """测试 Level 2 - 缺少 tests 和 readme"""
        structure = {
            "has_skill_md": True,
            "has_scripts": True,
            "has_evals": True,
            "has_tests": False,
            "has_readme": False
        }
        
        result = calculate_skill_level(structure, {})
        
        assert result == "Level 2"
    
    def test_level1_only_skill_md(self):
        """测试 Level 1 - 只有 SKILL.md"""
        structure = {
            "has_skill_md": True,
            "has_scripts": False,
            "has_evals": False,
            "has_tests": False,
            "has_readme": False
        }
        
        result = calculate_skill_level(structure, {})
        
        assert result == "Level 1"
    
    def test_unrated_no_skill_md(self):
        """测试未评级 - 没有 SKILL.md"""
        structure = {
            "has_skill_md": False,
            "has_scripts": False,
            "has_evals": False,
            "has_tests": False,
            "has_readme": False
        }
        
        result = calculate_skill_level(structure, {})
        
        assert result == "未评级"
    
    def test_level3_with_eval_results(self):
        """测试 Level 3 - 带评估结果"""
        structure = {
            "has_skill_md": True,
            "has_scripts": True,
            "has_evals": True,
            "has_tests": True,
            "has_readme": True
        }
        eval_result = {
            "accuracy": 0.95,
            "reliability": 0.98,
            "test_coverage": 0.97
        }
        
        result = calculate_skill_level(structure, eval_result)
        
        assert result == "Level 3"


class TestGenerateMarkdownReport:
    """测试 Markdown 报告生成功能"""
    
    def test_generate_basic_report(self):
        """测试生成基本报告"""
        skill_info = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test description",
            "author": "Test Author",
            "tags": ["test", "evaluation"]
        }
        structure = {
            "has_skill_md": True,
            "has_scripts": True,
            "has_evals": True,
            "has_tests": False,
            "has_readme": False
        }
        eval_result = {}
        timestamp = "20260325-120000"
        
        report = generate_markdown_report(skill_info, structure, eval_result, timestamp)
        
        assert "# Skill 评估报告" in report
        assert "test-skill" in report
        assert "1.0.0" in report
        assert "能力等级" in report
        assert "目录结构检查" in report
    
    def test_generate_report_with_suggestions(self):
        """测试生成带改进建议的报告"""
        skill_info = {"name": "incomplete-skill"}
        structure = {
            "has_skill_md": True,
            "has_scripts": False,
            "has_evals": False,
            "has_tests": False,
            "has_readme": False
        }
        
        report = generate_markdown_report(skill_info, structure, {}, "20260325-120000")
        
        assert "改进建议" in report
        assert "高优先级" in report
    
    def test_generate_report_complete_skill(self):
        """测试生成完整 Skill 的报告"""
        skill_info = {"name": "complete-skill"}
        structure = {
            "has_skill_md": True,
            "has_scripts": True,
            "has_evals": True,
            "has_tests": True,
            "has_readme": True
        }
        
        report = generate_markdown_report(skill_info, structure, {}, "20260325-120000")
        
        assert "改进建议" in report
        assert "无需改进" in report or "✅" in report
    
    def test_generate_report_missing_info(self):
        """测试生成缺失信息 Skill 的报告"""
        skill_info = {}
        structure = {}
        
        report = generate_markdown_report(skill_info, structure, {}, "20260325-120000")
        
        assert "# Skill 评估报告" in report
        assert "N/A" in report or "未知" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
