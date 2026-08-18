"""
Tab 5: 批量操作 UI

提供批量触发和批量审批功能。
"""
import streamlit as st
import time

from circleCi.batch_operations import (
    batch_trigger_pipelines,
    batch_trigger_pipelines_by_mapping,
    batch_approve_jobs,
    get_pending_approvals_for_batch,
    parse_service_branch_mappings,
    build_resolved_service_branch_map,
)
from circleCi.pipeline_config import (
    BATCH_APPROVE_ENV_OPTIONS,
    DEFAULT_BATCH_APPROVE_ENV,
    getBatchApproveEnvLabel,
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
    st.info(
        "💡 批量触发多个服务到指定分支，并支持批量审批到 **PP / Dev** 环境"
        "（默认 PP）。请使用下方 **「🔀 多分支批量触发」** 子 Tab 为不同服务指定不同分支。"
    )

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

    tab_same, tab_multi = st.tabs(["🚀 同分支批量触发", "🔀 多分支批量触发"])
    with tab_same:
        _render_batch_trigger_section(all_services, vcs_type, organization, api_token)
    with tab_multi:
        _render_multi_branch_trigger_section(all_services, vcs_type, organization, api_token)


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
    results = st.session_state.batch_trigger_results
    if results and results.get('mode', 'same_branch') == 'same_branch':
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
            'failed': failed_list,
            'mode': 'same_branch',
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

    env_labels = list(BATCH_APPROVE_ENV_OPTIONS.keys())
    current_env = st.session_state.get('batch_target_env', DEFAULT_BATCH_APPROVE_ENV)
    current_label = getBatchApproveEnvLabel(current_env)
    default_idx = env_labels.index(current_label) if current_label in env_labels else 0

    header_col, env_col = st.columns([2, 1])
    with header_col:
        st.subheader("✅ 批量审批")
    with env_col:
        selected_label = st.selectbox(
            "目标环境",
            options=env_labels,
            index=default_idx,
            key="batch_target_env_select",
            help="默认 PP；可选 Dev。扫描与审批均按所选环境匹配 approval job 名称。"
        )
        selected_env = BATCH_APPROVE_ENV_OPTIONS[selected_label]
        if selected_env != current_env:
            st.session_state.batch_target_env = selected_env
            st.session_state.batch_pending_approvals = []
            st.session_state.batch_approve_results = None
            st.session_state.batch_scan_completed = False
            st.rerun()

    env_label = getBatchApproveEnvLabel(selected_env)

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
        with st.spinner(f"正在扫描 {len(pipeline_ids)} 个 Pipeline 的 {env_label} 待审批 Jobs..."):
            from modules.user_config_loader import get_circleci_config
            current_user = st.session_state.current_user
            user_config = get_circleci_config(current_user)
            api_token = user_config.get('api_token', '') if user_config else ''

            pending_approvals = get_pending_approvals_for_batch(
                pipeline_ids=pipeline_ids,
                api_token=api_token,
                target_env=selected_env,
                max_workers=10
            )
        st.session_state.batch_pending_approvals = pending_approvals
        st.session_state.batch_scan_completed = True

    # 显示扫描结果
    if st.session_state.get('batch_scan_completed'):
        pending_approvals = st.session_state.batch_pending_approvals or []

        if pending_approvals and len(pending_approvals) > 0:
            st.success(f"🎯 发现 {len(pending_approvals)} 个待审批 Jobs（{env_label}）")
            _render_pending_approvals_list(pending_approvals)
            _render_batch_approve_action(pending_approvals, target_env=selected_env)
        else:
            st.info(f"ℹ️ 当前没有发现待审批的 {env_label} Jobs")
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

                # 初始化审批结果
                if not st.session_state.get('batch_approve_results'):
                    st.session_state.batch_approve_results = {'success': [], 'failed': []}

                # 追加到审批结果（累积，不覆盖）
                result_item = {
                    'service': approval['service_name'],
                    'pipeline_number': approval['pipeline_number'],
                    'job_name': approval['job_name']
                }
                st.session_state.batch_approve_results['success'].append(result_item)

                # 从待审批列表移除
                st.session_state.batch_pending_approvals = [
                    a for a in pending_approvals
                    if a['job_id'] != approval['job_id']
                ]
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ 审批失败: {single_failed[0].get('error')}")


def _render_batch_approve_action(pending_approvals: list, target_env: str = DEFAULT_BATCH_APPROVE_ENV) -> None:
    """渲染批量审批操作

    Args:
        pending_approvals: 待审批列表
        target_env: 目标环境关键字
    """
    from modules.user_config_loader import get_circleci_config

    st.markdown("---")
    env_label = getBatchApproveEnvLabel(target_env)

    confirm_approve = st.checkbox(
        f"⚠️ 我确认要批量审批 {len(pending_approvals)} 个 Jobs 到 {env_label} 环境",
        value=False,
        key=f"batch_confirm_approve_{target_env}"
    )

    approve_btn_disabled = not confirm_approve or len(pending_approvals) == 0
    if st.button("✅ 执行批量审批", type="primary", use_container_width=True,
                 disabled=approve_btn_disabled, key="batch_approve_btn"):

        current_user = st.session_state.current_user
        user_config = get_circleci_config(current_user)
        api_token = user_config.get('api_token', '') if user_config else ''

        with st.status("正在批量审批...", expanded=True) as status:
            st.write(f"📋 准备审批 {len(pending_approvals)} 个 Jobs 到 {env_label}...")

            approve_success, approve_failed = batch_approve_jobs(
                pending_approvals=pending_approvals,
                api_token=api_token,
                max_workers=5
            )

            # 初始化审批结果
            if not st.session_state.get('batch_approve_results'):
                st.session_state.batch_approve_results = {'success': [], 'failed': []}

            # 防止重复：过滤已存在的 job_id
            already_approved_ids = {s['job_name'] for s in st.session_state.batch_approve_results.get('success', [])}
            new_success = [s for s in approve_success if s['job_name'] not in already_approved_ids]
            new_failed = [f for f in approve_failed if f['job_name'] not in already_approved_ids]

            # 累积结果（不覆盖历史）
            st.session_state.batch_approve_results['success'].extend(new_success)
            st.session_state.batch_approve_results['failed'].extend(new_failed)

            # 更新待审批列表
            approved_ids = [s['job_name'] for s in approve_success]
            st.session_state.batch_pending_approvals = [
                a for a in pending_approvals
                if a['job_name'] not in approved_ids
            ]

            total_success = len(st.session_state.batch_approve_results['success'])
            total_failed = len(st.session_state.batch_approve_results['failed'])
            status.update(
                label=f"✅ 批量审批完成！本次: 成功 {len(approve_success)}，失败 {len(approve_failed)} | 累计: 成功 {total_success}，失败 {total_failed}",
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


def _render_multi_branch_trigger_section(
    all_services: list,
    vcs_type: str,
    organization: str,
    api_token: str
) -> None:
    """渲染多分支批量触发区域"""
    st.subheader("🔀 多分支批量触发")
    st.info(
        "💡 每个服务可指定不同分支。支持文本键值对输入，"
        "或使用表格逐行选择服务并填写分支。"
    )

    reset_col1, reset_col2 = st.columns([3, 1])
    with reset_col2:
        if st.button("🔄 重置结果", use_container_width=True, key="multi_batch_reset"):
            st.session_state.batch_trigger_results = None
            st.session_state.batch_pending_approvals = []
            st.session_state.batch_approve_results = None
            st.session_state.batch_scan_completed = False
            st.rerun()

    input_mode = st.radio(
        "输入方式",
        ["📝 文本键值对", "📋 表格逐行配置"],
        horizontal=True,
        key="batch_multi_branch_mode_radio",
    )
    use_text_mode = input_mode.startswith("📝")

    raw_map: dict[str, str] = {}

    if use_text_mode:
        st.markdown("**格式:** `服务名: 分支名` 或 `服务名=分支名`（每行一条，`#` 开头为注释）")
        default_text = st.session_state.batch_multi_branch_text or (
            "back-office-cloud: SP-34377\n"
            "factory-service-cloud: SP-epic-inspection-booking-with-factory\n"
            "psi-service: SP-epic-inspection-booking-with-factory\n"
            "irp-service-cloud: SP-epic-inspection-booking-with-factory\n"
            "irp-web-cloud: SP-epic-inspection-booking-with-factory"
        )
        text_input = st.text_area(
            "服务与分支映射",
            value=default_text,
            height=220,
            key="batch_multi_branch_text_area",
            placeholder="back-office-cloud: SP-34377\npsi-service: SP-epic",
        )
        st.session_state.batch_multi_branch_text = text_input
        raw_map = parse_service_branch_mappings(text_input)
    else:
        import pandas as pd

        if not st.session_state.batch_multi_branch_rows:
            st.session_state.batch_multi_branch_rows = [
                {'service': all_services[0] if all_services else '', 'branch': 'master'},
                {'service': '', 'branch': ''},
                {'service': '', 'branch': ''},
            ]

        st.markdown("**在表格中选择服务并填写对应分支（留空行会被忽略）:**")
        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.batch_multi_branch_rows),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                'service': st.column_config.SelectboxColumn(
                    '服务',
                    options=[''] + all_services,
                    required=False,
                ),
                'branch': st.column_config.TextColumn(
                    '分支',
                    required=False,
                    help='例如 SP-34377 或 master',
                ),
            },
            key="batch_multi_branch_data_editor",
            hide_index=True,
        )
        st.session_state.batch_multi_branch_rows = edited_df.to_dict('records')

        for row in st.session_state.batch_multi_branch_rows:
            service = str(row.get('service', '')).strip()
            branch = str(row.get('branch', '')).strip()
            if service and branch:
                raw_map[service] = branch

    resolved_map, invalid_entries = build_resolved_service_branch_map(
        raw_map, all_services
    )

    if resolved_map:
        st.success(f"✅ 已解析 **{len(resolved_map)}** 个有效服务→分支映射")
        with st.expander("📋 映射预览", expanded=True):
            for svc, br in resolved_map.items():
                st.write(f"`{svc}` → **{br}**")

    if invalid_entries:
        st.warning(f"⚠️ {len(invalid_entries)} 条无效映射将被忽略")
        with st.expander("查看无效项", expanded=False):
            for item in invalid_entries:
                st.error(
                    f"**{item['input_service']}** → {item['branch']}: "
                    f"{'; '.join(item['warnings'])}"
                )

    st.markdown("---")

    confirm_multi = st.checkbox(
        f"⚠️ 我确认要触发 {len(resolved_map)} 个服务到各自指定分支",
        value=False,
        key="batch_confirm_multi_trigger",
    )

    trigger_disabled = not confirm_multi or len(resolved_map) == 0
    if st.button(
        "🚀 开始多分支批量触发",
        type="primary",
        use_container_width=True,
        disabled=trigger_disabled,
        key="batch_multi_trigger_btn",
    ):
        _execute_multi_branch_trigger(resolved_map, vcs_type, organization, api_token)

    results = st.session_state.batch_trigger_results
    if results and results.get('mode') == 'multi_branch':
        _render_multi_branch_trigger_results(vcs_type, organization)


