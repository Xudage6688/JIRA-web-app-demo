"""监控 Tab 自动审批 Preprod 纯逻辑

从 monitor_view 中抽出的可测试逻辑：筛选 preprod 待审批 Job、批量审批、
判断 Pipeline 是否仍有活动 Workflow（决定自动轮询是否继续）。
"""
from typing import Callable, Dict, List, Optional, Tuple

from circleCi.pipeline_data import approve_job

# 处于这些状态的 workflow 视为「未结束」，自动轮询继续
ACTIVE_WORKFLOW_STATUSES = {'running', 'queued', 'on_hold', 'failing'}

# Preprod 部署 Job 名称子串（如 deploy-docker-image-on-preprod-aca-new）
PREPROD_DEPLOY_JOB_SUBSTR = 'deploy-docker-image-on-preprod'

# 部署 Job 仍在进行中的状态
IN_PROGRESS_JOB_STATUSES = {'running', 'queued'}

# 部署 Job 尚未开始（CircleCI 在审批前常显示 blocked / not_running）
DEPLOY_NOT_STARTED_STATUSES = {'blocked', 'not_running', 'not_run', 'on_hold'}

# preprod 自动模式状态（get_preprod_auto_mode_status 返回值）
PREPROD_AUTO_POLLING = 'polling'
PREPROD_AUTO_DEPLOY_SUCCESS = 'deploy_success'
PREPROD_AUTO_DEPLOY_FAILED = 'deploy_failed'
PREPROD_AUTO_IDLE = 'idle'


def find_pending_preprod_approvals(
    workflows: Optional[List[Dict]],
    wf_jobs_map: Dict[str, List[Dict]],
    target_env: str = 'preprod',
) -> List[Dict]:
    """从 workflows + jobs 映射中筛选目标环境的待审批 approval Job

    命中的 job 会被原地附加 `_workflow_id` / `_workflow_name`（与
    monitor_view._refresh_workflows 中 pending 列表的结构一致）。

    Args:
        workflows: workflow 列表（每项含 id/name/status）
        wf_jobs_map: workflow_id -> jobs 列表
        target_env: 目标环境关键字（小写子串匹配 job 名）

    Returns:
        待审批 job 列表
    """
    pending = []
    env = target_env.lower()
    for wf in (workflows or []):
        wf_id = wf.get('id')
        for job in wf_jobs_map.get(wf_id, []):
            if job.get('type') != 'approval' or job.get('status') != 'on_hold':
                continue
            if env not in job.get('name', '').lower():
                continue
            job['_workflow_id'] = wf_id
            job['_workflow_name'] = wf.get('name')
            pending.append(job)
    return pending


def auto_approve_jobs(
    pending: List[Dict],
    api_token: str,
    approve_fn: Callable = approve_job,
) -> Tuple[List[Dict], List[Dict]]:
    """逐个审批 pending 列表中的 Job

    Args:
        pending: find_pending_preprod_approvals 返回的 job 列表
            （每项需含 `_workflow_id` 和 `approval_request_id`）
        api_token: CircleCI API Token
        approve_fn: 审批函数，默认 pipeline_data.approve_job；测试时注入 mock

    Returns:
        (approved, failed)；失败的 job 原地附加 `_approve_error`
    """
    approved: List[Dict] = []
    failed: List[Dict] = []
    for job in pending:
        try:
            res = approve_fn(
                job.get('_workflow_id'),
                job.get('approval_request_id'),
                api_token=api_token,
            )
        except Exception as e:
            res = {'success': False, 'error': str(e)}
        if res.get('success'):
            approved.append(job)
        else:
            job['_approve_error'] = res.get('error', '未知错误')
            failed.append(job)
    return approved, failed


def has_active_workflows(workflows: Optional[List[Dict]]) -> bool:
    """是否仍有未结束的 Workflow（用于决定是否继续自动轮询）"""
    return any(
        w.get('status') in ACTIVE_WORKFLOW_STATUSES for w in (workflows or [])
    )


def _is_preprod_approval_job(job: Dict) -> bool:
    """是否为 preprod 环境的 approval Job"""
    return (
        job.get('type') == 'approval'
        and 'preprod' in job.get('name', '').lower()
    )


def _is_preprod_deploy_job(job: Dict) -> bool:
    """是否为 preprod 镜像部署 Job"""
    return PREPROD_DEPLOY_JOB_SUBSTR in job.get('name', '').lower()


