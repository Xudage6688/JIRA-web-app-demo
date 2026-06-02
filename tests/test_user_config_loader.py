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
    get_users_list,
    get_default_user,
    get_jira_config,
    get_circleci_config,
    get_argocd_config,
    get_jenkins_config,
    build_jira_auth_headers,
    build_jenkins_auth,
    build_circleci_headers,
    sanitize_error_message
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
                    "email": "user1@example.com",
                    "display_name": "User One",
                    "jira": {"base_url": "https://jira.example.com", "api_token": "token1"},
                    "circleci": {"api_token": "circle1", "vcs_type": "github"},
                    "argocd": {"url": "https://argocd.example.com", "token": "argo1"},
                    "jenkins": {"url": "https://jenkins.example.com", "username": "jenkins1", "token": "jenkins1_token"}
                },
                "user2": {
                    "email": "user2@example.com",
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
        assert config["email"] == "user1@example.com"

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
        config_data = {"users": {"user3": {"email": "user3@example.com"}}}
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
        assert loader.get_user_email("user1") == "user1@example.com"

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
        config_data = {"users": {"user3": {"email": "user3@example.com"}}}
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

    def test_get_user_config_loader_returns_new_instance(self):
        """每次调用返回新实例"""
        loader1 = get_user_config_loader()
        loader2 = get_user_config_loader()
        # 不同实例（因为每次都重新读取文件）
        assert loader1 is not loader2


class TestBuildJiraAuthHeaders:
    """测试 build_jira_auth_headers 函数"""

    def test_normal_case(self):
        """正常情况"""
        headers = build_jira_auth_headers("user@example.com", "api_token_123")
        assert headers['Authorization'].startswith('Basic ')
        assert headers['Content-Type'] == 'application/json'

    def test_empty_email(self):
        """空邮箱"""
        headers = build_jira_auth_headers("", "token")
        assert headers['Authorization'].startswith('Basic ')

    def test_empty_token(self):
        """空 token"""
        headers = build_jira_auth_headers("user@example.com", "")
        assert headers['Authorization'].startswith('Basic ')

    def test_special_chars_in_token(self):
        """token 包含特殊字符"""
        headers = build_jira_auth_headers("user@example.com", "token:with:special@chars")
        assert headers['Authorization'].startswith('Basic ')

    def test_base64_encoding_is_correct(self):
        """验证 Base64 编码正确"""
        import base64
        email = "test@example.com"
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


class TestSanitizeErrorMessage:
    """测试 sanitize_error_message 函数"""

    def test_bearer_token_redacted(self):
        """Bearer token should be redacted"""
        result = sanitize_error_message("Failed to fetch: Bearer abc123xyz_token")
        assert result == "Failed to fetch: Bearer ***"
        assert "abc123xyz_token" not in result

    def test_api_key_variations_redacted(self):
        """API key variations should be redacted"""
        # api_key
        result = sanitize_error_message("Error: api_key=sk1234567890abcdef")
        assert result == "Error: api_key=***"
        # api-key
        result = sanitize_error_message("Error: api-key=sk1234567890abcdef")
        assert result == "Error: api_key=***"
        # apiKey (camelCase)
        result = sanitize_error_message("Error: apiKey=sk1234567890abcdef")
        assert "sk1234567890abcdef" not in result

    def test_token_key_redacted(self):
        """token key should be redacted"""
        result = sanitize_error_message("Auth failed: token=my_secret_token_here")
        assert result == "Auth failed: token=***"
        assert "my_secret_token_here" not in result

    def test_password_redacted(self):
        """password should be redacted"""
        result = sanitize_error_message("Login failed: password=supersecret123")
        assert result == "Login failed: password=***"
        assert "supersecret123" not in result

    def test_basic_auth_redacted(self):
        """Basic auth header should be redacted"""
        result = sanitize_error_message("Unauthorized: Basic dXNlcjpwYXNzMTIz")
        assert result == "Unauthorized: Basic ***"
        assert "dXNlcjpwYXNzMTIz" not in result

    def test_circle_token_redacted(self):
        """CircleCI token should be redacted"""
        result = sanitize_error_message("CircleCI error: Circle-Token cci_token_abc123")
        assert result == "CircleCI error: Circle-Token ***"
        assert "cci_token_abc123" not in result

    def test_multiple_sensitive_values_redacted(self):
        """Multiple sensitive values in same message should all be redacted"""
        msg = "Token=abc123, api_key=xyz789, Bearer auth123"
        result = sanitize_error_message(msg)
        # All sensitive values should be redacted
        assert "abc123" not in result
        assert "xyz789" not in result
        assert "auth123" not in result
        assert "***" in result

    def test_no_sensitive_data_unchanged(self):
        """Messages without sensitive data should be unchanged"""
        msg = "Failed to connect to server"
        result = sanitize_error_message(msg)
        assert result == msg

    def test_error_structure_preserved(self):
        """Error message structure should be preserved after redaction"""
        msg = "API Error: token=secret123 at endpoint https://api.example.com"
        result = sanitize_error_message(msg)
        # The structure should be preserved
        assert "API Error:" in result
        assert "endpoint" in result
        assert "https://api.example.com" in result
        # But token should be redacted
        assert "secret123" not in result

    def test_case_insensitive_matching(self):
        """Pattern matching should be case insensitive"""
        msg = "Error: TOKEN=my_token, API_KEY=my_key"
        result = sanitize_error_message(msg)
        assert "my_token" not in result
        assert "my_key" not in result

    def test_empty_string(self):
        """Empty string should return empty string"""
        result = sanitize_error_message("")
        assert result == ""

    def test_quoted_password(self):
        """Quoted password values should be redacted"""
        result = sanitize_error_message('Auth: password="secret123"')
        assert "secret123" not in result
        assert "password" in result

    def test_github_pat_ghp_redacted(self):
        """GitHub PAT starting with ghp_ should be redacted"""
        result = sanitize_error_message("GitHub error: ghp_abc123xyz456def789")
        assert result == "GitHub error: [GITHUB_TOKEN]***"
        assert "abc123xyz456def789" not in result

    def test_github_pat_github_pat_redacted(self):
        """GitHub PAT starting with github_pat_ should be redacted"""
        result = sanitize_error_message("Error: github_pat_abc123xyz456def789")
        assert result == "Error: [GITHUB_TOKEN]***"
        assert "abc123xyz456def789" not in result

    def test_github_pat_gho_redacted(self):
        """GitHub OAuth token starting with gho_ should be redacted"""
        result = sanitize_error_message("Auth failed: gho_abc123xyz456def789")
        assert result == "Auth failed: [GITHUB_TOKEN]***"
        assert "abc123xyz456def789" not in result

    def test_jira_token_variations_redacted(self):
        """Jira token variations should be redacted"""
        # jira_token
        result = sanitize_error_message("Error: jira_token=abc123xyz_token")
        assert result == "Error: jira_token=***"
        assert "abc123xyz_token" not in result
        # jira-token
        result = sanitize_error_message("Error: jira-token=abc123xyz_token")
        assert "jira-token" in result
        assert "abc123xyz_token" not in result
        # jiraToken
        result = sanitize_error_message("Error: jiraToken=abc123xyz_token")
        assert "abc123xyz_token" not in result
