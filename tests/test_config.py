"""灵犀·校园 — 配置测试"""
import os
import sys
import pytest

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestConfig:
    """配置模块测试"""

    def test_project_root_exists(self):
        """测试项目根目录存在"""
        from lingxi_qwenpaw.config import PROJECT_ROOT
        assert PROJECT_ROOT.exists()

    def test_db_path_configured(self):
        """测试数据库路径已配置"""
        from lingxi_qwenpaw.config import DB_PATH
        assert DB_PATH is not None
        assert str(DB_PATH).endswith("lingxi.db")

    def test_llm_config_exists(self):
        """测试 LLM 配置存在"""
        from lingxi_qwenpaw.config import LLM_API_URL, LLM_MODEL
        assert LLM_API_URL is not None
        assert LLM_MODEL is not None


class TestAuth:
    """认证模块测试"""

    def test_password_validation_short(self):
        """测试短密码验证"""
        from lingxi_qwenpaw.auth import register
        result = register("testuser", "123")
        assert result["ok"] is False
        assert "密码" in result["error"]

    def test_password_validation_no_letter(self):
        """测试无字母密码验证"""
        from lingxi_qwenpaw.auth import register
        result = register("testuser", "12345678")
        assert result["ok"] is False
        assert "字母" in result["error"]

    def test_password_validation_no_digit(self):
        """测试无数字密码验证"""
        from lingxi_qwenpaw.auth import register
        result = register("testuser", "abcdefgh")
        assert result["ok"] is False
        assert "数字" in result["error"]

    def test_username_validation_short(self):
        """测试短用户名验证"""
        from lingxi_qwenpaw.auth import register
        result = register("a", "testpass123")
        assert result["ok"] is False
        assert "用户名" in result["error"]


class TestTools:
    """工具模块测试"""

    def test_tool_functions_exist(self):
        """测试工具函数存在"""
        from lingxi_qwenpaw.tools import TOOL_FUNCTIONS
        assert isinstance(TOOL_FUNCTIONS, dict)
        assert len(TOOL_FUNCTIONS) > 0

    def test_get_emotion_status_tool(self):
        """测试情绪状态工具"""
        from lingxi_qwenpaw.tools import get_emotion_status
        import asyncio
        result = asyncio.run(get_emotion_status("test_user"))
        assert "success" in result
