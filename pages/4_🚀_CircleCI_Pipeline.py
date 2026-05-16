import streamlit as st
import streamlit.components.v1 as components
import sys
import os
import urllib.parse
from pathlib import Path
import time
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入CircleCI模块
from circleCi.triggerJob import trigger_circleci_pipeline, validate_project_slug
from circleCi.monitoring import (
    get_pipeline_status,
    get_pipeline_workflows,
    format_status,
    monitor_pipeline,
    monitor_by_pipeline_number
)
from circleCi.batch_operations import (
    batch_trigger_pipelines,
    batch_approve_jobs,
    get_pending_approvals_for_batch,
    check_pipeline_approval_status
)
from modules.user_config_loader import get_circleci_config, get_user_config_loader, build_circleci_headers

# CircleCI API基础URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 全局 Session（连接复用，Keep-Alive）
_http_session = requests.Session()

# 设置页面配置
st.set_page_config(
    page_title="CircleCI Pipeline管理",
    page_icon="🚀",
    layout="wide"
)

# 检查当前用户
if 'current_user' not in st.session_state or not st.session_state.current_user:
    st.error("❌ 未选择使用者，请返回主页选择你的身份")
    st.stop()

current_user = st.session_state.current_user

# 从用户配置加载CircleCI配置
user_circleci_config = get_circleci_config(current_user)

if not user_circleci_config:
    st.error(f"❌ 未找到用户 {current_user} 的 CircleCI 配置")
    st.info("请联系管理员在 config/users_config.json 中配置你的信息")
    st.stop()

# 使用用户配置
CIRCLECI_API_TOKEN = user_circleci_config.get('api_token', '')
VCS_TYPE = user_circleci_config.get('vcs_type', 'github')
ORGANIZATION = user_circleci_config.get('organization', 'demo-org')
DEFAULT_PROJECT = user_circleci_config.get('default_project', 'demo-service-b')
DEFAULT_BRANCH = user_circleci_config.get('default_branch', 'master')

# 辅助函数：调用 CircleCI API
def call_circleci_api(endpoint, method='GET', data=None, params=None):
    """调用 CircleCI API

    Args:
        endpoint: API 端点路径（不含基础 URL）
        method: HTTP 方法，GET 或 POST
        data: POST 请求的 JSON 数据
        params: GET 请求的查询参数

    Returns:
        tuple: (response, error_info)
        - response: requests.Response 对象（仅在成功时非 None）
        - error_info: 错误信息字典，包含 'error', 'status_code', 'url' 等字段

    约定:
        - 若 error_info 非 None，response 视为不可用，调用方应立即处理错误
        - 仅当 error_info 为 None 且 response 非 None 时，response 才可安全使用
    """
    url = f"{CIRCLECI_API_BASE}/{endpoint}"
    headers = build_circleci_headers(CIRCLECI_API_TOKEN)

    # timeout 增大至 30s，因为长分支名 URL 编码后请求可能较慢
    try:
        if method == 'GET':
            response = _http_session.get(url, headers=headers, params=params, timeout=30)
        elif method == 'POST':
            response = _http_session.post(url, headers=headers, json=data, timeout=30)
        else:
            return None, {'error': 'Invalid method', 'url': url}

        # 4xx 错误：返回错误信息，response 视为不可用
        if response.status_code >= 400 and response.status_code < 500:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', response.text[:200])
            except Exception:
                error_msg = response.text[:200]
            return None, {
                'status_code': response.status_code,
                'error': error_msg,
                'url': url
            }

        # 5xx 错误：服务端错误
        if response.status_code >= 500:
            return None, {'error': f'Server error: {response.status_code}', 'url': url}

        # 成功（2xx/3xx）
        return response, None
    except Exception as e:
        return None, {'error': str(e), 'url': url}

def search_pipelines_by_revision(revision_prefix: str, services: list, max_pipelines_per_service: int = 20, show_progress: bool = False):
    """
    跨多个服务并发搜索匹配 revision 前缀的 Pipeline

    Args:
        revision_prefix: commit ID 前缀（部分匹配，如 "8a688704")
        services: 要搜索的服务名称列表
        max_pipelines_per_service: 每个服务最多检查的 pipeline 数量
        show_progress: 是否显示进度信息

    Returns:
        tuple: (results, errors) - 匹配的 pipeline 列表和错误信息字典
    """
    if not revision_prefix or len(revision_prefix.strip()) < 4:
        return [], {'error': 'Revision prefix too short (minimum 4 characters)'}

    revision_prefix = revision_prefix.strip().lower()
    raw_matches = []
    errors = {}

    def search_service(service_name: str):
        """搜索单个服务"""
        try:
            project_slug = f"{VCS_TYPE}/{ORGANIZATION}/{service_name}"
            response, error = call_circleci_api(f"project/{project_slug}/pipeline")

            if error:
                return [], error

            if not response or response.status_code != 200:
                return [], {'error': 'Failed to fetch pipelines'}

            items = response.json().get('items', [])[:max_pipelines_per_service]
            matched = []

            for p in items:
                revision = p.get('vcs', {}).get('revision', '')
                if revision and revision.lower().startswith(revision_prefix):
                    matched.append({
                        'id': p.get('id'),
                        'number': p.get('number'),
                        'state': p.get('state'),
                        'created_at': p.get('created_at'),
                        'updated_at': p.get('updated_at'),
                        'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
                        'branch': p.get('vcs', {}).get('branch'),
                        'revision': revision,
                        'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
                        'project_slug': project_slug,
                        'service_name': service_name
                    })

            return matched, None
        except Exception as e:
            return [], {'error': str(e)}

    # 第一阶段：并发搜索所有服务，获取匹配的 pipeline
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
    raw_matches = raw_matches[:100]  # 最多处理100条

    if show_progress:
        logger.info(f"Found {len(raw_matches)} matching pipelines, fetching approval info...")

    # 第二阶段：并发获取每个匹配 pipeline 的 approval 信息
    def fetch_approval_data(p, idx):
        """获取单个 pipeline 的 approval 信息"""
        pipeline_id = p.get('id')
        service_name = p.get('service_name')

        if show_progress:
            logger.info(f"  [{idx+1}/{len(raw_matches)}] Fetching approval for #{p.get('number')} ({service_name})")

        # 获取所有环境的 approval 信息
        all_approvals_info = get_all_approvals_info(pipeline_id, service_name)

        if show_progress and all_approvals_info:
            logger.info(f"  ✓ Found approval info for #{p.get('number')}: {list(all_approvals_info.keys())}")

        return {
            **p,
            'all_approvals': all_approvals_info
        }

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_approval_data, p, idx): idx
                  for idx, p in enumerate(raw_matches)}

        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                # 如果获取 approval 失败，仍然保留基本信息
                idx = futures[future]
                p = raw_matches[idx]
                results.append({
                    **p,
                    'all_approvals': {'error': {'error': str(e), 'status': 'error'}}
                })

    # 再次排序确保顺序正确
    results.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return results[:100], errors  # 最多返回100条


def fetch_recent_branches(project_slug, max_count=8):
    """
    查询项目最近的 pipelines，提取不重复的分支名列表。

    Returns:
        tuple: (branches, error_info) - 分支名列表和错误信息
    """
    response, error = call_circleci_api(f"project/{project_slug}/pipeline")
    if error:
        return [], error
    if not response or response.status_code != 200:
        return [], {'error': 'Failed to fetch pipelines'}
    items = response.json().get('items', [])
    seen = []
    for item in items[:max_count * 2]:  # 多取一些防止重复不足
        branch = item.get('vcs', {}).get('branch')
        if branch and branch not in seen:
            seen.append(branch)
        if len(seen) >= max_count:
            break
    return seen, None


def _fetch_all_pipelines_with_pagination(project_slug, max_pages=3, show_progress=False):
    """获取多页 pipeline 数据（解决 CircleCI API 分页限制）

    Args:
        project_slug: 项目标识
        max_pages: 最大获取页数（每页约20条）
        show_progress: 是否显示进度

    Returns:
        tuple: (pipelines_list, error_info)
    """
    all_pipelines = []
    page_token = None

    for page_num in range(max_pages):
        params = {}
        if page_token:
            params['page-token'] = page_token

        response, error = call_circleci_api(f"project/{project_slug}/pipeline", params=params)

        if error:
            return all_pipelines, error

        if not response or response.status_code != 200:
            break

        data = response.json()
        items = data.get('items', [])
        all_pipelines.extend(items)

        if show_progress:
            st.caption(f"📦 第 {page_num + 1} 页: {len(items)} 条，累计 {len(all_pipelines)} 条")

        page_token = data.get('next_page_token')
        if not page_token:
            break

    return all_pipelines, None


def _fallback_filter_by_branch(all_pipelines, branch, show_progress=False):
    """本地过滤分支（用于 API 查询返回空时的回退）

    Args:
        all_pipelines: 所有 pipeline 列表
        branch: 目标分支名（已 trim）
        show_progress: 是否显示进度

    Returns:
        list: 匹配的 pipeline 列表
    """
    branch_lower = branch.lower()

    # 先尝试精确匹配
    matched = [
        p for p in all_pipelines
        if p.get('vcs', {}).get('branch', '').lower() == branch_lower
    ]

    if matched:
        if show_progress:
            st.caption(f"✅ 精确匹配找到 {len(matched)} 个 Pipeline")
        return matched

    # 精确匹配失败，尝试模糊匹配（包含）
    matched = [
        p for p in all_pipelines
        if branch_lower in p.get('vcs', {}).get('branch', '').lower()
    ]

    if matched and show_progress:
        st.caption(f"✨ 模糊匹配找到 {len(matched)} 个 Pipeline")

    return matched


