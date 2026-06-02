"""
CircleCI Pipeline 数据处理

提供 Pipeline 数据获取、审批信息查询等纯数据逻辑。
"""
import logging
from typing import Optional


logger = logging.getLogger(__name__)

# 从 pipeline_config 导入环境优先级定义
from circleCi.pipeline_config import ENVIRONMENT_PRIORITIES


def get_user_info_by_id(user_id: str, api_token: Optional[str] = None) -> Optional[str]:
    """通过用户 UUID 获取用户信息（用户名）
    使用缓存避免重复 API 调用

    Args:
        user_id: 用户的 UUID
        api_token: API Token

    Returns:
        用户名（login）或 None
    """
    import streamlit as st

    # 确保缓存已初始化（防止并发调用时出错）
    if 'user_cache' not in st.session_state:
        st.session_state.user_cache = {}

    # 检查缓存
    if user_id in st.session_state.user_cache:
        return st.session_state.user_cache[user_id]

    try:
        # Late import to avoid circular dependency
        from circleCi.pipeline_api import call_circleci_api
        endpoint = f'user/{user_id}'
        response, error = call_circleci_api(endpoint, api_token=api_token)

        if error:
            st.session_state.user_cache[user_id] = None
            return None

        if response and response.status_code == 200:
            user_data = response.json()
            # 尝试多个可能的字段
            login = user_data.get('login') or user_data.get('username') or user_data.get('name')

            # 缓存结果
            if login:
                st.session_state.user_cache[user_id] = login

            return login

        # 缓存失败结果，避免重复请求
        st.session_state.user_cache[user_id] = None
        return None
    except Exception as e:
        logger.error(f"Error fetching user info for {user_id}: {e}")
        # 缓存失败结果
        st.session_state.user_cache[user_id] = None
        return None


def approve_job(
    workflow_id: str,
    approval_request_id: str,
    api_token: Optional[str] = None
) -> dict:
    """审批一个 Job"""
    # Late import to avoid circular dependency
    from circleCi.pipeline_api import call_circleci_api
    endpoint = f"workflow/{workflow_id}/approve/{approval_request_id}"
    response, error = call_circleci_api(
        endpoint,
        method='POST',
        data={},
        api_token=api_token
    )

    if error:
        return {
            'success': False,
            'error': error.get('error', 'Unknown error')
        }

    if response and response.status_code < 400:
        return {'success': True, 'message': '审批成功'}
    else:
        return {
            'success': False,
            'error': response.json().get('message', '审批失败') if response else '网络错误'
        }


def get_all_approvals_info_with_workflows(
    workflows: list,
    wf_jobs_map: dict
) -> dict:
    """获取 Pipeline 中所有环境的 approval 信息（给定 workflows 和 jobs）

    用于 search_pipelines_by_revision 的第二阶段

    Args:
        workflows: workflow 列表
        wf_jobs_map: workflow_id -> jobs 列表的映射

    Returns:
        dict: 按环境名组织的 approval 信息字典
    """
    approvals_by_env = {}

    for workflow in workflows:
        workflow_id = workflow.get('id')
        workflow_name = workflow.get('name', '').lower()
        all_jobs = wf_jobs_map.get(workflow_id, [])

        # 查找 approval 类型的 job
        for job in all_jobs:
            job_name = job.get('name', '')
            job_name_lower = job_name.lower()
            job_type = job.get('type', '')

            # 只处理 approval 类型的 job
            if job_type != 'approval':
                continue

            # 检测 job 属于哪个环境
            detected_env = None
            for env in ENVIRONMENT_PRIORITIES:
                if env in job_name_lower:
                    detected_env = env
                    break

            # 如果没有匹配到已知环境，跳过
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

            # 根据状态填充信息
            if status == 'success':
                approved_by_data = job.get('approved_by')
                approver_name = None

                if isinstance(approved_by_data, str) and approved_by_data:
                    if approved_by_data.count('-') >= 4:
                        # UUID 格式，查询用户名
                        logger.debug(f"Fetching user info for UUID: {approved_by_data}")
                        approver_name = get_user_info_by_id(approved_by_data)
                        if approver_name:
                            logger.debug(f"Found username: {approver_name}")
                    else:
                        approver_name = approved_by_data
                elif isinstance(approved_by_data, dict):
                    approver_name = approved_by_data.get('login') or approved_by_data.get('username')

                if approver_name:
                    approval_info['approved_by'] = approver_name
                else:
                    approval_info['approved_by'] = '已审批'
                    approval_info['note'] = '无法获取审批者信息'

                approval_info['approved_at'] = job.get('stopped_at', job.get('approved_at'))
                approval_info['status'] = 'approved'

            elif status == 'on_hold':
                approval_info['approved_by'] = 'Pending'
                approval_info['approved_at'] = None
                approval_info['status'] = 'pending'
            else:
                approval_info['approved_by'] = 'N/A'
                approval_info['approved_at'] = job.get('stopped_at')

            # 添加到对应环境（如果已有同环境的，保留状态更重要的）
            if detected_env not in approvals_by_env:
                approvals_by_env[detected_env] = approval_info
            else:
                existing = approvals_by_env[detected_env]
                # 优先保留 pending（需要关注）和 approved（已完成）的状态
                if approval_info['status'] == 'pending' and existing['status'] != 'pending':
                    approvals_by_env[detected_env] = approval_info

    return approvals_by_env


