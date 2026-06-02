"""
tests/test_commit_search.py
覆盖 Tab4 Commit ID 搜索功能的核心逻辑

由于 Streamlit 页面模块在导入时执行 UI 代码，
这里将核心函数复制并进行独立测试。
"""

import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed


# 环境优先级常量（与页面模块一致）
ENVIRONMENT_PRIORITIES = ['preprod', 'staging', 'dev', 'uat', 'prod', 'production']


# === 核心函数复制（用于测试） ===

def search_pipelines_by_revision(revision_prefix: str, services: list,
                                  max_pipelines_per_service: int = 20,
                                  call_api_func=None,
                                  get_approvals_func=None):
    """
    跨多个服务并发搜索匹配 revision 前缀的 Pipeline（测试版本）

    Args:
        revision_prefix: commit ID 前缀
        services: 服务列表
        max_pipelines_per_service: 每服务最大 pipeline 数
        call_api_func: Mock 的 API 调用函数
        get_approvals_func: Mock 的获取 approvals 函数

    Returns:
        tuple: (results, errors)
    """
    if not revision_prefix or len(revision_prefix.strip()) < 4:
        return [], {'error': 'Revision prefix too short (minimum 4 characters)'}

    revision_prefix = revision_prefix.strip().lower()
    raw_matches = []
    errors = {}

    def search_service(service_name: str):
        """搜索单个服务"""
        try:
            # 使用传入的 mock 函数
            if call_api_func:
                response, error = call_api_func(service_name)
            else:
                return [], {'error': 'No API function provided'}

            if error:
                return [], error

            if not response or response.get('status_code') != 200:
                return [], {'error': 'Failed to fetch pipelines'}

            items = response.get('items', [])[:max_pipelines_per_service]
            matched = []

            for p in items:
                revision = p.get('vcs', {}).get('revision', '')
                if revision and revision.lower().startswith(revision_prefix):
                    matched.append({
                        'id': p.get('id'),
                        'number': p.get('number'),
                        'state': p.get('state'),
                        'created_at': p.get('created_at'),
                        'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
                        'branch': p.get('vcs', {}).get('branch'),
                        'revision': revision,
                        'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
                        'service_name': service_name
                    })

            return matched, None
        except Exception as e:
            return [], {'error': str(e)}

    # 第一阶段：并发搜索所有服务
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(search_service, svc): svc for svc in services}

        for future in as_completed(futures):
            svc = futures[future]
            try:
                matched, error = future.result()
                if matched:
                    raw_matches.extend(matched)
                if error:
                    errors[svc] = error
            except Exception as e:
                errors[svc] = {'error': str(e)}

    if not raw_matches:
        return [], errors

    # 按创建时间排序（最新优先）
    raw_matches.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    raw_matches = raw_matches[:100]

    # 第二阶段：获取 approval 信息
    results = []
    if get_approvals_func:
        for p in raw_matches:
            approvals = get_approvals_func(p.get('id'), p.get('service_name'))
            results.append({**p, 'all_approvals': approvals})
    else:
        results = raw_matches

    return results[:100], errors


