"""
Jira Operations 辅助模块
提供 Jira REST API v3 的封装，支持创建、查询和更新 Issue
"""

import base64
import requests
from typing import Dict, Optional, List, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback 配置（当动态获取失败时使用）
FALLBACK_CONFIG = {
  "work_types": {
    "Improvement": "4",
    "Bug": "1",
    "Task": "3",
    "Sub-task": "5",
    "Story": "7",
    "Epic": "6",
    "UX": "10254",
    "UI": "10255",
    "Test": "10218",
    "Test Set": "10219",
    "Test Plan": "10220",
    "Test Execution": "10221",
    "Precondition": "10222",
    "Sub Test Execution": "10223"
  },
  "priorities": {
    "N/A": "6",
    "Blocker": "1",
    "Highest": "2",
    "High": "3",
    "Medium": "4",
    "Low": "5",
    "Lowest": "10000"
  },
  "sp_teams": [
    "Apollo", "X-Men", "Pioneer", "Titan",
    "Mermaid", "Loong", "Compass", "NewWave"
  ],
  "sp_team_field": "customfield_12628",
  "resolutions": [
    "Fixed", "Won't Fix", "Duplicate",
    "Incomplete", "Cannot Reproduce", "Done",
    "Won't Do", "Archived", "False Alert"
  ],
  "environment_occured": [
    "DEV",
    "PP",
    "PROD"
  ],
  "bug_categories": [
    "Developer Error", "PM Error", "QA Mistake",
    "Environmental Issue", "False Alarm", "Performance Issue",
    "UX/UI Problem", "Data Issue", "External system issue"
  ]
}


