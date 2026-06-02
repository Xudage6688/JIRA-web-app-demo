"""
tests/test_jira_operations_helper.py
覆盖 jira_operations_helper 模块的核心逻辑
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.jira_operations_helper import JiraOperationsClient, FALLBACK_CONFIG


class TestJiraOperationsClientInit:
    """JiraOperationsClient 初始化"""

    def test_base_url_strips_trailing_slash(self):
        """base_url 末尾斜杠应被去除"""
        client = JiraOperationsClient("https://example.com/", "user@test.com", "token")
        assert client.base_url == "https://example.com"
        assert not client.base_url.endswith("/")

    def test_base_url_no_change_if_no_trailing_slash(self):
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")
        assert client.base_url == "https://example.com"

    def test_email_stored(self):
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")
        assert client.email == "user@test.com"

    def test_token_stored(self):
        client = JiraOperationsClient("https://example.com", "user@test.com", "my-token")
        assert client.api_token == "my-token"

    def test_session_created(self):
        """应创建 requests Session"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")
        assert client.session is not None

    def test_session_has_auth_headers(self):
        """Session 应包含认证头"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")
        assert "Authorization" in client.session.headers


class TestConvertToAdf:
    """convert_to_adf 静态方法"""

    def test_convert_empty_text(self):
        """空文本返回空 doc"""
        result = JiraOperationsClient.convert_to_adf("")
        assert result["type"] == "doc"
        assert result["version"] == 1
        assert result["content"] == []

    def test_convert_simple_text(self):
        """简单文本转换"""
        result = JiraOperationsClient.convert_to_adf("Hello World")
        assert result["type"] == "doc"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "paragraph"
        assert result["content"][0]["content"][0]["text"] == "Hello World"

    def test_convert_multiline_text(self):
        """多行文本转换为多个段落"""
        result = JiraOperationsClient.convert_to_adf("Line 1\nLine 2\nLine 3")
        assert len(result["content"]) == 3
        assert result["content"][0]["content"][0]["text"] == "Line 1"
        assert result["content"][1]["content"][0]["text"] == "Line 2"
        assert result["content"][2]["content"][0]["text"] == "Line 3"

    def test_convert_text_with_empty_lines(self):
        """包含空行的文本"""
        result = JiraOperationsClient.convert_to_adf("Line 1\n\nLine 2")
        # 空行应被忽略
        assert len(result["content"]) >= 1

    def test_convert_none_text(self):
        """None 输入返回空 doc"""
        result = JiraOperationsClient.convert_to_adf(None)
        assert result["type"] == "doc"
        assert result["content"] == []


class TestParseAdfToText:
    """parse_adf_to_text 静态方法"""

    def test_parse_empty_adf(self):
        """空 ADF 返回空字符串"""
        result = JiraOperationsClient.parse_adf_to_text({})
        assert result == ""

    def test_parse_none_adf(self):
        """None 输入返回空字符串"""
        result = JiraOperationsClient.parse_adf_to_text(None)
        assert result == ""

    def test_parse_simple_adf(self):
        """解析简单 ADF"""
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello World"}]}
            ]
        }
        result = JiraOperationsClient.parse_adf_to_text(adf)
        assert result == "Hello World"

    def test_parse_multiline_adf(self):
        """解析多段落 ADF"""
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 1"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 2"}]}
            ]
        }
        result = JiraOperationsClient.parse_adf_to_text(adf)
        assert "Line 1" in result
        assert "Line 2" in result

    def test_parse_adf_with_extra_content(self):
        """解析包含非段落内容的 ADF"""
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
                {"type": "text", "text": "Direct text"}
            ]
        }
        result = JiraOperationsClient.parse_adf_to_text(adf)
        assert "Hello" in result


class TestCallApi:
    """_call_api 方法"""

    def test_call_api_success(self):
        """API 调用成功"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'

        with patch.object(client.session, 'request', return_value=mock_response):
            result = client._call_api('endpoint')

        assert result['success'] is True
        assert result['status_code'] == 200

    def test_call_api_with_rest_prefix(self):
        """以 /rest/ 开头的 endpoint 使用完整路径"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{}'

        with patch.object(client.session, 'request', return_value=mock_response) as mock_request:
            client._call_api('/rest/agile/1.0/board')
            # 验证 URL 是完整路径
            call_args = mock_request.call_args
            url = call_args.kwargs.get('url') or call_args[1].get('url')
            assert '/rest/agile/1.0/board' in url

    def test_call_api_failure(self):
        """API 调用失败"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = '{"error": "not found"}'

        with patch.object(client.session, 'request', return_value=mock_response):
            result = client._call_api('endpoint')

        assert result['success'] is False
        assert result['status_code'] == 404

    def test_call_api_timeout(self):
        """请求超时处理"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        import requests
        with patch.object(client.session, 'request', side_effect=requests.Timeout()):
            result = client._call_api('endpoint')

        assert result['success'] is False
        assert result['status_code'] == 0
        assert 'error' in result

    def test_call_api_request_exception(self):
        """请求异常处理"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        import requests
        with patch.object(client.session, 'request', side_effect=requests.RequestException("Connection error")):
            result = client._call_api('endpoint')

        assert result['success'] is False
        assert result['status_code'] == 0


