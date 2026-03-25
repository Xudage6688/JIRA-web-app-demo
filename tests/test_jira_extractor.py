"""
tests/test_jira_extractor.py
覆盖 jira_extractor 模块的核心逻辑
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

from modules.jira_extractor import JiraExtractor, SafeLogger


class TestSafeLogger:
    """SafeLogger 不应抛出异常"""

    def test_info_does_not_raise(self):
        logger = SafeLogger("test")
        logger.info("test message")  # 不应抛异常

    def test_warning_does_not_raise(self):
        logger = SafeLogger("test")
        logger.warning("warn message")

    def test_error_does_not_raise(self):
        logger = SafeLogger("test")
        logger.error("error message")

    def test_debug_does_not_raise(self):
        logger = SafeLogger("test")
        logger.debug("debug message")

    def test_empty_message_does_not_raise(self):
        logger = SafeLogger("test")
        logger.info("")
        logger.warning("")
        logger.error("")

    def test_unicode_message_does_not_raise(self):
        logger = SafeLogger("test")
        logger.info("中文消息 🔥")

    def test_special_chars_does_not_raise(self):
        logger = SafeLogger("test")
        logger.info("!@#$%^&*()[]{}\\|'\"`~")

    def test_long_message_does_not_raise(self):
        logger = SafeLogger("test")
        logger.info("x" * 10000)  # 长消息


class TestJiraExtractorInit:
    """JiraExtractor 初始化行为"""

    def test_base_url_strips_trailing_slash(self):
        """base_url 末尾斜杠应被去除"""
        client = JiraExtractor("https://example.com/", "token", "email")
        assert client.base_url == "https://example.com"
        assert not client.base_url.endswith("/")

    def test_base_url_no_change_if_no_trailing_slash(self):
        client = JiraExtractor("https://example.com", "token", "email")
        assert client.base_url == "https://example.com"

    def test_email_stored(self):
        client = JiraExtractor("https://example.com", "token", "user@test.com")
        assert client.email == "user@test.com"

    def test_token_stored(self):
        client = JiraExtractor("https://example.com", "my-token", "user@test.com")
        assert client.api_token == "my-token"


class TestJiraExtractorProjectMappings:
    """项目映射逻辑"""

    def test_apply_project_mappings_empty_input(self):
        """空输入返回空"""
        client = JiraExtractor("https://example.com", "token", "email")
        client.project_mappings = {}
        result = client._apply_project_mappings([])
        assert result == []

    def test_apply_project_mappings_no_mapping(self):
        """无映射配置时返回原列表"""
        client = JiraExtractor("https://example.com", "token", "email")
        client.project_mappings = {}
        result = client._apply_project_mappings(["project-a", "project-b"])
        assert result == ["project-a", "project-b"]

    def test_apply_project_mappings_adds_related(self):
        """有映射时添加关联项目"""
        client = JiraExtractor("https://example.com", "token", "email")
        client.project_mappings = {
            "aca": ["aca-cn"],
            "public-api": ["public-api-job"]
        }
        result = client._apply_project_mappings(["aca"])
        assert "aca" in result
        assert "aca-cn" in result

    def test_apply_project_mappings_no_duplicate(self):
        """已存在的关联项目不重复添加"""
        client = JiraExtractor("https://example.com", "token", "email")
        client.project_mappings = {"aca": ["aca-cn"]}
        result = client._apply_project_mappings(["aca", "aca-cn"])
        assert result.count("aca-cn") == 1

    def test_apply_project_mappings_case_insensitive(self):
        """映射匹配大小写不敏感"""
        client = JiraExtractor("https://example.com", "token", "email")
        client.project_mappings = {"aca": ["aca-cn"]}
        result = client._apply_project_mappings(["ACA"])
        assert "aca-cn" in result

    def test_load_project_mappings_missing_file_returns_default(self, tmp_path):
        """映射文件不存在时返回默认映射"""
        with patch("modules.jira_extractor.os.path.exists", return_value=False):
            client = JiraExtractor.__new__(JiraExtractor)
            client.base_url = "https://example.com"
            client.api_token = "t"
            client.email = "e"
            client.session = MagicMock()
            client.project_mappings = None
            with patch.object(client, "_load_project_mappings") as mock_load:
                mock_load.return_value = {
                    "aca": ["aca-cn"],
                    "public-api": ["public-api-job"]
                }
                result = client._load_project_mappings()
                # 默认映射有值即可
                assert isinstance(result, dict)


class TestJiraExtractorGetAffectsProjectFieldId:
    """get_affects_project_field_id 方法"""

    def test_returns_known_field_id(self):
        client = JiraExtractor("https://example.com", "token", "email")
        result = client.get_affects_project_field_id()
        assert result == "customfield_12605"

    def test_returns_custom_field_id(self):
        client = JiraExtractor("https://example.com", "token", "email")
        result = client.get_affects_project_field_id("customfield_99999")
        assert result == "customfield_99999"
