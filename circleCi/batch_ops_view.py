"""
Tab 5: 批量操作 UI

提供批量触发和批量审批功能。
"""
import streamlit as st
import time

from circleCi.batch_operations import (
    batch_trigger_pipelines,
    batch_approve_jobs,
    get_pending_approvals_for_batch
)


def render_batch_ops_tab(
    project_root,
    default_project: str,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """渲染批量操作 Tab UI

    Args:
        project_root: 项目根路径
        default_project: 默认项目名
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: CircleCI API Token
    """
    st.header("📦 批量操作")
    st.info("💡 批量触发多个服务到指定分支，并支持批量审批到 Preprod 环境")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    all_services = [default_project]
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                all_services = [line.strip() for line in f if line.strip()]
    except Exception as e:
        import logging
        logging.warning(f"Could not load services list: {e}")

    _render_batch_trigger_section(all_services, vcs_type, organization, api_token)


def _render_batch_trigger_section(
    all_services: list,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """渲染批量触发区域

    Args:
        all_services: 所有服务列表
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
    """
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
        placeholder="ACA\naca-new\naims-service-cloud\n...",
        help="每行输入一个服务名称，系统会自动过滤出存在于服务列表中的服务",
        key="batch_services_text"
    )

    # 解析文本输入
    text_services = [s.strip() for s in services_text.split('\n') if s.strip()]
    valid_text_services = [s for s in text_services if s in all_services]
    invalid_text_services = [s for s in text_services if s not in all_services]

    if invalid_text_services:
        st.warning(f"⚠️ 以下服务不在服务列表中，将被忽略: {', '.join(invalid_text_services[:5])}{'...' if len(invalid_text_services) > 5 else ''}")

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
        placeholder="例如: master, develop, SP-12345",
        help="所有服务将触发到此分支",
        key="batch_branch_input"
    )

    st.info(f"📊 已选择 **{len(selected_services)}** 个服务，目标分支: **{batch_branch}**")

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

    if trigger_btn and selected_services and batch_branch:
        _execute_batch_trigger(selected_services, batch_branch, vcs_type, organization, api_token)

    # 触发结果展示
    if st.session_state.batch_trigger_results:
        _render_trigger_results(vcs_type, organization)