def _execute_multi_branch_trigger(
    resolved_map: dict[str, str],
    vcs_type: str,
    organization: str,
    api_token: str,
) -> None:
    """执行多分支批量触发"""
    with st.status("正在多分支批量触发 Pipeline...", expanded=True) as status:
        st.write(f"📋 准备触发 {len(resolved_map)} 个服务（各服务分支不同）...")

        success_list, failed_list = batch_trigger_pipelines_by_mapping(
            service_branch_map=resolved_map,
            vcs_type=vcs_type,
            organization=organization,
            api_token=api_token,
            max_workers=5,
        )

        st.session_state.batch_trigger_results = {
            'success': success_list,
            'failed': failed_list,
            'mode': 'multi_branch',
        }
        st.session_state.batch_pending_approvals = []
        st.session_state.batch_approve_results = None
        st.session_state.batch_scan_completed = False

        status.update(
            label=(
                f"✅ 多分支批量触发完成！成功: {len(success_list)}，"
                f"失败: {len(failed_list)}"
            ),
            state="complete",
        )


def _render_multi_branch_trigger_results(
    vcs_type: str,
    organization: str,
) -> None:
    """渲染多分支触发结果（含分支列）并复用审批区域"""
    results = st.session_state.batch_trigger_results
    success_list = results.get('success', [])
    failed_list = results.get('failed', [])

    st.subheader("📊 多分支触发结果")

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("✅ 成功", len(success_list))
    with stat_col2:
        st.metric("❌ 失败", len(failed_list))
    with stat_col3:
        st.metric("📊 总计", len(success_list) + len(failed_list))

    if success_list:
        with st.expander(f"✅ 成功 ({len(success_list)} 个)", expanded=True):
            for item in success_list:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**服务:** `{item['service']}`")
                    st.write(f"**分支:** `{item.get('branch', '-')}`")
                with col2:
                    st.write(f"**Pipeline:** #{item['pipeline_number']}")
                    st.code(item['pipeline_id'][:16] + "...", language=None)
                with col3:
                    if st.button(
                        "📊 监控",
                        key=f"multi_monitor_{item['pipeline_id'][:8]}",
                        use_container_width=True,
                    ):
                        st.session_state.current_pipeline_id = item['pipeline_id']
                        st.session_state.pending_tab3_monitor = item['pipeline_id']
                        st.rerun()

    if failed_list:
        with st.expander(f"❌ 失败 ({len(failed_list)} 个)", expanded=False):
            for item in failed_list:
                st.error(
                    f"**{item['service']}** (分支: {item.get('branch', '-')})"
                    f": {item.get('error', 'Unknown error')}"
                )

    if success_list:
        st.caption(
            "Pipeline 构建需要数分钟。可先选择目标环境（默认 PP），再点「扫描待审批 Jobs」，"
            "若无结果请稍后重试扫描。"
        )
        _render_batch_approve_section(success_list)