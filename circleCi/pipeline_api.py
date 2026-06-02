"""
CircleCI Pipeline API 封装

提供 CircleCI API 调用的核心封装和数据获取逻辑。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

from modules.user_config_loader import build_circleci_headers

logger = logging.getLogger(__name__)

# CircleCI API 基础 URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 全局 Session（连接复用，Keep-Alive）
_http_session = requests.Session()


def get_http_session() -> requests.Session:
    """获取全局 HTTP Session"""
    return _http_session


def call_circleci_api(
    endpoint: str,
    method: str = 'GET',
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    api_token: Optional[str] = None
) -> tuple:
    """调用 CircleCI API

    Args:
        endpoint: API 端点路径（不含基础 URL）
        method: HTTP 方法，GET 或 POST
        data: POST 请求的 JSON 数据
        params: GET 请求的查询参数
        api_token: API Token（可选，默认使用全局变量）

    Returns:
        tuple: (response, error_info)
        - response: requests.Response 对象（仅在成功时非 None）
        - error_info: 错误信息字典，包含 'error', 'status_code', 'url' 等字段

    约定:
        - 若 error_info 非 None，response 视为不可用，调用方应立即处理错误
        - 仅当 error_info 为 None 且 response 非 None 时，response 才可安全使用
    """
    url = f"{CIRCLECI_API_BASE}/{endpoint}"
    headers = build_circleci_headers(api_token)

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


def _fetch_workflow_jobs_concurrent(
    workflow_ids: list,
    api_token: Optional[str] = None
) -> dict:
    """并发获取多个 workflow 的 jobs"""
    def fetch_one(wid):
        resp, error = call_circleci_api(f"workflow/{wid}/job", api_token=api_token)
        if error:
            return []
        if resp and resp.status_code == 200:
            return resp.json().get('items', [])
        return []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {wid: executor.submit(fetch_one, wid) for wid in workflow_ids}
        return {wid: future.result() for wid, future in futures.items()}


def search_pipelines_by_revision(
    revision_prefix: str,
    services: list,
    vcs_type: str,
    organization: str,
    api_token: str,
    max_pipelines_per_service: int = 20,
    show_progress: bool = False
) -> tuple:
    """跨多个服务并发搜索匹配 revision 前缀的 Pipeline

    Args:
        revision_prefix: commit ID 前缀（部分匹配，如 "8a688704")
        services: 要搜索的服务名称列表
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
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
            project_slug = f"{vcs_type}/{organization}/{service_name}"
            response, error = call_circleci_api(
                f"project/{project_slug}/pipeline",
                api_token=api_token
            )

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
        from circleCi.pipeline_data import get_all_approvals_info
        from circleCi.monitoring import get_pipeline_workflows

        # 使用 monitoring 模块的 get_pipeline_workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=api_token, silent=True)

        all_approvals_info = {}
        if workflows:
            from circleCi.pipeline_data import get_all_approvals_info_with_workflows
            all_approvals_info = get_all_approvals_info_with_workflows(
                workflows, _fetch_workflow_jobs_concurrent([w.get('id') for w in workflows if w.get('id')], api_token=api_token)
            )

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


def fetch_recent_branches(
    project_slug: str,
    api_token: str,
    max_count: int = 8
) -> tuple:
    """查询项目最近的 pipelines，提取不重复的分支名列表。

    Args:
        project_slug: 项目标识
        api_token: API Token
        max_count: 最大返回数量

    Returns:
        tuple: (branches, error_info) - 分支名列表和错误信息
    """
    response, error = call_circleci_api(
        f"project/{project_slug}/pipeline",
        api_token=api_token
    )
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


def _fetch_all_pipelines_with_pagination(
    project_slug: str,
    api_token: str,
    max_pages: int = 3,
    show_progress: bool = False
) -> tuple:
    """获取多页 pipeline 数据（解决 CircleCI API 分页限制）

    Args:
        project_slug: 项目标识
        api_token: API Token
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

        response, error = call_circleci_api(
            f"project/{project_slug}/pipeline",
            params=params,
            api_token=api_token
        )

        if error:
            return all_pipelines, error

        if not response or response.status_code != 200:
            break

        data = response.json()
        items = data.get('items', [])
        all_pipelines.extend(items)

        if show_progress:
            import streamlit as st
            st.caption(f"📦 第 {page_num + 1} 页: {len(items)} 条，累计 {len(all_pipelines)} 条")

        page_token = data.get('next_page_token')
        if not page_token:
            break

    return all_pipelines, None


def _fallback_filter_by_branch(
    all_pipelines: list,
    branch: str,
    show_progress: bool = False
) -> list:
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
            import streamlit as st
            st.caption(f"✅ 精确匹配找到 {len(matched)} 个 Pipeline")
        return matched

    # 精确匹配失败，尝试模糊匹配（包含）
    matched = [
        p for p in all_pipelines
        if branch_lower in p.get('vcs', {}).get('branch', '').lower()
    ]

    if matched and show_progress:
        import streamlit as st
        st.caption(f"✨ 模糊匹配找到 {len(matched)} 个 Pipeline")

    return matched


def query_pipelines(
    project_slug: str,
    branch: Optional[str] = None,
    api_token: Optional[str] = None,
    show_progress: bool = False
) -> tuple:
    """查询项目的 Pipeline 列表

    策略：当指定分支时，先尝试 API 过滤；如果返回空则回退到查询全部后本地过滤

    Args:
        project_slug: 项目标识
        branch: 分支名（可选，会自动 trim）
        api_token: API Token
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

    response, error = call_circleci_api(
        f"project/{project_slug}/pipeline",
        params=params,
        api_token=api_token
    )

    if error:
        return None, error

    pipelines = []
    if response and response.status_code == 200:
        data = response.json()
        pipelines = data.get('items', [])

    # 如果指定了分支但 API 返回空，回退到查询全部后本地过滤
    if branch and len(pipelines) == 0:
        if show_progress:
            import streamlit as st
            st.info(f"💡 指定分支 '{branch}' API 查询返回空，尝试本地过滤...")

        # 获取多页数据（最多3页约60条）
        all_pipelines, fallback_error = _fetch_all_pipelines_with_pagination(
            project_slug, api_token, max_pages=3, show_progress=show_progress
        )

        if fallback_error:
            return None, fallback_error

        if show_progress:
            import streamlit as st
            st.caption(f"📦 共获取 {len(all_pipelines)} 个 Pipeline 用于本地过滤")

        # 本地过滤
        pipelines = _fallback_filter_by_branch(all_pipelines, branch, show_progress)

        if len(pipelines) == 0 and show_progress:
            import streamlit as st
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
    from circleCi.pipeline_data import get_preprod_approval_info

    def fetch_pipeline_data(p, idx):
        """获取单个 pipeline 的完整数据"""
        pipeline_id = p.get('id')
        pipeline_number = p.get('number')

        if show_progress:
            logger.info(f"  [{idx+1}/{total}] Processing Pipeline #{pipeline_number}")

        # 获取 preprod approval 信息
        preprod_approval_info = get_preprod_approval_info(
            pipeline_id, project_name, api_token=api_token
        )

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