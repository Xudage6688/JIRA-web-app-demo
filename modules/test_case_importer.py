"""
Test Case Importer - 导入 Test Cases 到 Xray
从 pages/5_📝_Jira_Operations.py 拆分而出
UI 编排层，核心业务逻辑委托给 _test_case_importer_logic.py
"""

import os
import time
import streamlit as st
import pandas as pd
from typing import Dict, Optional, List

from modules.user_config_loader import get_user_config_loader, build_jira_auth_headers
from modules._test_case_importer_logic import (
    authenticate_xray,
    build_tests_payload,
    submit_tests_bulk,
    poll_job_status,
    query_related_ticket,
    get_test_numeric_ids,
    link_tests_to_test_set,
    link_tests_to_story,
    XrayAuthError,
    XrayImportError,
    XrayJobFailedError,
    XrayJobTimeoutError,
)


def render_test_case_importer_tab(
    current_user: str,
    base_url: str,
    config_email: str,
    api_token: str,
    metadata: Dict,
) -> None:
    """渲染"导入 Test Cases"Tab，接受外部注入的上下文变量"""

    st.header("📥 导入 Test Cases 到 Xray")
    st.markdown("将测试用例批量导入 Jira Xray，并与指定 Ticket 建立关联。")

    # ===== 加载 Xray 配置 =====
    user_config_loader_inst = get_user_config_loader()
    user_full_cfg = user_config_loader_inst.get_user_config(current_user) \
        if hasattr(user_config_loader_inst, 'get_user_config') else {}
    xray_cfg = user_full_cfg.get('xray', {}) if user_full_cfg else {}
    default_xray_id = xray_cfg.get('client_id', '')
    default_xray_secret = xray_cfg.get('client_secret', '')

    st.markdown("---")

    # ===== 区域 A：参数配置 =====
    st.subheader("⚙️ 导入参数配置")

    param_col1, param_col2 = st.columns(2)

    with param_col1:
        sp_teams_list = metadata.get('sp_teams', [])
        sp_team_options_import = sp_teams_list if sp_teams_list else ["Mermaid"]
        default_team_idx = sp_team_options_import.index("Mermaid") \
            if "Mermaid" in sp_team_options_import else 0
        selected_sp_team = st.selectbox(
            "SP Team",
            options=sp_team_options_import,
            index=default_team_idx,
            key="import_sp_team"
        )

        priority_options = ["Low", "Medium", "High", "Critical"]
        selected_priority = st.selectbox(
            "Priority",
            options=priority_options,
            index=0,
            key="import_priority"
        )

    with param_col2:
        title_mode = st.selectbox(
            "Title 来源",
            options=["使用 Action 列作为 Title（推荐）", "自定义统一 Title"],
            index=0,
            key="import_title_mode"
        )
        if title_mode == "自定义统一 Title":
            custom_title = st.text_input(
                "自定义 Title",
                placeholder="所有 Test Case 使用此标题",
                key="import_custom_title"
            )
        else:
            custom_title = ""

        related_ticket = st.text_input(
            "Related Ticket（SP-XXXXX）",
            value=st.session_state.get("import_related_ticket", ""),
            placeholder="例如: SP-30088",
            help="所有导入的 Test Cases 将与此 Ticket 建立 is tested by 关联",
            key="import_related_ticket_input"
        )
        st.session_state.import_related_ticket = related_ticket

    st.markdown("---")

    # ===== 区域 B：数据来源 =====
    st.subheader("📂 Test Cases 数据来源")

    tab_upload, tab_manual = st.tabs(["📁 上传 Excel 文件", "✏️ 手动填写"])

    df_cases = None

    # ---------- Tab 1: 上传文件 ----------
    with tab_upload:
        template_col1, template_col2 = st.columns([1, 3])

        with template_col1:
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "assets", "test-cases-template.xlsx"
            )
            if os.path.exists(template_path):
                with open(template_path, "rb") as f:
                    template_bytes = f.read()
                st.download_button(
                    label="📥 下载模板",
                    data=template_bytes,
                    file_name="test-cases-template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="下载 Excel 模板，填写 Action / Data / Expected Result 三列后上传"
                )
            else:
                st.warning("⚠️ 模板文件未找到")

        with template_col2:
            st.info("📋 模板说明：Excel 文件包含三列 — **Action**（动作）、**Data**（测试数据）、**Expected Result**（预期结果）。每行对应一条 Test Case。")

        uploaded_file = st.file_uploader(
            "上传填写好的 xlsx 文件",
            type=["xlsx"],
            help="请使用模板格式，确保包含 Action / Data / Expected Result 三列",
            key="import_xlsx_uploader"
        )

        if uploaded_file is not None:
            try:
                df_raw = pd.read_excel(uploaded_file, engine="openpyxl")
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                col_map = {}
                for col in df_raw.columns:
                    col_lower = col.lower()
                    if col_lower == "action":
                        col_map[col] = "Action"
                    elif col_lower == "data":
                        col_map[col] = "Data"
                    elif "expected" in col_lower or "result" in col_lower:
                        col_map[col] = "Expected Result"
                df_raw = df_raw.rename(columns=col_map)

                required_cols = ["Action", "Expected Result"]
                missing_cols = [c for c in required_cols if c not in df_raw.columns]

                if missing_cols:
                    st.error(f"❌ 文件缺少必要列：{missing_cols}。请使用模板文件。")
                else:
                    if "Data" not in df_raw.columns:
                        df_raw["Data"] = ""
                    df_upload = df_raw[
                        df_raw["Action"].notna() &
                        (df_raw["Action"].astype(str).str.strip() != "")
                    ].copy().reset_index(drop=True)

                    if df_upload.empty:
                        st.warning("⚠️ 文件中没有有效的 Test Case 数据（Action 列为空）")
                    else:
                        st.success(f"✅ 解析成功，共 **{len(df_upload)}** 条 Test Cases")
                        preview_df = df_upload[["Action", "Data", "Expected Result"]].copy()
                        preview_df.index = preview_df.index + 1
                        preview_df.index.name = "#"
                        st.dataframe(preview_df, use_container_width=True)
                        df_cases = df_upload

            except Exception as parse_err:
                st.error(f"❌ 解析文件失败: {str(parse_err)}")
                import traceback
                with st.expander("🔍 错误详情"):
                    st.code(traceback.format_exc())

    # ---------- Tab 2: 手动填写 ----------
    with tab_manual:
        st.markdown("逐行填写测试用例，**Action** 为必填项，**Data** 可留空。")

        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        with btn_col1:
            if st.button("➕ 添加一行", key="manual_add_row"):
                st.session_state.manual_cases.append(
                    {"Action": "", "Data": "", "Expected Result": ""}
                )
                st.rerun()
        with btn_col2:
            if st.button("🗑️ 清空所有行", key="manual_clear_rows"):
                st.session_state.manual_cases = [{"Action": "", "Data": "", "Expected Result": ""}]
                st.rerun()

        st.markdown("")

        rows_to_delete = []
        for row_idx, case_item in enumerate(st.session_state.manual_cases):
            row_cols = st.columns([3, 2, 3, 0.5])
            with row_cols[0]:
                new_action = st.text_input(
                    f"Action #{row_idx + 1}",
                    value=case_item.get("Action", ""),
                    placeholder="操作步骤（必填）",
                    key=f"manual_action_{row_idx}",
                    label_visibility="collapsed" if row_idx > 0 else "visible"
                )
                st.session_state.manual_cases[row_idx]["Action"] = new_action
            with row_cols[1]:
                new_data = st.text_input(
                    f"Data #{row_idx + 1}",
                    value=case_item.get("Data", ""),
                    placeholder="测试数据（可选）",
                    key=f"manual_data_{row_idx}",
                    label_visibility="collapsed" if row_idx > 0 else "visible"
                )
                st.session_state.manual_cases[row_idx]["Data"] = new_data
            with row_cols[2]:
                new_result = st.text_input(
                    f"Expected Result #{row_idx + 1}",
                    value=case_item.get("Expected Result", ""),
                    placeholder="预期结果（必填）",
                    key=f"manual_result_{row_idx}",
                    label_visibility="collapsed" if row_idx > 0 else "visible"
                )
                st.session_state.manual_cases[row_idx]["Expected Result"] = new_result
            with row_cols[3]:
                if row_idx == 0:
                    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                if st.button("✕", key=f"manual_del_{row_idx}",
                             help="删除此行",
                             disabled=len(st.session_state.manual_cases) <= 1):
                    rows_to_delete.append(row_idx)

        if rows_to_delete:
            for del_idx in sorted(rows_to_delete, reverse=True):
                st.session_state.manual_cases.pop(del_idx)
            st.rerun()

        st.markdown(
            "<small style='color:#888'>列说明：Action（操作步骤）| Data（测试数据）| Expected Result（预期结果）| 删除</small>",
            unsafe_allow_html=True
        )

        valid_manual = [
            r for r in st.session_state.manual_cases
            if r.get("Action", "").strip()
        ]
        if valid_manual:
            df_manual = pd.DataFrame(valid_manual)[["Action", "Data", "Expected Result"]]
            df_manual = df_manual.reset_index(drop=True)
            st.success(f"✅ 已填写 **{len(df_manual)}** 条有效 Test Cases（Action 不为空）")
            if st.button("📋 使用手动填写的数据", key="manual_use_data", type="secondary"):
                st.session_state.manual_cases_confirmed = df_manual.to_dict("records")
                st.session_state.df_cases = df_manual
                st.success("✅ 已确认使用手动填写的数据，请点击下方「开始导入」")
        else:
            st.info("💡 请至少填写一行 Action 和 Expected Result")

        if df_cases is None and st.session_state.get("manual_cases_confirmed"):
            df_manual_confirmed = pd.DataFrame(st.session_state.manual_cases_confirmed)
            if not df_manual_confirmed.empty:
                df_cases = df_manual_confirmed

        if st.session_state.get("df_cases") is not None and df_cases is None:
            df_cases = st.session_state.df_cases

    # ===== 区域 C：预览 + 导入 =====
    if df_cases is not None and not df_cases.empty:
        st.markdown("---")
        st.subheader("🚀 开始导入")

        with st.expander(f"👁️ 待导入数据预览（共 {len(df_cases)} 条）", expanded=False):
            preview_df2 = df_cases[["Action", "Data", "Expected Result"]].copy()
            preview_df2.index = preview_df2.index + 1
            preview_df2.index.name = "#"
            st.dataframe(preview_df2, use_container_width=True)

        xray_id = default_xray_id
        xray_secret = default_xray_secret

        import_ready = bool(xray_id and xray_secret and related_ticket.strip())
        if not import_ready:
            st.warning("⚠️ 请确保填写了 Xray Client ID、Client Secret 以及 Related Ticket")

        if st.button("🚀 开始导入", type="primary",
                     disabled=not import_ready, key="import_start_btn"):
            progress_bar = st.progress(0, text="准备中...")
            status_area = st.empty()

            try:
                # ---- Step 1: 获取 Xray Token ----
                status_area.info("🔑 Step 1/4 — 获取 Xray 鉴权 Token...")
                progress_bar.progress(5, text="获取 Xray Token...")
                xray_token = authenticate_xray(xray_id, xray_secret)

                # ---- Step 2: 构建 payload ----
                status_area.info("📝 Step 2/4 — 构建 Test Case 数据...")
                progress_bar.progress(15, text="构建数据...")
                tests_payload = build_tests_payload(
                    df_cases,
                    selected_sp_team,
                    selected_priority,
                    title_mode,
                    custom_title,
                )
                progress_bar.progress(20, text=f"构建完成，共 {len(tests_payload)} 条...")

                # ---- Step 3: 批量提交 + 轮询 ----
                status_area.info(
                    f"📤 Step 3/4 — 提交 {len(tests_payload)} 条 Test Cases 到 Xray..."
                )
                progress_bar.progress(25, text="提交导入任务...")

                job_id, direct_keys = submit_tests_bulk(xray_token, tests_payload)

                if job_id:
                    def poll_progress_cb(poll_count, max_polls, msg):
                        poll_pct = 25 + int((poll_count / max_polls) * 45)
                        progress_bar.progress(poll_pct, text=msg)
                        status_area.info(f"⏳ Step 3/4 — {msg}")

                    created_keys = poll_job_status(
                        xray_token, job_id, progress_cb=poll_progress_cb
                    )
                else:
                    created_keys = direct_keys

                progress_bar.progress(
                    70, text=f"导入完成！获取到 {len(created_keys)} 个 Test Cases..."
                )

                # ---- Step 4: 关联 Related Ticket ----
                related_ticket_clean = related_ticket.strip().upper()
                link_successes = []
                link_failures = []

                if created_keys and related_ticket_clean:
                    status_area.info(
                        f"🔗 Step 4/4 — 查询 {related_ticket_clean} 类型并建立关联..."
                    )
                    jira_headers = build_jira_auth_headers(config_email, api_token)
                    jira_headers["Accept"] = "application/json"

                    issue_type, numeric_id = query_related_ticket(
                        base_url, jira_headers, related_ticket_clean
                    )
                    is_test_set = issue_type == "Test Set"

                    if is_test_set and numeric_id:
                        status_area.info(
                            f"🔗 Step 4/4 — 通过 Xray GraphQL 加入 Test Set "
                            f"{related_ticket_clean}..."
                        )
                        progress_bar.progress(75, text="查询 Test Case IDs...")
                        test_numeric_ids = get_test_numeric_ids(
                            base_url, jira_headers, created_keys
                        )
                        progress_bar.progress(
                            85,
                            text=f"添加 {len(test_numeric_ids)} 个 Test Cases 到 Test Set..."
                        )
                        if test_numeric_ids:
                            link_successes, link_failures = link_tests_to_test_set(
                                xray_token, numeric_id, test_numeric_ids
                            )
                            if link_successes and not link_failures:
                                st.warning("⚠️ Xray 提示: 有关联警告")
                    else:
                        status_area.info(
                            f"🔗 Step 4/4 — 通过 Jira issueLink 建立 is tested by 关联..."
                        )
                        for i, test_key in enumerate(created_keys):
                            link_pct = 70 + int(((i + 1) / len(created_keys)) * 25)
                            progress_bar.progress(
                                link_pct,
                                text=f"关联中 {i+1}/{len(created_keys)}: {test_key}"
                            )
                        link_successes, link_failures = link_tests_to_story(
                            base_url, jira_headers, created_keys,
                            related_ticket_clean
                        )

                progress_bar.progress(100, text="✅ 全部完成！")
                status_area.empty()

                # ---- 展示导入结果 ----
                st.markdown("---")
                st.subheader("📊 导入结果")

                total = len(tests_payload)
                imported = len(created_keys)
                linked = len(link_successes)

                result_c1, result_c2, result_c3 = st.columns(3)
                result_c1.metric("📤 提交数量", total)
                result_c2.metric("✅ 成功创建", imported)
                result_c3.metric("🔗 成功关联", linked)

                if created_keys:
                    with st.expander(
                            f"✅ 已创建的 Test Cases（{len(created_keys)} 条）",
                            expanded=True):
                        for k in created_keys:
                            st.markdown(f"- [{k}]({base_url}/browse/{k})")

                if related_ticket_clean:
                    if link_successes:
                        if is_test_set:
                            st.success(
                                f"🔗 已通过 Xray GraphQL 将 {len(link_successes)} 个 "
                                f"Test Cases 添加到 Test Set **{related_ticket_clean}**"
                            )
                        else:
                            st.success(
                                f"🔗 已成功将 {len(link_successes)} 个 Test Cases 与 "
                                f"**{related_ticket_clean}** 建立 is tested by 关联"
                            )
                    if link_failures:
                        with st.expander(
                                f"⚠️ {len(link_failures)} 个关联失败", expanded=False):
                            for lf in link_failures:
                                st.write(f"- **{lf['key']}**: {lf['error']}")

                st.session_state.import_results = {
                    "total": total,
                    "imported": imported,
                    "created_keys": created_keys,
                    "linked": linked,
                    "link_failures": link_failures,
                }
                st.session_state.pop("manual_cases_confirmed", None)
                st.session_state.pop("df_cases", None)

            except XrayAuthError as e:
                status_area.error(f"❌ {str(e)}")
            except XrayImportError as e:
                status_area.error(f"❌ {str(e)}")
                with st.expander("🔍 错误详情"):
                    st.code(str(e))
            except XrayJobFailedError as e:
                status_area.error(f"❌ Xray 导入任务失败: {str(e)}")
                with st.expander("🔍 错误详情"):
                    st.json(str(e))
            except XrayJobTimeoutError as e:
                status_area.error(f"❌ 轮询超时: {str(e)}")
            except Exception as e:
                status_area.error(f"❌ 导入过程发生错误: {str(e)}")
                import traceback
                with st.expander("🔍 错误详情"):
                    st.code(traceback.format_exc())
