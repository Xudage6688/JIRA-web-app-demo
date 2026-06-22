"""
Tab 4: Commit ID 搜索 UI

提供跨服务搜索匹配 Commit ID 的 Pipeline 功能。
"""
import streamlit as st

from circleCi.pipeline_api import search_pipelines_by_revision
from circleCi.pipeline_display import convert_utc_to_beijing, format_time_ago
from circleCi.pipeline_config import ENVIRONMENT_PRIORITIES
from modules.components import copyable_text


def render_commit_search_tab(
    project_root,
    default_project: str,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """渲染 Commit ID 搜索 Tab UI

    Args:
        project_root: 项目根路径
        default_project: 默认项目名
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: CircleCI API Token
    """
    st.header("🔍 Commit ID 搜索")
    st.info("💡 输入 Commit ID 前缀（如 8a688704），跨多个服务并发搜索匹配的 Pipeline")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    all_services = [default_project]
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                all_services = [line.strip() for line in f if line.strip()]
    except Exception:
        pass

    _render_search_input(all_services, vcs_type, organization, api_token)


def _render_search_input(
    all_services: list,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """渲染搜索输入区域

    Args:
        all_services: 所有服务列表
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
    """
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

    if not search_all:
        selected_services = st.multiselect(
            "选择要搜索的服务",
            options=all_services,
            default=st.session_state.commit_search_services,
            help="可以多选，或直接输入关键字快速过滤"
        )
    else:
        selected_services = all_services

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        search_btn = st.button("🔍 开始搜索", type="primary", use_container_width=True)
    with col_btn2:
        if st.session_state.commit_search_results:
            if st.button("🗑️ 清空结果", use_container_width=True, key="clear_commit_search"):
                st.session_state.commit_search_results = None
                st.session_state.commit_search_prefix = ""
                st.rerun()

    if search_btn:
        _handle_search(commit_prefix, selected_services, vcs_type, organization, api_token, search_all)

    # 显示已缓存的搜索结果
    if st.session_state.commit_search_results:
        _render_search_results()


def _handle_search(
    commit_prefix: str,
    selected_services: list,
    vcs_type: str,
    organization: str,
    api_token: str,
    search_all: bool = True
) -> None:
    """处理搜索请求

    Args:
        commit_prefix: Commit ID 前缀
        selected_services: 选中的服务列表
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
        search_all: 是否搜索所有服务（搜索全部时限制20条，选特定服务时放宽到100）
    """
    st.session_state.commit_search_prefix = commit_prefix

    if not commit_prefix or len(commit_prefix.strip()) < 4:
        st.warning("⚠️ 请输入至少4位的 Commit ID 前缀")
        return

    if not selected_services:
        st.warning("⚠️ 请至少选择一个服务")
        return

    max_pipelines = 20 if search_all else 100
    hint = "搜索所有服务" if search_all else "指定服务"
    with st.spinner(f"🔍 正在搜索 {len(selected_services)} 个服务 ({hint}, 每个最多查 {max_pipelines} 条)..."):
        results, errors, debug_info = search_pipelines_by_revision(
            commit_prefix,
            selected_services,
            vcs_type=vcs_type,
            organization=organization,
            api_token=api_token,
            max_pipelines_per_service=max_pipelines
        )

    # 显示错误信息
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
        if debug_info:
            with st.expander("🔬 诊断信息：前3个服务的 Pipeline Revision 样本"):
                for svc, samples in debug_info.items():
                    st.caption(f"**{svc}** (最近 {len(samples)} 个 pipeline revision):")
                    for s in samples:
                        st.code(s or "(空)", language="text")
                    st.divider()
        st.info("💡 建议：检查 commit ID 是否正确，或尝试更短的前缀")


def _render_search_results() -> None:
    """渲染搜索结果列表"""
    results = st.session_state.commit_search_results
    st.info(f"📊 显示 {len(results)} 个结果（Commit ID: {st.session_state.commit_search_prefix}）")

    for i, r in enumerate(results):
        _render_search_result_item(r, i)


def _render_search_result_item(r: dict, idx: int) -> None:
    """渲染单个搜索结果

    Args:
        r: 结果数据
        idx: 索引
    """
    service_name = r.get('service_name', 'Unknown')
    pipeline_number = r.get('number', 'N/A')
    state = r.get('state', 'unknown')
    branch = r.get('branch') or 'N/A'
    actor = r.get('actor', 'Unknown')
    revision = r.get('revision', 'N/A')
    created_at = r.get('created_at')

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
            copyable_text("Revision:", revision, f"copy_rev_{idx}")
            st.write(f"**分支:** {branch}")
            st.write(f"**触发者:** {actor}")
            commit_subject = r.get('commit_subject')
            if commit_subject:
                st.write(f"**提交:** {commit_subject[:50]}...")

        with col_r3:
            if st.button("📊 监控", key=f"commit_monitor_{idx}", use_container_width=True, type="primary"):
                st.session_state.current_pipeline_id = r.get('id')
                st.session_state.pending_tab3_monitor = r.get('id')
                st.rerun()

        # 时间信息
        if created_at:
            beijing_time = convert_utc_to_beijing(created_at)
            time_ago = format_time_ago(created_at)
            st.caption(f"创建时间: {beijing_time} ({time_ago})")

        # 环境审批信息
        _render_env_approvals(r)


def _render_env_approvals(r: dict) -> None:
    """渲染环境审批信息

    Args:
        r: 结果数据
    """
    all_approvals = r.get('all_approvals', {})
    if not all_approvals:
        st.markdown("---")
        st.caption("ℹ️ 此 Pipeline 没有环境审批步骤")
        return

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
        sorted_envs = [e for e in sorted_envs if e != 'error']

    # 使用列布局显示环境
    env_cols = st.columns(min(3, len(sorted_envs)))

    for idx, env in enumerate(sorted_envs):
        approval_info = all_approvals[env]
        col = env_cols[idx % 3]

        with col:
            _render_env_approval_item(env, approval_info, env_icons)

    # 待审批环境提示
    pending_envs = [
        env for env, info in all_approvals.items()
        if info.get('status') in ('pending', 'on_hold')
    ]
    if pending_envs:
        st.warning(f"⏸️ 此 Pipeline 有待审批环境: {', '.join([e.upper() for e in pending_envs])}，点击上方「📊 监控」按钮前往审批")


def _render_env_approval_item(env: str, approval_info: dict, env_icons: dict) -> None:
    """渲染单个环境审批项

    Args:
        env: 环境名
        approval_info: 审批信息
        env_icons: 环境图标映射
    """
    env_icon = env_icons.get(env, '📦')
    approval_status = approval_info.get('status', 'unknown')

    if approval_status == 'approved':
        status_container = st.success
    elif approval_status in ('pending', 'on_hold'):
        status_container = st.warning
    elif approval_status == 'error':
        status_container = st.error
    else:
        status_container = st.info

    approved_by = approval_info.get('approved_by', 'N/A')
    approved_at = approval_info.get('approved_at')

    if approval_status == 'approved':
        status_container(f"{env_icon} **{env.upper()}**: ✅ 已审批")
        st.caption(f"👤 {approved_by}")
        if approved_at:
            beijing_time_approval = convert_utc_to_beijing(approved_at)
            st.caption(f"⏰ {beijing_time_approval}")
    elif approval_status in ('pending', 'on_hold'):
        status_container(f"{env_icon} **{env.upper()}**: ⏳ 待审批")
    elif approval_status == 'error':
        status_container(f"{env_icon} **{env.upper()}**: ⚠️ 获取失败")
    else:
        status_container(f"{env_icon} **{env.upper()}**: {approval_status}")

    job_name = approval_info.get('job_name')
    if job_name:
        st.caption(f"📋 {job_name}")