"""合分支远程逻辑单元测试"""
from unittest.mock import MagicMock, patch

from circleCi.branch_merge_logic import (
  build_conflict_tips,
  build_github_branch_url,
  build_merge_branch_name,
  merge_service_branches,
  parse_branch_names,
)


class TestParseBranchNames:
  """测试 parse_branch_names"""

  def test_parse_space_and_newline(self):
    """空格与换行分隔"""
    text = "SP-12345 SP-54321\nSP-99999"
    assert parse_branch_names(text) == ["SP-12345", "SP-54321", "SP-99999"]

  def test_parse_comma_and_dedupe(self):
    """逗号分隔并去重保序"""
    text = "SP-1, SP-2, SP-1; SP-3"
    assert parse_branch_names(text) == ["SP-1", "SP-2", "SP-3"]

  def test_parse_empty(self):
    """空输入"""
    assert parse_branch_names("") == []
    assert parse_branch_names("   ") == []

  def test_parse_single_branch(self):
    """单个分支仍返回列表"""
    assert parse_branch_names("SP-12345") == ["SP-12345"]


class TestBuildMergeBranchName:
  """测试 build_merge_branch_name"""

  def test_two_branches(self):
    """两个分支命名"""
    assert build_merge_branch_name(["SP-12345", "SP-54321"]) == "merge/SP-12345/SP-54321"

  def test_three_branches(self):
    """三个及以上分支命名"""
    assert build_merge_branch_name(["A", "B", "C"]) == "merge/A/B/C"

  def test_avoids_source_branch_prefix_collision(self):
    """合并名不以源分支本身为顶层路径，避免 Reference update failed"""
    name = build_merge_branch_name([
      "feat-SP-35008",
      "epic-supplier-confirmation-migration_smart-address",
    ])
    assert name == (
      "merge/feat-SP-35008/epic-supplier-confirmation-migration_smart-address"
    )
    assert not name.startswith("feat-SP-35008/")


class TestBuildConflictTips:
  """测试冲突提示"""

  def test_tips_include_pr_url(self):
    """提示包含冲突 PR"""
    tips = build_conflict_tips("SP-1", "SP-2", 2, "https://github.com/org/repo/pull/1")
    joined = "\n".join(tips)
    assert "SP-2" in joined
    assert "pull/1" in joined
    assert "远程" in joined


def test_build_github_branch_url():
  """GitHub URL 构建"""
  url = build_github_branch_url("asiainspection", "aca-new", "SP-1/SP-2")
  assert url == "https://github.com/asiainspection/aca-new/tree/SP-1/SP-2"


def _mock_response(status_code: int, payload=None, text: str = ""):
  """构建 mock Response"""
  response = MagicMock()
  response.status_code = status_code
  response.text = text or str(payload or "")
  if payload is None:
    response.json.side_effect = ValueError("no json")
  else:
    response.json.return_value = payload
  return response


