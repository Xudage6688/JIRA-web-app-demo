"""
CircleCI Pipeline 业务逻辑模块
从 pages/4_🚀_CircleCI_Pipeline.py 提取的 API 调用和业务逻辑函数
"""
from typing import Dict, Any, Optional, List, Tuple
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

# CircleCI API 基础 URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 全局 Session（连接复用）
_http_session = requests.Session()

# 环境优先级列表
ENVIRONMENT_PRIORITIES = ['preprod', 'staging', 'dev', 'uat', 'prod', 'production']


def call_circleci_api(
    endpoint: str,
    api_token: str,
    method: str = 'GET',
    data: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Tuple[Optional[requests.Response], Optional[Dict[str, Any]]]:
    """
    调用 CircleCI API

    Args:
        endpoint: API 端点路径（不含基础 URL）
        api_token: CircleCI API Token
        method: HTTP 方法，GET 或 POST
        data: POST 请求的 JSON 数据
        params: GET 请求的查询参数

    Returns:
        tuple: (response, error_info)
    """
    url = f"{CIRCLECI_API_BASE}/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Circle-Token": api_token
    }

    try:
        if method == 'GET':
            response = _http_session.get(url, headers=headers, params=params, timeout=30)
        elif method == 'POST':
            response = _http_session.post(url, headers=headers, json=data, timeout=30)
        else:
            return None, {'error': 'Invalid method', 'url': url}

        if 400 <= response.status_code < 500:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', response.text[:200])
            except Exception:
                error_msg = response.text[:200]
            return None, {'status_code': response.status_code, 'error': error_msg, 'url': url}

        if response.status_code >= 500:
            return None, {'error': f'Server error: {response.status_code}', 'url': url}

        return response, None
    except Exception as e:
        return None, {'error': str(e), 'url': url}


def fetch_recent_branches(project_slug: str, api_token: str, max_count: int = 8) -> Tuple[List[str], Optional[Dict]]:
    """查询项目最近的 pipelines，提取不重复的分支名列表"""
    response, error = call_circleci_api(f"project/{project_slug}/pipeline", api_token)
    if error:
        return [], error
    if not response or response.status_code != 200:
        return [], {'error': 'Failed to fetch pipelines'}

    items = response.json().get('items', [])
    seen = []
    for item in items[:max_count * 2]:
        branch = item.get('vcs', {}).get('branch')
        if branch and branch not in seen:
            seen.append(branch)
        if len(seen) >= max_count:
            break
    return seen, None


def get_workflow_jobs(workflow_id: str, api_token: str) -> Tuple[List[Dict], Optional[Dict]]:
    """获取 workflow 的 jobs 列表"""
    response, error = call_circleci_api(f"workflow/{workflow_id}/job", api_token)
    if error:
        return [], error
    if response and response.status_code == 200:
        return response.json().get('items', []), None
    return [], None


def approve_job(workflow_id: str, approval_request_id: str, api_token: str) -> Tuple[bool, Optional[str]]:
    """批准 workflow 中的 approval job"""
    response, error = call_circleci_api(
        f"workflow/{workflow_id}/approve/{approval_request_id}", api_token, method='POST'
    )
    if error:
        return False, error.get('error', 'Unknown error')
    if response and response.status_code == 200:
        return True, None
    return False, f"Unexpected status: {response.status_code if response else 'No response'}"


def format_duration(started_at: str, stopped_at: Optional[str] = None) -> str:
    """格式化运行时长"""
    try:
        start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        end_str = stopped_at or datetime.utcnow().isoformat()
        end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        duration = (end - start).total_seconds()

        if duration < 60:
            return f"{int(duration)}s"
        elif duration < 3600:
            return f"{int(duration // 60)}m {int(duration % 60)}s"
        else:
            return f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m"
    except Exception:
        return "N/A"


def convert_utc_to_beijing(utc_time_str: str) -> str:
    """将 UTC 时间转换为北京时间"""
    try:
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        beijing_time = utc_time.astimezone()
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return utc_time_str


def format_time_ago(utc_time_str: str) -> str:
    """格式化为相对时间"""
    try:
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        now = datetime.now(utc_time.tzinfo)
        diff = now - utc_time

        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"
    except Exception:
        return "N/A"


def detect_environment_from_job_name(job_name: str) -> Optional[str]:
    """从 job 名称检测环境"""
    job_lower = job_name.lower()
    for env in ENVIRONMENT_PRIORITIES:
        if env in job_lower:
            return env
    return None