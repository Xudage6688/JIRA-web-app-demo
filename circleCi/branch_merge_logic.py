"""GitHub 远程多分支合并纯逻辑

通过 GitHub REST API 在远端创建合并分支并顺序 merge，无需本地 clone。
冲突时自动创建 PR，便于在 GitHub 上线解决。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence
from urllib.parse import quote

import requests

from modules.user_config_loader import parse_api_error_message, sanitize_error_message

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 30
PR_MERGEABLE_POLL_ATTEMPTS = 6
PR_MERGEABLE_POLL_INTERVAL_SECONDS = 1.0
# 合并分支统一加此前缀，避免与源分支同名冲突：
# 已有 refs/heads/feat-SP-35008 时无法再创建 feat-SP-35008/xxx
MERGE_BRANCH_PREFIX = "merge"


@dataclass
class MergeResult:
  """合并操作结果"""
  success: bool
  merge_branch: str = ""
  base_branch: str = ""
  merged_branches: List[str] = field(default_factory=list)
  conflict_files: List[str] = field(default_factory=list)
  conflict_at_branch: str = ""
  conflict_step: int = 0
  commit_sha: str = ""
  branch_url: str = ""
  pr_url: str = ""
  pr_urls: List[str] = field(default_factory=list)
  pushed: bool = False
  error: str = ""
  tips: List[str] = field(default_factory=list)
  steps: List[str] = field(default_factory=list)


def parse_branch_names(text: str) -> List[str]:
  """解析用户输入的分支名列表

  支持空格、逗号、换行分隔；去重并保持首次出现顺序。

  Args:
    text: 原始输入文本

  Returns:
    分支名列表（可能为空或不足 2 个）
  """
  import re

  if not text or not str(text).strip():
    return []

  parts = re.split(r"[\s,;，；]+", str(text).strip())
  seen = set()
  branches: List[str] = []
  for part in parts:
    name = part.strip()
    if not name or name in seen:
      continue
    seen.add(name)
    branches.append(name)
  return branches


def build_merge_branch_name(branches: Sequence[str]) -> str:
  """根据分支列表生成合并分支名

  使用 `merge/<branch1>/<branch2>/...`，避免源分支名作为路径前缀时
  与已有分支引用冲突（Git 不允许同时存在 `feat-X` 与 `feat-X/yyy`）。

  Args:
    branches: 源分支列表

  Returns:
    带 merge/ 前缀、以 '/' 连接的合并分支名
  """
  return f"{MERGE_BRANCH_PREFIX}/{'/'.join(branches)}"


def is_ref_update_failed_error(message: str) -> bool:
  """判断是否为 Git 引用更新失败（常见于分支路径冲突）

  Args:
    message: 错误文本

  Returns:
    是否为 Reference update failed 类错误
  """
  if not message:
    return False
  lower = message.lower()
  return (
    "reference update failed" in lower
    or "cannot lock ref" in lower
    or "exists; cannot create" in lower
  )


def build_ref_conflict_tips(merge_branch: str, base_branch: str) -> List[str]:
  """生成引用路径冲突的处理建议

  Args:
    merge_branch: 目标合并分支名
    base_branch: 基分支名

  Returns:
    中文提示列表
  """
  return [
    "Git 不允许同时存在同名分支与其「子路径」分支"
    f"（例如已有 `{base_branch}`，就不能再创建 `{base_branch}/xxx`）。",
    f"当前目标分支：`{merge_branch}`。",
    "本工具已使用 `merge/` 前缀规避该问题；若仍失败，请检查是否已有同名合并分支，"
    "或勾选「覆盖重建」后重试。",
    "也可在 GitHub 上手动删除冲突的旧合并分支后再试。",
  ]


def build_github_branch_url(organization: str, service: str, branch: str) -> str:
  """构建 GitHub 分支页面 URL

  Args:
    organization: GitHub 组织名
    service: 仓库/服务名
    branch: 分支名

  Returns:
    分支页面 URL
  """
  return f"https://github.com/{organization}/{service}/tree/{branch}"


def build_conflict_tips(
  base_branch: str,
  conflict_at_branch: str,
  conflict_step: int,
  pr_url: str = "",
) -> List[str]:
  """生成远程合并冲突友好提示

  Args:
    base_branch: 基分支
    conflict_at_branch: 发生冲突时正在合并的分支
    conflict_step: 合并步骤序号
    pr_url: 冲突对应的 PR 链接（如有）

  Returns:
    中文提示列表
  """
  tips = [
    f"冲突发生在远程合并第 {conflict_step} 个分支 `{conflict_at_branch}` 时"
    f"（合并分支由 `{base_branch}` 创建）。",
    "本次操作在 GitHub 服务端完成，不会占用本机磁盘克隆整仓。",
  ]
  if pr_url:
    tips.append(f"已自动创建冲突 PR，请在 GitHub 上解决后 Merge：{pr_url}")
  tips.extend([
    "建议：在 PR 页面查看冲突文件，或联系对应开发同学协商解决。",
    "也可减少一次合并的分支数量，先两两合并成功后再继续合入其余分支。",
  ])
  return tips


def build_github_headers(github_token: str) -> dict:
  """构建 GitHub API 请求头

  Args:
    github_token: GitHub Personal Access Token

  Returns:
    headers dict
  """
  return {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {github_token}",
    "X-GitHub-Api-Version": "2022-11-28",
  }


def merge_service_branches(
  service: str,
  branches: Sequence[str],
  organization: str,
  github_token: str,
  force_recreate: bool = False,
  create_prs: bool = True,
  progress_callback: Optional[Callable[[str], None]] = None,
  http_session: Optional[requests.Session] = None,
  project_root=None,
  push: bool = True,
) -> MergeResult:
  """通过 GitHub API 远程合并多个分支到新的合并分支

  流程：
  1. 校验源分支存在
  2. 以第 1 个分支为基，创建/重置合并分支
  3. 对其余分支依次：创建 PR → 检查可合并性 → Merge PR
  4. 冲突时保留 PR 链接供在 GitHub 上解决

  Args:
    service: 服务/仓库名
    branches: 源分支列表（至少 2 个，第一个为基分支）
    organization: GitHub 组织名
    github_token: GitHub Token（需 repo 权限）
    force_recreate: 目标合并分支已存在时是否强制重置为基分支
    create_prs: True 时以 PR 形式合并；False 时用 Merges API（无 PR）
    progress_callback: 可选进度回调
    http_session: 可选 requests.Session
    project_root: 兼容旧调用签名，忽略
    push: 兼容旧调用签名，远程合并始终落在远端

  Returns:
    MergeResult 结构化结果
  """
  del project_root, push  # 兼容旧参数
  steps: List[str] = []

  def report(message: str) -> None:
    """记录并回调进度消息"""
    steps.append(message)
    logger.info(message)
    if progress_callback:
      progress_callback(message)

  branch_list = [b.strip() for b in branches if b and str(b).strip()]
  if len(branch_list) < 2:
    return MergeResult(success=False, error="至少需要 2 个分支名才能合并", steps=steps)

  if not service or not str(service).strip():
    return MergeResult(success=False, error="请选择服务名称", steps=steps)

  if not organization or not str(organization).strip():
    return MergeResult(success=False, error="缺少 GitHub 组织名", steps=steps)

  if not github_token or not str(github_token).strip():
    return MergeResult(
      success=False,
      error="缺少 GitHub Token，请在 users_config.json 配置或在页面输入",
      steps=steps,
    )

  service_name = str(service).strip()
  org = str(organization).strip()
  token = str(github_token).strip()
  base_branch = branch_list[0]
  merge_branch = build_merge_branch_name(branch_list)
  headers = build_github_headers(token)
  owns_session = http_session is None
  session = http_session or requests.Session()
  pr_urls: List[str] = []

  try:
    report(f"远程仓库: {org}/{service_name}（无本地 clone）")

    report("校验远程源分支是否存在...")
    missing = []
    branch_shas = {}
    for branch in branch_list:
      sha, err = _get_branch_sha(session, headers, org, service_name, branch)
      if err:
        missing.append(branch)
      else:
        branch_shas[branch] = sha
    if missing:
      return MergeResult(
        success=False,
        merge_branch=merge_branch,
        base_branch=base_branch,
        error=f"以下分支在远程不存在: {', '.join(missing)}",
        tips=["请确认分支名拼写，或先在 GitHub 上确认分支已推送。"],
        steps=steps,
      )

    base_sha = branch_shas[base_branch]
    report(f"基于 `{base_branch}` ({base_sha[:8]}) 准备合并分支 `{merge_branch}`")
    ensure_err = _ensure_merge_branch(
      session=session,
      headers=headers,
      organization=org,
      service=service_name,
      merge_branch=merge_branch,
      base_sha=base_sha,
      force_recreate=force_recreate,
      report=report,
    )
    if ensure_err:
      tips = ["若远程已有同名合并分支，请勾选「目标分支已存在时覆盖重建」。"]
      if is_ref_update_failed_error(ensure_err):
        tips = build_ref_conflict_tips(merge_branch, base_branch)
      return MergeResult(
        success=False,
        merge_branch=merge_branch,
        base_branch=base_branch,
        error=ensure_err,
        tips=tips,
        steps=steps,
      )

    merged: List[str] = [base_branch]
    latest_sha = base_sha

    for index, branch in enumerate(branch_list[1:], start=2):
      report(f"远程合并分支 ({index}/{len(branch_list)}): `{branch}` → `{merge_branch}`")
      if create_prs:
        step_result = _merge_via_pull_request(
          session=session,
          headers=headers,
          organization=org,
          service=service_name,
          base_branch=merge_branch,
          head_branch=branch,
          report=report,
        )
      else:
        step_result = _merge_via_merges_api(
          session=session,
          headers=headers,
          organization=org,
          service=service_name,
          base_branch=merge_branch,
          head_branch=branch,
          report=report,
        )

      if step_result.get("pr_url"):
        pr_urls.append(step_result["pr_url"])

      if not step_result.get("success"):
        pr_url = step_result.get("pr_url", "")
        tips = build_conflict_tips(
          base_branch=base_branch,
          conflict_at_branch=branch,
          conflict_step=index,
          pr_url=pr_url,
        )
        if step_result.get("tips"):
          tips.extend(step_result["tips"])
        return MergeResult(
          success=False,
          merge_branch=merge_branch,
          base_branch=base_branch,
          merged_branches=merged,
          conflict_at_branch=branch,
          conflict_step=index,
          commit_sha=latest_sha,
          branch_url=build_github_branch_url(org, service_name, merge_branch),
          pr_url=pr_url,
          pr_urls=pr_urls,
          pushed=True,
          error=step_result.get("error", f"合并 `{branch}` 失败"),
          tips=tips,
          steps=steps,
        )

      latest_sha = step_result.get("sha") or latest_sha
      merged.append(branch)

    branch_url = build_github_branch_url(org, service_name, merge_branch)
    report("远程合并完成")
    return MergeResult(
      success=True,
      merge_branch=merge_branch,
      base_branch=base_branch,
      merged_branches=merged,
      commit_sha=latest_sha,
      branch_url=branch_url,
      pr_urls=pr_urls,
      pushed=True,
      steps=steps,
    )
  except requests.exceptions.Timeout:
    return MergeResult(
      success=False,
      merge_branch=merge_branch,
      base_branch=base_branch,
      error="请求 GitHub API 超时",
      steps=steps,
    )
  except requests.exceptions.RequestException as exc:
    err = sanitize_error_message(str(exc))
    logger.error("GitHub merge request failed: %s", err)
    return MergeResult(
      success=False,
      merge_branch=merge_branch,
      base_branch=base_branch,
      error=err,
      steps=steps,
    )
  except Exception as exc:
    err = sanitize_error_message(str(exc))
    logger.error("merge_service_branches failed: %s", err)
    return MergeResult(
      success=False,
      merge_branch=merge_branch,
      base_branch=base_branch,
      error=err,
      steps=steps,
    )
  finally:
    if owns_session:
      session.close()


def _repo_api(organization: str, service: str, path: str = "") -> str:
  """拼接仓库 API URL

  Args:
    organization: 组织名
    service: 仓库名
    path: 相对路径（不含前导 /）

  Returns:
    完整 API URL
  """
  base = f"{GITHUB_API_BASE}/repos/{organization}/{service}"
  return f"{base}/{path}" if path else base


def _get_branch_sha(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  branch: str,
) -> tuple[Optional[str], str]:
  """获取分支最新 commit SHA

  Args:
    session: HTTP Session
    headers: 请求头
    organization: 组织名
    service: 仓库名
    branch: 分支名

  Returns:
    (sha, error_message)
  """
  url = _repo_api(organization, service, f"git/ref/heads/{quote(branch, safe='')}")
  response = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
  if response.status_code == 404:
    return None, "not found"
  if response.status_code != 200:
    return None, parse_api_error_message(response)

  data = response.json()
  # 偶发同名目录时返回列表
  if isinstance(data, list):
    for item in data:
      ref = item.get("ref", "")
      if ref == f"refs/heads/{branch}":
        return item.get("object", {}).get("sha"), ""
    return None, "not found"
  sha = data.get("object", {}).get("sha")
  if not sha:
    return None, "empty sha"
  return sha, ""


def _ensure_merge_branch(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  merge_branch: str,
  base_sha: str,
  force_recreate: bool,
  report: Callable[[str], None],
) -> str:
  """创建或重置合并分支到基分支 SHA

  Args:
    session: HTTP Session
    headers: 请求头
    organization: 组织名
    service: 仓库名
    merge_branch: 合并分支名
    base_sha: 基分支 SHA
    force_recreate: 已存在时是否强制重置
    report: 进度回调

  Returns:
    错误信息；空字符串表示成功
  """
  existing_sha, _ = _get_branch_sha(session, headers, organization, service, merge_branch)
  if existing_sha:
    if not force_recreate:
      return (
        f"远程已存在合并分支 `{merge_branch}`。"
        "如需覆盖重建，请勾选「目标分支已存在时覆盖重建」。"
      )
    report(f"覆盖重建合并分支 `{merge_branch}` → {base_sha[:8]}")
    url = _repo_api(
      organization, service, f"git/refs/heads/{quote(merge_branch, safe='')}"
    )
    response = session.patch(
      url,
      headers=headers,
      json={"sha": base_sha, "force": True},
      timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    if response.status_code not in (200, 201):
      return sanitize_error_message(parse_api_error_message(response))
    return ""

  report(f"创建合并分支 `{merge_branch}`")
  url = _repo_api(organization, service, "git/refs")
  response = session.post(
    url,
    headers=headers,
    json={"ref": f"refs/heads/{merge_branch}", "sha": base_sha},
    timeout=DEFAULT_TIMEOUT_SECONDS,
  )
  if response.status_code not in (200, 201):
    return sanitize_error_message(parse_api_error_message(response))
  return ""


def _merge_via_merges_api(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  base_branch: str,
  head_branch: str,
  report: Callable[[str], None],
) -> dict:
  """使用 GitHub Merges API 合并分支

  Args:
    session: HTTP Session
    headers: 请求头
    organization: 组织名
    service: 仓库名
    base_branch: 目标分支
    head_branch: 源分支
    report: 进度回调

  Returns:
    结果 dict: success/error/sha/pr_url/tips
  """
  url = _repo_api(organization, service, "merges")
  response = session.post(
    url,
    headers=headers,
    json={
      "base": base_branch,
      "head": head_branch,
      "commit_message": f"Merge branch '{head_branch}' into {base_branch}",
    },
    timeout=DEFAULT_TIMEOUT_SECONDS,
  )

  if response.status_code in (200, 201):
    sha = response.json().get("sha", "")
    report(f"Merges API 成功: `{head_branch}` → `{base_branch}` ({sha[:8] if sha else 'ok'})")
    return {"success": True, "sha": sha}

  if response.status_code == 204:
    report(f"`{head_branch}` 已包含在 `{base_branch}`，无需合并")
    sha, _ = _get_branch_sha(session, headers, organization, service, base_branch)
    return {"success": True, "sha": sha or ""}

  if response.status_code == 409:
    report(f"检测到冲突，正在创建冲突 PR: `{head_branch}` → `{base_branch}`")
    pr_url, pr_err = _create_pull_request(
      session=session,
      headers=headers,
      organization=organization,
      service=service,
      base_branch=base_branch,
      head_branch=head_branch,
      title=f"[conflict] Merge {head_branch} into {base_branch}",
      body=(
        f"自动合分支时检测到冲突。\n\n"
        f"- Base: `{base_branch}`\n"
        f"- Head: `{head_branch}`\n\n"
        "请在此 PR 中解决冲突后 Merge，或关闭后调整分支再重试。"
      ),
    )
    return {
      "success": False,
      "error": f"合并 `{head_branch}` 时发生冲突",
      "pr_url": pr_url,
      "tips": [pr_err] if pr_err and not pr_url else [],
    }

  return {
    "success": False,
    "error": sanitize_error_message(parse_api_error_message(response)),
  }


def _merge_via_pull_request(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  base_branch: str,
  head_branch: str,
  report: Callable[[str], None],
) -> dict:
  """以创建 PR 并 Merge 的方式合并分支

  Args:
    session: HTTP Session
    headers: 请求头
    organization: 组织名
    service: 仓库名
    base_branch: 目标分支（合并分支）
    head_branch: 源分支
    report: 进度回调

  Returns:
    结果 dict
  """
  pr_url, pr_number, create_err = _create_pull_request_with_number(
    session=session,
    headers=headers,
    organization=organization,
    service=service,
    base_branch=base_branch,
    head_branch=head_branch,
    title=f"Merge {head_branch} into {base_branch}",
    body=(
      f"由 CircleCI 合分支工具自动创建。\n\n"
      f"- Base: `{base_branch}`\n"
      f"- Head: `{head_branch}`\n"
    ),
  )
  if create_err:
    # 若已存在同 head/base 的打开 PR，尝试复用
    existing = _find_open_pull_request(
      session, headers, organization, service, base_branch, head_branch
    )
    if existing:
      pr_url = existing.get("html_url", "")
      pr_number = existing.get("number")
      report(f"复用已有 PR #{pr_number}: {pr_url}")
    else:
      return {"success": False, "error": create_err, "pr_url": pr_url}

  if not pr_number:
    return {"success": False, "error": "未能创建或找到 PR", "pr_url": pr_url}

  report(f"已创建 PR #{pr_number}，检查是否可合并...")
  mergeable, mergeable_state = _wait_for_mergeable(
    session, headers, organization, service, pr_number
  )

  if mergeable is False or mergeable_state == "dirty":
    return {
      "success": False,
      "error": f"PR #{pr_number} 存在合并冲突（`{head_branch}` → `{base_branch}`）",
      "pr_url": pr_url,
    }

  if mergeable is None and mergeable_state not in ("clean", "has_hooks", "unstable"):
    # 状态未知时仍尝试 merge；失败再回退
    report(f"PR #{pr_number} mergeable 状态未知（{mergeable_state}），尝试 Merge...")

  merge_url = _repo_api(organization, service, f"pulls/{pr_number}/merge")
  response = session.put(
    merge_url,
    headers=headers,
    json={
      "commit_title": f"Merge branch '{head_branch}' into {base_branch}",
      "merge_method": "merge",
    },
    timeout=DEFAULT_TIMEOUT_SECONDS,
  )

  if response.status_code in (200, 201):
    data = response.json()
    sha = data.get("sha", "")
    report(f"PR #{pr_number} 已 Merge ({sha[:8] if sha else 'ok'})")
    return {"success": True, "sha": sha, "pr_url": pr_url}

  if response.status_code == 405:
    return {
      "success": False,
      "error": f"PR #{pr_number} 无法 Merge（可能有冲突或分支保护）",
      "pr_url": pr_url,
    }

  if response.status_code == 409:
    return {
      "success": False,
      "error": f"PR #{pr_number} 合并冲突或 head 已变更",
      "pr_url": pr_url,
    }

  return {
    "success": False,
    "error": sanitize_error_message(parse_api_error_message(response)),
    "pr_url": pr_url,
  }


def _create_pull_request(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  base_branch: str,
  head_branch: str,
  title: str,
  body: str,
) -> tuple[str, str]:
  """创建 PR，仅返回 URL

  Returns:
    (pr_url, error)
  """
  pr_url, _, err = _create_pull_request_with_number(
    session, headers, organization, service, base_branch, head_branch, title, body
  )
  return pr_url, err


def _create_pull_request_with_number(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  base_branch: str,
  head_branch: str,
  title: str,
  body: str,
) -> tuple[str, Optional[int], str]:
  """创建 Pull Request

  Returns:
    (html_url, number, error)
  """
  url = _repo_api(organization, service, "pulls")
  response = session.post(
    url,
    headers=headers,
    json={
      "title": title,
      "head": head_branch,
      "base": base_branch,
      "body": body,
    },
    timeout=DEFAULT_TIMEOUT_SECONDS,
  )
  if response.status_code in (200, 201):
    data = response.json()
    return data.get("html_url", ""), data.get("number"), ""

  err = sanitize_error_message(parse_api_error_message(response))
  return "", None, err


def _find_open_pull_request(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  base_branch: str,
  head_branch: str,
) -> Optional[dict]:
  """查找已打开的同 base/head PR

  Returns:
    PR JSON 或 None
  """
  url = _repo_api(organization, service, "pulls")
  response = session.get(
    url,
    headers=headers,
    params={
      "state": "open",
      "base": base_branch,
      "head": f"{organization}:{head_branch}",
      "per_page": 5,
    },
    timeout=DEFAULT_TIMEOUT_SECONDS,
  )
  if response.status_code != 200:
    return None
  items = response.json() or []
  return items[0] if items else None


def _wait_for_mergeable(
  session: requests.Session,
  headers: dict,
  organization: str,
  service: str,
  pr_number: int,
) -> tuple[Optional[bool], str]:
  """轮询 PR mergeable 状态

  GitHub 创建 PR 后 mergeable 可能短暂为 null。

  Returns:
    (mergeable, mergeable_state)
  """
  url = _repo_api(organization, service, f"pulls/{pr_number}")
  mergeable = None
  mergeable_state = ""
  for _ in range(PR_MERGEABLE_POLL_ATTEMPTS):
    response = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
    if response.status_code != 200:
      break
    data = response.json()
    mergeable = data.get("mergeable")
    mergeable_state = data.get("mergeable_state") or ""
    if mergeable is not None:
      break
    time.sleep(PR_MERGEABLE_POLL_INTERVAL_SECONDS)
  return mergeable, mergeable_state
