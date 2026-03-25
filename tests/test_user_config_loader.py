"""
tests/test_user_config_loader.py
覆盖 user_config_loader 模块的核心函数
"""

import pytest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.user_config_loader import build_jira_auth_headers, build_jenkins_auth, build_circleci_headers
from requests.auth import HTTPBasicAuth


class TestBuildJiraAuthHeaders:
    """build_jira_auth_headers() 的边界测试"""

    def test_normal_case(self):
        """正常 email + token，输出包含 Basic 头"""
        headers = build_jira_auth_headers("test@example.com", "api-token-123")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_empty_email(self):
        """空 email 不应抛异常"""
        headers = build_jira_auth_headers("", "token")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Basic OnRva2Vu"  # base64(":")

    def test_empty_token(self):
        """空 token 不应抛异常"""
        headers = build_jira_auth_headers("user@test.com", "")
        assert "Authorization" in headers

    def test_special_chars_in_token(self):
        """token 含特殊字符不应抛异常"""
        headers = build_jira_auth_headers("user@test.com", "tok-en_123.456")
        assert "Authorization" in headers

    def test_base64_encoding_is_correct(self):
        """验证 base64 编码结果正确"""
        import base64
        email = "alice@example.com"
        token = "secret123"
        expected = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("utf-8")
        headers = build_jira_auth_headers(email, token)
        assert expected in headers["Authorization"]

    def test_returns_dict(self):
        """返回类型必须是 dict"""
        result = build_jira_auth_headers("u", "t")
        assert isinstance(result, dict)

    def test_has_content_type(self):
        """必须包含 Content-Type"""
        headers = build_jira_auth_headers("u", "t")
        assert "Content-Type" in headers


class TestBuildJenkinsAuth:
    """build_jenkins_auth() 的测试"""

    def test_returns_httpbasicauth(self):
        """返回值必须是 HTTPBasicAuth 实例"""
        result = build_jenkins_auth("admin", "secret")
        assert isinstance(result, HTTPBasicAuth)

    def test_username_set(self):
        auth = build_jenkins_auth("myuser", "mytoken")
        assert auth.username == "myuser"

    def test_password_set(self):
        auth = build_jenkins_auth("myuser", "mytoken")
        assert auth.password == "mytoken"

    def test_empty_username(self):
        auth = build_jenkins_auth("", "token")
        assert auth.username == ""
        assert auth.password == "token"


class TestBuildCircleciHeaders:
    """build_circleci_headers() 的测试"""

    def test_has_circle_token(self):
        headers = build_circleci_headers("my-circle-token")
        assert "Circle-Token" in headers
        assert headers["Circle-Token"] == "my-circle-token"

    def test_has_content_type(self):
        headers = build_circleci_headers("token")
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_returns_dict(self):
        result = build_circleci_headers("token")
        assert isinstance(result, dict)

    def test_empty_token(self):
        """空 token 不应抛异常"""
        headers = build_circleci_headers("")
        assert headers["Circle-Token"] == ""