def get_all_approvals_info(workflows, jobs_map, get_user_func=None):
    """
    获取所有环境的 approval 信息（测试版本）

    Args:
        workflows: workflow 列表
        jobs_map: {workflow_id: jobs_list} 字典
        get_user_func: Mock 的获取用户名函数

    Returns:
        dict: {environment: approval_info}
    """
    if not workflows:
        return {}

    approvals_by_env = {}

    for workflow in workflows:
        workflow_id = workflow.get('id')
        all_jobs = jobs_map.get(workflow_id, [])

        for job in all_jobs:
            job_name = job.get('name', '')
            job_name_lower = job_name.lower()
            job_type = job.get('type', '')

            if job_type != 'approval':
                continue

            # 检测环境
            detected_env = None
            for env in ENVIRONMENT_PRIORITIES:
                if env in job_name_lower:
                    detected_env = env
                    break

            if not detected_env:
                continue

            status = job.get('status')
            approval_info = {
                'approved_by': None,
                'approved_at': None,
                'job_name': job_name,
                'status': status,
                'environment': detected_env
            }

            if status == 'success':
                approved_by_data = job.get('approved_by')
                approver_name = None

                if isinstance(approved_by_data, str) and approved_by_data:
                    if approved_by_data.count('-') >= 4:
                        # UUID format
                        if get_user_func:
                            approver_name = get_user_func(approved_by_data)
                    else:
                        approver_name = approved_by_data
                elif isinstance(approved_by_data, dict):
                    approver_name = approved_by_data.get('login')

                if approver_name:
                    approval_info['approved_by'] = approver_name
                else:
                    approval_info['approved_by'] = '已审批'

                approval_info['approved_at'] = job.get('stopped_at')
                approval_info['status'] = 'approved'

            elif status == 'on_hold':
                approval_info['approved_by'] = 'Pending'
                approval_info['approved_at'] = None
                approval_info['status'] = 'pending'

            if detected_env not in approvals_by_env:
                approvals_by_env[detected_env] = approval_info

    return approvals_by_env


# === 测试类 ===

