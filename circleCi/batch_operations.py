"""CircleCI 批量操作模块

提供批量触发 Pipeline 和批量审批的纯函数逻辑。
"""
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import logging

from modules.user_config_loader import build_circleci_headers, parse_api_error_message

logger = logging.getLogger(__name__)

# CircleCI API 基础 URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 超时常量
DEFAULT_TIMEOUT_SECONDS = 30
QUICK_TIMEOUT_SECONDS = 15

# 模块级 Session 用于连接池复用
_session = requests.Session()


def _handle_request_error(operation: str, e: Exception, context: Dict) -> Dict:
    """统一的请求错误处理"""
    if isinstance(e, requests.exceptions.Timeout):
        logger.error(f"Timeout {operation}")
        return {**context, 'success': False, 'error': '请求超时', 'status_code': None}
    elif isinstance(e, requests.exceptions.ConnectionError):
        logger.error(f"Connection error {operation}: {e}")
        return {**context, 'success': False, 'error': '网络连接错误', 'status_code': None}
    elif isinstance(e, requests.exceptions.RequestException):
        logger.error(f"Request error {operation}: {e}")
        return {**context, 'success': False, 'error': f'请求错误: {str(e)}', 'status_code': None}
    return {**context, 'success': False, 'error': str(e)}


def _trigger_single_service(
    service: str,
    branch: str,
    vcs_type: str,
    organization: str,
    api_token: str
) -> Dict:
    """
    触发单个服务的 Pipeline

    Args:
        service: 服务名称
        branch: 分支名称
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token

    Returns:
        结果字典，包含 success、service、pipeline_id 等字段
    """
    project_slug = f"{vcs_type}/{organization}/{service}"
    url = f"{CIRCLECI_API_BASE}/project/{project_slug}/pipeline"
    headers = build_circleci_headers(api_token)
    data = {"branch": branch}

    try:
        response = _session.post(url, json=data, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)

        if response.status_code == 201:
            result = response.json()
            return {
                'success': True,
                'service': service,
                'pipeline_id': result.get('id'),
                'pipeline_number': result.get('number'),
                'project_slug': project_slug
            }
        else:
            error_msg = parse_api_error_message(response)
            logger.warning(f"Failed to trigger {service}: {error_msg}")
            return {
                'success': False,
                'service': service,
                'error': error_msg,
                'status_code': response.status_code
            }

    except requests.exceptions.RequestException as e:
        return _handle_request_error(f"triggering {service}", e, {'service': service})


