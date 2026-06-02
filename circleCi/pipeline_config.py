"""
CircleCI Pipeline 配置和状态管理

提供 CircleCI 配置加载、session state 初始化等基础设施。
"""
from typing import Optional


# CircleCI API 基础 URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 环境优先级
ENVIRONMENT_PRIORITIES = ['preprod', 'staging', 'dev', 'uat', 'prod', 'production']


def init_session_state(default_project: str, default_branch: str) -> None:
    """初始化 session state 变量

    Args:
        default_project: 默认项目名
        default_branch: 默认分支名
    """
    import streamlit as st

    # 基础状态
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

    # 用户信息缓存
    if 'user_cache' not in st.session_state:
        st.session_state.user_cache = {}

    # Tab1: Trigger 状态
    if 'trigger_project' not in st.session_state:
        st.session_state.trigger_project = default_project
    if 'trigger_branch' not in st.session_state:
        st.session_state.trigger_branch = default_branch
    if 'recent_branches' not in st.session_state:
        st.session_state.recent_branches = []

    # Tab2: Pipeline List 状态
    if 'query_project' not in st.session_state:
        st.session_state.query_project = default_project
    if 'query_branch' not in st.session_state:
        st.session_state.query_branch = ""

    # Tab3: Monitor 状态
    if 'pending_tab3_monitor' not in st.session_state:
        st.session_state.pending_tab3_monitor = None

    # Tab4: Commit Search 状态
    if 'commit_search_results' not in st.session_state:
        st.session_state.commit_search_results = None
    if 'commit_search_prefix' not in st.session_state:
        st.session_state.commit_search_prefix = ""
    if 'commit_search_services' not in st.session_state:
        st.session_state.commit_search_services = []

    # Tab5: Batch Operations 状态
    if 'batch_trigger_results' not in st.session_state:
        st.session_state.batch_trigger_results = None
    if 'batch_pending_approvals' not in st.session_state:
        st.session_state.batch_pending_approvals = []
    if 'batch_approve_results' not in st.session_state:
        st.session_state.batch_approve_results = None
    if 'batch_selected_services' not in st.session_state:
        st.session_state.batch_selected_services = []
    if 'batch_branch' not in st.session_state:
        st.session_state.batch_branch = 'master'
    if 'batch_scan_completed' not in st.session_state:
        st.session_state.batch_scan_completed = False


def get_services_list(project_root, default_project: str) -> list:
    """加载服务列表

    Args:
        project_root: 项目根路径
        default_project: 默认项目

    Returns:
        服务名称列表
    """
    services_file = project_root / "config" / "circleci-services.txt"
    service_list = [default_project]

    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list = services
    except Exception:
        pass

    return service_list