class TestMergeServiceBranchesRemote:
  """测试 GitHub 远程合并主流程"""

  def test_rejects_less_than_two_branches(self):
    """少于 2 个分支直接失败"""
    result = merge_service_branches(
      service="aca-new",
      branches=["SP-1"],
      organization="asiainspection",
      github_token="ghp_test",
    )
    assert result.success is False
    assert "2" in result.error

  def test_missing_remote_branch(self):
    """源分支不存在"""
    session = MagicMock()

    def get_side_effect(url, **kwargs):
      if url.endswith("heads/SP-1"):
        return _mock_response(200, {"object": {"sha": "aaa111"}})
      return _mock_response(404, {"message": "Not Found"})

    session.get.side_effect = get_side_effect

    result = merge_service_branches(
      service="aca-new",
      branches=["SP-1", "SP-2"],
      organization="asiainspection",
      github_token="ghp_testtoken",
      http_session=session,
    )
    assert result.success is False
    assert "不存在" in result.error
    assert "SP-2" in result.error

  def test_success_via_pull_request(self):
    """PR 形式远程合并成功"""
    session = MagicMock()

    def get_side_effect(url, **kwargs):
      if "pulls/10" in url:
        return _mock_response(200, {"mergeable": True, "mergeable_state": "clean"})
      if "merge%2FSP-12345%2FSP-54321" in url or "heads/merge/SP-12345/SP-54321" in url:
        return _mock_response(404, {"message": "Not Found"})
      if "git/ref/heads/" in url:
        return _mock_response(200, {"object": {"sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}})
      return _mock_response(404, {"message": "Not Found"})

    def post_side_effect(url, **kwargs):
      if url.endswith("/git/refs"):
        return _mock_response(201, {"ref": "refs/heads/merge/SP-12345/SP-54321"})
      if url.endswith("/pulls"):
        return _mock_response(
          201,
          {
            "number": 10,
            "html_url": "https://github.com/asiainspection/aca-new/pull/10",
          },
        )
      return _mock_response(400, {"message": f"unexpected post {url}"})

    def put_side_effect(url, **kwargs):
      if url.endswith("/pulls/10/merge"):
        return _mock_response(200, {"sha": "deadbeefcafebabe0123456789abcdef00000000", "merged": True})
      return _mock_response(400, {"message": f"unexpected put {url}"})

    session.get.side_effect = get_side_effect
    session.post.side_effect = post_side_effect
    session.put.side_effect = put_side_effect

    with patch("circleCi.branch_merge_logic.time.sleep", return_value=None):
      result = merge_service_branches(
        service="aca-new",
        branches=["SP-12345", "SP-54321"],
        organization="asiainspection",
        github_token="ghp_testtoken",
        create_prs=True,
        http_session=session,
      )
    assert result.success is True
    assert result.merge_branch == "merge/SP-12345/SP-54321"
    assert result.pushed is True
    assert result.commit_sha.startswith("deadbeef")
    assert any("pull/10" in u for u in result.pr_urls)

  def test_conflict_via_merges_api_creates_pr(self):
    """Merges API 冲突时创建冲突 PR"""
    session = MagicMock()

    def get_side_effect(url, **kwargs):
      if "merge%2FSP-1%2FSP-2" in url or "heads/merge/SP-1/SP-2" in url:
        return _mock_response(404, {"message": "Not Found"})
      if "git/ref/heads/" in url:
        return _mock_response(200, {"object": {"sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}})
      return _mock_response(404, {"message": "Not Found"})

    def post_side_effect(url, **kwargs):
      if url.endswith("/git/refs"):
        return _mock_response(201, {"ref": "refs/heads/merge/SP-1/SP-2"})
      if url.endswith("/merges"):
        return _mock_response(409, {"message": "Merge conflict"})
      if url.endswith("/pulls"):
        return _mock_response(
          201,
          {
            "number": 99,
            "html_url": "https://github.com/asiainspection/aca-new/pull/99",
          },
        )
      return _mock_response(400, {"message": f"unexpected post {url}"})

    session.get.side_effect = get_side_effect
    session.post.side_effect = post_side_effect

    result = merge_service_branches(
      service="aca-new",
      branches=["SP-1", "SP-2"],
      organization="asiainspection",
      github_token="ghp_testtoken",
      create_prs=False,
      http_session=session,
    )
    assert result.success is False
    assert result.conflict_at_branch == "SP-2"
    assert "pull/99" in result.pr_url
    assert any("冲突" in tip or "PR" in tip for tip in result.tips)

  def test_existing_merge_branch_without_force(self):
    """合并分支已存在且未勾选覆盖"""
    session = MagicMock()

    def get_side_effect(url, **kwargs):
      return _mock_response(200, {"object": {"sha": "cccccccccccccccccccccccccccccccccccccccc"}})

    session.get.side_effect = get_side_effect

    result = merge_service_branches(
      service="aca-new",
      branches=["SP-1", "SP-2"],
      organization="asiainspection",
      github_token="ghp_testtoken",
      force_recreate=False,
      http_session=session,
    )
    assert result.success is False
    assert "已存在" in result.error
