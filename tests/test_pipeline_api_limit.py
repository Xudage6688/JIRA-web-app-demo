"""query_pipelines limit / 分页单元测试"""
from unittest.mock import Mock, patch

from circleCi.pipeline_api import (
  _fetch_all_pipelines_with_pagination,
  query_pipelines,
)


def _mockResponse(items, next_page_token=None, status_code=200):
  """构造 CircleCI API mock response"""
  response = Mock()
  response.status_code = status_code
  response.json.return_value = {
    'items': items,
    'next_page_token': next_page_token,
  }
  return response


def _pipelineItem(number: int, branch: str = 'main') -> dict:
  """构造最小 pipeline item"""
  return {
    'id': f'id-{number}',
    'number': number,
    'state': 'created',
    'created_at': '2026-01-01T00:00:00Z',
    'updated_at': '2026-01-01T00:00:00Z',
    'trigger': {'actor': {'login': 'tester'}},
    'vcs': {
      'branch': branch,
      'revision': f'rev-{number}',
      'commit': {'subject': f'commit {number}'},
    },
  }


class TestFetchPagination:
  """测试分页拉取与提前停止"""

  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_stop_after_limits_pages(self, mockCall):
    """累计达到 stop_after 后不再翻页"""
    page1 = [_pipelineItem(i) for i in range(1, 21)]
    page2 = [_pipelineItem(i) for i in range(21, 41)]
    mockCall.side_effect = [
      (_mockResponse(page1, next_page_token='tok-2'), None),
      (_mockResponse(page2, next_page_token='tok-3'), None),
    ]

    pipelines, error = _fetch_all_pipelines_with_pagination(
      'gh/org/svc',
      api_token='token',
      max_pages=5,
      stop_after=25
    )

    assert error is None
    assert len(pipelines) == 40  # 第二页整页追加后才检查 stop
    assert mockCall.call_count == 2

  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_branch_passed_to_api(self, mockCall):
    """分页请求透传 branch 参数"""
    mockCall.return_value = (_mockResponse([_pipelineItem(1, 'feat/x')]), None)

    _fetch_all_pipelines_with_pagination(
      'gh/org/svc',
      api_token='token',
      max_pages=1,
      branch='feat/x'
    )

    _, kwargs = mockCall.call_args
    assert kwargs['params'].get('branch') == 'feat/x'


class TestQueryPipelinesLimit:
  """测试 query_pipelines 的 limit 行为"""

  @patch('circleCi.pipeline_data.get_preprod_approval_info', return_value=None)
  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_default_limit_ten(self, mockCall, _mockApproval):
    """默认截断为 10 条"""
    items = [_pipelineItem(i) for i in range(1, 21)]
    mockCall.return_value = (_mockResponse(items), None)

    pipelines, error = query_pipelines('gh/org/svc', api_token='token', limit=10)

    assert error is None
    assert len(pipelines) == 10
    assert pipelines[0]['number'] == 1
    assert mockCall.call_count == 1

  @patch('circleCi.pipeline_data.get_preprod_approval_info', return_value=None)
  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_limit_twenty_single_page(self, mockCall, _mockApproval):
    """limit=20 仍走单页请求"""
    items = [_pipelineItem(i) for i in range(1, 21)]
    mockCall.return_value = (_mockResponse(items, next_page_token='more'), None)

    pipelines, error = query_pipelines('gh/org/svc', api_token='token', limit=20)

    assert error is None
    assert len(pipelines) == 20
    assert mockCall.call_count == 1

  @patch('circleCi.pipeline_data.get_preprod_approval_info', return_value=None)
  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_limit_forty_uses_pagination(self, mockCall, _mockApproval):
    """limit=40 走分页并截断到 40"""
    page1 = [_pipelineItem(i) for i in range(1, 21)]
    page2 = [_pipelineItem(i) for i in range(21, 41)]
    mockCall.side_effect = [
      (_mockResponse(page1, next_page_token='tok-2'), None),
      (_mockResponse(page2), None),
    ]

    pipelines, error = query_pipelines('gh/org/svc', api_token='token', limit=40)

    assert error is None
    assert len(pipelines) == 40
    assert mockCall.call_count == 2

  @patch('circleCi.pipeline_data.get_preprod_approval_info', return_value=None)
  @patch('circleCi.pipeline_api.call_circleci_api')
  def test_branch_filter_on_paginated_query(self, mockCall, _mockApproval):
    """高 limit + branch 时分页请求带 branch"""
    items = [_pipelineItem(i, 'release/1') for i in range(1, 41)]
    mockCall.side_effect = [
      (_mockResponse(items[:20], next_page_token='tok-2'), None),
      (_mockResponse(items[20:]), None),
    ]

    pipelines, error = query_pipelines(
      'gh/org/svc',
      branch='release/1',
      api_token='token',
      limit=40
    )

    assert error is None
    assert len(pipelines) == 40
    assert mockCall.call_args_list[0].kwargs['params']['branch'] == 'release/1'