def query_pipelines(project_slug, branch=None, show_progress=False):
    """查询项目的 Pipeline 列表

    策略：当指定分支时，先尝试 API 过滤；如果返回空则回退到查询全部后本地过滤

    Args:
        project_slug: 项目标识
        branch: 分支名（可选，会自动 trim）
        show_progress: 是否显示进度信息

    Returns:
        tuple: (pipelines, error_info) - pipeline 列表和错误信息
    """
    # 清理分支名（去除首尾空格）
    if branch:
        branch = branch.strip()

    params = {}
    if branch:
        params['branch'] = branch

    response, error = call_circleci_api(f"project/{project_slug}/pipeline", params=params)

    if error:
        return None, error

    pipelines = []
    if response and response.status_code == 200:
        data = response.json()
        pipelines = data.get('items', [])

    # 如果指定了分支但 API 返回空，回退到查询全部后本地过滤
    if branch and len(pipelines) == 0:
        if show_progress:
            st.info(f"💡 指定分支 '{branch}' API 查询返回空，尝试本地过滤...")

        # 获取多页数据（最多3页约60条）
        all_pipelines, fallback_error = _fetch_all_pipelines_with_pagination(
            project_slug, max_pages=3, show_progress=show_progress
        )

        if fallback_error:
            return None, fallback_error

        if show_progress:
            st.caption(f"📦 共获取 {len(all_pipelines)} 个 Pipeline 用于本地过滤")

        # 本地过滤
        pipelines = _fallback_filter_by_branch(all_pipelines, branch, show_progress)

        if len(pipelines) == 0 and show_progress:
            st.warning(f"❌ 本地过滤也未找到分支 '{branch}'")

    pipelines = pipelines[:10]  # 只取前10个

    if len(pipelines) == 0:
        return [], None

    # 从 project_slug 中提取项目名称
    project_name = project_slug.split('/')[-1] if '/' in project_slug else project_slug

    total = len(pipelines)
    if show_progress:
        logger.info(f"开始处理 {total} 个 Pipeline（并发模式）")

    # 使用并发获取审批信息
    def fetch_pipeline_data(p, idx):
        """获取单个 pipeline 的完整数据"""
        pipeline_id = p.get('id')
        pipeline_number = p.get('number')

        if show_progress:
            logger.info(f"  [{idx+1}/{total}] Processing Pipeline #{pipeline_number}")

        # 获取 preprod approval 信息
        preprod_approval_info = get_preprod_approval_info(pipeline_id, project_name)

        if show_progress and preprod_approval_info:
            logger.info(f"  ✓ Found preprod approval for #{pipeline_number}")

        return {
            'id': pipeline_id,
            'number': pipeline_number,
            'state': p.get('state'),
            'created_at': p.get('created_at'),
            'updated_at': p.get('updated_at'),
            'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
            'branch': p.get('vcs', {}).get('branch'),
            'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
            'revision': p.get('vcs', {}).get('revision'),
            'preprod_approval': preprod_approval_info,
            'project_name': project_name
        }

    # 使用线程池并发处理（最多10个并发）
    formatted = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有任务
        futures = {executor.submit(fetch_pipeline_data, p, idx): idx
                  for idx, p in enumerate(pipelines)}

        # 按提交顺序收集结果
        results = [None] * total
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                logger.error(f"Error processing pipeline {idx}: {e}")
                # 即使出错也添加基本信息
                p = pipelines[idx]
                results[idx] = {
                    'id': p.get('id'),
                    'number': p.get('number'),
                    'state': p.get('state'),
                    'created_at': p.get('created_at'),
                    'updated_at': p.get('updated_at'),
                    'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
                    'branch': p.get('vcs', {}).get('branch'),
                    'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
                    'revision': p.get('vcs', {}).get('revision'),
                    'preprod_approval': None,
                    'project_name': project_name
                }

        formatted = [r for r in results if r is not None]

    if show_progress:
        logger.info(f"完成！共处理 {len(formatted)} 个 Pipeline")

    return formatted, None

def get_user_info_by_id(user_id):
    """
    通过用户 UUID 获取用户信息（用户名）
    使用缓存避免重复 API 调用
    
    Args:
        user_id: 用户的 UUID
        
    Returns:
        用户名（login）或 None
    """
    # 确保缓存已初始化（防止并发调用时出错）
    if 'user_cache' not in st.session_state:
        st.session_state.user_cache = {}
    
    # 检查缓存
    if user_id in st.session_state.user_cache:
        return st.session_state.user_cache[user_id]
    
    try:
        endpoint = f'user/{user_id}'
        response, error = call_circleci_api(endpoint)

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

def _fetch_workflow_jobs_concurrent(workflow_ids):
    """并发获取多个 workflow 的 jobs"""
    def fetch_one(wid):
        resp, error = call_circleci_api(f"workflow/{wid}/job")
        if error:
            return []
        if resp and resp.status_code == 200:
            return resp.json().get('items', [])
        return []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {wid: executor.submit(fetch_one, wid) for wid in workflow_ids}
        return {wid: future.result() for wid, future in futures.items()}


# 定义要检测的环境列表（按优先级排序）
ENVIRONMENT_PRIORITIES = ['preprod', 'staging', 'dev', 'uat', 'prod', 'production']


def get_all_approvals_info(pipeline_id, project_name=None):
    """
    获取 Pipeline 中所有环境的 approval 信息
    支持多个环境：dev, staging, preprod, uat, prod 等

    Args:
        pipeline_id: Pipeline ID
        project_name: 项目名称（用于匹配对应的 approval job）

    Returns:
        dict: 按环境名组织的 approval 信息字典，如:
        {
            'preprod': {'approved_by': 'john', 'approved_at': '...', 'status': 'approved', 'job_name': 'preprod-deploy'},
            'staging': {'approved_by': 'Pending', 'approved_at': None, 'status': 'pending', 'job_name': 'staging-approval'},
            'dev': {...}
        }
    """
    try:
        # 获取 workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=CIRCLECI_API_TOKEN, silent=True)

        if not workflows:
            return {}

        # 并发获取所有 workflow 的 jobs
        workflow_ids = [w.get('id') for w in workflows]
        all_jobs_map = _fetch_workflow_jobs_concurrent(workflow_ids)

        # 按环境收集所有 approval jobs
        approvals_by_env = {}

        for workflow in workflows:
            workflow_id = workflow.get('id')
            workflow_name = workflow.get('name', '').lower()
            all_jobs = all_jobs_map.get(workflow_id, [])

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
                    'job_name_lower': job_name_lower,
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

        # 清理内部字段
        for env, info in approvals_by_env.items():
            if 'job_name_lower' in info:
                del info['job_name_lower']

        return approvals_by_env

    except Exception as e:
        return {'error': {'error': str(e), 'status': 'error', 'approved_by': 'Error', 'approved_at': None}}


def get_preprod_approval_info(pipeline_id, project_name=None):
    """
    获取 Pipeline 中 preprod approval 的信息
    pipeline_id: Pipeline ID
    project_name: 项目名称（用于匹配对应的 approval job）
    返回：{'approved_by': '审批人', 'approved_at': '审批时间', 'status': '状态'} 或 None
    """
    try:
        # 获取 workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=CIRCLECI_API_TOKEN, silent=True)

        if not workflows:
            return None

        # 并发获取所有 workflow 的 jobs
        workflow_ids = [w.get('id') for w in workflows]
        all_jobs_map = _fetch_workflow_jobs_concurrent(workflow_ids)

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
                                approver_name = get_user_info_by_id(approved_by_data)
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
            # 从 project_slug 中提取项目名称（例如：github/demo-org/demo-service-a-new -> demo-service-a-new）
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

def get_workflow_jobs(workflow_id):
    """获取 Workflow 的 Jobs（包括 approval jobs）"""
    response, error = call_circleci_api(f"workflow/{workflow_id}/job")

    if error:
        return None

    if response and response.status_code == 200:
        data = response.json()
        jobs = data.get('items', [])

        # 筛选出 approval 类型的 job
        approval_jobs = [
            {**job, 'workflow_id': workflow_id}
            for job in jobs
            if job.get('type') == 'approval' and job.get('status') == 'on_hold'
        ]

        return {
            'jobs': jobs,
            'approval_jobs': approval_jobs
        }
    return None

def approve_job(workflow_id, approval_request_id):
    """审批一个 Job"""
    endpoint = f"workflow/{workflow_id}/approve/{approval_request_id}"
    response, error = call_circleci_api(endpoint, method='POST', data={})

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

def format_duration(started_at, stopped_at=None):
    """
    格式化持续时间
    如果 stopped_at 为 None，则计算从 started_at 到现在的时间
    """
    if not started_at:
        return 'N/A'
    
    try:
        from datetime import datetime, timezone
        
        # 解析 started_at
        if isinstance(started_at, str):
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        else:
            start = started_at
        
        # 确定结束时间
        if stopped_at:
            if isinstance(stopped_at, str):
                end = datetime.fromisoformat(stopped_at.replace('Z', '+00:00'))
            else:
                end = stopped_at
        else:
            # 如果没有 stopped_at，使用当前时间
            end = datetime.now(timezone.utc)
        
        # 计算时间差
        duration = end - start
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 0:
            return 'N/A'
        
        # 格式化显示
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception as e:
        return 'N/A'

def convert_utc_to_beijing(utc_time_str):
    """
    将 UTC 时间转换为北京时间（UTC+8）
    """
    if not utc_time_str:
        return None
    
    try:
        from datetime import datetime, timedelta
        
        # 解析 UTC 时间
        if isinstance(utc_time_str, str):
            dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        else:
            dt = utc_time_str
        
        # 转换为北京时间 (UTC+8)
        beijing_time = dt + timedelta(hours=8)
        
        # 格式化返回
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return utc_time_str

def format_time_ago(utc_time_str):
    """计算相对时间（多久之前）"""
    if not utc_time_str:
        return ""
    try:
        from datetime import datetime, timezone
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - utc_time
        
        if delta.days > 0:
            return f"{delta.days}天前"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}小时前"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except Exception as e:
        return ""


def _copy_button(text: str, key: str, label: str = "📋"):
    """点击复制按钮（JS clipboard API）"""
    aid = f"copy_{key}"
    html = f"""
<script>
function copy_{key}() {{
    navigator.clipboard.writeText({repr(text)}).then(() => {{
        var el = document.getElementById({repr(aid)});
        if(el) {{ el.textContent = '✅ 已复制'; setTimeout(function(){{ el.textContent = {repr(label)}; }}, 1500); }}
    }});
}}
</script>
<span id="{aid}" style="
    display:inline-flex; align-items:center; gap:2px;
    background:#f0f0f0; border:1px solid #ddd; border-radius:4px;
    padding:1px 6px; font-size:13px; cursor:pointer;
    color:#333; user-select:none;
" onclick="copy_{key}()">{label}</span>
"""
    st.html(html)