def _collect_preprod_deploy_jobs(
    workflows: Optional[List[Dict]],
    wf_jobs_map: Dict[str, List[Dict]],
) -> List[Tuple[Dict, Dict]]:
    """收集 workflow 与 preprod 部署 Job 对"""
    pairs: List[Tuple[Dict, Dict]] = []
    for wf in (workflows or []):
        wf_id = wf.get('id')
        for job in wf_jobs_map.get(wf_id, []):
            if _is_preprod_deploy_job(job):
                pairs.append((wf, job))
    return pairs


def get_preprod_auto_mode_status(
    workflows: Optional[List[Dict]],
    wf_jobs_map: Dict[str, List[Dict]],
) -> str:
    """preprod 自动模式应处的状态

    返回:
        polling — 继续 10 秒轮询
        deploy_success — preprod 部署已成功结束，停止轮询
        deploy_failed — preprod 部署失败，停止轮询
        idle — 无 preprod 相关工作且 Pipeline 已结束

    停止策略:
        - 出现 deploy-docker-image-on-preprod-* 且全部达终态后停止
          （即使 Workflow 仍在等待 staging/prod 审批）
        - 若同一 Workflow 内多个顺序部署 Job：在 Workflow 仍为 running 且
          当前可见的 preprod 部署 Job 均已 success 时继续轮询，等待后续 Job 出现
    """
    found_preprod_deploy = False
    found_any_preprod_signal = False

    for wf in (workflows or []):
        wf_id = wf.get('id')
        for job in wf_jobs_map.get(wf_id, []):
            if _is_preprod_approval_job(job):
                found_any_preprod_signal = True
                if job.get('status') == 'on_hold':
                    return PREPROD_AUTO_POLLING

            if _is_preprod_deploy_job(job):
                found_preprod_deploy = True
                found_any_preprod_signal = True
                if job.get('status') in IN_PROGRESS_JOB_STATUSES:
                    return PREPROD_AUTO_POLLING

    if found_preprod_deploy:
        deploy_pairs = _collect_preprod_deploy_jobs(workflows, wf_jobs_map)
        if any(job.get('status') == 'failed' for _, job in deploy_pairs):
            return PREPROD_AUTO_DEPLOY_FAILED

        if any(
            job.get('status') in IN_PROGRESS_JOB_STATUSES for _, job in deploy_pairs
        ):
            return PREPROD_AUTO_POLLING

        if any(
            job.get('status') in DEPLOY_NOT_STARTED_STATUSES for _, job in deploy_pairs
        ):
            return PREPROD_AUTO_POLLING

        success_deploys = [
            job for _, job in deploy_pairs if job.get('status') == 'success'
        ]
        if not success_deploys:
            return (
                PREPROD_AUTO_POLLING
                if has_active_workflows(workflows)
                else PREPROD_AUTO_IDLE
            )

        for wf in (workflows or []):
            wf_id = wf.get('id')
            wf_deploy_jobs = [
                j for j in wf_jobs_map.get(wf_id, []) if _is_preprod_deploy_job(j)
            ]
            if not wf_deploy_jobs:
                continue
            if wf.get('status') == 'running' and all(
                j.get('status') == 'success' for j in wf_deploy_jobs
            ):
                return PREPROD_AUTO_POLLING

        return PREPROD_AUTO_DEPLOY_SUCCESS

    for wf in (workflows or []):
        wf_id = wf.get('id')
        jobs = wf_jobs_map.get(wf_id, [])
        approval_done = any(
            _is_preprod_approval_job(j) and j.get('status') == 'success'
            for j in jobs
        )
        has_deploy = any(_is_preprod_deploy_job(j) for j in jobs)
        if (
            approval_done
            and not has_deploy
            and wf.get('status') in ACTIVE_WORKFLOW_STATUSES
        ):
            return PREPROD_AUTO_POLLING

    if not found_any_preprod_signal and has_active_workflows(workflows):
        return PREPROD_AUTO_POLLING

    return PREPROD_AUTO_IDLE


def has_pending_preprod_work(
    workflows: Optional[List[Dict]],
    wf_jobs_map: Dict[str, List[Dict]],
) -> bool:
    """是否仍有 preprod 审批/部署相关的未完成工作（需继续自动轮询）"""
    return get_preprod_auto_mode_status(workflows, wf_jobs_map) == PREPROD_AUTO_POLLING