def _fetch_pending_for_pipeline(
    pipeline_id: str,
    api_token: str,
    target_env: str
) -> List[Dict]:
    """
    获取单个 Pipeline 的待审批 jobs

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
        target_env: 目标环境

    Returns:
        待审批 job 列表
    """
    pending_jobs = []
    headers = build_circleci_headers(api_token)
    target_env_lower = target_env.lower()

    try:
        pipeline_url = f"{CIRCLECI_API_BASE}/pipeline/{pipeline_id}"
        pipeline_resp = _session.get(pipeline_url, headers=headers, timeout=QUICK_TIMEOUT_SECONDS)

        if pipeline_resp.status_code != 200:
            return []

        pipeline_data = pipeline_resp.json()
        pipeline_number = pipeline_data.get('number')
        project_slug = pipeline_data.get('project_slug', '')
        service_name = project_slug.split('/')[-1] if project_slug else 'Unknown'

        workflows_url = f"{CIRCLECI_API_BASE}/pipeline/{pipeline_id}/workflow"
        workflows_resp = _session.get(workflows_url, headers=headers, timeout=QUICK_TIMEOUT_SECONDS)

        if workflows_resp.status_code != 200:
            return []

        workflows = workflows_resp.json().get('items', [])

        for workflow in workflows:
            workflow_id = workflow.get('id')
            workflow_name = workflow.get('name', 'Unknown')

            jobs_url = f"{CIRCLECI_API_BASE}/workflow/{workflow_id}/job"
            jobs_resp = _session.get(jobs_url, headers=headers, timeout=QUICK_TIMEOUT_SECONDS)

            if jobs_resp.status_code != 200:
                continue

            jobs = jobs_resp.json().get('items', [])

            for job in jobs:
                job_type = job.get('type')
                job_status = job.get('status')
                job_name = job.get('name', '').lower()

                # 组合条件扁平化嵌套判断
                is_approval_on_hold = (
                    job_type == 'approval' and
                    job_status == 'on_hold' and
                    target_env_lower in job_name
                )

                if is_approval_on_hold:
                    pending_jobs.append({
                        'pipeline_id': pipeline_id,
                        'pipeline_number': pipeline_number,
                        'workflow_id': workflow_id,
                        'workflow_name': workflow_name,
                        'job_id': job.get('id'),
                        'job_name': job.get('name'),
                        'approval_request_id': job.get('approval_request_id'),
                        'environment': target_env,
                        'service_name': service_name
                    })

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching pending approvals for {pipeline_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching pending for {pipeline_id}: {e}")
    except (ValueError, KeyError) as e:
        logger.error(f"JSON parse error for {pipeline_id}: {e}")

    return pending_jobs


def _approve_single_job(
    approval: Dict,
    api_token: str
) -> Dict:
    """
    审批单个 job

    Args:
        approval: 审批信息字典
        api_token: API Token

    Returns:
        结果字典
    """
    workflow_id = approval.get('workflow_id')
    approval_request_id = approval.get('approval_request_id')
    service_name = approval.get('service_name')
    pipeline_number = approval.get('pipeline_number')
    job_name = approval.get('job_name')

    url = f"{CIRCLECI_API_BASE}/workflow/{workflow_id}/approve/{approval_request_id}"
    headers = build_circleci_headers(api_token)
    context = {
        'service': service_name,
        'pipeline_number': pipeline_number,
        'job_name': job_name
    }

    try:
        response = _session.post(url, json={}, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)

        if response.status_code < 400:
            logger.info(f"Approved {service_name} #{pipeline_number} - {job_name}")
            return {**context, 'success': True}
        else:
            error_msg = parse_api_error_message(response)
            logger.warning(f"Failed to approve {service_name}: {error_msg}")
            return {
                **context,
                'success': False,
                'error': error_msg,
                'status_code': response.status_code
            }

    except requests.exceptions.RequestException as e:
        return _handle_request_error(f"approving {service_name}", e, context)


def batch_trigger_pipelines(
    services: List[str],
    branch: str,
    vcs_type: str,
    organization: str,
    api_token: str,
    max_workers: int = 5
) -> Tuple[List[Dict], List[Dict]]:
    """
    批量触发多个服务的 Pipeline

    Args:
        services: 服务名称列表
        branch: 分支名称
        vcs_type: VCS 类型 (github/bitbucket)
        organization: 组织名称
        api_token: CircleCI API Token
        max_workers: 并发数（默认 5，避免 API 限流）

    Returns:
        (成功列表, 失败列表)
        成功项: {'service': str, 'pipeline_id': str, 'pipeline_number': int, 'project_slug': str}
        失败项: {'service': str, 'error': str, 'status_code': Optional[int]}
    """
    success_list = []
    failed_list = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _trigger_single_service, svc, branch, vcs_type, organization, api_token
            ): svc
            for svc in services
        }

        for future in as_completed(futures):
            result = future.result()
            if result.get('success'):
                success_list.append(result)
            else:
                failed_list.append(result)

    return success_list, failed_list


