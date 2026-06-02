"""
Tab 3: 监控 Pipeline UI

提供 Pipeline 状态监控、工作流展示和审批功能。
"""
import streamlit as st
import time

from circleCi.monitoring import get_pipeline_status, get_pipeline_workflows
from circleCi.pipeline_api import _fetch_workflow_jobs_concurrent
from circleCi.pipeline_data import approve_job
from circleCi.pipeline_display import (
    convert_utc_to_beijing,
    format_duration,
    format_time_ago,
    small_metric
)
from circleCi.monitoring import format_status


def render_monitor_tab(api_token: str) -> None:
    """渲染监控 Pipeline Tab UI

    Args:
        api_token: CircleCI API Token
    """
    st.header("📊 监控 Pipeline")

    _render_pipeline_input(api_token)


def _render_pipeline_input(api_token: str) -> None:
    """渲染 Pipeline 输入和主要展示区

    Args:
        api_token: API Token
    """
    # Pipeline ID 查询
    _auto_pipeline_id = (
        st.session_state.pending_tab3_monitor or
        st.session_state.current_pipeline_id or
        ""
    )
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

    # 判断是否需要重新获取数据
    _cached = st.session_state.get('tab3_cached_pipeline_id') == pipeline_id_input
    _needs_refetch = (check_status_btn or _auto_trigger) and pipeline_id_input

    if _needs_refetch:
        _fetch_and_display_pipeline(pipeline_id_input, api_token)
    elif _cached and pipeline_id_input:
        _display_cached_pipeline(pipeline_id_input, api_token=api_token)
    elif pipeline_id_input:
        st.info("💡 点击「🔍 查看状态」或切换 Tab 获取最新数据")


def _fetch_and_display_pipeline(pipeline_id: str, api_token: str) -> None:
    """获取并展示 Pipeline 数据

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
    """
    with st.spinner("正在获取详细状态..."):
        pipeline_data = get_pipeline_status(pipeline_id, api_token=api_token)

        if pipeline_data:
            st.session_state.tab3_cached_pipeline_id = pipeline_id
            st.session_state.tab3_pipeline_data = pipeline_data

            st.success("✅ 状态获取成功")

            _render_pipeline_info(pipeline_data)
            st.markdown("---")

            _precheck_pending_jobs(pipeline_id, api_token)
            _render_git_commit_info(pipeline_data)

            workflows = get_pipeline_workflows(pipeline_id, api_token=api_token)
            _render_workflows_section(workflows, api_token)

            st.markdown("---")
            st.subheader("✅ 审批面板")
            _render_approval_panel(pipeline_id, api_token)
        else:
            st.error("❌ 无法获取 Pipeline 状态")


def _display_cached_pipeline(pipeline_id: str, api_token: str) -> None:
    """从缓存展示 Pipeline 数据

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
    """
    pipeline_data = st.session_state.tab3_pipeline_data
    workflows = st.session_state.tab3_workflows
    wf_jobs_map = st.session_state.tab3_wf_jobs_map
    pending_approvals = st.session_state.tab3_pending_approvals

    _render_pipeline_info(pipeline_data)
    st.markdown("---")
    st.subheader("📝 Git 提交信息")
    _render_git_commit_info(pipeline_data)

    st.markdown("---")
    if workflows:
        _render_workflows_expanders(workflows, wf_jobs_map)
    else:
        st.info("暂无 Workflows 信息")

    st.markdown("---")
    st.subheader("✅ 审批面板")
    _render_approval_panel_content(pending_approvals, api_token=api_token)


def _render_pipeline_info(pipeline_data: dict) -> None:
    """渲染 Pipeline 基本信息

    Args:
        pipeline_data: Pipeline 数据字典
    """
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


def _precheck_pending_jobs(pipeline_id: str, api_token: str) -> None:
    """预检并显示待审批 Jobs

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
    """
    try:
        precheck_wfs = get_pipeline_workflows(pipeline_id, api_token=api_token, silent=True)
        if precheck_wfs:
            precheck_wf_ids = [w.get('id') for w in precheck_wfs if w.get('id')]
            precheck_jobs_map = _fetch_workflow_jobs_concurrent(precheck_wf_ids, api_token=api_token)
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


def _render_git_commit_info(pipeline_data: dict) -> None:
    """渲染 Git 提交信息

    Args:
        pipeline_data: Pipeline 数据字典
    """
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


def _render_workflows_section(workflows: list, api_token: str) -> None:
    """渲染 Workflows 区域

    Args:
        workflows: Workflow 列表
        api_token: API Token
    """
    if workflows:
        st.subheader(f"🔄 Workflows ({len(workflows)})")
        wf_ids = [w.get('id') for w in workflows if w.get('id')]
        wf_jobs_map = _fetch_workflow_jobs_concurrent(wf_ids, api_token=api_token)

        # 缓存到 session_state
        st.session_state.tab3_workflows = workflows
        st.session_state.tab3_wf_jobs_map = wf_jobs_map

        _render_workflows_expanders(workflows, wf_jobs_map)
    else:
        st.info("暂无 Workflows 信息")
        st.session_state.tab3_workflows = []
        st.session_state.tab3_wf_jobs_map = {}