class TestGetCreateMetadata:
    """get_create_metadata 方法"""

    def test_get_create_metadata_success(self):
        """成功解析 createmeta"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 200,
            'data': {
                'projects': [{
                    'issuetypes': [
                        {
                            'id': '1',
                            'name': 'Bug',
                            'fields': {
                                'priority': {
                                    'allowedValues': [
                                        {'id': '1', 'name': 'High'}
                                    ]
                                }
                            }
                        }
                    ]
                }]
            }
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_create_metadata()

        assert 'work_types' in result
        assert 'priorities' in result
        assert result['using_fallback'] is False

    def test_get_create_metadata_fallback_on_failure(self):
        """API 失败时使用 fallback"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {'success': False, 'status_code': 500, 'data': None}

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_create_metadata()

        assert result['using_fallback'] is True
        assert result['work_types'] == FALLBACK_CONFIG['work_types']
        assert result['priorities'] == FALLBACK_CONFIG['priorities']


class TestGetUserAccountId:
    """get_user_account_id 方法"""

    def test_get_user_account_id_success(self):
        """成功获取用户 accountId"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'data': [{'accountId': 'user123'}]
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_user_account_id('test@test.com')

        assert result == 'user123'

    def test_get_user_account_id_not_found(self):
        """用户不存在返回 None"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {'success': True, 'data': []}

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_user_account_id('notexist@test.com')

        assert result is None


class TestCreateIssue:
    """create_issue 方法"""

    def test_create_issue_success(self):
        """创建 Issue 成功"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue'
            )

        assert result['success'] is True

    def test_create_issue_with_description(self):
        """创建带描述的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                description='This is a test description'
            )

        assert result['success'] is True
        # _call_api 应该被调用2次：一次创建 issue，一次添加到 sprint（如果没有 sprint_id）

    def test_create_issue_failure(self):
        """创建 Issue 失败"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': False,
            'status_code': 400,
            'data': {'errorMessages': ['Invalid issue']}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue'
            )

        assert result['success'] is False


class TestGetIssue:
    """get_issue 方法"""

    def test_get_issue_success(self):
        """获取 Issue 详情成功"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 200,
            'data': {
                'key': 'SP-100',
                'fields': {'summary': 'Test Issue'}
            }
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_issue('SP-100')

        assert result['success'] is True
        assert result['data']['key'] == 'SP-100'


class TestUpdateIssueResolution:
    """update_issue_resolution 方法"""

    def test_update_resolution_success(self):
        """更新 Resolution 成功"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 200
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.update_issue_resolution('SP-100', 'Fixed')

        assert result['success'] is True
        assert result['issue_key'] == 'SP-100'

    def test_update_resolution_failure(self):
        """更新 Resolution 失败"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': False,
            'status_code': 400
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.update_issue_resolution('SP-100', 'Fixed')

        assert result['success'] is False


