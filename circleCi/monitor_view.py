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
from circleCi.auto_approve import (
    find_pending_preprod_approvals,
    auto_approve_jobs,
    get_preprod_auto_mode_status,
    PREPROD_AUTO_POLLING,
    PREPROD_AUTO_DEPLOY_SUCCESS,
    PREPROD_AUTO_DEPLOY_FAILED,
    PREPROD_AUTO_IDLE,
)

AUTO_REFRESH_INTERVAL_SECONDS = 10
AUTO_APPROVE_MAX_ITERATIONS = 30


def _on_auto_approve_toggle_change() -> None:
    """开启自动模式时标记需要立即刷新，避免用旧缓存误判部署状态"""
    if st.session_state.get('tab3_auto_approve_preprod'):
        st.session_state.tab3_auto_initial_refresh_pending = True


def _track_auto_approve_toggle_edge() -> None:
    """检测自动模式从关→开，备用 on_change（部分 Streamlit 版本回调不稳定）"""
    curr = bool(st.session_state.get('tab3_auto_approve_preprod'))
    prev = bool(st.session_state.get('tab3_auto_approve_preprod_prev'))
    if curr and not prev:
        st.session_state.tab3_auto_initial_refresh_pending = True
    st.session_state.tab3_auto_approve_preprod_prev = curr


def _maybe_refresh_workflows_for_auto_mode(pipeline_id: str, api_token: str) -> None:
    """在渲染 Workflows 之前拉取最新数据，确保自动模式可见刷新

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
    """
    if not st.session_state.get('tab3_auto_approve_preprod'):
        return
    if st.session_state.get('tab3_cached_pipeline_id') != pipeline_id:
        return
    should_refresh = st.session_state.get('tab3_auto_initial_refresh_pending')
    if not should_refresh:
        return
    _refresh_workflows(pipeline_id, api_token)
    st.session_state.tab3_auto_initial_refresh_pending = False


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

    _track_auto_approve_toggle_edge()

    # Pipeline ID 变化时清除缓存
    if st.session_state.get('tab3_cached_pipeline_id') and st.session_state.tab3_cached_pipeline_id != pipeline_id_input:
        for key in [
            'tab3_cached_pipeline_id', 'tab3_pipeline_data', 'tab3_workflows',
            'tab3_wf_jobs_map', 'tab3_pending_approvals',
            'tab3_auto_initial_refresh_pending',
        ]:
            st.session_state.pop(key, None)

    # 判断是否需要重新获取数据
    _cached = st.session_state.get('tab3_cached_pipeline_id') == pipeline_id_input
    _needs_refetch = (check_status_btn or _auto_trigger) and pipeline_id_input

    if _needs_refetch:
        _fetch_and_display_pipeline(pipeline_id_input, api_token)
    elif _cached and pipeline_id_input:
        _maybe_refresh_workflows_for_auto_mode(pipeline_id_input, api_token)
        _display_cached_pipeline(pipeline_id_input, api_token=api_token)
    elif pipeline_id_input:
        st.info("💡 点击「🔍 查看状态」或切换 Tab 获取最新数据")

    _run_auto_approve_loop(pipeline_id_input, api_token)


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
            _render_workflows_section(pipeline_id, workflows, api_token)

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
      _render_workflows_header(pipeline_id, api_token, workflows)
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


def _refresh_workflows(pipeline_id: str, api_token: str) -> None:
  workflows = get_pipeline_workflows(pipeline_id, api_token=api_token)
  if workflows:
    wf_ids = [w.get('id') for w in workflows if w.get('id')]
    wf_jobs_map = _fetch_workflow_jobs_concurrent(wf_ids, api_token=api_token)
    st.session_state.tab3_workflows = workflows
    st.session_state.tab3_wf_jobs_map = wf_jobs_map
  else:
    st.session_state.tab3_workflows = []
    st.session_state.tab3_wf_jobs_map = {}
  pending = []
  for wf in (workflows or []):
    for job in st.session_state.tab3_wf_jobs_map.get(wf.get('id'), []):
      if job.get('type') == 'approval' and job.get('status') == 'on_hold':
        job['_workflow_id'] = wf.get('id')
        job['_workflow_name'] = wf.get('name')
        pending.append(job)
  st.session_state.tab3_pending_approvals = pending

def _render_workflows_header(pipeline_id: str, api_token: str, workflows: list) -> None:
    """渲染 Workflows 标题行：标题 + 刷新按钮 + 自动审批 Preprod 开关

    Args:
        pipeline_id: Pipeline ID
        api_token: API Token
        workflows: Workflow 列表（用于标题计数）
    """
    col_wf1, col_wf2, col_wf3 = st.columns([2, 1, 2])
    with col_wf1:
        st.subheader(f"🔄 Workflows ({len(workflows)})")
    with col_wf2:
        if st.button("🔄 刷新", key="refresh_workflows", use_container_width=True):
            _refresh_workflows(pipeline_id, api_token)
            st.rerun()
    with col_wf3:
        st.toggle(
            "🤖 自动刷新并审批 Preprod",
            key="tab3_auto_approve_preprod",
            on_change=_on_auto_approve_toggle_change,
            help=f"开启后每 {AUTO_REFRESH_INTERVAL_SECONDS} 秒自动刷新；"
                 "出现名称含 preprod 的待审批 Job 时自动通过，"
                 "deploy-docker-image-on-preprod 部署成功后自动停止",
        )