class JiraOperationsClient:
  """Jira Operations API 客户端"""
  
  def __init__(self, base_url: str, email: str, api_token: str):
    """
    初始化 Jira 客户端
    
    Args:
      base_url: Jira 实例 URL (e.g., https://qima.atlassian.net)
      email: 用户邮箱
      api_token: Jira API Token
    """
    self.base_url = base_url.rstrip('/')
    self.email = email
    self.api_token = api_token
    self.session = requests.Session()
    self.session.headers.update(self._get_auth_header())
  
  def _get_auth_header(self) -> Dict[str, str]:
    """
    生成 Basic Auth 请求头
    
    Returns:
      包含认证信息的请求头字典
    """
    auth_str = f"{self.email}:{self.api_token}"
    auth_bytes = auth_str.encode('utf-8')
    auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
    
    return {
      'Authorization': f'Basic {auth_b64}',
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
  
  def _call_api(
    self,
    endpoint: str,
    method: str = 'GET',
    data: Optional[Dict] = None,
    params: Optional[Dict] = None
  ) -> Optional[Dict]:
    """
    调用 Jira API
    
    Args:
      endpoint: API 端点（相对路径，如 'issue' 或完整路径如 '/rest/agile/1.0/board'）
      method: HTTP 方法
      data: 请求体数据
      params: URL 参数
    
    Returns:
      API 响应的 JSON 数据，失败返回 None
    """
    # 如果 endpoint 以 /rest/ 开头，说明是完整路径，直接拼接 base_url
    if endpoint.startswith('/rest/'):
      url = f"{self.base_url}{endpoint}"
    else:
      url = f"{self.base_url}/rest/api/3/{endpoint}"
    
    try:
      response = self.session.request(
        method=method,
        url=url,
        json=data,
        params=params,
        timeout=30
      )
      
      # 尝试解析 JSON 响应
      response_data = None
      if response.text:
        try:
          response_data = response.json()
        except ValueError:
          # 响应不是 JSON 格式
          response_data = {'error': 'Invalid JSON response', 'text': response.text[:500]}
      
      # 返回响应对象，让调用者处理状态码
      return {
        'status_code': response.status_code,
        'data': response_data,
        'success': 200 <= response.status_code < 300
      }
      
    except requests.Timeout:
      logger.error("API 请求超时")
      return {'status_code': 0, 'data': None, 'success': False, 'error': 'timeout'}
    except requests.RequestException as e:
      logger.error(f"API 请求失败: {str(e)}")
      return {'status_code': 0, 'data': None, 'success': False, 'error': str(e)}
    except Exception as e:
      logger.error(f"未知错误: {str(e)}")
      return {'status_code': 0, 'data': None, 'success': False, 'error': str(e)}
  
  def get_create_metadata(self, project_key: str = "SP") -> Optional[Dict[str, Any]]:
    """
    获取创建 Issue 的元数据（issue types, priorities, custom fields）
    
    Args:
      project_key: 项目 key，默认 "SP"
    
    Returns:
      包含 work_types, priorities, sp_teams, sp_team_field 的字典
    """
    params = {
      'projectKeys': project_key,
      'issuetypeNames': '*',
      'expand': 'projects.issuetypes.fields'
    }
    
    response = self._call_api('issue/createmeta', params=params)
    
    if not response or not response['success']:
      logger.warning("无法获取 createmeta，使用 fallback 配置")
      return {
        'work_types': FALLBACK_CONFIG['work_types'],
        'priorities': FALLBACK_CONFIG['priorities'],
        'sp_teams': FALLBACK_CONFIG['sp_teams'],
        'sp_team_field': FALLBACK_CONFIG['sp_team_field'],
        'using_fallback': True
      }
    
    data = response['data']
    metadata = {
      'work_types': {},
      'priorities': {},
      'sp_teams': [],
      'sp_team_field': None,
      'using_fallback': False
    }
    
    try:
      # 解析项目数据
      projects = data.get('projects', [])
      if not projects:
        raise ValueError("未找到项目数据")
      
      project = projects[0]
      issuetypes = project.get('issuetypes', [])
      
      # 提取 issue types
      for issuetype in issuetypes:
        name = issuetype.get('name')
        id = issuetype.get('id')
        if name and id:
          metadata['work_types'][name] = id
      
      # 从所有 issuetype 中查找字段（某些字段可能只在特定类型中存在）
      all_fields = {}
      for issuetype in issuetypes:
        fields = issuetype.get('fields', {})
        all_fields.update(fields)
      
      # 提取 priorities
      priority_field = all_fields.get('priority', {})
      allowed_values = priority_field.get('allowedValues', [])
      for priority in allowed_values:
        name = priority.get('name')
        id = priority.get('id')
        if name and id:
          metadata['priorities'][name] = id
      
      # 查找 SP Team 字段（优先使用 customfield_12628）
      sp_team_candidates = ['customfield_12628']  # 已知的 SP Team 字段
      
      for field_id in sp_team_candidates:
        if field_id in all_fields:
          field_info = all_fields[field_id]
          metadata['sp_team_field'] = field_id
          # 提取 team 选项
          allowed_values = field_info.get('allowedValues', [])
          for value in allowed_values:
            team_name = value.get('value')
            if team_name and team_name not in metadata['sp_teams']:
              metadata['sp_teams'].append(team_name)
          break
      
      # 如果没找到，尝试通过字段名查找
      if not metadata['sp_team_field']:
        for field_id, field_info in all_fields.items():
          if not field_id.startswith('customfield_'):
            continue
          field_name = field_info.get('name', '').lower()
          # 匹配 "sp team" 或包含 "team" 且是 select 类型
          if 'sp team' in field_name or (
            'team' in field_name and 
            field_info.get('schema', {}).get('type') == 'option'
          ):
            metadata['sp_team_field'] = field_id
            # 提取 team 选项
            allowed_values = field_info.get('allowedValues', [])
            for value in allowed_values:
              team_name = value.get('value')
              if team_name and team_name not in metadata['sp_teams']:
                metadata['sp_teams'].append(team_name)
            break
      
      # 如果没有找到数据，使用 fallback
      if not metadata['work_types']:
        metadata['work_types'] = FALLBACK_CONFIG['work_types']
      if not metadata['priorities']:
        metadata['priorities'] = FALLBACK_CONFIG['priorities']
      if not metadata['sp_teams']:
        metadata['sp_teams'] = FALLBACK_CONFIG['sp_teams']
      if not metadata['sp_team_field']:
        metadata['sp_team_field'] = FALLBACK_CONFIG['sp_team_field']
      
      return metadata
      
    except Exception as e:
      logger.error(f"解析 createmeta 失败: {str(e)}")
      return {
        'work_types': FALLBACK_CONFIG['work_types'],
        'priorities': FALLBACK_CONFIG['priorities'],
        'sp_teams': FALLBACK_CONFIG['sp_teams'],
        'sp_team_field': FALLBACK_CONFIG['sp_team_field'],
        'using_fallback': True
      }
  
  def get_user_account_id(self, email: str) -> Optional[str]:
    """
    根据邮箱获取用户的 accountId
    
    Args:
      email: 用户邮箱
    
    Returns:
      用户的 accountId，失败返回 None
    """
    params = {'query': email}
    response = self._call_api('user/search', params=params)
    
    if response and response['success']:
      users = response['data']
      if users and len(users) > 0:
        return users[0].get('accountId')
    
    logger.warning(f"无法获取用户 {email} 的 accountId")
    return None
  
  @staticmethod
  def convert_to_adf(text: str) -> Dict[str, Any]:
    """
    将纯文本转换为 Atlassian Document Format (ADF)
    
    Args:
      text: 纯文本内容
    
    Returns:
      ADF 格式的字典
    """
    if not text:
      return {
        "type": "doc",
        "version": 1,
        "content": []
      }
    
    # 简单实现：将文本按换行符分割为段落
    paragraphs = text.split('\n')
    content = []
    
    for para in paragraphs:
      if para.strip():
        content.append({
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": para
            }
          ]
        })
    
    return {
      "type": "doc",
      "version": 1,
      "content": content if content else [
        {
          "type": "paragraph",
          "content": [{"type": "text", "text": text}]
        }
      ]
    }
  
  @staticmethod
  def parse_adf_to_text(adf: Dict[str, Any]) -> str:
    """
    将 ADF 格式解析为纯文本
    
    Args:
      adf: ADF 格式的字典
    
    Returns:
      纯文本字符串
    """
    if not adf or not isinstance(adf, dict):
      return ""
    
    content = adf.get('content', [])
    text_parts = []
    
    for node in content:
      if node.get('type') == 'paragraph':
        para_content = node.get('content', [])
        para_text = []
        for text_node in para_content:
          if text_node.get('type') == 'text':
            para_text.append(text_node.get('text', ''))
        if para_text:
          text_parts.append(''.join(para_text))
      elif node.get('type') == 'text':
        text_parts.append(node.get('text', ''))
    
    return '\n'.join(text_parts)
  
  def create_issue(
    self,
    project_key: str,
    issue_type_id: str,
    summary: str,
    description: str = "",
    priority_id: Optional[str] = None,
    reporter_account_id: Optional[str] = None,
    sp_team: Optional[str] = None,
    sp_team_field: Optional[str] = None,
    environment_occured: Optional[str] = None,
    bug_category: Optional[str] = None,
    sprint_id: Optional[int] = None
  ) -> Dict[str, Any]:
    """
    创建 Jira Issue
    
    Args:
      project_key: 项目 key
      issue_type_id: Issue 类型 ID
      summary: Issue 标题
      description: Issue 描述（纯文本）
      priority_id: 优先级 ID
      reporter_account_id: 报告人 accountId
      sp_team: SP Team 名称
      sp_team_field: SP Team 字段 ID
      environment_occured: 发生环境（Bug 类型必填）
      bug_category: Bug 分类（customfield_12977）
      sprint_id: Sprint ID
    
    Returns:
      包含 success, status_code, data 的字典
    """
    fields = {
      "project": {"key": project_key},
      "issuetype": {"id": issue_type_id},
      "summary": summary
    }
    
    # 添加描述（转换为 ADF 格式）
    if description:
      fields["description"] = self.convert_to_adf(description)
    
    # 添加优先级
    if priority_id:
      fields["priority"] = {"id": priority_id}
    
    # 添加报告人
    if reporter_account_id:
      fields["reporter"] = {"id": reporter_account_id}
    
    # 添加 SP Team
    if sp_team and sp_team_field:
      fields[sp_team_field] = {"value": sp_team}
    
    # 添加 Environment Occured（Bug 类型必填）
    if environment_occured:
      fields["customfield_12602"] = [{"value": environment_occured}]
    
    # 添加 Bug Category（customfield_12977）
    if bug_category:
      fields["customfield_12977"] = {"value": bug_category}
    
    # 注意：Sprint 不能在创建时设置，需要创建后单独添加
    
    data = {"fields": fields}
    response = self._call_api('issue', method='POST', data=data)
    
    # 如果创建成功且有 Sprint ID，将 Issue 添加到 Sprint
    if response and response.get('success') and sprint_id:
      issue_data = response.get('data', {})
      issue_id = issue_data.get('id')
      issue_key = issue_data.get('key')
      
      if issue_id:
        print(f"[DEBUG] 创建 Issue 成功: {issue_key}，正在添加到 Sprint {sprint_id}")
        
        # 使用 Agile API 将 Issue 添加到 Sprint
        sprint_response = self._call_api(
          f'/rest/agile/1.0/sprint/{sprint_id}/issue',
          method='POST',
          data={"issues": [issue_key]}
        )
        
        if sprint_response and sprint_response.get('success'):
          print(f"[DEBUG] 成功将 {issue_key} 添加到 Sprint {sprint_id}")
        else:
          print(f"[WARNING] 添加到 Sprint 失败，但 Issue 创建成功: {issue_key}")
          # 不影响创建成功的返回
    
    # 始终返回完整的响应对象
    return response if response else {'success': False, 'status_code': 0, 'data': None}
  
  def get_issue(self, issue_key: str) -> Dict[str, Any]:
    """
    查询 Issue 详情
    
    Args:
      issue_key: Issue key (e.g., SP-30061)
    
    Returns:
      包含 success, status_code, data 的字典
    """
    params = {
      'fields': 'summary,description,status,priority,reporter,resolution,project,assignee,created,updated,issuetype,customfield_12628'
    }
    response = self._call_api(f'issue/{issue_key}', params=params)
    
    # 始终返回完整的响应对象（包含 success, status_code, data）
    return response if response else {'success': False, 'status_code': 0, 'data': None}
  
  def update_issue_resolution(
    self,
    issue_key: str,
    resolution_name: str
  ) -> Dict[str, Any]:
    """
    更新 Issue 的 Resolution
    
    Args:
      issue_key: Issue key (e.g., SP-30061)
      resolution_name: Resolution 名称 (e.g., "Fixed")
    
    Returns:
      包含 success 状态和消息的字典
    """
    # 简化版：直接尝试更新 resolution 字段
    data = {
      "fields": {
        "resolution": {"name": resolution_name}
      }
    }
    
    response = self._call_api(f'issue/{issue_key}', method='PUT', data=data)
    
    return {
      'success': response['success'] if response else False,
      'status_code': response['status_code'] if response else 0,
      'issue_key': issue_key
    }
  
  def get_resolutions(self) -> List[str]:
    """
    获取所有可用的 Resolution 选项
    
    Returns:
      Resolution 名称列表
    """
    response = self._call_api('resolution')
    
    if response and response['success']:
      resolutions = response['data']
      return [r.get('name') for r in resolutions if r.get('name')]
    
    # Fallback
    return FALLBACK_CONFIG['resolutions']
  
  def delete_issue(self, issue_key: str, delete_subtasks: bool = False) -> Dict[str, Any]:
    """
    删除 Issue
    
    Args:
      issue_key: Issue key (e.g., SP-30061)
      delete_subtasks: 是否同时删除子任务
    
    Returns:
      包含 success 状态和消息的字典
    """
    params = {}
    if delete_subtasks:
      params['deleteSubtasks'] = 'true'
    
    response = self._call_api(f'issue/{issue_key}', method='DELETE', params=params)
    
    return {
      'success': response['success'] if response else False,
      'status_code': response['status_code'] if response else 0,
      'issue_key': issue_key
    }
  
  def get_active_sprints(
      self,
      board_ids: Optional[List[int]] = None,
      team_name: Optional[str] = None,
  ) -> List[Dict[str, Any]]:
    """
    获取 Active Sprints - 使用 Jira Agile API，支持并发加速。

    优化点：
    1. type=scrum 过滤，减少无关 Board 数量
    2. 指定 board_ids 时仅查询目标 Board（Team 预过滤）
    3. 多 Board 并发查询（ThreadPoolExecutor）
    """
    try:
      print(f"[DEBUG] get_active_sprints: 使用 Agile API 获取 Active Sprints")

      # 构造 Board 查询参数
      board_params: Dict[str, Any] = {
          'projectKeyOrId': 'SP',
          'maxResults': 50,
          'type': 'scrum',   # 只查 Scrum Board，排除 Kanban
      }
      boards_response = self._call_api(
          '/rest/agile/1.0/board', method='GET', params=board_params
      )

      if not (boards_response and boards_response['success']):
          print(f"[DEBUG] 无法获取 Board 列表")
          return []

      boards = boards_response['data'].get('values', [])
      print(f"[DEBUG] 找到 {len(boards)} 个 Scrum Board")

      # Team 预过滤：仅保留 Board 名称包含 team_name 的 Board
      if team_name and team_name != "（不设置）":
          boards = [
              b for b in boards
              if team_name.lower() in b.get('name', '').lower()
          ]
          print(f"[DEBUG] Team '{team_name}' 过滤后剩余 {len(boards)} 个 Board")

      # 指定了 board_ids 时进一步限制
      if board_ids is not None:
          boards = [b for b in boards if b.get('id') in board_ids]
          print(f"[DEBUG] board_ids 过滤后剩余 {len(boards)} 个 Board")

      if not boards:
          return []

      # 并发查询各 Board 的 Active Sprints
      all_sprints: Dict[int, Dict[str, Any]] = {}

      def fetch_board_sprints(board: Dict) -> List[Dict]:
          bid = board.get('id')
          bname = board.get('name', '')
          if not bid:
              return []
          resp = self._call_api(
              f'/rest/agile/1.0/board/{bid}/sprint',
              method='GET',
              params={'state': 'active'}
          )
          if not (resp and resp['success']):
              return []
          sprints = resp['data'].get('values', [])
          for sp in sprints:
              sp['boardName'] = bname
          return sprints

      with ThreadPoolExecutor(max_workers=10) as executor:
          futures = {executor.submit(fetch_board_sprints, b): b for b in boards}
          for future in as_completed(futures):
              try:
                  sprints = future.result()
                  for sp in sprints:
                      sid = sp.get('id')
                      if sid and sid not in all_sprints:
                          all_sprints[sid] = sp
              except Exception as exc:
                  board_name = futures[future].get('name', '')
                  print(f"[WARN] Board '{board_name}' 查询异常: {exc}")

      print(f"[DEBUG] 总共找到 {len(all_sprints)} 个 Active Sprint")
      return list(all_sprints.values())

    except Exception as e:
      print(f"[ERROR] 获取 Sprint 失败: {str(e)}")
      import traceback
      traceback.print_exc()
      return []

  def get_sprints_by_team(self, team_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取指定 Team 的 Active Sprints。

    Args:
      team_name: Team 名称（如 "Mermaid"），None 则返回全部
    """
    try:
      sprints = self.get_active_sprints(team_name=team_name)
      print(f"[DEBUG] get_sprints_by_team: 获取到 {len(sprints)} 个总 Sprint")
      return sprints
    except Exception as e:
      print(f"[ERROR] get_sprints_by_team 失败: {str(e)}")
      import traceback
      traceback.print_exc()
      return []
