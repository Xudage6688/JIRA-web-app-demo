"""Tab: GitHub 远程合分支 UI

选择服务、输入多个分支名，通过 GitHub API / PR 在远端合并，无需本地 clone。
"""
from pathlib import Path
from typing import Optional

import streamlit as st

from circleCi.branch_merge_logic import (
  MergeResult,
  build_merge_branch_name,
  merge_service_branches,
  parse_branch_names,
)
from circleCi.pipeline_config import get_services_list
from modules.components import copyable_text


def render_branch_merge_tab(
  project_root: Path,
  organization: str,
  default_project: str,
  github_token: str,
) -> None:
  """渲染合分支 Tab UI

  Args:
    project_root: 项目根路径（用于加载服务列表）
    organization: GitHub 组织名
    default_project: 默认服务名
    github_token: 当前用户 GitHub Token（可为空）
  """
  st.header("🔀 合分支")
  st.info(
    "选择服务并输入 2 个及以上分支名（第一个为基分支）。"
    "系统通过 **GitHub 远程 API / PR** 合并，"
    "例如 `SP-12345` + `SP-54321` → 远程分支 `merge/SP-12345/SP-54321`，"
    "**不会把整仓 clone 到本机**。"
  )

  all_services = get_services_list(project_root, default_project)
  default_service = (
    "aca-new" if "aca-new" in all_services else (default_project if default_project in all_services else all_services[0])
  )
  if "merge_service" not in st.session_state:
    st.session_state.merge_service = default_service

  st.caption(
    "💡 冲突时会自动创建 GitHub PR，可在网页上解决冲突后再 Merge。"
    " 合并分支名带 `merge/` 前缀，避免与源分支路径冲突。"
  )

  st.markdown("---")

  col1, col2 = st.columns([1, 1])
  with col1:
    service_index = 0
    if st.session_state.merge_service in all_services:
      service_index = all_services.index(st.session_state.merge_service)
    service = st.selectbox(
      "服务名称",
      options=all_services,
      index=service_index,
      key="merge_service_select",
      help="对应 GitHub 仓库名，例如 aca-new",
    )
    st.session_state.merge_service = service

  with col2:
    token_from_config = (github_token or "").strip()
    if token_from_config:
      st.success("✅ 已从用户配置加载 GitHub Token")
      effective_token = token_from_config
      override = st.checkbox("临时覆盖 Token", value=False, key="merge_override_token")
      if override:
        effective_token = st.text_input(
          "GitHub Personal Access Token",
          type="password",
          key="merge_github_token_input",
          help="需要 repo 权限，用于创建分支 / PR / Merge",
        )
    else:
      st.warning("⚠️ 未在 users_config 中找到 GitHub Token")
      effective_token = st.text_input(
        "GitHub Personal Access Token",
        type="password",
        key="merge_github_token_input",
        help="需要 repo 权限，用于创建分支 / PR / Merge",
      )

  st.markdown("**分支列表**（每行一个，或用空格/逗号分隔；第一个为基分支）")
  branches_text = st.text_area(
    "分支名",
    height=120,
    placeholder="SP-12345\nSP-54321\nSP-99999",
    key="merge_branches_text",
    label_visibility="collapsed",
  )

  branches = parse_branch_names(branches_text)
  merge_branch_name = build_merge_branch_name(branches) if len(branches) >= 2 else ""

  if branches:
    with st.container(border=True):
      st.markdown("**预览**")
      if len(branches) < 2:
        st.warning("至少需要 2 个不同的分支名")
      else:
        st.write(f"**基分支:** `{branches[0]}`")
        st.write(f"**合并顺序:** {' → '.join(f'`{b}`' for b in branches)}")
        st.write(f"**目标合并分支:** `{merge_branch_name}`")
        st.caption(f"远程路径: `github.com/{organization}/{service}`")

  opt_col1, opt_col2 = st.columns(2)
  with opt_col1:
    create_prs = st.checkbox(
      "以 PR 形式合并（推荐）",
      value=True,
      key="merge_create_prs",
      help="勾选：为每个源分支创建 PR 并 Merge；取消：使用 Merges API（冲突时仍会建 PR）",
    )
  with opt_col2:
    force_recreate = st.checkbox(
      "目标分支已存在时覆盖重建",
      value=False,
      key="merge_force_recreate",
      help="远程已有同名合并分支时，强制重置为基分支后再合并",
    )

  st.markdown("---")
  start_disabled = (
    len(branches) < 2
    or not (effective_token or "").strip()
    or not service
  )
  if st.button(
    "🚀 开始远程合并",
    type="primary",
    use_container_width=True,
    disabled=start_disabled,
    key="merge_start_btn",
  ):
    _run_merge(
      service=service,
      branches=branches,
      organization=organization,
      github_token=effective_token.strip(),
      force_recreate=force_recreate,
      create_prs=create_prs,
    )

  result: Optional[MergeResult] = st.session_state.get("merge_last_result")
  if result is not None:
    st.markdown("---")
    _render_merge_result(result)


def _run_merge(
  service: str,
  branches: list,
  organization: str,
  github_token: str,
  force_recreate: bool,
  create_prs: bool,
) -> None:
  """执行远程合并并保存结果到 session_state

  Args:
    service: 服务名
    branches: 分支列表
    organization: 组织名
    github_token: GitHub Token
    force_recreate: 是否覆盖已存在分支
    create_prs: 是否以 PR 形式合并
  """
  progress_box = st.empty()

  def on_progress(message: str) -> None:
    """更新进度展示"""
    progress_box.info(f"⏳ {message}")

  with st.spinner("正在通过 GitHub API 远程合并，请稍候..."):
    result = merge_service_branches(
      service=service,
      branches=branches,
      organization=organization,
      github_token=github_token,
      force_recreate=force_recreate,
      create_prs=create_prs,
      progress_callback=on_progress,
    )

  st.session_state.merge_last_result = result
  progress_box.empty()
  st.rerun()


def _render_merge_result(result: MergeResult) -> None:
  """渲染最近一次合并结果

  Args:
    result: 合并结果
  """
  st.subheader("最近一次合并结果")

  if result.success:
    st.success("远程合并成功")
    copyable_text("合并分支:", result.merge_branch, "merge_result_branch")
    if result.commit_sha:
      copyable_text("Commit:", result.commit_sha, "merge_result_sha")
    st.write(f"**基分支:** `{result.base_branch}`")
    st.write(f"**已合并:** {' → '.join(f'`{b}`' for b in result.merged_branches)}")
    if result.branch_url:
      st.markdown(f"[在 GitHub 打开合并分支]({result.branch_url})")
    if result.pr_urls:
      with st.expander("相关 PR", expanded=False):
        for url in result.pr_urls:
          st.markdown(f"- {url}")
    st.caption("可在该分支上手动创建 PR，或切到「触发 Pipeline」Tab 触发构建。")
  else:
    st.error(result.error or "合并失败")
    if result.conflict_at_branch:
      st.warning(
        f"冲突分支：`{result.conflict_at_branch}`"
        + (f"（第 {result.conflict_step} 步）" if result.conflict_step else "")
      )
    if result.pr_url:
      st.markdown(f"**冲突 PR:** [{result.pr_url}]({result.pr_url})")
    if result.tips:
      with st.expander("处理建议", expanded=True):
        for tip in result.tips:
          st.markdown(f"- {tip}")
    if result.branch_url:
      st.markdown(f"[查看当前合并分支]({result.branch_url})")

  if result.steps:
    with st.expander("执行步骤日志", expanded=False):
      for step in result.steps:
        st.text(step)