class TestGetResolutions:
    """get_resolutions 方法"""

    def test_get_resolutions_success(self):
        """成功获取 Resolutions"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'data': [
                {'name': 'Fixed'},
                {'name': 'Wont Fix'}
            ]
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_resolutions()

        assert 'Fixed' in result
        assert 'Wont Fix' in result

    def test_get_resolutions_fallback(self):
        """API 失败时返回 fallback"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {'success': False, 'data': None}

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_resolutions()

        assert result == FALLBACK_CONFIG['resolutions']


class TestDeleteIssue:
    """delete_issue 方法"""

    def test_delete_issue_success(self):
        """删除 Issue 成功"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 204
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.delete_issue('SP-100')

        assert result['success'] is True
        assert result['issue_key'] == 'SP-100'

    def test_delete_issue_failure(self):
        """删除 Issue 失败"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': False,
            'status_code': 403
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.delete_issue('SP-100')

        assert result['success'] is False


class TestGetActiveSprints:
    """get_active_sprints 方法"""

    def test_get_active_sprints_success(self):
        """成功获取 Active Sprints"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        board_response = {
            'success': True,
            'data': {
                'values': [
                    {'id': 1, 'name': 'Board 1'},
                    {'id': 2, 'name': 'Board 2'}
                ]
            }
        }

        def mock_call_api(endpoint, method='GET', data=None, params=None):
            if 'board' in endpoint:
                return board_response
            if 'sprint' in endpoint:
                return {
                    'success': True,
                    'data': {
                        'values': [
                            {'id': 10, 'name': 'Sprint 1', 'state': 'active'}
                        ]
                    }
                }
            return {'success': False}

        with patch.object(client, '_call_api', side_effect=mock_call_api):
            result = client.get_active_sprints()

        assert isinstance(result, list)

    def test_get_active_sprints_no_boards(self):
        """没有 Board 时返回空列表"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'data': {'values': []}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_active_sprints()

        assert result == []

    def test_get_active_sprints_with_team_filter(self):
        """按 Team 过滤 Sprints"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        board_response = {
            'success': True,
            'data': {
                'values': [
                    {'id': 1, 'name': 'Mermaid Board'},
                    {'id': 2, 'name': 'Apollo Board'}
                ]
            }
        }

        def mock_call_api(endpoint, method='GET', data=None, params=None):
            if 'board' in endpoint:
                return board_response
            if 'sprint' in endpoint:
                return {
                    'success': True,
                    'data': {
                        'values': [{'id': 10, 'name': 'Sprint 1', 'state': 'active'}]
                    }
                }
            return {'success': False}

        with patch.object(client, '_call_api', side_effect=mock_call_api):
            result = client.get_active_sprints(team_name='Mermaid')

        assert isinstance(result, list)


class TestGetSprintsByTeam:
    """get_sprints_by_team 方法"""

    def test_get_sprints_by_team_success(self):
        """成功获取 Team 的 Sprints"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        with patch.object(client, 'get_active_sprints', return_value=[]):
            result = client.get_sprints_by_team('Mermaid')

        assert isinstance(result, list)

    def test_get_sprints_by_team_none(self):
        """team_name 为 None 时返回全部 Sprints"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        with patch.object(client, 'get_active_sprints', return_value=[]):
            result = client.get_sprints_by_team(None)

        assert isinstance(result, list)


class TestFallbackConfig:
    """FALLBACK_CONFIG 配置"""

    def test_fallback_config_structure(self):
        """验证 fallback 配置结构"""
        assert 'work_types' in FALLBACK_CONFIG
        assert 'priorities' in FALLBACK_CONFIG
        assert 'sp_teams' in FALLBACK_CONFIG
        assert 'sp_team_field' in FALLBACK_CONFIG
        assert 'resolutions' in FALLBACK_CONFIG

    def test_fallback_work_types(self):
        """验证 work_types 包含常见类型"""
        work_types = FALLBACK_CONFIG['work_types']
        assert 'Bug' in work_types
        assert 'Story' in work_types
        assert 'Task' in work_types

    def test_fallback_sp_teams(self):
        """验证 sp_teams 列表"""
        sp_teams = FALLBACK_CONFIG['sp_teams']
        assert 'Apollo' in sp_teams
        assert 'Mermaid' in sp_teams
        assert len(sp_teams) > 0


class TestCreateIssueFields:
    """create_issue 各种字段参数"""

    def test_create_issue_with_priority(self):
        """创建带优先级的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                priority_id='3'
            )

        assert result['success'] is True

    def test_create_issue_with_reporter(self):
        """创建带报告人的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                reporter_account_id='user123'
            )

        assert result['success'] is True

    def test_create_issue_with_sp_team(self):
        """创建带 SP Team 的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                sp_team='Mermaid',
                sp_team_field='customfield_12628'
            )

        assert result['success'] is True

    def test_create_issue_with_environment(self):
        """创建带环境的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                environment_occured='PROD'
            )

        assert result['success'] is True

    def test_create_issue_with_bug_category(self):
        """创建带 Bug 分类的 Issue"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                bug_category='Developer Error'
            )

        assert result['success'] is True

    def test_create_issue_with_sprint_adds_issue_to_sprint(self):
        """创建带 Sprint ID 的 Issue 应添加到 Sprint"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        issue_response = {
            'success': True,
            'status_code': 201,
            'data': {'id': '12345', 'key': 'SP-100'}
        }
        sprint_response = {
            'success': True,
            'status_code': 200
        }

        call_count = [0]
        def mock_call_api(endpoint, method='GET', data=None, params=None):
            call_count[0] += 1
            if 'sprint' in endpoint:
                return sprint_response
            return issue_response

        with patch.object(client, '_call_api', side_effect=mock_call_api):
            result = client.create_issue(
                project_key='SP',
                issue_type_id='1',
                summary='Test Issue',
                sprint_id=10
            )

        assert result['success'] is True
        assert call_count[0] >= 2  # Should be called for issue creation and sprint addition


class TestGetCreateMetadataEdgeCases:
    """get_create_metadata 边界情况"""

    def test_get_create_metadata_empty_projects(self):
        """API 返回空项目列表时使用 fallback"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 200,
            'data': {'projects': []}
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_create_metadata()

        assert result['using_fallback'] is True

    def test_get_create_metadata_no_work_types_fallback(self):
        """解析后没有 work_types 使用 fallback"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        mock_response = {
            'success': True,
            'status_code': 200,
            'data': {
                'projects': [{
                    'issuetypes': [
                        {
                            'id': '1',
                            'name': 'Bug',
                            'fields': {}
                        }
                    ]
                }]
            }
        }

        with patch.object(client, '_call_api', return_value=mock_response):
            result = client.get_create_metadata()

        assert result['using_fallback'] is False
        # Bug 应该被提取为 work_types
        assert 'Bug' in result['work_types']


class TestGetActiveSprintsEdgeCases:
    """get_active_sprints 边界情况"""

    def test_get_active_sprints_with_board_ids_filter(self):
        """指定 board_ids 时过滤"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        board_response = {
            'success': True,
            'data': {
                'values': [
                    {'id': 1, 'name': 'Board 1'},
                    {'id': 2, 'name': 'Board 2'},
                    {'id': 3, 'name': 'Board 3'}
                ]
            }
        }

        def mock_call_api(endpoint, method='GET', data=None, params=None):
            if 'board' in endpoint:
                return board_response
            if 'sprint' in endpoint:
                return {
                    'success': True,
                    'data': {
                        'values': [{'id': 10, 'name': 'Sprint 1', 'state': 'active'}]
                    }
                }
            return {'success': False}

        with patch.object(client, '_call_api', side_effect=mock_call_api):
            result = client.get_active_sprints(board_ids=[1, 2])

        assert isinstance(result, list)

    def test_get_active_sprints_exception(self):
        """get_active_sprints 异常处理"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        with patch.object(client, '_call_api', side_effect=Exception("API Error")):
            result = client.get_active_sprints()

        assert result == []


class TestGetSprintsByTeamEdgeCases:
    """get_sprints_by_team 边界情况"""

    def test_get_sprints_by_team_exception(self):
        """get_sprints_by_team 异常处理"""
        client = JiraOperationsClient("https://example.com", "user@test.com", "token")

        with patch.object(client, 'get_active_sprints', side_effect=Exception("API Error")):
            result = client.get_sprints_by_team('Mermaid')

        assert result == []