def _execute_batch_trigger(
    selected_services: list,
    batch_branch: str,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """执行批量触发

    Args:
        selected_services: 选中的服务列表
        batch_branch: 目标分支
        vcs_type: VCS 类型
        organization: 组织名称
        api_token: API Token
    """
    st.session_state.batch_selected_services = selected_services
    st.session_state.batch_branch = batch_branch

    with st.status("正在批量触发 Pipeline...", expanded=True) as status:
        st.write(f"📋 准备触发 {len(selected_services)} 个服务到 {batch_branch} 分支...")

        success_list, failed_list = batch_trigger_pipelines(
            services=selected_services,
            branch=batch_branch,
            vcs_type=vcs_type,
            organization=organization,
            api_token=api_token,
            max_workers=5
        )

        st.session_state.batch_trigger_results = {
            'success': success_list,
            'failed': failed_list
        }

        status.update(
            label=f"✅ 批量触发完成！成功: {len(success_list)}，失败: {len(failed_list)}",
            state="complete"
        )


def _render_trigger_results(vcs_type: str, organization: str) -> None:
    """渲染触发结果

    Args:
        vcs_type: VCS 类型
        organization: 组织名称
    """
    results = st.session_state.batch_trigger_results
    success_list = results.get('success', [])
    failed_list = results.get('failed', [])

    st.subheader("📊 触发结果")

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
                _render_trigger_result_item(item)

    # 失败列表
    if failed_list:
        with st.expander(f"❌ 触发失败的服务 ({len(failed_list)} 个)", expanded=False):
            for item in failed_list:
                st.error(f"**{item['service']}**: {item.get('error', 'Unknown error')}")
                if item.get('status_code'):
                    st.caption(f"HTTP 状态码: {item.get('status_code')}")

    # 批量审批区域
    if success_list:
        _render_batch_approve_section(success_list)


def _render_trigger_result_item(item: dict) -> None:
    """渲染单个触发结果项

    Args:
        item: 触发结果项
    """
    col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
    with col_s1:
        st.write(f"**服务:** `{item['service']}`")
        st.write(f"**Pipeline Number:** #{item['pipeline_number']}")
    with col_s2:
        st.write("**Pipeline ID:**")
        st.code(item['pipeline_id'][:16] + "...", language=None)
    with col_s3:
        if st.button("📊 监控", key=f"batch_monitor_{item['pipeline_id'][:8]}",
                     use_container_width=True, type="primary"):
            st.session_state.current_pipeline_id = item['pipeline_id']
            st.session_state.pending_tab3_monitor = item['pipeline_id']
            st.rerun()


def _render_batch_approve_section(success_list: list) -> None:
    """渲染批量审批区域

    Args:
        success_list: 成功触发的服务列表
    """
    st.markdown("---")
    st.subheader("✅ 批量审批")

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

    if scan_btn:
        pipeline_ids = [item['pipeline_id'] for item in success_list]
        with st.spinner(f"正在扫描 {len(pipeline_ids)} 个 Pipeline 的待审批 Jobs..."):
            from modules.user_config_loader import get_circleci_config
            current_user = st.session_state.current_user
            user_config = get_circleci_config(current_user)
            api_token = user_config.get('api_token', '') if user_config else ''

            pending_approvals = get_pending_approvals_for_batch(
                pipeline_ids=pipeline_ids,
                api_token=api_token,
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
            _render_pending_approvals_list(pending_approvals)
            _render_batch_approve_action(pending_approvals)
        else:
            st.info("ℹ️ 当前没有发现待审批的 Preprod Jobs")
            st.caption("💡 提示：Pipelines 可能还在构建中，请稍后再次扫描")

    # 显示审批结果
    if st.session_state.batch_approve_results:
        _render_approve_results()


def _render_pending_approvals_list(pending_approvals: list) -> None:
    """渲染待审批列表

    Args:
        pending_approvals: 待审批列表
    """
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
                _render_single_approve_button(approval, pending_approvals)


def _render_single_approve_button(approval: dict, pending_approvals: list) -> None:
    """渲染单独审批按钮

    Args:
        approval: 审批项
        pending_approvals: 待审批列表（用于更新）
    """
    from modules.user_config_loader import get_circleci_config

    if st.button("✅ 审批", key=f"batch_single_approve_{approval['job_id'][:8]}",
                 use_container_width=True):
        current_user = st.session_state.current_user
        user_config = get_circleci_config(current_user)
        api_token = user_config.get('api_token', '') if user_config else ''

        with st.spinner("正在审批..."):
            single_success, single_failed = batch_approve_jobs([approval], api_token)

            if single_success:
                st.success(f"✅ {approval['service_name']} 审批成功！")
                st.session_state.batch_pending_approvals = [
                    a for a in pending_approvals
                    if a['job_id'] != approval['job_id']
                ]
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ 审批失败: {single_failed[0].get('error')}")


def _render_batch_approve_action(pending_approvals: list) -> None:
    """渲染批量审批操作

    Args:
        pending_approvals: 待审批列表
    """
    from modules.user_config_loader import get_circleci_config

    st.markdown("---")

    confirm_approve = st.checkbox(
        f"⚠️ 我确认要批量审批 {len(pending_approvals)} 个 Jobs 到 Preprod 环境",
        value=False,
        key="batch_confirm_approve"
    )

    approve_btn_disabled = not confirm_approve or len(pending_approvals) == 0
    if st.button("✅ 执行批量审批", type="primary", use_container_width=True,
                 disabled=approve_btn_disabled, key="batch_approve_btn"):

        current_user = st.session_state.current_user
        user_config = get_circleci_config(current_user)
        api_token = user_config.get('api_token', '') if user_config else ''

        with st.status("正在批量审批...", expanded=True) as status:
            st.write(f"📋 准备审批 {len(pending_approvals)} 个 Jobs...")

            approve_success, approve_failed = batch_approve_jobs(
                pending_approvals=pending_approvals,
                api_token=api_token,
                max_workers=5
            )

            st.session_state.batch_approve_results = {
                'success': approve_success,
                'failed': approve_failed
            }

            # 更新待审批列表
            approved_ids = [s['job_name'] for s in approve_success]
            st.session_state.batch_pending_approvals = [
                a for a in pending_approvals
                if a['job_name'] not in approved_ids
            ]

            status.update(
                label=f"✅ 批量审批完成！成功: {len(approve_success)}，失败: {len(approve_failed)}",
                state="complete"
            )


def _render_approve_results() -> None:
    """渲染审批结果"""
    approve_results = st.session_state.batch_approve_results
    approve_success = approve_results.get('success', [])
    approve_failed = approve_results.get('failed', [])

    st.subheader("📊 审批结果")

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