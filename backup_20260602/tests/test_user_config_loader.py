"""
tests/test_user_config_loader.py
覆盖 user_config_loader 模块的所有功能
"""

import pytest
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.user_config_loader import (
    UserConfigLoader,
    get_user_config_loader,
    reload_config,
    get_users_list,
    get_default_user,
    get_jira_config,
    get_circleci_config,
    get_argocd_config,
    get_jenkins_config,
    build_jira_auth_headers,
    build_jenkins_auth,
    build_circleci_headers
)
from requests.auth import HTTPBasicAuth


class TestUserConfigLoader:
    """测试 UserConfigLoader 类"""

    @pytest.fixture
    def temp_config_file(self):
        """创建临时配置文件"""
        config_data = {
            "users": {
                "user1": {
                    "email": "demo@example.com",
                    "display_name": "User One",
                    "jira": {"base_url": "https://jira.example.com", "api_token": "token1"},
                    "circleci": {"api_token": "circle1", "vcs_type": "github"},
                    "argocd": {"url": "https://argocd.example.com", "token": "argo1"},
                    "jenkins": {"url": "https://jenkins.example.com", "username": "jenkins1", "token": "jenkins1_token"}
                },
                "user2": {
                    "email": "demo@example.com",
                    "display_name": "User Two",
                    "jira": {"base_url": "https://jira.example.com", "api_token": "token2"}
                }
            },
            "default_user": "user1"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    def test_init_loads_config(self, temp_config_file):
        """初始化应加载配置文件"""
        loader = UserConfigLoader(temp_config_file)
        assert loader._config is not None
        assert "users" in loader._config

    def test_init_missing_file(self):
        """配置文件不存在应使用默认空配置"""
        loader = UserConfigLoader("nonexistent_file.json")
        assert loader._config == {"users": {}, "default_user": None}

    def test_init_invalid_json(self):
        """无效 JSON 应使用默认空配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name

        loader = UserConfigLoader(temp_path)
        assert loader._config == {"users": {}, "default_user": None}
        os.unlink(temp_path)

    def test_get_users_list(self, temp_config_file):
        """获取用户列表"""
        loader = UserConfigLoader(temp_config_file)
        users = loader.get_users_list()
        assert set(users) == {"user1", "user2"}

    def test_get_users_list_empty(self):
        """空配置返回空用户列表"""
        loader = UserConfigLoader("nonexistent.json")
        assert loader.get_users_list() == []

    def test_get_default_user(self, temp_config_file):
        """获取默认用户"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_default_user() == "user1"

    def test_get_default_user_none(self):
        """无默认用户返回 None"""
        loader = UserConfigLoader("nonexistent.json")
        assert loader.get_default_user() is None

    def test_get_user_config_existing(self, temp_config_file):
        """获取存在用户的配置"""
        loader = UserConfigLoader(temp_config_file)
        config = loader.get_user_config("user1")
        assert config is not None
        assert config["email"] == "demo@example.com"

    def test_get_user_config_nonexistent(self, temp_config_file):
        """获取不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_user_config("nonexistent") is None

    def test_get_jira_config_existing(self, temp_config_file):
        """获取 Jira 配置"""
        loader = UserConfigLoader(temp_config_file)
        jira_config = loader.get_jira_config("user1")
        assert jira_config is not None
        assert jira_config["api_token"] == "token1"

    def test_get_jira_config_nonexistent_user(self, temp_config_file):
        """不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_jira_config("nonexistent") is None

    def test_get_jira_config_user_without_jira(self):
        """用户无 Jira 配置返回 None"""
        config_data = {"users": {"user3": {"email": "demo@example.com"}}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        loader = UserConfigLoader(temp_path)
        assert loader.get_jira_config("user3") is None
        os.unlink(temp_path)

    def test_get_circleci_config(self, temp_config_file):
        """获取 CircleCI 配置"""
        loader = UserConfigLoader(temp_config_file)
        circleci_config = loader.get_circleci_config("user1")
        assert circleci_config is not None
        assert circleci_config["api_token"] == "circle1"

    def test_get_circleci_config_nonexistent(self, temp_config_file):
        """不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_circleci_config("nonexistent") is None

    def test_get_circleci_config_user_without_circleci(self, temp_config_file):
        """用户无 CircleCI 配置返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_circleci_config("user2") is None

    def test_get_argocd_config(self, temp_config_file):
        """获取 ArgoCD 配置"""
        loader = UserConfigLoader(temp_config_file)
        argocd_config = loader.get_argocd_config("user1")
        assert argocd_config is not None
        assert argocd_config["token"] == "argo1"

    def test_get_argocd_config_nonexistent(self, temp_config_file):
        """不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_argocd_config("nonexistent") is None

    def test_get_argocd_config_user_without_argocd(self, temp_config_file):
        """用户无 ArgoCD 配置返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_argocd_config("user2") is None

    def test_get_jenkins_config(self, temp_config_file):
        """获取 Jenkins 配置"""
        loader = UserConfigLoader(temp_config_file)
        jenkins_config = loader.get_jenkins_config("user1")
        assert jenkins_config is not None
        assert jenkins_config["username"] == "jenkins1"

    def test_get_jenkins_config_nonexistent(self, temp_config_file):
        """不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_jenkins_config("nonexistent") is None

    def test_get_jenkins_config_user_without_jenkins(self, temp_config_file):
        """用户无 Jenkins 配置返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_jenkins_config("user2") is None

    def test_get_user_email(self, temp_config_file):
        """获取用户邮箱"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_user_email("user1") == "demo@example.com"

    def test_get_user_email_nonexistent(self, temp_config_file):
        """不存在用户返回 None"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_user_email("nonexistent") is None

    def test_get_user_display_name(self, temp_config_file):
        """获取用户显示名称"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_user_display_name("user1") == "User One"

    def test_get_user_display_name_default_to_username(self):
        """无显示名称时返回用户名"""
        config_data = {"users": {"user3": {"email": "demo@example.com"}}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        loader = UserConfigLoader(temp_path)
        assert loader.get_user_display_name("user3") == "user3"
        os.unlink(temp_path)

    def test_get_user_display_name_nonexistent(self, temp_config_file):
        """不存在用户返回用户名"""
        loader = UserConfigLoader(temp_config_file)
        assert loader.get_user_display_name("nonexistent") == "nonexistent"


class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.fixture
    def mock_loader(self):
        """Mock UserConfigLoader"""
        mock = MagicMock()
        mock.get_users_list.return_value = ["user1", "user2"]
        mock.get_default_user.return_value = "user1"
        mock.get_jira_config.return_value = {"api_token": "token"}
        mock.get_circleci_config.return_value = {"api_token": "circle"}
        mock.get_argocd_config.return_value = {"token": "argo"}
        mock.get_jenkins_config.return_value = {"username": "jenkins"}
        return mock

    def test_get_users_list(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_users_list()
            assert result == ["user1", "user2"]

    def test_get_default_user(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_default_user()
            assert result == "user1"

    def test_get_jira_config(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_jira_config("user1")
            assert result == {"api_token": "token"}

    def test_get_circleci_config(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_circleci_config("user1")
            assert result == {"api_token": "circle"}

    def test_get_argocd_config(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_argocd_config("user1")
            assert result == {"token": "argo"}

    def test_get_jenkins_config(self, mock_loader):
        """便捷函数调用 loader"""
        with patch('modules.user_config_loader.get_user_config_loader', return_value=mock_loader):
            result = get_jenkins_config("user1")
            assert result == {"username": "jenkins"}

    def test_get_user_config_loader_returns_same_instance(self):
        """单例模式：多次调用返回同一实例"""
        import modules.user_config_loader as module
        module._loader_instance = None

        loader1 = get_user_config_loader()
        loader2 = get_user_config_loader()
        # 同一实例（单例模式）
        assert loader1 is loader2

    def test_reload_config_returns_new_instance(self):
        """reload_config 返回新实例"""
        loader1 = get_user_config_loader()
        loader2 = reload_config()
        # 不同实例（强制重新加载）
        assert loader1 is not loader2


class TestBuildJiraAuthHeaders:
    """测试 build_jira_auth_headers 函数"""

    def test_normal_case(self):
        """正常情况"""
        headers = build_jira_auth_headers("demo@example.com", "api_token_123")
        assert headers['Authorization'].startswith('Basic ')
        assert headers['Content-Type'] == 'application/json'

    def test_empty_email(self):
        """空邮箱"""
        headers = build_jira_auth_headers("", "token")
        assert headers['Authorization'].startswith('Basic ')

    def test_empty_token(self):
        """空 token"""
        headers = build_jira_auth_headers("demo@example.com", "")
        assert headers['Authorization'].startswith('Basic ')

    def test_special_chars_in_token(self):
        """token 包含特殊字符"""
        headers = build_jira_auth_headers("demo@example.com", "token:with:special@chars")
        assert headers['Authorization'].startswith('Basic ')

    def test_base64_encoding_is_correct(self):
        """验证 Base64 编码正确"""
        import base64
        email = "demo@example.com"
        token = "secret123"
        headers = build_jira_auth_headers(email, token)

        expected = base64.b64encode(f"{email}:{token}".encode()).decode()
        actual = headers['Authorization'].replace('Basic ', '')
        assert actual == expected

    def test_returns_dict(self):
        """返回字典类型"""
        headers = build_jira_auth_headers("email", "token")
        assert isinstance(headers, dict)

    def test_has_content_type(self):
        """包含 Content-Type"""
        headers = build_jira_auth_headers("email", "token")
        assert 'Content-Type' in headers


class TestBuildJenkinsAuth:
    """测试 build_jenkins_auth 函数"""

    def test_returns_httpbasicauth(self):
        """返回 HTTPBasicAuth 对象"""
        auth = build_jenkins_auth("username", "token")
        assert isinstance(auth, HTTPBasicAuth)

    def test_username_set(self):
        """用户名正确设置"""
        auth = build_jenkins_auth("myuser", "mytoken")
        assert auth.username == "myuser"

    def test_password_set(self):
        """密码正确设置"""
        auth = build_jenkins_auth("user", "secret")
        assert auth.password == "secret"

    def test_empty_username(self):
        """空用户名"""
        auth = build_jenkins_auth("", "token")
        assert auth.username == ""

    def test_empty_password(self):
        """空密码"""
        auth = build_jenkins_auth("user", "")
        assert auth.password == ""


class TestBuildCircleciHeaders:
    """测试 build_circleci_headers 函数"""

    def test_has_circle_token(self):
        """包含 Circle-Token"""
        headers = build_circleci_headers("my_token")
        assert headers['Circle-Token'] == "my_token"

    def test_has_content_type(self):
        """包含 Content-Type"""
        headers = build_circleci_headers("token")
        assert headers['Content-Type'] == 'application/json'

    def test_returns_dict(self):
        """返回字典类型"""
        headers = build_circleci_headers("token")
        assert isinstance(headers, dict)

    def test_empty_token(self):
        """空 token"""
        headers = build_circleci_headers("")
        assert headers['Circle-Token'] == ""