def _render_workflows_expanders(workflows: list, wf_jobs_map: dict) -> None:
    """渲染 Workflows 展开列表

    Args:
        workflows: Workflow 列表
        wf_jobs_map: workflow_id -> jobs 列表的映射
    """
    for idx, workflow in enumerate(workflows):
        wf_id = workflow.get('id', 'N/A')
        wf_name = workflow.get('name', 'Unknown')
        wf_status = workflow.get('status', 'unknown')
        disp_txt, emoji = format_status(wf_status)
        started_at = workflow.get('started_at')
        stopped_at = workflow.get('stopped_at')
        duration_str = format_duration(started_at, stopped_at) if started_at else 'N/A'

        with st.expander(f"{emoji} **{wf_name}** - {disp_txt} (⏱️ {duration_str})", expanded=(idx == 0)):
            _render_workflow_detail(workflow, wf_jobs_map, disp_txt, emoji, started_at, stopped_at)


def _render_workflow_detail(
    workflow: dict,
    wf_jobs_map: dict,
    disp_txt: str,
    emoji: str,
    started_at: str,
    stopped_at: str
) -> None:
    """渲染单个 Workflow 详情

    Args:
        workflow: Workflow 数据
        wf_jobs_map: jobs 映射
        disp_txt: 状态描述
        emoji: 状态表情
        started_at: 开始时间
        stopped_at: 结束时间
    """
    wf_id = workflow.get('id', 'N/A')

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
        _render_jobs_stats(jobs)
        _render_jobs_list(jobs)
    else:
        st.info("暂无 Jobs 信息")


def _render_jobs_stats(jobs: list) -> None:
    """渲染 Jobs 统计

    Args:
        jobs: Jobs 列表
    """
    stats = {'success': 0, 'running': 0, 'failed': 0, 'on_hold': 0, 'other': 0}
    for j in jobs:
        s = j.get('status', 'unknown')
        if s == 'success':
            stats['success'] += 1
        elif s in ['running', 'queued']:
            stats['running'] += 1
        elif s in ['failed', 'failing']:
            stats['failed'] += 1
        elif s == 'on_hold':
            stats['on_hold'] += 1
        else:
            stats['other'] += 1

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric("✅ 成功", stats['success'])
    sc2.metric("🔄 运行中", stats['running'])
    sc3.metric("❌ 失败", stats['failed'])
    sc4.metric("⏸️ 待审批", stats['on_hold'])
    sc5.metric("📊 总计", len(jobs))


def _render_jobs_list(jobs: list) -> None:
    """渲染 Jobs 列表

    Args:
        jobs: Jobs 列表
    """
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


def _render_approval_panel(pipeline_id: str, api_token: str) -> None:
    """渲染审批面板

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
    """
    pending_approvals = []
    try:
        approval_wfs = get_pipeline_workflows(pipeline_id, api_token=api_token, silent=True)
        if approval_wfs:
            wf_ids = [w.get('id') for w in approval_wfs if w.get('id')]
            aj_map = _fetch_workflow_jobs_concurrent(wf_ids, api_token=api_token)
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

    _render_approval_panel_content(pending_approvals, api_token=api_token)


def _render_approval_panel_content(pending_approvals: list, api_token: str = '') -> None:
    """渲染审批面板内容

    Args:
        pending_approvals: 待审批列表
        api_token: API Token
    """
    if pending_approvals:
        st.success(f"🎯 当前 Pipeline 有 {len(pending_approvals)} 个待审批 Jobs")
        for job in pending_approvals:
            _render_approval_item(job, api_token=api_token)
    else:
        st.info("ℹ️ 当前 Pipeline 无待审批 Jobs")


def _render_approval_item(job: dict, api_token: str = '') -> None:
    """渲染单个审批项

    Args:
        job: Job 数据
        api_token: API Token
    """
    wf_name = job.get('_workflow_name', '')
    job_name = job.get('name', '').lower()
    dur = format_duration(job.get('started_at'), job.get('stopped_at'))
    is_preprod = 'preprod' in job_name
    should_expand = is_preprod or len(st.session_state.tab3_pending_approvals) == 1

    with st.expander(f"✋ {job.get('name')} — {wf_name} — ⏱️ {dur}", expanded=should_expand):
        ac1, ac2 = st.columns([3, 1])
        with ac1:
            st.write(f"**Job ID:** `{job.get('id')}`")
            st.write(f"**Workflow:** {wf_name}")
            st.write(f"**Approval Request ID:** `{job.get('approval_request_id')}`")
        with ac2:
            _render_approve_button(job, api_token=api_token)


def _render_approve_button(job: dict, api_token: str = '') -> None:
    """渲染审批按钮

    Args:
        job: Job 数据
        api_token: API Token
    """
    pipeline_id = st.session_state.tab3_cached_pipeline_id
    ak = f"inline_approve_{job.get('id')}"

    if st.button("✅ 审批", key=ak, type="primary", use_container_width=True):
        with st.spinner("正在审批..."):
            res = approve_job(job.get('_workflow_id'), job.get('approval_request_id'), api_token=api_token)
            if res.get('success'):
                st.success("✅ 审批成功！")
                st.balloons()
                time.sleep(1.5)
                st.session_state.pending_tab3_monitor = pipeline_id
                st.rerun()
            else:
                st.error(f"❌ 审批失败: {res.get('error')}")