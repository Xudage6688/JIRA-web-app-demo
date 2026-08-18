"""
单元测试：Services Images 审批人查询纯函数逻辑

测试 modules/_services_approver_logic.py：
- extractCommitSha: 从镜像标签末尾提取 commit sha
- matchesEnvironment: approval job 名称与环境匹配
- selectApprovalJob: 从 job 列表中挑出目标环境已审批的 job
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules._services_approver_logic import (
    buildProjectCandidates,
    extractCommitSha,
    matchesEnvironment,
    selectApprovalJob,
)


class TestExtractCommitSha:
  """测试 extractCommitSha 函数"""

  def test_master_snapshot_tag(self):
    """测试：master SNAPSHOT 标签提取 sha"""
    assert extractCommitSha('master-26.07.21-SNAPSHOT-f94a18c') == 'f94a18c'

  def test_pr_tag(self):
    """测试：PR 标签提取 sha"""
    assert extractCommitSha('pr2869-1.184.0-20e930f85') == '20e930f85'

  def test_long_branch_tag(self):
    """测试：含长分支名的标签提取 sha"""
    tag = 'merge-epic-supplier-confirmation_smart-address-SP-35008-1.184.0-2c2091498'
    assert extractCommitSha(tag) == '2c2091498'

  def test_release_tag(self):
    """测试：release 标签提取 sha"""
    assert extractCommitSha('release-260728-26.07.21-SNAPSHOT-c48da80') == 'c48da80'

  def test_uppercase_sha_normalized(self):
    """测试：大写 sha 归一化为小写"""
    assert extractCommitSha('master-1.0.0-ABCDEF1') == 'abcdef1'

  def test_no_sha_suffix(self):
    """测试：无 sha 后缀返回 None"""
    assert extractCommitSha('master') is None

  def test_pure_version_tag(self):
    """测试：纯版本号结尾（数字）不视为 sha"""
    assert extractCommitSha('release-1.0.0') is None

  def test_na_value(self):
    """测试：N/A 返回 None"""
    assert extractCommitSha('N/A') is None

  def test_empty_and_none(self):
    """测试：空值返回 None"""
    assert extractCommitSha('') is None
    assert extractCommitSha(None) is None

  def test_too_short_suffix(self):
    """测试：短于 7 位的十六进制不视为 sha"""
    assert extractCommitSha('master-1.0.0-abc12') is None


class TestMatchesEnvironment:
  """测试 matchesEnvironment 函数"""

  def test_preprod_lowercase(self):
    """测试：小写 preprod job 名匹配"""
    assert matchesEnvironment('Do you want to deploy aca-new on preprod?', 'preprod') is True

  def test_preprod_capitalized(self):
    """测试：首字母大写 Preprod 匹配"""
    assert matchesEnvironment('Do you want to deploy on Preprod?', 'preprod') is True

  def test_staging(self):
    """测试：staging 匹配"""
    assert matchesEnvironment('Do you want to deploy on Staging?', 'staging') is True

  def test_prod_not_matching_preprod_job(self):
    """测试：preprod 的 job 不应被判为 prod（关键边界）"""
    assert matchesEnvironment('Do you want to deploy aca-new on preprod?', 'prod') is False

  def test_prod_matches_production(self):
    """测试：Production 字样匹配 prod"""
    assert matchesEnvironment('Do you want to prepare PRs for Production?', 'prod') is True

  def test_dev(self):
    """测试：dev 匹配"""
    assert matchesEnvironment('Do you want to deploy on Dev?', 'dev') is True

  def test_mismatch(self):
    """测试：环境不匹配"""
    assert matchesEnvironment('Do you want to deploy on Staging?', 'preprod') is False

  def test_empty_inputs(self):
    """测试：空输入返回 False"""
    assert matchesEnvironment('', 'preprod') is False
    assert matchesEnvironment('Deploy on preprod?', '') is False


class TestSelectApprovalJob:
  """测试 selectApprovalJob 函数"""

  @staticmethod
  def buildJobs():
    """构造多服务 pipeline 的 job 列表"""
    return [
      {'name': 'build', 'type': 'build', 'status': 'success'},
      {'name': 'Do you want to deploy lab-photos on preprod?',
       'type': 'approval', 'status': 'success', 'approved_by': 'uuid-lab-photos'},
      {'name': 'Do you want to deploy aca-new on preprod?',
       'type': 'approval', 'status': 'success', 'approved_by': 'uuid-aca-new'},
      {'name': 'Do you want to deploy aca-new on staging?',
       'type': 'approval', 'status': 'on_hold', 'approved_by': None},
    ]

  def test_prefers_matching_service(self):
    """测试：多服务 pipeline 中优先选中同名服务的 job"""
    job = selectApprovalJob(self.buildJobs(), 'preprod', 'aca-new')
    assert job['approved_by'] == 'uuid-aca-new'

  def test_falls_back_without_service_name(self):
    """测试：未提供服务名时返回首个匹配环境的已审批 job"""
    job = selectApprovalJob(self.buildJobs(), 'preprod')
    assert job['approved_by'] == 'uuid-lab-photos'

  def test_single_candidate_without_service_in_name(self):
    """测试：仅一个候选且名称不含服务名时允许回退"""
    jobs = [{
      'name': 'Do you want to deploy on Preprod?',
      'type': 'approval',
      'status': 'success',
      'approved_by': 'uuid-single',
    }]
    job = selectApprovalJob(jobs, 'preprod', 'aims-service-cloud')
    assert job['approved_by'] == 'uuid-single'

  def test_no_fallback_when_service_misses_among_multiple(self):
    """测试：多服务 pipeline 中服务名未命中时禁止回退到其他服务审批人"""
    assert selectApprovalJob(self.buildJobs(), 'preprod', 'unknown-service') is None

  def test_ignores_pending_jobs(self):
    """测试：未审批（on_hold）的 job 不被选中"""
    assert selectApprovalJob(self.buildJobs(), 'staging', 'aca-new') is None

  def test_ignores_non_approval_jobs(self):
    """测试：非 approval 类型的 job 不被选中"""
    jobs = [{'name': 'deploy on preprod', 'type': 'build', 'status': 'success'}]
    assert selectApprovalJob(jobs, 'preprod') is None

  def test_environment_not_present(self):
    """测试：无该环境的 job 返回 None"""
    assert selectApprovalJob(self.buildJobs(), 'dev', 'aca-new') is None

  def test_empty_job_list(self):
    """测试：空列表返回 None"""
    assert selectApprovalJob([], 'preprod') is None
    assert selectApprovalJob(None, 'preprod') is None

  def test_prod_not_confused_with_preprod(self):
    """测试：查 prod 时不会误取 preprod 的审批人"""
    assert selectApprovalJob(self.buildJobs(), 'prod', 'aca-new') is None


class TestBuildProjectCandidates:
  """测试 buildProjectCandidates 函数"""

  def test_plain_name_only_itself(self):
    """测试：无已知后缀时只返回原名"""
    assert buildProjectCandidates('aca-new') == ['aca-new']

  def test_service_cloud_suffix_stripped(self):
    """测试：-service-cloud 各后缀均生成候选（CircleCI 上实为 claim）"""
    candidates = buildProjectCandidates('claim-service-cloud')
    assert candidates[0] == 'claim-service-cloud'
    assert 'claim' in candidates
    assert 'claim-service' in candidates

  def test_cloud_suffix_stripped(self):
    """测试：-cloud 后缀剥离"""
    assert buildProjectCandidates('claim-cloud') == ['claim-cloud', 'claim']

  def test_service_suffix_stripped(self):
    """测试：-service 后缀剥离"""
    assert buildProjectCandidates('psi-service') == ['psi-service', 'psi']

  def test_explicit_mapping_takes_priority(self):
    """测试：显式映射优先于原名（lab-photos 的 approval 在 aca-new 的 pipeline 中）"""
    candidates = buildProjectCandidates('lab-photos', {'lab-photos': 'aca-new'})
    assert candidates[0] == 'aca-new'
    assert 'lab-photos' in candidates

  def test_mapping_not_duplicated(self):
    """测试：映射值与原名相同时不重复"""
    assert buildProjectCandidates('aca-new', {'aca-new': 'aca-new'}) == ['aca-new']

  def test_empty_name(self):
    """测试：空服务名返回空列表"""
    assert buildProjectCandidates('') == []
    assert buildProjectCandidates(None) == []