def _render_workflows_section(pipeline_id: str, workflows: list, api_token: str) -> None:
    """渲染 Workflows 区域

    Args:
        pipeline_id: Pipeline ID，用于刷新按钮重新获取
        workflows: Workflow 列表
        api_token: API Token
    """
    if workflows:
      _render_workflows_header(pipeline_id, api_token, workflows)
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
    target_env = st.session_state.get('batch_target_env', 'preprod')
    is_target_env = target_env in job_name
    should_expand = is_target_env or len(st.session_state.tab3_pending_approvals) == 1

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

def _render_auto_mode_standby(status: str) -> None:
    """根据 preprod 自动模式状态展示待机说明

    Args:
        status: get_preprod_auto_mode_status 返回值
    """
    if status == PREPROD_AUTO_DEPLOY_SUCCESS:
        st.caption("🤖 自动模式待机中：Preprod 部署已完成")
    elif status == PREPROD_AUTO_DEPLOY_FAILED:
        st.caption("🤖 自动模式已停止：Preprod 部署失败")
    elif status == PREPROD_AUTO_IDLE:
        st.caption("🤖 自动模式待机中：无 Preprod 相关任务")


def _toast_auto_mode_stopped(status: str) -> None:
    """轮询刚停止时的一次性 toast

    Args:
        status: get_preprod_auto_mode_status 返回值
    """
    if status == PREPROD_AUTO_DEPLOY_SUCCESS:
        st.toast("🤖 Preprod 部署已完成，自动模式待机", icon="✅")
    elif status == PREPROD_AUTO_DEPLOY_FAILED:
        st.toast("🤖 Preprod 部署失败，自动模式已停止", icon="❌")


def _run_auto_approve_loop(pipeline_id: str, api_token: str) -> None:
    """自动刷新并自动审批 Preprod 的轮询循环

    开关（st.session_state.tab3_auto_approve_preprod）开启、当前有缓存
    Pipeline 且仍有 preprod 相关未完成工作时：等待固定间隔 → 刷新数据 →
    自动审批名称含 preprod 的待审批 Job → rerun 进入下一轮。
    deploy-docker-image-on-preprod 部署成功后停止轮询（即使 Workflow 仍在
    等待 staging/prod 审批）。

    注意：不能直接给 toggle 的 session_state key 赋值（widget 实例化后
    Streamlit 会抛 StreamlitAPIException），所以停止轮询只靠提前 return。
    同时限制最大轮询次数 AUTO_APPROVE_MAX_ITERATIONS，防止异常场景下无限循环。

    Args:
        pipeline_id: 当前输入框中的 Pipeline ID
        api_token: API Token
    """
    if not st.session_state.get('tab3_auto_approve_preprod'):
        return
    if not pipeline_id or st.session_state.get('tab3_cached_pipeline_id') != pipeline_id:
        return

    # 读取轮询计数，首次进入时初始化为 0
    current_iteration = st.session_state.get('tab3_auto_approve_iteration', 0)
    if current_iteration == 0:
        st.session_state.tab3_auto_approve_iteration = 1
    else:
        st.session_state.tab3_auto_approve_iteration += 1

    if st.session_state.tab3_auto_approve_iteration > AUTO_APPROVE_MAX_ITERATIONS:
        st.toast(f"⚠️ 自动审批轮询已达上限（{AUTO_APPROVE_MAX_ITERATIONS} 次），已停止", icon="⚠️")
        st.session_state.tab3_auto_approve_iteration = 0
        return

    workflows = st.session_state.get('tab3_workflows') or []
    wf_jobs_map = st.session_state.get('tab3_wf_jobs_map') or {}
    if not workflows:
        _refresh_workflows(pipeline_id, api_token)
        if not st.session_state.get('tab3_workflows'):
            return
        st.rerun()

    auto_status = get_preprod_auto_mode_status(workflows, wf_jobs_map)
    if auto_status != PREPROD_AUTO_POLLING:
        _render_auto_mode_standby(auto_status)
        st.session_state.tab3_auto_approve_iteration = 0
        return

    with st.spinner(
        f"🤖 自动模式（第 {st.session_state.tab3_auto_approve_iteration}/{AUTO_APPROVE_MAX_ITERATIONS} 轮）："
        f"{AUTO_REFRESH_INTERVAL_SECONDS} 秒后刷新并检查 preprod 审批..."
    ):
        time.sleep(AUTO_REFRESH_INTERVAL_SECONDS)

    _refresh_workflows(pipeline_id, api_token)

    pending_preprod = find_pending_preprod_approvals(
        st.session_state.tab3_workflows,
        st.session_state.tab3_wf_jobs_map,
    )
    if pending_preprod:
        approved, failed = auto_approve_jobs(pending_preprod, api_token)
        if approved:
            names = '、'.join(j.get('name', '') for j in approved)
            st.toast(f"🤖 已自动审批 {len(approved)} 个 Preprod Job：{names}", icon="✅")
        for j in failed:
            st.toast(f"❌ 自动审批失败: {j.get('name')} — {j.get('_approve_error')}", icon="❌")

    auto_status = get_preprod_auto_mode_status(
        st.session_state.tab3_workflows,
        st.session_state.tab3_wf_jobs_map,
    )
    if auto_status != PREPROD_AUTO_POLLING:
        st.session_state.tab3_auto_approve_iteration = 0
        _toast_auto_mode_stopped(auto_status)

    st.rerun()

