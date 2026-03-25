"""
tests/test_test_case_importer_logic.py
覆盖 _test_case_importer_logic.py 核心纯函数
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules._test_case_importer_logic import (
    authenticate_xray,
    build_tests_payload,
    submit_tests_bulk,
    poll_job_status,
    query_related_ticket,
    get_test_numeric_ids,
    link_tests_to_test_set,
    link_tests_to_story,
    XrayAuthError,
    XrayImportError,
    XrayJobFailedError,
    XrayJobTimeoutError,
)


# ── 测试数据 fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_df():
    """构造测试用 DataFrame"""
    import pandas as pd
    return pd.DataFrame([
        {"Action": "登录系统", "Data": "admin", "Expected Result": "登录成功"},
        {"Action": "提交订单", "Data": "", "Expected Result": "订单提交成功"},
    ])


# ── build_tests_payload ──────────────────────────────────────────────────────

class TestBuildTestsPayload:
    def test_uses_action_as_title(self, mock_df):
        payload = build_tests_payload(
            mock_df, "Mermaid", "Medium",
            "使用 Action 列作为 Title（推荐）", ""
        )
        assert len(payload) == 2
        assert payload[0]["fields"]["summary"] == "登录系统"
        assert payload[0]["fields"]["project"] == {"key": "SP"}
        assert payload[0]["fields"]["issuetype"] == {"name": "Test"}
        assert payload[0]["fields"]["priority"] == {"name": "Medium"}
        assert payload[0]["xray_test_type"] == "Manual"
        assert payload[0]["steps"][0]["action"] == "登录系统"
        assert payload[0]["steps"][0]["data"] == "admin"

    def test_uses_custom_title(self, mock_df):
        payload = build_tests_payload(
            mock_df, "Mermaid", "High",
            "自定义统一 Title", "回归测试-登录模块"
        )
        assert payload[0]["fields"]["summary"] == "回归测试-登录模块"
        assert payload[1]["fields"]["summary"] == "回归测试-登录模块"

    def test_empty_custom_title_falls_back_to_action(self, mock_df):
        payload = build_tests_payload(
            mock_df, "Mermaid", "Low",
            "自定义统一 Title", "   "
        )
        assert payload[0]["fields"]["summary"] == "登录系统"

    def test_sp_team_field(self, mock_df):
        payload = build_tests_payload(
            mock_df, "QA-Team", "Critical",
            "使用 Action 列作为 Title（推荐）", ""
        )
        assert payload[0]["fields"]["customfield_12628"] == {"value": "QA-Team"}

    def test_empty_data_becomes_empty_string(self, mock_df):
        payload = build_tests_payload(
            mock_df, "M", "L",
            "使用 Action 列作为 Title（推荐）", ""
        )
        assert payload[1]["steps"][0]["data"] == ""


# ── authenticate_xray ────────────────────────────────────────────────────────

class TestAuthenticateXray:
    def test_success_returns_token(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '"test-token-abc"'

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        token = authenticate_xray("cid", "csec", http_client=mock_client)
        assert token == "test-token-abc"

    def test_success_strips_quotes(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '"test-token-abc"'
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        assert authenticate_xray("cid", "csec", http_client=mock_client) == "test-token-abc"

    def test_failure_raises_xray_auth_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "invalid credentials"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        with pytest.raises(XrayAuthError):
            authenticate_xray("bad", "bad", http_client=mock_client)


# ── submit_tests_bulk ────────────────────────────────────────────────────────

class TestSubmitTestsBulk:
    def test_direct_response_no_job_id(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = [
            {"key": "SP-1"}, {"key": "SP-2"}
        ]
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        job_id, keys = submit_tests_bulk("token", [{}, {}], http_client=mock_client)
        assert job_id is None
        assert keys == ["SP-1", "SP-2"]

    def test_response_with_issues(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"issues": [{"key": "SP-3"}]}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        job_id, keys = submit_tests_bulk("token", [{}], http_client=mock_client)
        assert job_id is None
        assert keys == ["SP-3"]

    def test_job_id_returned_for_async(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {"jobId": "job-123"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        job_id, keys = submit_tests_bulk("token", [{}], http_client=mock_client)
        assert job_id == "job-123"
        assert keys == []

    def test_non_2xx_raises_import_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        with pytest.raises(XrayImportError):
            submit_tests_bulk("token", [{}], http_client=mock_client)


# ── poll_job_status ─────────────────────────────────────────────────────────

class TestPollJobStatus:
    def test_successful_status_returns_keys(self):
        mock_client = MagicMock()
        # First 2 polls return pending, 3rd returns SUCCESS
        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status": "PENDING"}),
            MagicMock(status_code=200, json=lambda: {"status": "RUNNING"}),
            MagicMock(status_code=200, json=lambda: {
                "status": "SUCCESSFUL",
                "result": {"issues": [{"key": "SP-1"}, {"key": "SP-2"}]}
            }),
        ]

        keys = poll_job_status(
            "token", "job-123",
            max_polls=3, poll_interval=0,
            http_client=mock_client
        )
        assert keys == ["SP-1", "SP-2"]

    def test_failed_job_raises_xray_job_failed_error(self):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "FAILED", "result": {"error": "bad stuff"}}
        )
        with pytest.raises(XrayJobFailedError):
            poll_job_status("token", "job-123", max_polls=3,
                            poll_interval=0, http_client=mock_client)

    def test_timeout_raises_xray_job_timeout_error(self):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "RUNNING"}
        )
        with pytest.raises(XrayJobTimeoutError):
            poll_job_status("token", "job-123", max_polls=2,
                            poll_interval=0, http_client=mock_client)

    def test_progress_callback_called(self):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "SUCCESSFUL", "result": {"issues": []}}
        )
        calls = []

        def cb(count, max_polls, msg):
            calls.append((count, max_polls, msg))

        poll_job_status("token", "job-123", max_polls=1,
                        poll_interval=0, progress_cb=cb,
                        http_client=mock_client)
        assert len(calls) == 1
        assert calls[0][0] == 1


# ── query_related_ticket ────────────────────────────────────────────────────

class TestQueryRelatedTicket:
    def test_returns_type_and_id(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "12345",
            "fields": {"issuetype": {"name": "Test Set"}}
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        issue_type, numeric_id = query_related_ticket(
            "https://jira.example.com",
            {"Authorization": "Basic xxx"},
            "SP-30088",
            http_client=mock_client
        )
        assert issue_type == "Test Set"
        assert numeric_id == "12345"

    def test_non_200_returns_empty(self):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(status_code=404)
        issue_type, numeric_id = query_related_ticket(
            "https://jira.example.com",
            {}, "SP-NOTFOUND",
            http_client=mock_client
        )
        assert issue_type == ""
        assert numeric_id == ""


# ── get_test_numeric_ids ────────────────────────────────────────────────────

class TestGetTestNumericIds:
    def test_returns_numeric_ids(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "111"}),
            MagicMock(status_code=200, json=lambda: {"id": "222"}),
        ]
        ids = get_test_numeric_ids(
            "https://jira.example.com",
            {}, ["SP-1", "SP-2"],
            http_client=mock_client
        )
        assert ids == ["111", "222"]

    def test_skips_failed_requests(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "111"}),
            MagicMock(status_code=403, json=lambda: {}),
            MagicMock(status_code=200, json=lambda: {"id": "333"}),
        ]
        ids = get_test_numeric_ids(
            "https://jira.example.com",
            {}, ["SP-1", "SP-2", "SP-3"],
            http_client=mock_client
        )
        assert sorted(ids) == ["111", "333"]


# ── link_tests_to_test_set ─────────────────────────────────────────────────

class TestLinkTestsToTestSet:
    def test_success_returns_all_keys(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "addTestsToTestSet": {
                    "addedTests": ["SP-1", "SP-2"],
                    "warning": ""
                }
            }
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        success, failures = link_tests_to_test_set(
            "xray-token", "12345", ["SP-1", "SP-2"],
            http_client=mock_client
        )
        assert success == ["SP-1", "SP-2"]
        assert failures == []

    def test_graphql_errors_return_failures(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "errors": [{"message": "invalid id"}]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        success, failures = link_tests_to_test_set(
            "token", "bad-id", ["SP-1"],
            http_client=mock_client
        )
        assert success == []
        assert len(failures) == 1


# ── link_tests_to_story ────────────────────────────────────────────────────

class TestLinkTestsToStory:
    def test_partial_success(self):
        mock_client = MagicMock()
        mock_client.post.side_effect = [
            MagicMock(status_code=201),
            MagicMock(status_code=400, text="bad request"),
        ]
        success, failures = link_tests_to_story(
            "https://jira.example.com",
            {}, ["SP-1", "SP-2"], "SP-999",
            http_client=mock_client
        )
        assert success == ["SP-1"]
        assert len(failures) == 1
        assert failures[0]["key"] == "SP-2"
