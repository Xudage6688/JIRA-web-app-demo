"""
Services Images 审批人查询的纯函数逻辑（可单测，不依赖 Streamlit / 网络）

kustomize 仓库的提交人恒为部署机器人（qimabot），无法反映真实操作人。
真实操作人来自 CircleCI 对应环境 approval job 的 approved_by，
因此需要用镜像标签末尾的 commit sha 反查 pipeline。
"""

import re
from typing import Dict, List, Optional


# 环境 -> approval job 名称中可能出现的关键词
# 注意 'preprod' 本身包含 'prod'，prod 匹配时必须排除 preprod
ENVIRONMENT_KEYWORDS: Dict[str, List[str]] = {
  'dev': ['dev'],
  'preprod': ['preprod', 'pre-prod', 'pre prod'],
  'staging': ['staging'],
  'prod': ['production', 'prod'],
}

# 镜像标签末尾的 commit sha（7~40 位十六进制）
_SHA_SUFFIX_PATTERN = re.compile(r'([0-9a-f]{7,40})$', re.IGNORECASE)

# kustomize 目录名常见于 CircleCI 项目名之外的后缀，按长到短依次剥离
_PROJECT_NAME_SUFFIXES = ['-service-cloud', '-cloud', '-service']


def buildProjectCandidates(
  service_name: str,
  project_mappings: Optional[Dict[str, str]] = None
) -> List[str]:
  """
  生成服务对应的 CircleCI 项目名候选列表

  kustomize 目录名与 CircleCI 项目名并不总是一致
  （如 claim-service-cloud 对应 CircleCI 的 claim），
  显式映射优先，其次按已知后缀逐级剥离。

  Args:
    service_name: kustomize 目录名
    project_mappings: 显式映射 {kustomize 目录名: CircleCI 项目名}

  Returns:
    去重后的候选项目名列表，按尝试优先级排序
  """
  if not service_name:
    return []

  candidates: List[str] = []
  mapped = (project_mappings or {}).get(service_name)
  if mapped:
    candidates.append(mapped)

  candidates.append(service_name)
  for suffix in _PROJECT_NAME_SUFFIXES:
    if service_name.endswith(suffix):
      trimmed = service_name[: -len(suffix)]
      if trimmed:
        candidates.append(trimmed)

  return list(dict.fromkeys(candidates))


def extractCommitSha(image_tag: Optional[str]) -> Optional[str]:
  """
  从镜像标签末尾提取 commit sha

  Args:
    image_tag: 镜像标签，如 'master-26.07.21-SNAPSHOT-f94a18c'

  Returns:
    commit sha 字符串，无法提取时返回 None
  """
  if not image_tag or image_tag == 'N/A':
    return None

  last_segment = str(image_tag).rsplit('-', 1)[-1]
  matched = _SHA_SUFFIX_PATTERN.match(last_segment)
  if not matched:
    return None

  sha = matched.group(1)
  # 纯数字段（如版本号 1.184.0 拆出的 "0"）不是 sha
  if sha.isdigit():
    return None
  return sha.lower()


def matchesEnvironment(job_name: str, environment: str) -> bool:
  """
  判断 approval job 名称是否属于指定环境

  Args:
    job_name: approval job 名称，如 'Do you want to deploy aca-new on preprod?'
    environment: 环境名称（dev/preprod/staging/prod）

  Returns:
    是否匹配该环境
  """
  if not job_name or not environment:
    return False

  name_lower = job_name.lower()
  keywords = ENVIRONMENT_KEYWORDS.get(environment.lower(), [environment.lower()])

  # prod 与 preprod 前缀重叠，含 preprod 的 job 不能算作 prod
  if environment.lower() == 'prod':
    for preprod_keyword in ENVIRONMENT_KEYWORDS['preprod']:
      if preprod_keyword in name_lower:
        return False

  return any(keyword in name_lower for keyword in keywords)


def selectApprovalJob(
  jobs: List[Dict],
  environment: str,
  service_name: Optional[str] = None
) -> Optional[Dict]:
  """
  从 workflow 的 job 列表中挑出目标环境已审批的 approval job

  同一条 pipeline 可能为多个服务分别生成 approval job
  （如 aca-new 的 pipeline 同时含 lab-photos 的 job），
  因此在环境匹配的基础上优先选择名称含服务名的 job。

  Args:
    jobs: workflow 的 job 列表（CircleCI API 原始结构）
    environment: 环境名称（dev/preprod/staging/prod）
    service_name: 服务名称，用于在多服务 pipeline 中消歧

  Returns:
    匹配的 job 字典，未找到返回 None
  """
  candidates = [
    job for job in (jobs or [])
    if job.get('type') == 'approval'
    and job.get('status') == 'success'
    and matchesEnvironment(job.get('name', ''), environment)
  ]

  if not candidates:
    return None

  if service_name:
    service_lower = service_name.lower()
    named = [
      job for job in candidates
      if service_lower in job.get('name', '').lower()
    ]
    if named:
      return named[0]
    # 多服务 pipeline 中名称未命中时禁止回退到第一个候选，避免串号
    # （如查 lab-photos 却拿到 aca-new 的审批人）
    if len(candidates) > 1:
      return None

  return candidates[0]