class TestSearchPipelinesByRevision:
    """测试 search_pipelines_by_revision 函数"""

    def test_empty_revision_prefix(self):
        """空 revision 前缀应返回错误"""
        results, errors = search_pipelines_by_revision("", ["service1"])
        assert results == []
        assert "error" in errors
        assert "too short" in errors["error"].lower()

    def test_short_revision_prefix(self):
        """少于 4 位的 revision 前缀应返回错误"""
        results, errors = search_pipelines_by_revision("abc", ["service1"])
        assert results == []
        assert "error" in errors
        assert "too short" in errors["error"].lower()

    def test_minimum_valid_revision_prefix(self):
        """4 位 revision 前缀是有效的"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-123",
                    "number": 100,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {
                        "revision": "abcd1234567890",
                        "branch": "main",
                        "commit": {"subject": "Test commit"}
                    },
                    "trigger": {"actor": {"login": "john"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1"], call_api_func=mock_api)

        assert len(results) >= 1
        assert results[0]['revision'] == "abcd1234567890"
        assert results[0]['service_name'] == "service1"

    def test_no_matching_revision(self):
        """没有匹配的 revision 应返回空结果"""
        mock_response = {
            'status_code': 200,
            'items': [
                {"id": "pipe-123", "vcs": {"revision": "xyz1234567890"}}
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1"], call_api_func=mock_api)

        assert results == []

    def test_partial_revision_match(self):
        """部分 revision 匹配应正确工作"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-1",
                    "number": 1,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {"revision": "abcd1234", "branch": "main"},
                    "trigger": {"actor": {"login": "user1"}}
                },
                {
                    "id": "pipe-2",
                    "number": 2,
                    "state": "success",
                    "created_at": "2024-01-02T00:00:00Z",
                    "vcs": {"revision": "abcd5678", "branch": "dev"},
                    "trigger": {"actor": {"login": "user2"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1"], call_api_func=mock_api)

        assert len(results) == 2

    def test_case_insensitive_match(self):
        """revision 匹配应不区分大小写"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-1",
                    "number": 1,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {"revision": "ABCD1234", "branch": "main"},
                    "trigger": {"actor": {"login": "user"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1"], call_api_func=mock_api)

        assert len(results) == 1

    def test_api_error_handling(self):
        """API 错误应正确收集"""
        def mock_api(service_name):
            return (None, {"error": "API failed"})

        results, errors = search_pipelines_by_revision("abcd1234", ["service1"], call_api_func=mock_api)

        assert results == []
        assert "service1" in errors

    def test_multiple_services_concurrent_search(self):
        """多个服务应并发搜索"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-1",
                    "number": 1,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {"revision": "abcd1234", "branch": "main"},
                    "trigger": {"actor": {"login": "user"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        services = ["service1", "service2", "service3"]
        results, errors = search_pipelines_by_revision("abcd", services, call_api_func=mock_api)

        assert len(results) == 3
        service_names = [r['service_name'] for r in results]
        assert set(service_names) == set(services)

    def test_results_sorted_by_created_at_desc(self):
        """结果应按创建时间倒序排序"""
        def mock_api(service_name):
            if service_name == "service1":
                return ({
                    'status_code': 200,
                    'items': [{
                        "id": "pipe-old",
                        "number": 1,
                        "state": "success",
                        "created_at": "2024-01-01T00:00:00Z",
                        "vcs": {"revision": "abcd1111", "branch": "main"},
                        "trigger": {"actor": {"login": "user"}}
                    }]
                }, None)
            else:
                return ({
                    'status_code': 200,
                    'items': [{
                        "id": "pipe-new",
                        "number": 2,
                        "state": "success",
                        "created_at": "2024-01-02T00:00:00Z",
                        "vcs": {"revision": "abcd2222", "branch": "main"},
                        "trigger": {"actor": {"login": "user"}}
                    }]
                }, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1", "service2"], call_api_func=mock_api)

        assert results[0]['created_at'] == "2024-01-02T00:00:00Z"
        assert results[1]['created_at'] == "2024-01-01T00:00:00Z"

    def test_max_results_limit(self):
        """结果应限制在 100 条"""
        items = []
        for i in range(150):
            items.append({
                "id": f"pipe-{i}",
                "number": i,
                "state": "success",
                "created_at": f"2024-01-{i%30+1:02d}T00:00:00Z",
                "vcs": {"revision": "abcd1234", "branch": "main"},
                "trigger": {"actor": {"login": "user"}}
            })

        mock_response = {'status_code': 200, 'items': items}

        def mock_api(service_name):
            return (mock_response, None)

        results, errors = search_pipelines_by_revision("abcd", ["service1"], call_api_func=mock_api)

        assert len(results) <= 100

    def test_with_approvals_info(self):
        """应正确获取 approval 信息"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-123",
                    "number": 100,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {"revision": "abcd1234", "branch": "main"},
                    "trigger": {"actor": {"login": "john"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        def mock_approvals(pipeline_id, service_name):
            return {'preprod': {'status': 'approved', 'approved_by': 'john'}}

        results, errors = search_pipelines_by_revision(
            "abcd", ["service1"],
            call_api_func=mock_api,
            get_approvals_func=mock_approvals
        )

        assert len(results) == 1
        assert 'all_approvals' in results[0]
        assert 'preprod' in results[0]['all_approvals']


class TestGetAllApprovalsInfo:
    """测试 get_all_approvals_info 函数"""

    def test_no_workflows_returns_empty(self):
        """没有 workflows 应返回空字典"""
        result = get_all_approvals_info(None, {})
        assert result == {}

        result = get_all_approvals_info([], {})
        assert result == {}

    def test_single_preprod_approval_approved(self):
        """单个 preprod approval 已审批"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "preprod-deploy",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "john.doe",
                    "stopped_at": "2024-01-01T10:00:00Z"
                }
            ]
        }

        result = get_all_approvals_info(workflows, jobs_map)

        assert "preprod" in result
        assert result["preprod"]["status"] == "approved"
        assert result["preprod"]["approved_by"] == "john.doe"

    def test_single_dev_approval_pending(self):
        """单个 dev approval 待审批"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "dev-approval",
                    "type": "approval",
                    "status": "on_hold"
                }
            ]
        }

        result = get_all_approvals_info(workflows, jobs_map)

        assert "dev" in result
        assert result["dev"]["status"] == "pending"
        assert result["dev"]["approved_by"] == "Pending"

    def test_multiple_environments(self):
        """多个环境 approval"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "dev-deploy",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "user1",
                    "stopped_at": "2024-01-01T09:00:00Z"
                },
                {
                    "name": "staging-deploy",
                    "type": "approval",
                    "status": "on_hold"
                },
                {
                    "name": "preprod-deploy",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "user2",
                    "stopped_at": "2024-01-01T10:00:00Z"
                }
            ]
        }

        result = get_all_approvals_info(workflows, jobs_map)

        assert "dev" in result
        assert "staging" in result
        assert "preprod" in result
        assert result["dev"]["status"] == "approved"
        assert result["staging"]["status"] == "pending"
        assert result["preprod"]["status"] == "approved"

    def test_uuid_to_username_conversion(self):
        """UUID 应转换为用户名"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "preprod-deploy",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "1234-5678-90ab-cdef-1234",
                    "stopped_at": "2024-01-01T10:00:00Z"
                }
            ]
        }

        def mock_get_user(uuid):
            return "converted_user"

        result = get_all_approvals_info(workflows, jobs_map, get_user_func=mock_get_user)

        assert result["preprod"]["approved_by"] == "converted_user"

    def test_non_approval_jobs_ignored(self):
        """非 approval 类型的 job 应被忽略"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {"name": "build-job", "type": "build", "status": "success"},
                {"name": "test-job", "type": "test", "status": "success"},
                {
                    "name": "preprod-approval",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "user"
                }
            ]
        }

        result = get_all_approvals_info(workflows, jobs_map)

        assert len(result) == 1
        assert "preprod" in result

    def test_unknown_environment_ignored(self):
        """未知环境的 approval job 应被忽略"""
        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "custom-approval",
                    "type": "approval",
                    "status": "success"
                },
                {
                    "name": "preprod-approval",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "user"
                }
            ]
        }

        result = get_all_approvals_info(workflows, jobs_map)

        assert "preprod" in result
        assert "custom" not in result


