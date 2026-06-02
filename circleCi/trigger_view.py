"""
Tab 1: 触发 Pipeline UI

提供 Pipeline 触发功能的 UI 组件。
"""
import streamlit as st
from pathlib import Path

from circleCi.pipeline_api import fetch_recent_branches
from circleCi.triggerJob import trigger_circleci_pipeline, validate_project_slug
from modules.components import copyable_text


def render_trigger_tab(
    project_root: Path,
    vcs_type: str,
    organization: str,
    default_project: str,
    default_branch: str,
    api_token: str
) -> None:
    """渲染触发 Pipeline Tab UI

    Args:
        project_root: 项目根路径
        vcs_type: VCS 类型
        organization: 组织名称
        default_project: 默认项目名
        default_branch: 默认分支名
        api_token: CircleCI API Token
    """
    st.header("🎯 触发 Pipeline")

    # 加载服务列表
    services_file = project_root / "config" / "circleci-services.txt"
    service_list_for_trigger = [default_project]

    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list_for_trigger = services
    except Exception as e:
        import logging
        logging.warning(f"Could not load services list: {e}")

    # 分支输入区（表单外，支持"查最新"按钮）
    branch_col1, branch_col2 = st.columns([3, 1])
    with branch_col1:
        branch = st.text_input(
            "分支名称",
            value=st.session_state.trigger_branch,
            placeholder="例如: master, develop, SP-12345",
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
        current_project = st.session_state.trigger_project or default_project
        full_slug = f"{vcs_type}/{organization}/{current_project}"
        with st.spinner("查询最近分支中..."):
            recent_branches, fetch_error = fetch_recent_branches(
                full_slug,
                api_token=api_token
            )
        if fetch_error:
            st.error(f"❌ 查询分支失败: {fetch_error.get('error', 'Unknown error')}")
            if fetch_error.get('status_code'):
                st.caption(f"HTTP 状态码: {fetch_error.get('status_code')}")
        elif recent_branches:
            st.session_state.recent_branches = recent_branches
        else:
            st.warning("未查询到最近分支，请确认该项目有历史构建记录")

    # 分支下拉选择（查询有结果时显示）
    if st.session_state.get("recent_branches"):
        def on_branch_selected():
            selected_val = st.session_state.get("branch_selector_select", "")
            if selected_val:
                st.session_state.trigger_branch = selected_val

        st.selectbox(
            "👇 选择分支（点击后自动填入上方输入框）",
            options=[""] + st.session_state.recent_branches,
            key="branch_selector_select",
            on_change=on_branch_selected
        )

    # 项目名同步到 session_state
    try:
        default_index = service_list_for_trigger.index(st.session_state.trigger_project)
    except (ValueError, AttributeError):
        default_index = service_list_for_trigger.index(default_project) if default_project in service_list_for_trigger else 0

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

    # 显示完整的 Project Slug
    full_project_slug = f"{vcs_type}/{organization}/{project_name}"
    st.info(f"📝 完整项目路径: `{full_project_slug}`")

    with st.form("trigger_form"):
        submit_button = st.form_submit_button("🚀 触发 Pipeline", type="primary", use_container_width=True)

        if submit_button:
            st.session_state.trigger_project = project_name
            st.session_state.trigger_branch = branch
            _handle_trigger_submit(
                project_slug=full_project_slug,
                branch=branch,
                api_token=api_token
            )


def _handle_trigger_submit(project_slug: str, branch: str, api_token: str) -> None:
    """处理触发提交

    Args:
        project_slug: 完整项目路径
        branch: 分支名
        api_token: API Token
    """
    import time

    if not validate_project_slug(project_slug):
        st.error("❌ 项目 Slug 格式错误")
        st.info("请检查项目名称是否正确")
        return

    with st.spinner("正在触发 Pipeline..."):
        try:
            result = trigger_circleci_pipeline(
                project_slug,
                branch,
                api_token=api_token
            )

            if result.get('success'):
                pipeline_id = result.get('pipeline_id')
                pipeline_number = result.get('pipeline_number')

                st.success(f"✅ Pipeline 触发成功!")

                copyable_text("Pipeline ID:", pipeline_id, f"pipeline_id_main")
                st.info(f"**Pipeline Number:** {pipeline_number}")

                # 保存到历史记录
                st.session_state.pipeline_history.append({
                    'id': pipeline_id,
                    'number': pipeline_number,
                    'branch': branch,
                    'project': project_slug,
                    'time': time.strftime('%Y-%m-%d %H:%M:%S')
                })

                st.session_state.current_pipeline_id = pipeline_id

                st.success("✅ Pipeline 触发成功！")
                st.info(f"**Pipeline Number:** {pipeline_number}")
                copyable_text("Pipeline ID:", pipeline_id, "pipeline_id_alt")
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
                _show_trigger_error(result)

        except Exception as e:
            import traceback
            st.error(f"❌ 发生异常: {str(e)}")
            with st.expander("🔍 查看详细错误"):
                st.code(traceback.format_exc())


def _show_trigger_error(result: dict) -> None:
    """显示触发错误信息

    Args:
        result: 触发结果字典
    """
    st.error("❌ Pipeline 触发失败")

    error_msg = result.get('error', '未知错误')
    status_code = result.get('status_code')

    if status_code:
        st.error(f"HTTP状态码: {status_code}")
    st.error(f"错误信息: {error_msg}")

    with st.expander("🔍 故障排查建议"):
        st.markdown("""
        请检查以下几点：
        - ✅ API Token 是否有效且未过期
        - ✅ 项目 Slug 格式是否正确 (vcs-type/org-name/repo-name)
        - ✅ 分支是否存在于仓库中
        - ✅ API Token 是否有足够的权限触发 Pipeline
        - ✅ 网络连接是否正常
        """)