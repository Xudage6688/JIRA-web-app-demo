"""CircleCI monitoring 模块单元测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from circleCi.monitoring import (
    get_pipeline_status,
    get_pipeline_workflows,
    get_workflow_status,
    format_status,
    get_pipeline_id_by_number,
)


class TestFormatStatus:
    """测试 format_status 函数"""

    def test_format_running(self):
        """测试 running 状态格式化"""
        display_text, emoji = format_status('running')
        assert display_text == 'Running'
        assert emoji == '🔄'

    def test_format_success(self):
        """测试 success 状态格式化"""
        display_text, emoji = format_status('success')
        assert display_text == 'Success'
        assert emoji == '✅'

    def test_format_failing(self):
        """测试 failing 状态格式化（配置中代表成功）"""
        display_text, emoji = format_status('failing')
        assert display_text == 'Success'
        assert emoji == '✅'

    def test_format_failed(self):
        """测试 failed 状态格式化"""
        display_text, emoji = format_status('failed')
        assert display_text == 'Failed'
        assert emoji == '❌'

    def test_format_error(self):
        """测试 error 状态格式化"""
        display_text, emoji = format_status('error')
        assert display_text == 'Error'
        assert emoji == '❌'

    def test_format_canceled(self):
        """测试 canceled 状态格式化"""
        display_text, emoji = format_status('canceled')
        assert display_text == 'Canceled'
        assert emoji == '⏹️'

    def test_format_on_hold(self):
        """测试 on_hold 状态格式化"""
        display_text, emoji = format_status('on_hold')
        assert display_text == 'On Hold'
        assert emoji == '⏸️'

    def test_format_not_run(self):
        """测试 not_run 状态格式化"""
        display_text, emoji = format_status('not_run')
        assert display_text == 'Not Run'
        assert emoji == '⚪'

    def test_format_queued(self):
        """测试 queued 状态格式化"""
        display_text, emoji = format_status('queued')
        assert display_text == 'Queued'
        assert emoji == '⏳'

    def test_format_created(self):
        """测试 created 状态格式化"""
        display_text, emoji = format_status('created')
        assert display_text == 'Created'
        assert emoji == '📝'

    def test_format_unknown_status(self):
        """测试未知状态格式化"""
        display_text, emoji = format_status('unknown_status')
        assert display_text == 'unknown_status'
        assert emoji == '❓'

    def test_format_none_status(self):
        """测试 None 状态格式化"""
        display_text, emoji = format_status(None)
        # 当传入 None 时，status_lower 变成 'unknown'，但 status_map 中没有 'unknown' 键
        # 所以默认返回 (status, '❓') 即 (None, '❓')
        assert display_text is None
        assert emoji == '❓'

    def test_format_case_insensitive(self):
        """测试大小写不敏感"""
        display_text, emoji = format_status('SUCCESS')
        assert display_text == 'Success'
        assert emoji == '✅'


class TestGetPipelineStatus:
    """测试 get_pipeline_status 函数"""

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_success(self, mock_get_headers, mock_get):
        """测试成功获取 pipeline 状态"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'pipeline-123',
            'number': 100,
            'state': 'running',
            'project_slug': 'github/org/repo'
        }
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {
            'Circle-Token': 'test-token'
        }

        result = get_pipeline_status('pipeline-123', api_token='test-token')

        assert result is not None
        assert result['id'] == 'pipeline-123'
        assert result['number'] == 100
        assert result['state'] == 'running'
        mock_get.assert_called_once()

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_404(self, mock_get_headers, mock_get):
        """测试 pipeline 未找到"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_status('non-existent-pipeline', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_401(self, mock_get_headers, mock_get):
        """测试认证失败"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_403(self, mock_get_headers, mock_get):
        """测试权限不足"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_500(self, mock_get_headers, mock_get):
        """测试服务器错误"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_timeout(self, mock_get_headers, mock_get):
        """测试请求超时"""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_request_exception(self, mock_get_headers, mock_get):
        """测试网络请求错误"""
        mock_get.side_effect = requests.exceptions.RequestException('Connection error')

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_status_generic_exception(self, mock_get_headers, mock_get):
        """测试通用异常"""
        mock_get.side_effect = Exception('Unexpected error')

        result = get_pipeline_status('pipeline-123', silent=True)

        assert result is None


