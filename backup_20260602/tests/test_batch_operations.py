"""CircleCI 批量操作模块单元测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from circleCi.batch_operations import (
    batch_trigger_pipelines,
    get_pending_approvals_for_batch,
    batch_approve_jobs,
    check_pipeline_approval_status,
    _trigger_single_service,
    _fetch_pending_for_pipeline,
    _approve_single_job,
    _parse_error_message,
    DEFAULT_TIMEOUT_SECONDS,
    QUICK_TIMEOUT_SECONDS
)
from modules.user_config_loader import build_circleci_headers


class TestBuildHeaders:
    """测试 build_circleci_headers 函数（统一函数）"""

    def test_build_headers_returns_correct_format(self):
        """测试返回正确的 header 格式"""
        token = "test-token-12345"
        headers = build_circleci_headers(token)

        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert headers["Circle-Token"] == token


class TestParseErrorMessage:
    """测试 _parse_error_message 函数"""

    def test_parse_json_error_message(self):
        """测试解析 JSON 格式的错误消息"""
        response = Mock()
        response.json.return_value = {"message": "Pipeline not found"}
        response.text = "Pipeline not found"
        response.status_code = 404

        result = _parse_error_message(response)
        assert result == "Pipeline not found"

    def test_parse_text_error_message(self):
        """测试解析纯文本错误消息"""
        response = Mock()
        response.json.side_effect = ValueError("No JSON")
        response.text = "Internal server error occurred"
        response.status_code = 500

        result = _parse_error_message(response)
        assert "Internal server error" in result

    def test_parse_empty_error_message(self):
        """测试解析空错误消息"""
        response = Mock()
        response.json.side_effect = ValueError("No JSON")
        response.text = ""
        response.status_code = 400

        result = _parse_error_message(response)
        assert result == "HTTP 400"


class TestTriggerSingleService:
    """测试 _trigger_single_service 函数"""

    @patch('circleCi.batch_operations.requests.post')
    def test_trigger_success(self, mock_post):
        """测试成功触发"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'id': 'pipeline-123',
            'number': 100
        }
        mock_post.return_value = mock_response

        result = _trigger_single_service(
            service='test-service',
            branch='master',
            vcs_type='github',
            organization='test-org',
            api_token='test-token'
        )

        assert result['success'] is True
        assert result['service'] == 'test-service'
        assert result['pipeline_id'] == 'pipeline-123'
        assert result['pipeline_number'] == 100

    @patch('circleCi.batch_operations.requests.post')
    def test_trigger_not_found(self, mock_post):
        """测试项目未找到"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Project not found"}
        mock_response.text = "Project not found"
        mock_post.return_value = mock_response

        result = _trigger_single_service(
            service='unknown-service',
            branch='master',
            vcs_type='github',
            organization='test-org',
            api_token='test-token'
        )

        assert result['success'] is False
        assert result['service'] == 'unknown-service'
        assert result['status_code'] == 404

    @patch('circleCi.batch_operations.requests.post')
    def test_trigger_timeout(self, mock_post):
        """测试请求超时"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        result = _trigger_single_service(
            service='test-service',
            branch='master',
            vcs_type='github',
            organization='test-org',
            api_token='test-token'
        )

        assert result['success'] is False
        assert result['error'] == '请求超时'
        assert result['status_code'] is None


class TestBatchTriggerPipelines:
    """测试 batch_trigger_pipelines 函数"""

    @patch('circleCi.batch_operations._trigger_single_service')
    def test_batch_trigger_all_success(self, mock_trigger):
        """测试全部成功触发"""
        mock_trigger.side_effect = [
            {'success': True, 'service': 'service-a', 'pipeline_id': 'id-1', 'pipeline_number': 1},
            {'success': True, 'service': 'service-b', 'pipeline_id': 'id-2', 'pipeline_number': 2},
        ]

        success, failed = batch_trigger_pipelines(
            services=['service-a', 'service-b'],
            branch='master',
            vcs_type='github',
            organization='test-org',
            api_token='test-token'
        )

        assert len(success) == 2
        assert len(failed) == 0

    @patch('circleCi.batch_operations._trigger_single_service')
    def test_batch_trigger_partial_failure(self, mock_trigger):
        """测试部分失败"""
        mock_trigger.side_effect = [
            {'success': True, 'service': 'service-a', 'pipeline_id': 'id-1', 'pipeline_number': 1},
            {'success': False, 'service': 'service-b', 'error': 'Not found', 'status_code': 404},
        ]

        success, failed = batch_trigger_pipelines(
            services=['service-a', 'service-b'],
            branch='master',
            vcs_type='github',
            organization='test-org',
            api_token='test-token'
        )

        assert len(success) == 1
        assert len(failed) == 1
        assert failed[0]['service'] == 'service-b'