class TestEnvironmentPriorities:
    """测试环境优先级常量"""

    def test_environment_priorities_defined(self):
        """环境优先级列表应定义"""
        assert ENVIRONMENT_PRIORITIES is not None
        assert 'preprod' in ENVIRONMENT_PRIORITIES
        assert 'staging' in ENVIRONMENT_PRIORITIES
        assert 'dev' in ENVIRONMENT_PRIORITIES
        assert 'prod' in ENVIRONMENT_PRIORITIES

    def test_preprod_has_high_priority(self):
        """preprod 应有较高优先级"""
        assert ENVIRONMENT_PRIORITIES.index('preprod') < ENVIRONMENT_PRIORITIES.index('dev')

    def test_staging_between_preprod_and_dev(self):
        """staging 应在 preprod 和 dev 之间"""
        preprod_idx = ENVIRONMENT_PRIORITIES.index('preprod')
        staging_idx = ENVIRONMENT_PRIORITIES.index('staging')
        dev_idx = ENVIRONMENT_PRIORITIES.index('dev')
        assert preprod_idx < staging_idx < dev_idx


class TestIntegration:
    """集成测试"""

    def test_full_search_with_approvals_flow(self):
        """完整搜索 + approvals 流程"""
        mock_response = {
            'status_code': 200,
            'items': [
                {
                    "id": "pipe-123",
                    "number": 100,
                    "state": "success",
                    "created_at": "2024-01-01T00:00:00Z",
                    "vcs": {
                        "revision": "abcd1234567890",
                        "branch": "main",
                        "commit": {"subject": "Test commit"}
                    },
                    "trigger": {"actor": {"login": "john"}}
                }
            ]
        }

        def mock_api(service_name):
            return (mock_response, None)

        workflows = [{"id": "wf-1", "name": "build"}]
        jobs_map = {
            "wf-1": [
                {
                    "name": "preprod-deploy",
                    "type": "approval",
                    "status": "success",
                    "approved_by": "john",
                    "stopped_at": "2024-01-01T10:00:00Z"
                }
            ]
        }

        def mock_approvals(pipeline_id, service_name):
            return get_all_approvals_info(workflows, jobs_map)

        results, errors = search_pipelines_by_revision(
            "abcd", ["service1"],
            call_api_func=mock_api,
            get_approvals_func=mock_approvals
        )

        assert len(results) == 1
        assert results[0]['revision'] == "abcd1234567890"
        assert results[0]['service_name'] == "service1"
        assert 'all_approvals' in results[0]
        assert 'preprod' in results[0]['all_approvals']
        assert results[0]['all_approvals']['preprod']['approved_by'] == "john"