def get_pending_approvals_for_batch(
    pipeline_ids: List[str],
    api_token: str,
    target_env: str = 'preprod',
    max_workers: int = 10
) -> List[Dict]:
    """
    批量获取待审批的 Job 信息

    Args:
        pipeline_ids: Pipeline ID 列表
        api_token: CircleCI API Token
        target_env: 目标环境（默认 preprod）
        max_workers: 并发数

    Returns:
        待审批列表，每项包含:
        {
            'pipeline_id': str,
            'pipeline_number': int,
            'workflow_id': str,
            'workflow_name': str,
            'job_id': str,
            'job_name': str,
            'approval_request_id': str,
            'environment': str,
            'service_name': str
        }
    """
    all_pending = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_fetch_pending_for_pipeline, pid, api_token, target_env)
            for pid in pipeline_ids
        ]

        for future in as_completed(futures):
            try:
                pending = future.result()
                all_pending.extend(pending)
            except Exception as e:
                logger.error(f"Error in future: {e}")

    return all_pending


def batch_approve_jobs(
    pending_approvals: List[Dict],
    api_token: str,
    max_workers: int = 5
) -> Tuple[List[Dict], List[Dict]]:
    """
    批量审批多个 Job

    Args:
        pending_approvals: 待审批列表（来自 get_pending_approvals_for_batch）
        api_token: CircleCI API Token
        max_workers: 并发数（默认 5，避免 API 限流）

    Returns:
        (成功列表, 失败列表)
        成功项: {'service': str, 'pipeline_number': int, 'job_name': str}
        失败项: {'service': str, 'pipeline_number': int, 'job_name': str, 'error': str}
    """
    success_list = []
    failed_list = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_approve_single_job, approval, api_token)
            for approval in pending_approvals
        ]

        for future in as_completed(futures):
            result = future.result()
            if result.get('success'):
                success_list.append(result)
            else:
                failed_list.append(result)

    return success_list, failed_list


def check_pipeline_approval_status(
    pipeline_id: str,
    api_token: str,
    target_env: str = 'preprod'
) -> Dict:
    """
    检查单个 Pipeline 的审批状态

    Args:
        pipeline_id: Pipeline ID
        api_token: CircleCI API Token
        target_env: 目标环境

    Returns:
        {
            'has_approval': bool,
            'status': str,  # 'pending', 'approved', 'not_found', 'error'
            'job_name': Optional[str],
            'approved_by': Optional[str],
            'approved_at': Optional[str]
        }
    """
    headers = build_circleci_headers(api_token)

    try:
        workflows_url = f"{CIRCLECI_API_BASE}/pipeline/{pipeline_id}/workflow"
        workflows_resp = _session.get(workflows_url, headers=headers, timeout=QUICK_TIMEOUT_SECONDS)

        if workflows_resp.status_code != 200:
            return {'has_approval': False, 'status': 'error', 'error': 'Failed to get workflows'}

        workflows = workflows_resp.json().get('items', [])

        for workflow in workflows:
            workflow_id = workflow.get('id')
            jobs_url = f"{CIRCLECI_API_BASE}/workflow/{workflow_id}/job"
            jobs_resp = _session.get(jobs_url, headers=headers, timeout=QUICK_TIMEOUT_SECONDS)

            if jobs_resp.status_code != 200:
                continue

            jobs = jobs_resp.json().get('items', [])

            for job in jobs:
                job_type = job.get('type')
                job_name = job.get('name', '').lower()
                job_status = job.get('status')

                is_target_approval = (
                    job_type == 'approval' and
                    target_env.lower() in job_name
                )

                if not is_target_approval:
                    continue

                if job_status == 'on_hold':
                    return {
                        'has_approval': True,
                        'status': 'pending',
                        'job_name': job.get('name')
                    }
                elif job_status == 'success':
                    return {
                        'has_approval': True,
                        'status': 'approved',
                        'job_name': job.get('name'),
                        'approved_by': job.get('approved_by'),
                        'approved_at': job.get('stopped_at')
                    }

        return {'has_approval': False, 'status': 'not_found'}

    except requests.exceptions.Timeout:
        return {'has_approval': False, 'status': 'error', 'error': '请求超时'}
    except requests.exceptions.RequestException as e:
        return {'has_approval': False, 'status': 'error', 'error': str(e)}