def small_metric(label: str, value: str):
    """小字体的 metric 展示（替代 st.metric 的 36px 大字）"""
    st.markdown(f"""
    <div style="font-size:13px; line-height:1.4; margin-bottom:4px;">
        <div style="color:#888; font-size:11px;">{label}</div>
        <div style="font-size:15px; font-weight:600; color:#333;">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def copy_button(text: str, key: str):
    """点击复制按钮（通用版，自动注入 clipboard 逻辑）"""
    btn_id = f"cpbtn_{key}"
    # 使用 encodeURIComponent 确保中文字符正确处理
    js = f"""
<script>
(function() {{
  window._copyText_{key} = function() {{
    var raw = "{text.replace('"', '\\"')}';
    try {{
      navigator.clipboard.writeText(raw).then(function() {{
        var el = document.getElementById("{btn_id}");
        if(el) {{ el.textContent = "✅ 已复制"; setTimeout(function(){{ el.textContent = "📋"; }}, 1500); }}
      }}).catch(function(err) {{}});
    }} catch(e) {{}}
  }}
}})();
</script>
<span id="{btn_id}" style="
    display:inline-flex; align-items:center; gap:3px;
    background:#e8f5e9; border:1px solid #a5d6a7; border-radius:4px;
    padding:0px 8px; font-size:12px; cursor:pointer;
    color:#2e7d32; user-select:none; margin-left:4px;
" onclick="window._copyText_{key}()">📋</span>
"""
    st.html(js)


# 初始化session state
if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False
if 'pipeline_history' not in st.session_state:
    st.session_state.pipeline_history = []
if 'current_pipeline_id' not in st.session_state:
    st.session_state.current_pipeline_id = None
if 'monitoring_status' not in st.session_state:
    st.session_state.monitoring_status = []
if 'show_pipelines_list' not in st.session_state:
    st.session_state.show_pipelines_list = False
if 'selected_pipeline_for_detail' not in st.session_state:
    st.session_state.selected_pipeline_for_detail = None
if 'queried_pipelines' not in st.session_state:
    st.session_state.queried_pipelines = None
if 'query_project_slug' not in st.session_state:
    st.session_state.query_project_slug = None
if 'approval_workflows' not in st.session_state:
    st.session_state.approval_workflows = None
if 'approval_search_pipeline_id' not in st.session_state:
    st.session_state.approval_search_pipeline_id = None

# 添加用户信息缓存（避免重复 API 调用）
if 'user_cache' not in st.session_state:
    st.session_state.user_cache = {}

# 初始化各个输入框的状态（保持输入值，切换Tab不丢失）
if 'trigger_project' not in st.session_state:
    st.session_state.trigger_project = DEFAULT_PROJECT
if 'trigger_branch' not in st.session_state:
    st.session_state.trigger_branch = DEFAULT_BRANCH
if 'recent_branches' not in st.session_state:
    st.session_state.recent_branches = []
if 'query_project' not in st.session_state:
    st.session_state.query_project = DEFAULT_PROJECT
if 'query_branch' not in st.session_state:
    st.session_state.query_branch = ""
if 'pending_tab3_monitor' not in st.session_state:
    st.session_state.pending_tab3_monitor = None
# Tab4: Commit Search 状态
if 'commit_search_results' not in st.session_state:
    st.session_state.commit_search_results = None
if 'commit_search_prefix' not in st.session_state:
    st.session_state.commit_search_prefix = ""
if 'commit_search_services' not in st.session_state:
    st.session_state.commit_search_services = []

# Tab5: 批量操作状态
if 'batch_trigger_results' not in st.session_state:
    st.session_state.batch_trigger_results = None  # {'success': [], 'failed': []}
if 'batch_pending_approvals' not in st.session_state:
    st.session_state.batch_pending_approvals = []
if 'batch_approve_results' not in st.session_state:
    st.session_state.batch_approve_results = None  # {'success': [], 'failed': []}
if 'batch_selected_services' not in st.session_state:
    st.session_state.batch_selected_services = []
if 'batch_branch' not in st.session_state:
    st.session_state.batch_branch = 'master'
if 'batch_scan_completed' not in st.session_state:
    st.session_state.batch_scan_completed = False

# 标题
st.title("🚀 CircleCI Pipeline 管理工具")

# 显示当前用户
user_display_name = get_user_config_loader().get_user_display_name(current_user)
st.info(f"👤 当前使用者: **{user_display_name}** ({current_user})")

st.markdown("---")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置")

    # API Token状态（不显示 Token 片段，避免泄露）
    if CIRCLECI_API_TOKEN and CIRCLECI_API_TOKEN != 'YOUR_CIRCLECI_TOKEN_HERE':
        st.success("✅ API Token: 已配置")
    else:
        st.error("❌ 未配置API Token")
    
    st.markdown("---")
    
    # 默认配置显示
    st.subheader("📋 默认配置")
    st.info(f"**VCS**: {VCS_TYPE}")
    st.info(f"**组织**: {ORGANIZATION}")
    st.info(f"**项目**: {DEFAULT_PROJECT}")
    st.info(f"**分支**: {DEFAULT_BRANCH}")
    
    st.markdown("---")
    
    # 历史记录
    st.subheader("📜 触发历史")
    if st.session_state.pipeline_history:
        for i, history in enumerate(reversed(st.session_state.pipeline_history[-5:])):
            with st.expander(f"Pipeline #{history['number']}"):
                st.write(f"**ID:** {history['id'][:16]}...")
                st.write(f"**分支:** {history['branch']}")
                st.write(f"**时间:** {history['time']}")
    else:
        st.write("暂无历史记录")

# 创建标签页导航
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 触发Pipeline", "📋 Pipeline列表", "📊 监控Pipeline", "🔍 Commit ID 搜索", "📦 批量操作"])

# 侧边栏设置
with st.sidebar:
    st.subheader("⚙️ 设置")
    
    # 显示缓存统计
    cached_users = len(st.session_state.get('user_cache', {}))
    if cached_users > 0:
        st.info(f"👤 已缓存 {cached_users} 个用户信息")
        if st.button("🗑️ 清空用户缓存", use_container_width=True):
            st.session_state.user_cache = {}
            st.success("✅ 缓存已清空")
            st.rerun()
    else:
        st.caption("暂无用户缓存")
    
    st.markdown("---")
    
    # API 信息
    st.caption(f"🔑 Token: {CIRCLECI_API_TOKEN[:15]}...")
    st.caption(f"🏢 Organization: {ORGANIZATION}")
    st.caption(f"📦 VCS: {VCS_TYPE}")

# Tab 1: 触发 Pipeline
with tab1:
    st.header("🎯 触发 Pipeline")
    
    # 读取服务列表（从 config 目录）
    services_file = project_root / "config" / "circleci-services.txt"
    service_list_for_trigger = [DEFAULT_PROJECT]
    
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list_for_trigger = services
    except Exception as e:
        logger.warning(f"Could not load services list: {e}")
    
    # 分支输入区（表单外，支持"查最新"按钮）
    branch_col1, branch_col2 = st.columns([3, 1])
    with branch_col1:
        branch = st.text_input(
            "分支名称",
            value=st.session_state.trigger_branch,
            placeholder="例如: master, develop, DEMO-12345",
            help="要触发的分支名称"
        )
    with branch_col2:
        st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
        fetch_clicked = st.button(
            "🔍 查最新",
            key="fetch_latest_branch",
            use_container_width=True,
            help="查询所选项目最近构建的分支"
        )

    # 查询最新分支
    if fetch_clicked:
        current_project = st.session_state.trigger_project or DEFAULT_PROJECT
        full_slug = f"{VCS_TYPE}/{ORGANIZATION}/{current_project}"
        with st.spinner("查询最近分支中..."):
            recent_branches, fetch_error = fetch_recent_branches(full_slug)
        if fetch_error:
            st.error(f"❌ 查询分支失败: {fetch_error.get('error', 'Unknown error')}")
            if fetch_error.get('status_code'):
                st.caption(f"HTTP 状态码: {fetch_error.get('status_code')}")
        elif recent_branches:
            st.session_state.recent_branches = recent_branches
        else:
            st.warning("未查询到最近分支，请确认该项目有历史构建记录")

    # 分支下拉选择（查询有结果时显示）- 不使用 rerun，改用 on_change 回调
    if st.session_state.get("recent_branches"):
        def on_branch_selected():
            # 从 branch_selector_select 获取选中的值并同步到 trigger_branch
            selected_val = st.session_state.get("branch_selector_select", "")
            if selected_val:
                st.session_state.trigger_branch = selected_val

        st.selectbox(
            "👇 选择分支（点击后自动填入上方输入框）",
            options=[""] + st.session_state.recent_branches,
            key="branch_selector_select",
            on_change=on_branch_selected
        )

    # 项目名同步到 session_state（供查最新使用）
    try:
        default_index = service_list_for_trigger.index(st.session_state.trigger_project)
    except (ValueError, AttributeError):
        default_index = service_list_for_trigger.index(DEFAULT_PROJECT) if DEFAULT_PROJECT in service_list_for_trigger else 0

    def on_project_change():
        st.session_state.trigger_project = st.session_state.trigger_project_select

    project_name = st.selectbox(
        "项目名称",
        options=service_list_for_trigger,
        index=default_index,
        key="trigger_project_select",
        on_change=on_project_change,
        help="选择项目或直接输入关键字快速过滤"
    )

    # 显示完整的 Project Slug（只读）
    full_project_slug = f"{VCS_TYPE}/{ORGANIZATION}/{project_name}"
    st.info(f"📝 完整项目路径: `{full_project_slug}`")

    with st.form("trigger_form"):
        # 提交按钮（表单只负责提交，不含分支输入）
        submit_button = st.form_submit_button("🚀 触发 Pipeline", type="primary", use_container_width=True)

        if submit_button:
            # 保存输入值到 session state（保持状态）
            st.session_state.trigger_project = project_name
            st.session_state.trigger_branch = branch

            # 构建完整的 project_slug
            project_slug = full_project_slug

            # 验证项目配置
            if not validate_project_slug(project_slug):
                st.error("❌ 项目 Slug 格式错误")
                st.info("请检查项目名称是否正确")
            else:
                with st.spinner("正在触发 Pipeline..."):
                    try:
                        # 触发pipeline，传入API Token
                        result = trigger_circleci_pipeline(
                            project_slug,
                            branch,
                            api_token=CIRCLECI_API_TOKEN
                        )
                        
                        if result.get('success'):
                            pipeline_id = result.get('pipeline_id')
                            pipeline_number = result.get('pipeline_number')
                            
                            st.success(f"✅ Pipeline 触发成功!")
                            
                            # 显示完整的 Pipeline ID（可复制）
                            st.write("**Pipeline ID:**")
                            st.code(pipeline_id, language=None)
                            st.info(f"**Pipeline Number:** {pipeline_number}")
                            
                            # 保存到历史记录
                            st.session_state.pipeline_history.append({
                                'id': pipeline_id,
                                'number': pipeline_number,
                                'branch': branch,
                                'project': project_slug,
                                'time': time.strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
                            # 设置当前pipeline ID（供其他 Tab 使用）
                            st.session_state.current_pipeline_id = pipeline_id

                            st.success("✅ Pipeline 触发成功！")
                            st.write(f"**Pipeline Number:** {pipeline_number}")
                            st.code(pipeline_id, language=None)
                            st.markdown("---")
                            st.markdown(
                                "#### 👉 **下一步：切换到「📊 监控Pipeline」标签页，"
                                "粘贴上方 Pipeline ID 查看实时状态**"
                            )
                            st.markdown(
                                "📌 **提示：** 审批面板已内嵌在监控页底部，"
                                "监控状态的同时可直接审批，**无需切换 Tab**"
                            )
                            st.balloons()
                        else:
                            st.error("❌ Pipeline 触发失败")
                            
                            # 显示具体错误信息
                            error_msg = result.get('error', '未知错误')
                            status_code = result.get('status_code')
                            
                            if status_code:
                                st.error(f"HTTP状态码: {status_code}")
                            st.error(f"错误信息: {error_msg}")
                            
                            # 显示排查建议
                            with st.expander("🔍 故障排查建议"):
                                st.markdown("""
                                请检查以下几点：
                                - ✅ API Token 是否有效且未过期
                                - ✅ 项目 Slug 格式是否正确 (vcs-type/org-name/repo-name)
                                - ✅ 分支是否存在于仓库中
                                - ✅ API Token 是否有足够的权限触发 Pipeline
                                - ✅ 网络连接是否正常
                                """)
                                
                                st.info(f"当前配置:\n- 项目: {project_slug}\n- 分支: {branch}")
                    
                    except Exception as e:
                        import traceback
                        st.error(f"❌ 发生异常: {str(e)}")
                        with st.expander("🔍 查看详细错误"):
                            st.code(traceback.format_exc())

# Tab 2: Pipeline 列表
with tab2:
    st.header("📋 Pipeline 列表")
    
    # 读取服务列表（从 config 目录）
    services_file = project_root / "config" / "circleci-services.txt"
    service_list = [DEFAULT_PROJECT]  # 默认从配置的项目开始
    
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list = services  # 使用完整服务列表
    except Exception as e:
        logger.warning(f"Could not load services list: {e}")
    
    col_list1, col_list2 = st.columns([2, 1])
    
    with col_list1:
        # 下拉选择框（使用 session state 保持值）
        try:
            default_index = service_list.index(st.session_state.query_project)
        except (ValueError, AttributeError):
            default_index = service_list.index(DEFAULT_PROJECT) if DEFAULT_PROJECT in service_list else 0
        
        query_project = st.selectbox(
            "项目名称",
            options=service_list,
            index=default_index,
            help="选择项目或直接输入关键字快速过滤",
            key="query_project_select"
        )
    
    with col_list2:
        query_branch = st.text_input(
            "分支（可选）",
            value=st.session_state.query_branch,
            help="留空查询所有分支",
            key="query_branch_input"
        )
    
    col_btn1, col_btn2 = st.columns([3, 1])
    
    with col_btn1:
        query_btn = st.button("🔍 查询 Pipelines", type="primary", use_container_width=True)
    
    with col_btn2:
        if st.session_state.queried_pipelines:
            if st.button("🗑️ 清空", use_container_width=True, key="clear_pipelines_list"):
                st.session_state.queried_pipelines = None
                st.session_state.query_project_slug = None
                st.rerun()
    
    if query_btn:
        # 保存输入值到 session state（保持状态）
        st.session_state.query_project = query_project
        st.session_state.query_branch = query_branch
        
        if not query_project:
            st.warning("⚠️ 请先选择项目名称")
        else:
            full_slug = f"{VCS_TYPE}/{ORGANIZATION}/{query_project}"
            
            with st.spinner("🚀 正在查询 Pipeline 列表（预计 5-10 秒）..."):
                pipelines, query_error = query_pipelines(full_slug, query_branch if query_branch else None, show_progress=True)

            if query_error:
                st.error(f"❌ 查询失败: {query_error.get('error', 'Unknown error')}")
                if query_error.get('status_code'):
                    st.caption(f"HTTP 状态码: {query_error.get('status_code')}")
                st.info(f"项目路径: {full_slug}")
                # 如果是分支查询失败，建议用户不指定分支重试
                if query_branch:
                    st.warning(f"💡 分支 '{query_branch}' 可能不存在或名称过长。建议留空分支查询所有记录，然后在列表中查找。")
                st.session_state.queried_pipelines = None
            elif pipelines:
                # 保存查询结果到 session_state
                st.session_state.queried_pipelines = pipelines
                st.session_state.query_project_slug = full_slug
                st.success(f"✅ 找到 {len(pipelines)} 个 Pipelines")
            else:
                st.session_state.queried_pipelines = None
                st.error("❌ 查询失败或未找到 Pipeline")
                st.info(f"项目路径: {full_slug}")
    
    # 显示查询结果（从 session_state 读取）
    if st.session_state.queried_pipelines:
        pipelines = st.session_state.queried_pipelines
        
        st.info(f"📊 显示 {len(pipelines)} 个 Pipeline（项目: {st.session_state.query_project_slug}）")
        
        # 显示 Pipeline 列表
        for i, p in enumerate(pipelines):
            # 准备 expander 标题，如果有 preprod approval 信息则显示
            title = f"Pipeline #{p['number']} - {p['state']} - {p['branch'] or 'N/A'}"
            
            with st.expander(title):
                col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                
                with col_p1:
                    st.write("**完整 ID:**")
                    st.code(p['id'], language=None)
                    st.write(f"**Number:** {p['number']}")
                    st.write(f"**状态:** {p['state']}")
                
                with col_p2:
                    branch_val = p['branch'] or 'N/A'
                    revision_val = p.get('revision')
                    revision_display = revision_val[:8] if revision_val else 'N/A'
                    commit_val = p['commit_subject'] or 'N/A'
                    # 分支：可复制的只读文本框（用户可选中 Ctrl+C）
                    st.text_input("分支", value=branch_val, disabled=True, label_visibility="collapsed", key=f"branch_{i}_{p['number']}")
                    st.text(f"Revision: {revision_display}")
                    st.text(f"触发者: {p['actor']}")
                    st.text(f"提交: {commit_val}")
                
                with col_p3:
                    if st.button("📊 监控", key=f"monitor_{i}", use_container_width=True, type="primary"):
                        st.session_state.current_pipeline_id = p['id']
                        st.session_state.pending_tab3_monitor = p['id']
                        st.rerun()
                
                # 显示 Preprod Approval 信息
                preprod_approval = p.get('preprod_approval')
                if preprod_approval:
                    st.markdown("---")
                    st.markdown("**🎯 Preprod Approval 信息:**")
                    
                    approval_status = preprod_approval.get('status', 'unknown')
                    
                    if approval_status == 'error':
                        st.error(f"⚠️ 获取审批信息失败: {preprod_approval.get('error', 'Unknown error')}")
                    else:
                        col_a1, col_a2 = st.columns(2)
                        
                        with col_a1:
                            approved_by = preprod_approval.get('approved_by', 'N/A')
                            if approved_by == 'Pending':
                                st.warning(f"👤 **审批人:** ⏳ 等待审批")
                            elif approved_by == 'Error':
                                st.error(f"👤 **审批人:** ❌ 获取失败")
                            elif approved_by == '已审批':
                                st.success(f"✅ **状态:** 已审批")
                                note = preprod_approval.get('note')
                                if note:
                                    st.caption(f"💡 {note}")
                            else:
                                st.info(f"👤 **审批人:** {approved_by}")
                        
                        with col_a2:
                            approved_at = preprod_approval.get('approved_at')
                            if approved_at:
                                # 转换为北京时间（UTC+8）
                                beijing_time = convert_utc_to_beijing(approved_at)
                                time_ago = format_time_ago(approved_at)
                                if beijing_time:
                                    st.info(f"⏰ **审批时间:** {beijing_time}\n📅 ({time_ago})")
                                else:
                                    st.info(f"⏰ **审批时间:** {approved_at}")
                            else:
                                st.warning(f"⏰ **审批时间:** ⏳ 待审批")
                        
                        # 显示 job 名称和状态
                        job_name = preprod_approval.get('job_name')
                        if job_name:
                            status_emoji = {
                                'approved': '✅',
                                'pending': '⏳',
                                'success': '✅',
                                'on_hold': '⏳',
                                'failed': '❌',
                                'error': '⚠️'
                            }.get(approval_status, '❓')
                            st.caption(f"{status_emoji} Job: {job_name} ({approval_status})")

                        # P2: 待审批时在 Tab2 直接提供审批入口（无需切换 Tab）
                        if approval_status in ('pending', 'on_hold') and p.get('preprod_approval', {}).get('job_name'):
                            approval_job_name = p['preprod_approval']['job_name']
                            # 获取 approval request id（从 preprod_approval 中获取）
                            # 注意：Tab2 的 preprod_approval 来自 query_pipelines，仅含展示信息不含 approval_request_id
                            # 所以这里提供跳转引导
                            st.warning("⏸️ 此 Pipeline 有待审批 Job，可直接前往监控页审批")
                else:
                    # 没有 preprod approval 信息
                    st.markdown("---")
                    st.caption("ℹ️ 此 Pipeline 没有 Preprod Approval 步骤")
                
                st.caption(f"创建时间: {p['created_at']}")
                if p['revision']:
                    st.caption(f"Revision: {p['revision'][:8]}")

# Tab 3: 监控Pipeline
with tab3:
    st.header("📊 监控 Pipeline")

    # Pipeline ID 查询
    _auto_pipeline_id = st.session_state.pending_tab3_monitor or st.session_state.current_pipeline_id or ""
    pipeline_id_input = st.text_input(
        "Pipeline ID",
        value=_auto_pipeline_id,
        help="输入要查询状态的 Pipeline ID"
    )
    _auto_trigger = st.session_state.pending_tab3_monitor is not None
    check_status_btn = st.button("🔍 查看状态", type="primary", use_container_width=True)

    if _auto_trigger:
        st.session_state.pending_tab3_monitor = None

    # Pipeline ID 变化时清除缓存
    if st.session_state.get('tab3_cached_pipeline_id') and st.session_state.tab3_cached_pipeline_id != pipeline_id_input:
        for key in ['tab3_cached_pipeline_id', 'tab3_pipeline_data', 'tab3_workflows', 'tab3_wf_jobs_map', 'tab3_pending_approvals']:
            st.session_state.pop(key, None)

    # 判断是否需要重新获取数据：手动触发 / 自动触发 / 或有缓存数据
    _cached = st.session_state.get('tab3_cached_pipeline_id') == pipeline_id_input
    _needs_refetch = (check_status_btn or _auto_trigger) and pipeline_id_input

    if _needs_refetch:
        # 重新获取并缓存到 session_state
        with st.spinner("正在获取详细状态..."):
            pipeline_data = get_pipeline_status(pipeline_id_input, api_token=CIRCLECI_API_TOKEN)

            if pipeline_data:
                st.session_state.tab3_cached_pipeline_id = pipeline_id_input
                st.session_state.tab3_pipeline_data = pipeline_data

                st.success("✅ 状态获取成功")

                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    small_metric("Pipeline Number", f"#{pipeline_data.get('number', 'N/A')}")
                    small_metric("状态", pipeline_data.get('state', 'unknown').upper())
                with col_info2:
                    small_metric("VCS 分支", pipeline_data.get('vcs', {}).get('branch', 'N/A'))
                    trigger_actor = pipeline_data.get('trigger', {}).get('actor', {}).get('login', 'Unknown')
                    small_metric("触发者", trigger_actor)
                with col_info3:
                    created_at = pipeline_data.get('created_at', '')
                    if created_at:
                        beijing_time = convert_utc_to_beijing(created_at)
                        time_ago = format_time_ago(created_at)
                        small_metric("创建时间", f"{time_ago}")
                        st.caption(beijing_time)
                    else:
                        small_metric("创建时间", "N/A")
                    project_slug = pipeline_data.get('project_slug', 'N/A')
                    project_name = project_slug.split('/')[-1] if '/' in project_slug else project_slug
                    small_metric("项目", project_name)

                st.markdown("---")

                # 预检：查看是否有待审批 Jobs，有则高亮提示（无需滚动到底部）
                try:
                    precheck_wfs = get_pipeline_workflows(pipeline_id_input, api_token=CIRCLECI_API_TOKEN, silent=True)
                    if precheck_wfs:
                        precheck_wf_ids = [w.get('id') for w in precheck_wfs if w.get('id')]
                        precheck_jobs_map = _fetch_workflow_jobs_concurrent(precheck_wf_ids)
                        precheck_pending = []
                        for wf in precheck_wfs:
                            for job in precheck_jobs_map.get(wf.get('id'), []):
                                if job.get('type') == 'approval' and job.get('status') == 'on_hold':
                                    job['_workflow_id'] = wf.get('id')
                                    job['_workflow_name'] = wf.get('name')
                                    precheck_pending.append(job)
                        if precheck_pending:
                            st.error(f"🎯 检测到 {len(precheck_pending)} 个待审批 Job，请滚动至底部「✅ 审批面板」进行处理")
                            for pj in precheck_pending:
                                st.warning(f"  ⏸️ {pj.get('name')} （Workflow: {pj.get('_workflow_name', 'N/A')}）")
                        else:
                            st.success("✅ 当前 Pipeline 无待审批 Job")
                except Exception:
                    pass  # 静默预检，不影响主流程

                st.subheader("📝 Git 提交信息")
                vcs = pipeline_data.get('vcs', {})
                col_vcs1, col_vcs2 = st.columns([2, 1])
                with col_vcs1:
                    commit_subject = vcs.get('commit', {}).get('subject', 'N/A')
                    st.write(f"**提交消息:** {commit_subject}")
                    commit_body = vcs.get('commit', {}).get('body', '')
                    if commit_body:
                        with st.expander("查看完整提交信息"):
                            st.code(commit_body)
                with col_vcs2:
                    revision = vcs.get('revision', 'N/A')
                    st.code(f"Revision: {revision[:8]}...", language="text")
                    branch = vcs.get('branch', 'N/A')
                    st.code(f"Branch: {branch}", language="text")

                # Workflows
                st.markdown("---")
                workflows = get_pipeline_workflows(pipeline_id_input, api_token=CIRCLECI_API_TOKEN)
                if workflows:
                    st.subheader(f"🔄 Workflows ({len(workflows)})")
                    wf_ids = [w.get('id') for w in workflows if w.get('id')]
                    wf_jobs_map = _fetch_workflow_jobs_concurrent(wf_ids)

                    # 缓存到 session_state（审批后 rerun 时需要）
                    st.session_state.tab3_workflows = workflows
                    st.session_state.tab3_wf_jobs_map = wf_jobs_map

                    for idx, workflow in enumerate(workflows):
                        wf_id = workflow.get('id', 'N/A')
                        wf_name = workflow.get('name', 'Unknown')
                        wf_status = workflow.get('status', 'unknown')
                        disp_txt, emoji = format_status(wf_status)
                        started_at = workflow.get('started_at')
                        stopped_at = workflow.get('stopped_at')
                        duration_str = format_duration(started_at, stopped_at) if started_at else 'N/A'

                        with st.expander(f"{emoji} **{wf_name}** - {disp_txt} (⏱️ {duration_str})", expanded=(idx == 0)):
                            wc1, wc2 = st.columns(2)
                            with wc1:
                                st.write(f"**Workflow ID:** `{wf_id[:16]}...`")
                                st.write(f"**状态:** {disp_txt} {emoji}")
                            with wc2:
                                if started_at:
                                    st.write(f"**开始时间:** {convert_utc_to_beijing(started_at)}")
                                if stopped_at:
                                    st.write(f"**结束时间:** {convert_utc_to_beijing(stopped_at)}")

                            st.write("---")
                            st.write("**📋 Jobs:**")
                            jobs = wf_jobs_map.get(wf_id, [])
                            if jobs:
                                stats = {'success': 0, 'running': 0, 'failed': 0, 'on_hold': 0, 'other': 0}
                                for j in jobs:
                                    s = j.get('status', 'unknown')
                                    if s == 'success': stats['success'] += 1
                                    elif s in ['running', 'queued']: stats['running'] += 1
                                    elif s in ['failed', 'failing']: stats['failed'] += 1
                                    elif s == 'on_hold': stats['on_hold'] += 1
                                    else: stats['other'] += 1
                                sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                                sc1.metric("✅ 成功", stats['success'])
                                sc2.metric("🔄 运行中", stats['running'])
                                sc3.metric("❌ 失败", stats['failed'])
                                sc4.metric("⏸️ 待审批", stats['on_hold'])
                                sc5.metric("📊 总计", len(jobs))
                                # 注入小字体样式
                                st.markdown("""
                                <style>
                                .job-item { font-size: 13px !important; line-height: 1.4 !important; }
                                </style>
                                """, unsafe_allow_html=True)
                                for j in jobs:
                                    jd, je = format_status(j.get('status', 'unknown'))
                                    jdur = format_duration(j.get('started_at'), j.get('stopped_at'))
                                    icon = "🔧" if j.get('type') == "build" else "✅" if j.get('type') == "approval" else "📦"
                                    job_name = j.get('name', 'Unknown')
                                    job_number = j.get('job_number', 'N/A')
                                    st.markdown(
                                        f'<div class="job-item">{icon} {je} <b>{job_name}</b> '
                                        f'(#{job_number}) - {jd} - ⏱️ {jdur}</div>',
                                        unsafe_allow_html=True
                                    )
                            else:
                                st.info("暂无 Jobs 信息")
                else:
                    st.info("暂无 Workflows 信息")
                    st.session_state.tab3_workflows = []
                    st.session_state.tab3_wf_jobs_map = {}

                # 内嵌审批面板
                st.markdown("---")
                st.subheader("✅ 审批面板")
                pending_approvals = []
                try:
                    approval_wfs = get_pipeline_workflows(pipeline_id_input, api_token=CIRCLECI_API_TOKEN, silent=True)
                    if approval_wfs:
                        wf_ids = [w.get('id') for w in approval_wfs if w.get('id')]
                        aj_map = _fetch_workflow_jobs_concurrent(wf_ids)
                        for wf in approval_wfs:
                            for job in aj_map.get(wf.get('id'), []):
                                if job.get('type') == 'approval' and job.get('status') == 'on_hold':
                                    job['_workflow_id'] = wf.get('id')
                                    job['_workflow_name'] = wf.get('name')
                                    pending_approvals.append(job)
                except Exception:
                    pass

                # 缓存 pending_approvals 到 session_state
                st.session_state.tab3_pending_approvals = pending_approvals

                if pending_approvals:
                    st.success(f"🎯 当前 Pipeline 有 {len(pending_approvals)} 个待审批 Jobs")
                    for job in pending_approvals:
                        wf_name = job.get('_workflow_name', '')
                        job_name = job.get('name', '').lower()
                        dur = format_duration(job.get('started_at'), job.get('stopped_at'))
                        # preprod 审批项 或 只有一个时自动展开
                        is_preprod = 'preprod' in job_name
                        should_expand = is_preprod or len(pending_approvals) == 1
                        with st.expander(f"✋ {job.get('name')} — {wf_name} — ⏱️ {dur}", expanded=should_expand):
                            ac1, ac2 = st.columns([3, 1])
                            with ac1:
                                st.write(f"**Job ID:** `{job.get('id')}`")
                                st.write(f"**Workflow:** {wf_name}")
                                st.write(f"**Approval Request ID:** `{job.get('approval_request_id')}`")
                            with ac2:
                                ak = f"inline_approve_{job.get('id')}"
                                if st.button("✅ 审批", key=ak, type="primary", use_container_width=True):
                                    with st.spinner("正在审批..."):
                                        res = approve_job(job.get('_workflow_id'), job.get('approval_request_id'))
                                        if res.get('success'):
                                            st.success("✅ 审批成功！")
                                            st.balloons()  # 礼花动效
                                            time.sleep(1.5)  # 让用户看见成功提示再刷新
                                            st.session_state.pending_tab3_monitor = pipeline_id_input
                                            st.rerun()
                                        else:
                                            st.error(f"❌ 审批失败: {res.get('error')}")
                else:
                    st.info("ℹ️ 当前 Pipeline 无待审批 Jobs")

            else:
                st.error("❌ 无法获取 Pipeline 状态")

    elif _cached and pipeline_id_input:
        # 从 session_state 缓存恢复展示（审批后 rerun 会走到此分支）
        pipeline_data = st.session_state.tab3_pipeline_data
        workflows = st.session_state.tab3_workflows
        wf_jobs_map = st.session_state.tab3_wf_jobs_map
        pending_approvals = st.session_state.tab3_pending_approvals

        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            small_metric("Pipeline Number", f"#{pipeline_data.get('number', 'N/A')}")
            small_metric("状态", pipeline_data.get('state', 'unknown').upper())
        with col_info2:
            small_metric("VCS 分支", pipeline_data.get('vcs', {}).get('branch', 'N/A'))
            trigger_actor = pipeline_data.get('trigger', {}).get('actor', {}).get('login', 'Unknown')
            small_metric("触发者", trigger_actor)
        with col_info3:
            created_at = pipeline_data.get('created_at', '')
            if created_at:
                beijing_time = convert_utc_to_beijing(created_at)
                time_ago = format_time_ago(created_at)
                small_metric("创建时间", f"{time_ago}")
                st.caption(beijing_time)
            else:
                small_metric("创建时间", "N/A")
            project_slug = pipeline_data.get('project_slug', 'N/A')
            project_name = project_slug.split('/')[-1] if '/' in project_slug else project_slug
            small_metric("项目", project_name)

        st.markdown("---")
        st.subheader("📝 Git 提交信息")
        vcs = pipeline_data.get('vcs', {})
        col_vcs1, col_vcs2 = st.columns([2, 1])
        with col_vcs1:
            commit_subject = vcs.get('commit', {}).get('subject', 'N/A')
            st.write(f"**提交消息:** {commit_subject}")
            commit_body = vcs.get('commit', {}).get('body', '')
            if commit_body:
                with st.expander("查看完整提交信息"):
                    st.code(commit_body)
        with col_vcs2:
            revision = vcs.get('revision', 'N/A')
            st.code(f"Revision: {revision[:8]}...", language="text")
            branch = vcs.get('branch', 'N/A')
            st.code(f"Branch: {branch}", language="text")

        st.markdown("---")
        if workflows:
            st.subheader(f"🔄 Workflows ({len(workflows)})")
            for idx, workflow in enumerate(workflows):
                wf_id = workflow.get('id', 'N/A')
                wf_name = workflow.get('name', 'Unknown')
                wf_status = workflow.get('status', 'unknown')
                disp_txt, emoji = format_status(wf_status)
                started_at = workflow.get('started_at')
                stopped_at = workflow.get('stopped_at')
                duration_str = format_duration(started_at, stopped_at) if started_at else 'N/A'

                with st.expander(f"{emoji} **{wf_name}** - {disp_txt} (⏱️ {duration_str})", expanded=(idx == 0)):
                    wc1, wc2 = st.columns(2)
                    with wc1:
                        st.write(f"**Workflow ID:** `{wf_id[:16]}...`")
                        st.write(f"**状态:** {disp_txt} {emoji}")
                    with wc2:
                        if started_at:
                            st.write(f"**开始时间:** {convert_utc_to_beijing(started_at)}")
                        if stopped_at:
                            st.write(f"**结束时间:** {convert_utc_to_beijing(stopped_at)}")

                    st.write("---")
                    st.write("**📋 Jobs:**")
                    jobs = wf_jobs_map.get(wf_id, [])
                    if jobs:
                        stats = {'success': 0, 'running': 0, 'failed': 0, 'on_hold': 0, 'other': 0}
                        for j in jobs:
                            s = j.get('status', 'unknown')
                            if s == 'success': stats['success'] += 1
                            elif s in ['running', 'queued']: stats['running'] += 1
                            elif s in ['failed', 'failing']: stats['failed'] += 1
                            elif s == 'on_hold': stats['on_hold'] += 1
                            else: stats['other'] += 1
                        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                        sc1.metric("✅ 成功", stats['success'])
                        sc2.metric("🔄 运行中", stats['running'])
                        sc3.metric("❌ 失败", stats['failed'])
                        sc4.metric("⏸️ 待审批", stats['on_hold'])
                        sc5.metric("📊 总计", len(jobs))
                        # 注入小字体样式
                        st.markdown("""
                        <style>
                        .job-item { font-size: 13px !important; line-height: 1.4 !important; }
                        </style>
                        """, unsafe_allow_html=True)
                        for j in jobs:
                            jd, je = format_status(j.get('status', 'unknown'))
                            jdur = format_duration(j.get('started_at'), j.get('stopped_at'))
                            icon = "🔧" if j.get('type') == "build" else "✅" if j.get('type') == "approval" else "📦"
                            job_name = j.get('name', 'Unknown')
                            job_number = j.get('job_number', 'N/A')
                            st.markdown(
                                f'<div class="job-item">{icon} {je} <b>{job_name}</b> '
                                f'(#{job_number}) - {jd} - ⏱️ {jdur}</div>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("暂无 Jobs 信息")
        else:
            st.info("暂无 Workflows 信息")

        st.markdown("---")
        st.subheader("✅ 审批面板")
        if pending_approvals:
            st.success(f"🎯 当前 Pipeline 有 {len(pending_approvals)} 个待审批 Jobs")
            for job in pending_approvals:
                wf_name = job.get('_workflow_name', '')
                job_name = job.get('name', '').lower()
                dur = format_duration(job.get('started_at'), job.get('stopped_at'))
                is_preprod = 'preprod' in job_name
                should_expand = is_preprod or len(pending_approvals) == 1
                with st.expander(f"✋ {job.get('name')} — {wf_name} — ⏱️ {dur}", expanded=should_expand):
                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        st.write(f"**Job ID:** `{job.get('id')}`")
                        st.write(f"**Workflow:** {wf_name}")
                        st.write(f"**Approval Request ID:** `{job.get('approval_request_id')}`")
                    with ac2:
                        ak = f"inline_approve_{job.get('id')}"
                        if st.button("✅ 审批", key=ak, type="primary", use_container_width=True):
                            with st.spinner("正在审批..."):
                                res = approve_job(job.get('_workflow_id'), job.get('approval_request_id'))
                                if res.get('success'):
                                    import time
                                    st.success("✅ 审批成功！")
                                    time.sleep(1.5)  # 让用户看见成功提示再刷新
                                    st.session_state.pending_tab3_monitor = pipeline_id_input
                                    st.rerun()
                                else:
                                    st.error(f"❌ 审批失败: {res.get('error')}")
        else:
            st.info("ℹ️ 当前 Pipeline 无待审批 Jobs")

# Tab 4: Commit ID 搜索
with tab4:
    st.header("🔍 Commit ID 搜索")
    st.info("💡 输入 Commit ID 前缀（如 8a688704），跨多个服务并发搜索匹配的 Pipeline")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    all_services = [DEFAULT_PROJECT]
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                all_services = [line.strip() for line in f if line.strip()]
    except Exception:
        pass

    # 输入区域
    col_input1, col_input2 = st.columns([2, 1])

    with col_input1:
        commit_prefix = st.text_input(
            "Commit ID 前缀",
            value=st.session_state.commit_search_prefix,
            placeholder="例如: 8a688704（最少4位）",
            help="输入完整的或部分的 commit hash，系统会搜索所有匹配的 Pipeline"
        )

    with col_input2:
        st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
        search_all = st.checkbox("搜索所有服务", value=True, help="勾选则搜索全部服务，取消则只搜索下方选定的服务")

    # 服务选择器（当不选择"搜索所有服务"时显示）
    if not search_all:
        selected_services = st.multiselect(
            "选择要搜索的服务",
            options=all_services,
            default=st.session_state.commit_search_services,
            help="可以多选，或直接输入关键字快速过滤"
        )
    else:
        selected_services = all_services

    # 搜索按钮
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        search_btn = st.button("🔍 开始搜索", type="primary", use_container_width=True)
    with col_btn2:
        if st.session_state.commit_search_results:
            if st.button("🗑️ 清空结果", use_container_width=True, key="clear_commit_search"):
                st.session_state.commit_search_results = None
                st.session_state.commit_search_prefix = ""
                st.rerun()

    # 执行搜索
    if search_btn:
        st.session_state.commit_search_prefix = commit_prefix

        if not commit_prefix or len(commit_prefix.strip()) < 4:
            st.warning("⚠️ 请输入至少4位的 Commit ID 前缀")
        elif not selected_services:
            st.warning("⚠️ 请至少选择一个服务")
        else:
            with st.spinner(f"🔍 正在搜索 {len(selected_services)} 个服务..."):
                results, errors = search_pipelines_by_revision(
                    commit_prefix,
                    selected_services,
                    max_pipelines_per_service=20
                )

            # 显示错误信息（如果有）
            if errors:
                with st.expander("⚠️ 部分服务搜索出错", expanded=False):
                    for svc, err in errors.items():
                        st.error(f"**{svc}:** {err.get('error', 'Unknown error')}")

            # 显示结果
            if results:
                st.session_state.commit_search_results = results
                st.success(f"✅ 找到 {len(results)} 个匹配的 Pipeline")
            else:
                st.session_state.commit_search_results = None
                st.warning(f"❌ 未找到匹配 '{commit_prefix}' 的 Pipeline")
                st.info("💡 建议：检查 commit ID 是否正确，或尝试更短的前缀")

    # 显示已缓存的搜索结果
    if st.session_state.commit_search_results:
        results = st.session_state.commit_search_results
        st.info(f"📊 显示 {len(results)} 个结果（Commit ID: {st.session_state.commit_search_prefix}）")

        for i, r in enumerate(results):
            service_name = r.get('service_name', 'Unknown')
            pipeline_number = r.get('number', 'N/A')
            state = r.get('state', 'unknown')
            branch = r.get('branch') or 'N/A'
            actor = r.get('actor', 'Unknown')
            revision = r.get('revision', 'N/A')
            created_at = r.get('created_at')

            # 构建 expander 标题
            state_emoji = {
                'success': '✅',
                'running': '🔄',
                'pending': '⏳',
                'failed': '❌',
                'on_hold': '⏸️'
            }.get(state, '❓')

            title = f"Pipeline #{pipeline_number} [{service_name}] {state_emoji} {state} - {branch}"

            with st.expander(title):
                col_r1, col_r2, col_r3 = st.columns([2, 2, 1])

                with col_r1:
                    st.write("**服务名称:**")
                    st.code(service_name, language=None)
                    st.write(f"**Pipeline Number:** {pipeline_number}")
                    st.write(f"**状态:** {state} {state_emoji}")

                with col_r2:
                    st.write("**完整 Revision:**")
                    rev_display = revision[:16] + "..." if len(revision) > 16 else revision
                    st.code(rev_display, language=None)
                    copy_button(revision, f"copy_rev_{i}")
                    st.write(f"**分支:** {branch}")
                    st.write(f"**触发者:** {actor}")
                    commit_subject = r.get('commit_subject')
                    if commit_subject:
                        st.write(f"**提交:** {commit_subject[:50]}...")

                with col_r3:
                    if st.button("📊 监控", key=f"commit_monitor_{i}", use_container_width=True, type="primary"):
                        st.session_state.current_pipeline_id = r.get('id')
                        st.session_state.pending_tab3_monitor = r.get('id')
                        st.rerun()

                # 时间信息
                if created_at:
                    beijing_time = convert_utc_to_beijing(created_at)
                    time_ago = format_time_ago(created_at)
                    st.caption(f"创建时间: {beijing_time} ({time_ago})")

                # 显示所有环境的 Approval 信息
                all_approvals = r.get('all_approvals', {})
                if all_approvals:
                    st.markdown("---")
                    st.markdown("**🎯 环境审批信息:**")

                    # 环境图标映射
                    env_icons = {
                        'dev': '🔧',
                        'staging': '🧪',
                        'preprod': '🚀',
                        'uat': '✅',
                        'prod': '🏭',
                        'production': '🏭'
                    }

                    # 按优先级排序显示
                    sorted_envs = sorted(
                        all_approvals.keys(),
                        key=lambda x: ENVIRONMENT_PRIORITIES.index(x) if x in ENVIRONMENT_PRIORITIES else 999
                    )

                    # 如果有错误信息，先显示
                    if 'error' in all_approvals:
                        st.error(f"⚠️ 获取审批信息失败: {all_approvals['error'].get('error', 'Unknown error')}")
                        # 移除 error 键以便后续处理
                        sorted_envs = [e for e in sorted_envs if e != 'error']

                    # 使用列布局显示环境（每行最多3个环境）
                    env_cols = st.columns(min(3, len(sorted_envs)))

                    for idx, env in enumerate(sorted_envs):
                        approval_info = all_approvals[env]
                        col = env_cols[idx % 3]

                        with col:
                            env_icon = env_icons.get(env, '📦')
                            approval_status = approval_info.get('status', 'unknown')

                            # 状态容器
                            if approval_status == 'approved':
                                status_container = st.success
                            elif approval_status in ('pending', 'on_hold'):
                                status_container = st.warning
                            elif approval_status == 'error':
                                status_container = st.error
                            else:
                                status_container = st.info

                            # 审批人信息
                            approved_by = approval_info.get('approved_by', 'N/A')
                            approved_at = approval_info.get('approved_at')

                            if approval_status == 'approved':
                                status_container(f"{env_icon} **{env.upper()}**: ✅ 已审批")
                                st.caption(f"👤 {approved_by}")
                                if approved_at:
                                    beijing_time_approval = convert_utc_to_beijing(approved_at)
                                    time_ago_approval = format_time_ago(approved_at)
                                    st.caption(f"⏰ {beijing_time_approval}")
                            elif approval_status in ('pending', 'on_hold'):
                                status_container(f"{env_icon} **{env.upper()}**: ⏳ 待审批")
                            elif approval_status == 'error':
                                status_container(f"{env_icon} **{env.upper()}**: ⚠️ 获取失败")
                            else:
                                status_container(f"{env_icon} **{env.upper()}**: {approval_status}")

                            # 显示 job 名称
                            job_name = approval_info.get('job_name')
                            if job_name:
                                st.caption(f"📋 {job_name}")

                    # 如果有待审批环境，提示跳转
                    pending_envs = [env for env, info in all_approvals.items()
                                   if info.get('status') in ('pending', 'on_hold')]
                    if pending_envs:
                        st.warning(f"⏸️ 此 Pipeline 有待审批环境: {', '.join([e.upper() for e in pending_envs])}，点击上方「📊 监控」按钮前往审批")
                else:
                    st.markdown("---")
                    st.caption("ℹ️ 此 Pipeline 没有环境审批步骤")


# Tab 5: 批量操作
with tab5:
    st.header("📦 批量操作")
    st.info("💡 批量触发多个服务到指定分支，并支持批量审批到 Preprod 环境")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    all_services = [DEFAULT_PROJECT]
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                all_services = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.warning(f"Could not load services list: {e}")

    # === Section 1: 批量触发 ===
    st.subheader("🚀 批量触发 Pipeline")

    # 快捷服务组
    st.markdown("**📌 快捷操作:**")
    quick_col1, quick_col2, quick_col3 = st.columns(3)

    with quick_col1:
        if st.button("📋 全选所有服务", use_container_width=True, key="batch_select_all"):
            st.session_state.batch_selected_services = all_services
            st.session_state.batch_services_multiselect = all_services
            st.rerun()

    with quick_col2:
        if st.button("🗑️ 清空选择", use_container_width=True, key="batch_clear"):
            st.session_state.batch_selected_services = []
            st.session_state.batch_services_multiselect = []
            st.rerun()

    with quick_col3:
        if st.button("🔄 重置结果", use_container_width=True, key="batch_reset"):
            st.session_state.batch_trigger_results = None
            st.session_state.batch_pending_approvals = []
            st.session_state.batch_approve_results = None
            st.session_state.batch_scan_completed = False
            st.rerun()

    st.markdown("---")

    # 文本输入服务列表
    st.markdown("**📝 输入服务列表（每行一个服务名）:**")
    services_text = st.text_area(
        "服务列表",
        value="",
        height=200,
        placeholder="demo-service-a\ndemo-service-a-new\naims-service-cloud\n...",
        help="每行输入一个服务名称，系统会自动过滤出存在于服务列表中的服务",
        key="batch_services_text"
    )

    # 解析文本输入
    text_services = [s.strip() for s in services_text.split('\n') if s.strip()]
    # 过滤出存在于服务列表中的服务
    valid_text_services = [s for s in text_services if s in all_services]
    invalid_text_services = [s for s in text_services if s not in all_services]

    if invalid_text_services:
        st.warning(f"⚠️ 以下服务不在服务列表中，将被忽略: {', '.join(invalid_text_services[:5])}{'...' if len(invalid_text_services) > 5 else ''}")

    # 应用文本输入按钮
    if st.button("✅ 应用文本输入的服务列表", type="primary", key="batch_apply_text"):
        st.session_state.batch_selected_services = valid_text_services
        st.session_state.batch_services_multiselect = valid_text_services
        st.success(f"✅ 已选择 {len(valid_text_services)} 个有效服务")
        st.rerun()

    st.markdown("---")

    # 服务多选
    selected_services = st.multiselect(
        "选择要触发的服务（支持输入关键字过滤）",
        options=all_services,
        default=st.session_state.batch_selected_services,
        key="batch_services_multiselect",
        help="可以多选，或输入关键字快速过滤"
    )

    # 分支输入
    batch_branch = st.text_input(
        "目标分支",
        value=st.session_state.batch_branch,
        placeholder="例如: master, develop, DEMO-12345",
        help="所有服务将触发到此分支",
        key="batch_branch_input"
    )

    # 显示选中统计
    st.info(f"📊 已选择 **{len(selected_services)}** 个服务，目标分支: **{batch_branch}**")

    # 确认触发
    st.markdown("---")
    confirm_trigger = st.checkbox(
        f"⚠️ 我确认要触发 {len(selected_services)} 个服务到 **{batch_branch}** 分支",
        value=False,
        key="batch_confirm_trigger"
    )

    col_trigger1, col_trigger2 = st.columns([3, 1])
    with col_trigger1:
        trigger_btn_disabled = not confirm_trigger or len(selected_services) == 0
        trigger_btn = st.button(
            "🚀 开始批量触发",
            type="primary",
            use_container_width=True,
            disabled=trigger_btn_disabled,
            key="batch_trigger_btn"
        )

    with col_trigger2:
        if st.session_state.batch_trigger_results:
            if st.button("🗑️ 清空结果", use_container_width=True, key="batch_clear_results"):
                st.session_state.batch_trigger_results = None
                st.session_state.batch_pending_approvals = []
                st.session_state.batch_approve_results = None
                st.rerun()

    # 执行批量触发
    if trigger_btn and selected_services and batch_branch:
        st.session_state.batch_selected_services = selected_services
        st.session_state.batch_branch = batch_branch

        with st.status("正在批量触发 Pipeline...", expanded=True) as status:
            st.write(f"📋 准备触发 {len(selected_services)} 个服务到 {batch_branch} 分支...")

            success_list, failed_list = batch_trigger_pipelines(
                services=selected_services,
                branch=batch_branch,
                vcs_type=VCS_TYPE,
                organization=ORGANIZATION,
                api_token=CIRCLECI_API_TOKEN,
                max_workers=5  # 限制并发避免 API 限流
            )

            st.session_state.batch_trigger_results = {
                'success': success_list,
                'failed': failed_list
            }

            status.update(
                label=f"✅ 批量触发完成！成功: {len(success_list)}，失败: {len(failed_list)}",
                state="complete"
            )

    # === Section 2: 触发结果展示 ===
    if st.session_state.batch_trigger_results:
        results = st.session_state.batch_trigger_results
        success_list = results.get('success', [])
        failed_list = results.get('failed', [])

        st.subheader("📊 触发结果")

        # 统计卡片
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("✅ 成功", len(success_list))
        with stat_col2:
            st.metric("❌ 失败", len(failed_list))
        with stat_col3:
            st.metric("📊 总计", len(success_list) + len(failed_list))

        # 成功列表
        if success_list:
            with st.expander(f"✅ 成功触发的服务 ({len(success_list)} 个)", expanded=True):
                for item in success_list:
                    col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
                    with col_s1:
                        st.write(f"**服务:** `{item['service']}`")
                        st.write(f"**Pipeline Number:** #{item['pipeline_number']}")
                    with col_s2:
                        st.write(f"**Pipeline ID:**")
                        st.code(item['pipeline_id'][:16] + "...", language=None)
                    with col_s3:
                        if st.button("📊 监控", key=f"batch_monitor_{item['pipeline_id'][:8]}",
                                     use_container_width=True, type="primary"):
                            st.session_state.current_pipeline_id = item['pipeline_id']
                            st.session_state.pending_tab3_monitor = item['pipeline_id']
                            st.rerun()

        # 失败列表
        if failed_list:
            with st.expander(f"❌ 触发失败的服务 ({len(failed_list)} 个)", expanded=False):
                for item in failed_list:
                    st.error(f"**{item['service']}**: {item.get('error', 'Unknown error')}")
                    if item.get('status_code'):
                        st.caption(f"HTTP 状态码: {item.get('status_code')}")

        # === Section 3: 批量审批 ===
        if success_list:
            st.markdown("---")
            st.subheader("✅ 批量审批")

            # 扫描待审批按钮
            scan_col1, scan_col2 = st.columns([3, 1])
            with scan_col1:
                scan_btn = st.button("🔍 扫描待审批 Jobs", type="primary", use_container_width=True,
                                     key="batch_scan_pending")

            with scan_col2:
                if st.session_state.batch_pending_approvals:
                    if st.button("🗑️ 清空", use_container_width=True, key="batch_clear_pending"):
                        st.session_state.batch_pending_approvals = []
                        st.session_state.batch_approve_results = None
                        st.rerun()

            # 执行扫描
            if scan_btn:
                pipeline_ids = [item['pipeline_id'] for item in success_list]
                with st.spinner(f"正在扫描 {len(pipeline_ids)} 个 Pipeline 的待审批 Jobs..."):
                    pending_approvals = get_pending_approvals_for_batch(
                        pipeline_ids=pipeline_ids,
                        api_token=CIRCLECI_API_TOKEN,
                        target_env='preprod',
                        max_workers=10
                    )
                st.session_state.batch_pending_approvals = pending_approvals
                st.session_state.batch_scan_completed = True

            # 显示扫描结果
            if st.session_state.get('batch_scan_completed'):
                pending_approvals = st.session_state.batch_pending_approvals or []

                if pending_approvals and len(pending_approvals) > 0:
                    st.success(f"🎯 发现 {len(pending_approvals)} 个待审批 Jobs（Preprod 环境）")

                    # 待审批列表展示
                    with st.expander("📋 待审批列表", expanded=True):
                        for approval in pending_approvals:
                            col_a1, col_a2, col_a3 = st.columns([2, 2, 1])
                            with col_a1:
                                st.write(f"**服务:** `{approval['service_name']}`")
                                st.write(f"**Pipeline:** #{approval['pipeline_number']}")
                            with col_a2:
                                st.write(f"**Job:** {approval['job_name']}")
                                st.write(f"**Workflow:** {approval['workflow_name']}")
                            with col_a3:
                                # 单独审批按钮
                                if st.button("✅ 审批", key=f"batch_single_approve_{approval['job_id'][:8]}",
                                             use_container_width=True):
                                    with st.spinner("正在审批..."):
                                        single_success, single_failed = batch_approve_jobs(
                                            [approval], CIRCLECI_API_TOKEN
                                        )
                                        if single_success:
                                            st.success(f"✅ {approval['service_name']} 审批成功！")
                                            # 更新待审批列表
                                            st.session_state.batch_pending_approvals = [
                                                a for a in pending_approvals
                                                if a['job_id'] != approval['job_id']
                                            ]
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ 审批失败: {single_failed[0].get('error')}")

                    # 批量审批确认
                    st.markdown("---")
                    confirm_approve = st.checkbox(
                        f"⚠️ 我确认要批量审批 {len(pending_approvals)} 个 Jobs 到 Preprod 环境",
                        value=False,
                        key="batch_confirm_approve"
                    )

                    approve_btn_disabled = not confirm_approve or len(pending_approvals) == 0
                    if st.button("✅ 执行批量审批", type="primary", use_container_width=True,
                                 disabled=approve_btn_disabled, key="batch_approve_btn"):
                        with st.status("正在批量审批...", expanded=True) as status:
                            st.write(f"📋 准备审批 {len(pending_approvals)} 个 Jobs...")

                            approve_success, approve_failed = batch_approve_jobs(
                                pending_approvals=pending_approvals,
                                api_token=CIRCLECI_API_TOKEN,
                                max_workers=5
                            )

                            st.session_state.batch_approve_results = {
                                'success': approve_success,
                                'failed': approve_failed
                            }

                            # 更新待审批列表（移除成功审批的）
                            approved_ids = [s['job_name'] for s in approve_success]
                            st.session_state.batch_pending_approvals = [
                                a for a in pending_approvals
                                if a['job_name'] not in approved_ids
                            ]

                            status.update(
                                label=f"✅ 批量审批完成！成功: {len(approve_success)}，失败: {len(approve_failed)}",
                                state="complete"
                            )
                else:
                    # 没有待审批 Jobs 的友好提示
                    st.info("ℹ️ 当前没有发现待审批的 Preprod Jobs")
                    st.caption("💡 提示：Pipelines 可能还在构建中，请稍后再次扫描")

            # 显示审批结果
            if st.session_state.batch_approve_results:
                approve_results = st.session_state.batch_approve_results
                approve_success = approve_results.get('success', [])
                approve_failed = approve_results.get('failed', [])

                st.subheader("📊 审批结果")

                # 统计
                appr_col1, appr_col2, appr_col3 = st.columns(3)
                with appr_col1:
                    st.metric("✅ 审批成功", len(approve_success))
                with appr_col2:
                    st.metric("❌ 审批失败", len(approve_failed))
                with appr_col3:
                    st.metric("📊 总计", len(approve_success) + len(approve_failed))

                if approve_success:
                    with st.expander("✅ 审批成功的 Jobs", expanded=True):
                        for item in approve_success:
                            st.success(f"**{item['service']}** #{item['pipeline_number']} - {item['job_name']}")

                if approve_failed:
                    with st.expander("❌ 审批失败的 Jobs", expanded=False):
                        for item in approve_failed:
                            st.error(f"**{item['service']}** #{item['pipeline_number']} - {item['job_name']}: {item.get('error', 'Unknown error')}")
st.markdown("---")
st.markdown("""
### 💡 功能说明

#### 🎯 触发 Pipeline（Tab1）
1. 选择项目名称
2. 输入分支名称，或点击 **"🔍 查最新"** 查询该项目最近构建的分支
3. 从下拉列表选择分支，自动填入输入框
4. 点击 **"🚀 触发 Pipeline"** 按钮
5. 系统自动拼接完整路径：`github/demo-org/项目名`
6. 触发成功后可一键跳转 Tab3 监控

#### 📋 Pipeline 列表（Tab2）
1. 选择项目名称，可选填写分支名称（留空查所有分支）
2. 点击 **"🔍 查询 Pipelines"** 查看最近 10 条 Pipeline 记录
3. 查看每个 Pipeline 的分支、触发者、提交信息
4. **分支** 可点击文本框选中后 Ctrl+C 复制
5. 点击 **"📊 监控"** 按钮，自动跳转 Tab3 并填入 Pipeline ID

#### 📊 监控 Pipeline（Tab3）
1. 输入 Pipeline ID（或从 Tab1/Tab2 自动带入）
2. 点击 **"🔍 查看状态"** 获取当前状态
3. 查看 Workflows / Jobs 统计面板（成功/失败/运行中/待审批）
4. **Preprod 审批项自动展开**，可直接在页面内完成审批
5. 无需切换 Tab，审批后自动刷新状态

#### ✅ 审批面板（Tab3 内嵌）
- 待审批 Jobs 自动展示，Preprod 环境 Jobs 默认展开
- 填写 Pipeline ID 后自动查找所有 on_hold 状态的 Approval Job
- 点击 **"✅ 审批"** 按钮直接通过，无需跳转 CircleCI 页面

#### 🔍 Commit ID 搜索（Tab4）
1. 输入 Commit ID 前缀（至少4位，如 `8a688704`）
2. 默认搜索所有服务，也可取消勾选后手动选择特定服务
3. 点击 **"🔍 开始搜索"** 跨服务并发查询
4. 查看匹配的 Pipeline：服务名、分支、触发者、状态等
5. **Revision** 可点击复制完整 commit hash
6. 点击 **"📊 监控"** 按钮，自动跳转 Tab3 查看详情

#### 📦 批量操作（Tab5）
1. **快捷选择**: 点击「选择 demo-service-a 服务组」一键选择20个服务
2. **批量触发**: 选择多个服务，输入目标分支（默认 master）
3. 点击 **"🚀 开始批量触发"** 并发触发所有服务
4. 查看触发结果统计（成功/失败列表）
5. 点击 **"🔍 扫描待审批 Jobs"** 查找所有待审批的 Preprod Jobs
6. 点击 **"✅ 执行批量审批"** 一键审批所有待审批 Jobs
7. 支持单独审批每个 Job，或批量审批全部

#### 💡 简化输入说明
- ✅ **只需输入项目名**: `demo-service-b`（不是完整路径）
- ✅ **自动拼接**: 系统自动组合为 `github/demo-org/demo-service-b`
- ✅ **配置预设**: VCS 类型和组织名已在配置中预设
- ✅ **分支查最新**: 无需记忆分支名，一键查询最近使用过的分支

#### ⚙️ 注意事项
- 确保在 `config/users_config.json` 中配置了正确的 API Token
- Tab2 最多显示 10 条 Pipeline 记录，按最新时间排序
- Tab3 审批面板仅展示当前 Pipeline 的待审批 Jobs
- Tab4 搜索所有服务约需 10-15 秒，最多返回 100 条结果
- Tab5 批量触发使用5并发，约需 30-60 秒完成
- 可以在侧边栏查看最近 5 次触发的历史记录
""")
