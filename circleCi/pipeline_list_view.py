"""
Tab 2: Pipeline 列表 UI

提供 Pipeline 列表查询和展示功能。
"""
import streamlit as st

from circleCi.pipeline_api import query_pipelines
from circleCi.pipeline_display import convert_utc_to_beijing, format_time_ago


def render_pipeline_list_tab(
    project_root,
    vcs_type: str,
    organization: str,
    default_project: str,
    api_token: str
) -> None:
    """渲染 Pipeline 列表 Tab UI

    Args:
        project_root: 项目根路径
        vcs_type: VCS 类型
        organization: 组织名称
        default_project: 默认项目名
        api_token: CircleCI API Token
    """
    st.header("📋 Pipeline 列表")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    service_list = [default_project]

    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list = services
    except Exception as e:
        import logging
        logging.warning(f"Could not load services list: {e}")

    col_list1, col_list2 = st.columns([2, 1])

    with col_list1:
        try:
            default_index = service_list.index(st.session_state.query_project)
        except (ValueError, AttributeError):
            default_index = service_list.index(default_project) if default_project in service_list else 0

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
        if st.button("🔍 查询 Pipelines", type="primary", use_container_width=True):
            _handle_query_submit(
                query_project=query_project,
                query_branch=query_branch,
                vcs_type=vcs_type,
                organization=organization,
                api_token=api_token
            )

    with col_btn2:
        if st.session_state.queried_pipelines:
            if st.button("🗑️ 清空", use_container_width=True, key="clear_pipelines_list"):
                st.session_state.queried_pipelines = None
                st.session_state.query_project_slug = None
                st.rerun()

    # 显示查询结果
    _render_query_results()


def _handle_query_submit(
    query_project: str,
    query_branch: str,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """处理查询提交

    Args:
        query_project: 项目名
        query_branch: 分支名
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
    """
    st.session_state.query_project = query_project
    st.session_state.query_branch = query_branch

    if not query_project:
        st.warning("⚠️ 请先选择项目名称")
        return

    full_slug = f"{vcs_type}/{organization}/{query_project}"

    with st.spinner("🚀 正在查询 Pipeline 列表（预计 5-10 秒）..."):
        pipelines, query_error = query_pipelines(
            full_slug,
            query_branch if query_branch else None,
            api_token=api_token,
            show_progress=True
        )

    if query_error:
        st.error(f"❌ 查询失败: {query_error.get('error', 'Unknown error')}")
        if query_error.get('status_code'):
            st.caption(f"HTTP 状态码: {query_error.get('status_code')}")
        st.info(f"项目路径: {full_slug}")
        if query_branch:
            st.warning(f"💡 分支 '{query_branch}' 可能不存在或名称过长。建议留空分支查询所有记录，然后在列表中查找。")
        st.session_state.queried_pipelines = None
    elif pipelines:
        st.session_state.queried_pipelines = pipelines
        st.session_state.query_project_slug = full_slug
        st.success(f"✅ 找到 {len(pipelines)} 个 Pipelines")
    else:
        st.session_state.queried_pipelines = None
        st.error("❌ 查询失败或未找到 Pipeline")
        st.info(f"项目路径: {full_slug}")


def _render_query_results() -> None:
    """渲染查询结果列表"""
    if not st.session_state.queried_pipelines:
        return

    pipelines = st.session_state.queried_pipelines
    st.info(f"📊 显示 {len(pipelines)} 个 Pipeline（项目: {st.session_state.query_project_slug}）")

    for i, p in enumerate(pipelines):
        _render_pipeline_item(p, i)


def _render_pipeline_item(p: dict, idx: int) -> None:
    """渲染单个 Pipeline 条目

    Args:
        p: Pipeline 数据字典
        idx: 索引
    """
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
            st.text_input("分支", value=branch_val, disabled=True, label_visibility="collapsed", key=f"branch_{idx}_{p['number']}")
            st.text(f"Revision: {revision_display}")
            st.text(f"触发者: {p['actor']}")
            st.text(f"提交: {commit_val}")

        with col_p3:
            if st.button("📊 监控", key=f"monitor_{idx}", use_container_width=True, type="primary"):
                st.session_state.current_pipeline_id = p['id']
                st.session_state.pending_tab3_monitor = p['id']
                st.rerun()

        # 显示 Preprod Approval 信息
        _render_preprod_approval(p)

        st.caption(f"创建时间: {p['created_at']}")
        if p['revision']:
            st.caption(f"Revision: {p['revision'][:8]}")


def _render_preprod_approval(p: dict) -> None:
    """渲染 Preprod Approval 信息

    Args:
        p: Pipeline 数据字典
    """
    preprod_approval = p.get('preprod_approval')
    if not preprod_approval:
        st.markdown("---")
        st.caption("ℹ️ 此 Pipeline 没有 Preprod Approval 步骤")
        return

    st.markdown("---")
    st.markdown("**🎯 Preprod Approval 信息:**")

    approval_status = preprod_approval.get('status', 'unknown')

    if approval_status == 'error':
        st.error(f"⚠️ 获取审批信息失败: {preprod_approval.get('error', 'Unknown error')}")
        return

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

    # 待审批时提示跳转
    if approval_status in ('pending', 'on_hold') and p.get('preprod_approval', {}).get('job_name'):
        st.warning("⏸️ 此 Pipeline 有待审批 Job，可直接前往监控页审批")