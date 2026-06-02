import os
import pytest
import tempfile
from modules.user_config_loader import UserConfigLoader


class TestCookiesPassword:
    """测试 cookies 密码的获取和设置"""

    def test_get_cookies_password_when_not_set(self, tmp_path):
        """测试获取未设置的密码"""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"users": {}, "cookies": {"password": ""}}')

        loader = UserConfigLoader(str(config_file))
        assert loader.get_cookies_password() == ""

    def test_get_cookies_password_when_set(self, tmp_path):
        """测试获取已设置的密码"""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"users": {}, "cookies": {"password": "my_secret"}}')

        loader = UserConfigLoader(str(config_file))
        assert loader.get_cookies_password() == "my_secret"

    def test_set_cookies_password(self, tmp_path):
        """测试设置密码并保存"""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"users": {}, "cookies": {"password": ""}}')

        loader = UserConfigLoader(str(config_file))
        result = loader.set_cookies_password("new_password")

        assert result is True
        # 重新加载验证保存
        loader2 = UserConfigLoader(str(config_file))
        assert loader2.get_cookies_password() == "new_password"

    def test_set_cookies_password_creates_cookies_section(self, tmp_path):
        """测试设置密码时创建 cookies section"""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('{"users": {"Daisy": {}}}')

        loader = UserConfigLoader(str(config_file))
        loader.set_cookies_password("secret123")

        loader2 = UserConfigLoader(str(config_file))
        assert loader2.get_cookies_password() == "secret123"
        # 确认 users 数据未丢失
        assert loader2.get_users_list() == ["Daisy"]