def get_all_approvals_info(
    pipeline_id: str,
    project_name: Optional[str] = None,
    api_token: Optional[str] = None
) -> dict:
    """获取 Pipeline 中所有环境的 approval 信息
    支持多个环境：dev, staging, preprod, uat, prod 等

    Args:
        pipeline_id: Pipeline ID
        project_name: 项目名称（用于匹配对应的 approval job）
        api_token: API Token

    Returns:
        dict: 按环境名组织的 approval 信息字典
    """
    try:
        # 获取 workflows
        from circleCi.monitoring import get_pipeline_workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=api_token, silent=True)

        if not workflows:
            return {}

        # 并发获取所有 workflow 的 jobs
        from circleCi.pipeline_api import _fetch_workflow_jobs_concurrent
        workflow_ids = [w.get('id') for w in workflows]
        all_jobs_map = _fetch_workflow_jobs_concurrent(workflow_ids, api_token=api_token)

        return get_all_approvals_info_with_workflows(workflows, all_jobs_map)

    except Exception as e:
        return {'error': {'error': str(e), 'status': 'error', 'approved_by': 'Error', 'approved_at': None}}


def get_preprod_approval_info(
    pipeline_id: str,
    project_name: Optional[str] = None,
    api_token: Optional[str] = None
) -> Optional[dict]:
    """获取 Pipeline 中 preprod approval 的信息

    Args:
        pipeline_id: Pipeline ID
        project_name: 项目名称（用于匹配对应的 approval job）
        api_token: API Token

    Returns:
        dict: {'approved_by': '审批人', 'approved_at': '审批时间', 'status': '状态'} 或 None
    """
    try:
        # 获取 workflows
        from circleCi.monitoring import get_pipeline_workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=api_token, silent=True)

        if not workflows:
            return None

        # 并发获取所有 workflow 的 jobs
        from circleCi.pipeline_api import _fetch_workflow_jobs_concurrent
        workflow_ids = [w.get('id') for w in workflows]
        all_jobs_map = _fetch_workflow_jobs_concurrent(workflow_ids, api_token=api_token)

        # 收集所有 preprod approval jobs
        all_preprod_approvals = []

        for workflow in workflows:
            workflow_id = workflow.get('id')
            workflow_name = workflow.get('name', '').lower()
            all_jobs = all_jobs_map.get(workflow_id, [])

            # 查找 approval 类型的 job
            for job in all_jobs:
                job_name = job.get('name', '').lower()
                job_type = job.get('type', '')

                # 检查是否是 preprod 的 approval job
                if job_type == 'approval' and 'preprod' in job_name:
                    status = job.get('status')

                    approval_info = {
                        'approved_by': None,
                        'approved_at': None,
                        'job_name': job.get('name'),
                        'status': status,
                        'job_name_lower': job_name
                    }

                    # 根据状态填充信息
                    if status == 'success':
                        # CircleCI 的 approval job 的 approved_by 是用户 UUID
                        # 需要通过 API 将 UUID 转换为用户名

                        approved_by_data = job.get('approved_by')
                        approver_name = None

                        if isinstance(approved_by_data, str) and approved_by_data:
                            # 检查是否是 UUID 格式（包含多个破折号）
                            if approved_by_data.count('-') >= 4:
                                # 这是一个 UUID，需要查询用户信息
                                logger.debug(f"Fetching user info for UUID: {approved_by_data}")
                                approver_name = get_user_info_by_id(approved_by_data, api_token=api_token)
                                if approver_name:
                                    logger.debug(f"Found username: {approver_name}")
                                else:
                                    logger.warning(f"Could not resolve UUID to username")
                            else:
                                # 不是 UUID，可能已经是用户名
                                approver_name = approved_by_data
                        elif isinstance(approved_by_data, dict):
                            # 如果是字典，尝试获取 login 字段
                            approver_name = approved_by_data.get('login') or approved_by_data.get('username')

                        # 设置审批人信息
                        if approver_name:
                            approval_info['approved_by'] = approver_name
                        else:
                            approval_info['approved_by'] = '已审批'
                            approval_info['note'] = '无法获取审批者信息'

                        approval_info['approved_at'] = job.get('stopped_at', job.get('approved_at'))
                        approval_info['status'] = 'approved'

                    elif status == 'on_hold':
                        approval_info['approved_by'] = 'Pending'
                        approval_info['approved_at'] = None
                        approval_info['status'] = 'pending'
                    else:
                        approval_info['approved_by'] = 'N/A'
                        approval_info['approved_at'] = job.get('stopped_at')

                    all_preprod_approvals.append(approval_info)

        if not all_preprod_approvals:
            return None

        # 如果提供了项目名称，尝试匹配相关的 approval
        if project_name:
            # 从 project_slug 中提取项目名称（例如：github/asiainspection/aca-new -> aca-new）
            if '/' in project_name:
                project_name = project_name.split('/')[-1]

            project_name_lower = project_name.lower()

            # 查找 job 名称中包含项目名称的 approval
            matched_approvals = [
                approval for approval in all_preprod_approvals
                if project_name_lower in approval['job_name_lower']
            ]

            if matched_approvals:
                # 优先返回已审批的，否则返回第一个匹配的
                approved_ones = [a for a in matched_approvals if a['status'] == 'approved']
                if approved_ones:
                    result = approved_ones[0].copy()
                    del result['job_name_lower']
                    return result
                else:
                    result = matched_approvals[0].copy()
                    del result['job_name_lower']
                    return result

        # 如果没有匹配的或没有提供项目名称，返回第一个已审批的，否则返回第一个
        approved_ones = [a for a in all_preprod_approvals if a['status'] == 'approved']
        if approved_ones:
            result = approved_ones[0].copy()
            del result['job_name_lower']
            return result
        else:
            result = all_preprod_approvals[0].copy()
            del result['job_name_lower']
            return result

    except Exception as e:
        # 返回错误信息而不是 None，方便调试
        return {
            'error': str(e),
            'approved_by': 'Error',
            'approved_at': None,
            'job_name': 'Error fetching approval info',
            'status': 'error'
        }