class TestGetPipelineWorkflows:
    """测试 get_pipeline_workflows 函数"""

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_success(self, mock_get_headers, mock_get):
        """测试成功获取 workflows"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'wf-1', 'name': 'build', 'status': 'success'},
                {'id': 'wf-2', 'name': 'deploy', 'status': 'running'}
            ]
        }
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('pipeline-123', api_token='test-token')

        assert result is not None
        assert len(result) == 2
        assert result[0]['id'] == 'wf-1'
        assert result[1]['status'] == 'running'

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_empty_items(self, mock_get_headers, mock_get):
        """测试返回空 items"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('pipeline-123', api_token='test-token')

        assert result == []

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_missing_items(self, mock_get_headers, mock_get):
        """测试响应中缺少 items 字段"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('pipeline-123', api_token='test-token')

        assert result == []

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_404(self, mock_get_headers, mock_get):
        """测试 workflows 未找到"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('non-existent-pipeline', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_401(self, mock_get_headers, mock_get):
        """测试认证失败"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_403(self, mock_get_headers, mock_get):
        """测试权限不足"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_workflows('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_timeout(self, mock_get_headers, mock_get):
        """测试请求超时"""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = get_pipeline_workflows('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_workflows_request_exception(self, mock_get_headers, mock_get):
        """测试网络请求错误"""
        mock_get.side_effect = requests.exceptions.RequestException('Connection error')

        result = get_pipeline_workflows('pipeline-123', silent=True)

        assert result is None


class TestGetWorkflowStatus:
    """测试 get_workflow_status 函数"""

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_with_running(self, mock_get_workflows):
        """测试有 running 状态时返回 running"""
        mock_get_workflows.return_value = [
            {'id': 'wf-1', 'status': 'success'},
            {'id': 'wf-2', 'status': 'running'},
            {'id': 'wf-3', 'status': 'failed'}
        ]

        result = get_workflow_status('pipeline-123', silent=True)

        assert result == 'running'

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_with_on_hold(self, mock_get_workflows):
        """测试有 on_hold 状态时返回 on_hold"""
        mock_get_workflows.return_value = [
            {'id': 'wf-1', 'status': 'success'},
            {'id': 'wf-2', 'status': 'on_hold'}
        ]

        result = get_workflow_status('pipeline-123', silent=True)

        assert result == 'on_hold'

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_all_complete(self, mock_get_workflows):
        """测试所有 workflow 都完成时返回最后一个状态"""
        mock_get_workflows.return_value = [
            {'id': 'wf-1', 'status': 'success'},
            {'id': 'wf-2', 'status': 'failed'}
        ]

        result = get_workflow_status('pipeline-123', silent=True)

        assert result == 'failed'  # 返回最后一个

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_empty_workflows(self, mock_get_workflows):
        """测试空 workflows 列表"""
        mock_get_workflows.return_value = []

        result = get_workflow_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_none_workflows(self, mock_get_workflows):
        """测试 workflows 返回 None"""
        mock_get_workflows.return_value = None

        result = get_workflow_status('pipeline-123', silent=True)

        assert result is None

    @patch('circleCi.monitoring.get_pipeline_workflows')
    def test_get_workflow_status_no_status_key(self, mock_get_workflows):
        """测试 workflows 中没有 status 键"""
        mock_get_workflows.return_value = [
            {'id': 'wf-1'},
            {'id': 'wf-2'}
        ]

        result = get_workflow_status('pipeline-123', silent=True)

        assert result == 'unknown'  # defaults to 'unknown'


class TestGetPipelineIdByNumber:
    """测试 get_pipeline_id_by_number 函数"""

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_id_found(self, mock_get_headers, mock_get):
        """测试找到匹配的 pipeline"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'pipeline-1', 'number': 100, 'state': 'completed'},
                {'id': 'pipeline-2', 'number': 101, 'state': 'running'},
                {'id': 'pipeline-3', 'number': 102, 'state': 'failed'}
            ]
        }
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_id_by_number('github/org/repo', 101, api_token='test-token')

        assert result == 'pipeline-2'

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_id_not_found(self, mock_get_headers, mock_get):
        """测试未找到匹配的 pipeline"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'pipeline-1', 'number': 100},
                {'id': 'pipeline-2', 'number': 101}
            ]
        }
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_id_by_number('github/org/repo', 999, api_token='test-token')

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_id_empty_items(self, mock_get_headers, mock_get):
        """测试空 items"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_id_by_number('github/org/repo', 100, api_token='test-token')

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_id_http_error(self, mock_get_headers, mock_get):
        """测试 HTTP 错误"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_get_headers.return_value = {}

        result = get_pipeline_id_by_number('github/org/repo', 100, api_token='test-token')

        assert result is None

    @patch('circleCi.monitoring.requests.get')
    @patch('circleCi.monitoring.get_headers')
    def test_get_pipeline_id_exception(self, mock_get_headers, mock_get):
        """测试请求异常"""
        mock_get.side_effect = Exception('Network error')

        result = get_pipeline_id_by_number('github/org/repo', 100, api_token='test-token')

        assert result is None