class TestFetchPendingForPipeline:
    """测试 _fetch_pending_for_pipeline 函数"""

    @patch('circleCi.batch_operations.requests.get')
    def test_fetch_pending_success(self, mock_get):
        """测试成功获取待审批"""
        # Mock pipeline info
        pipeline_response = Mock()
        pipeline_response.status_code = 200
        pipeline_response.json.return_value = {
            'number': 100,
            'project_slug': 'github/org/service-a'
        }

        # Mock workflows
        workflows_response = Mock()
        workflows_response.status_code = 200
        workflows_response.json.return_value = {
            'items': [{'id': 'wf-1', 'name': 'build'}]
        }

        # Mock jobs
        jobs_response = Mock()
        jobs_response.status_code = 200
        jobs_response.json.return_value = {
            'items': [
                {
                    'id': 'job-1',
                    'name': 'preprod-approval',
                    'type': 'approval',
                    'status': 'on_hold',
                    'approval_request_id': 'req-1'
                }
            ]
        }

        mock_get.side_effect = [pipeline_response, workflows_response, jobs_response]

        result = _fetch_pending_for_pipeline(
            pipeline_id='pipeline-123',
            api_token='test-token',
            target_env='preprod'
        )

        assert len(result) == 1
        assert result[0]['pipeline_number'] == 100
        assert result[0]['service_name'] == 'service-a'
        assert result[0]['job_name'] == 'preprod-approval'

    @patch('circleCi.batch_operations.requests.get')
    def test_fetch_pending_no_approval_jobs(self, mock_get):
        """测试没有待审批 jobs"""
        pipeline_response = Mock()
        pipeline_response.status_code = 200
        pipeline_response.json.return_value = {
            'number': 100,
            'project_slug': 'github/org/service-a'
        }

        workflows_response = Mock()
        workflows_response.status_code = 200
        workflows_response.json.return_value = {
            'items': [{'id': 'wf-1', 'name': 'build'}]
        }

        jobs_response = Mock()
        jobs_response.status_code = 200
        jobs_response.json.return_value = {
            'items': [
                {
                    'id': 'job-1',
                    'name': 'preprod-approval',
                    'type': 'build',  # 非 approval 类型
                    'status': 'running'
                }
            ]
        }

        mock_get.side_effect = [pipeline_response, workflows_response, jobs_response]

        result = _fetch_pending_for_pipeline(
            pipeline_id='pipeline-123',
            api_token='test-token',
            target_env='preprod'
        )

        assert len(result) == 0


class TestApproveSingleJob:
    """测试 _approve_single_job 函数"""

    @patch('circleCi.batch_operations.requests.post')
    def test_approve_success(self, mock_post):
        """测试成功审批"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        approval = {
            'workflow_id': 'wf-1',
            'approval_request_id': 'req-1',
            'service_name': 'service-a',
            'pipeline_number': 100,
            'job_name': 'preprod-approval'
        }

        result = _approve_single_job(approval, 'test-token')

        assert result['success'] is True
        assert result['service'] == 'service-a'

    @patch('circleCi.batch_operations.requests.post')
    def test_approve_failure(self, mock_post):
        """测试审批失败"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"message": "Permission denied"}
        mock_response.text = "Permission denied"
        mock_post.return_value = mock_response

        approval = {
            'workflow_id': 'wf-1',
            'approval_request_id': 'req-1',
            'service_name': 'service-a',
            'pipeline_number': 100,
            'job_name': 'preprod-approval'
        }

        result = _approve_single_job(approval, 'test-token')

        assert result['success'] is False
        assert result['status_code'] == 403


class TestBatchApproveJobs:
    """测试 batch_approve_jobs 函数"""

    @patch('circleCi.batch_operations._approve_single_job')
    def test_batch_approve_all_success(self, mock_approve):
        """测试全部成功审批"""
        mock_approve.side_effect = [
            {'success': True, 'service': 'service-a', 'pipeline_number': 1, 'job_name': 'job-1'},
            {'success': True, 'service': 'service-b', 'pipeline_number': 2, 'job_name': 'job-2'},
        ]

        pending = [
            {'workflow_id': 'wf-1', 'approval_request_id': 'req-1'},
            {'workflow_id': 'wf-2', 'approval_request_id': 'req-2'},
        ]

        success, failed = batch_approve_jobs(pending, 'test-token')

        assert len(success) == 2
        assert len(failed) == 0


class TestCheckPipelineApprovalStatus:
    """测试 check_pipeline_approval_status 函数"""

    @patch('circleCi.batch_operations.requests.get')
    def test_check_pending_status(self, mock_get):
        """测试检查待审批状态"""
        workflows_response = Mock()
        workflows_response.status_code = 200
        workflows_response.json.return_value = {
            'items': [{'id': 'wf-1', 'name': 'build'}]
        }

        jobs_response = Mock()
        jobs_response.status_code = 200
        jobs_response.json.return_value = {
            'items': [
                {
                    'id': 'job-1',
                    'name': 'preprod-approval',
                    'type': 'approval',
                    'status': 'on_hold'
                }
            ]
        }

        mock_get.side_effect = [workflows_response, jobs_response]

        result = check_pipeline_approval_status('pipeline-123', 'test-token')

        assert result['has_approval'] is True
        assert result['status'] == 'pending'

    @patch('circleCi.batch_operations.requests.get')
    def test_check_approved_status(self, mock_get):
        """测试检查已审批状态"""
        workflows_response = Mock()
        workflows_response.status_code = 200
        workflows_response.json.return_value = {
            'items': [{'id': 'wf-1', 'name': 'build'}]
        }

        jobs_response = Mock()
        jobs_response.status_code = 200
        jobs_response.json.return_value = {
            'items': [
                {
                    'id': 'job-1',
                    'name': 'preprod-approval',
                    'type': 'approval',
                    'status': 'success',
                    'approved_by': 'user-123',
                    'stopped_at': '2024-01-01T00:00:00Z'
                }
            ]
        }

        mock_get.side_effect = [workflows_response, jobs_response]

        result = check_pipeline_approval_status('pipeline-123', 'test-token')

        assert result['has_approval'] is True
        assert result['status'] == 'approved'
        assert result['approved_by'] == 'user-123'


class TestTimeoutConstants:
    """测试超时常量"""

    def test_timeout_constants_exist(self):
        """测试超时常量定义"""
        assert DEFAULT_TIMEOUT_SECONDS == 30
        assert QUICK_TIMEOUT_SECONDS == 10
