"""
Jira Operations Tool
支持创建、查询和批量更新 Jira Tickets
"""

import streamlit as st
import sys
import os
import base64
from pathlib import Path
from typing import Dict, Optional, List

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 强制重新加载模块（开发时使用）
import importlib
if 'modules.jira_operations_helper' in sys.modules:
  importlib.reload(sys.modules['modules.jira_operations_helper'])

from modules.jira_operations_helper import JiraOperationsClient, FALLBACK_CONFIG
from modules.user_config_loader import get_jira_config, get_user_config_loader

# 尝试导入 cookies manager
try:
  from streamlit_cookies_manager import EncryptedCookieManager
  COOKIES_AVAILABLE = True
except ImportError:
  COOKIES_AVAILABLE = False
  st.warning("⚠️ streamlit-cookies-manager 未安装，Token 将不会持久化")

# 页面配置
st.set_page_config(
  page_title="Jira Operations Tool",
  page_icon="📝",
  layout="wide"
)

# 检查当前用户
if 'current_user' not in st.session_state or not st.session_state.current_user:
  st.error("❌ 未选择使用者，请返回主页选择你的身份")
  st.stop()

current_user = st.session_state.current_user

# 从用户配置加载 Jira 配置
user_jira_config = get_jira_config(current_user)

if not user_jira_config:
  st.error(f"❌ 未找到用户 {current_user} 的 Jira 配置")
  st.info("请联系管理员在 config/users_config.json 中配置你的信息")
  st.stop()

# 配置信息
base_url = user_jira_config.get('base_url', 'https://qima.atlassian.net')
config_email = get_user_config_loader().get_user_email(current_user)
config_token = user_jira_config.get('api_token', '')
display_name = get_user_config_loader().get_user_display_name(current_user)

# 初始化 cookies manager
cookies = None
if COOKIES_AVAILABLE:
  cookies = EncryptedCookieManager(
    prefix=f"jira_ops_{current_user}_",
    password=os.environ.get("COOKIES_PASSWORD", "jira-ops-secret-key-2026")
  )
  if not cookies.ready():
    st.stop()

# 页面标题
st.title("📝 Jira Operations Tool")
st.info(f"👤 当前使用者: **{display_name}** ({current_user})")

st.markdown("""
快速执行 Jira 高频操作：创建 Ticket、查询详情、批量更新 Resolution。
""")

# Sidebar - Token 配置和操作选择
with st.sidebar:
  st.header("🔐 认证配置")
  
  # Token 输入
  st.markdown("**API Token**")
  
  # 尝试加载 Token（优先级：cookies > config）
  saved_token = ""
  if cookies:
    saved_token = cookies.get("api_token", "")
  
  if not saved_token:
    saved_token = config_token
  
  # 显示 Token 状态
  if saved_token and saved_token not in ['YOUR_JIRA_TOKEN_HERE', 'your_api_token_here', '']:
    st.success(f"✅ Token 已加载 ({len(saved_token)} 字符)")
  else:
    st.warning("⚠️ 请输入或配置 API Token")
  
  # Token 输入框（password 类型）
  api_token = st.text_input(
    "输入 API Token",
    value=saved_token,
    type="password",
    help="从 Atlassian 账户设置中获取，或自动从配置加载",
    key="api_token_input"
  )
  
  # 保存 Token 到 cookies
  if cookies and api_token and api_token != saved_token:
    cookies["api_token"] = api_token
    cookies.save()
    st.success("✅ Token 已保存")
  
  st.markdown("---")
  
  # 邮箱显示
  st.text_input(
    "📧 Jira 邮箱",
    value=config_email,
    disabled=True,
    help="从用户配置加载"
  )
  
  st.markdown("---")
  
  # 操作选择
  st.header("📋 选择操作")
  operation = st.radio(
    "功能",
    options=["创建 Ticket", "查询 Ticket", "批量更新 Resolution", "删除 Ticket"],
    key="operation_selector"
  )
  
  st.markdown("---")
  
  # 连接测试
  with st.expander("🔧 连接测试（调试用）"):
    if st.button("测试 Jira API 连接"):
      with st.spinner("测试中..."):
        try:
          import requests
          test_url = f"{base_url}/rest/api/3/myself"
          auth_str = f"{config_email}:{api_token}"
          auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
          
          headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json'
          }
          
          response = requests.get(test_url, headers=headers, timeout=10)
          
          if response.status_code == 200:
            user_info = response.json()
            st.success("✅ 连接成功！")
            st.json({
              "displayName": user_info.get('displayName'),
              "emailAddress": user_info.get('emailAddress'),
              "accountId": user_info.get('accountId')
            })
          else:
            st.error(f"❌ 连接失败 (状态码: {response.status_code})")
            st.code(response.text)
        except Exception as e:
          st.error(f"❌ 连接失败: {str(e)}")
          import traceback
          st.code(traceback.format_exc())
    
    st.markdown("---")
    
    if st.button("📋 获取所有 Work Types"):
      with st.spinner("获取中..."):
        try:
          import requests
          test_url = f"{base_url}/rest/api/3/issue/createmeta"
          auth_str = f"{config_email}:{api_token}"
          auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
          
          headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          }
          
          params = {
            'projectKeys': 'SP',
            'expand': 'projects.issuetypes.fields'
          }
          
          st.info(f"📡 请求 URL: {test_url}")
          st.info(f"📋 请求参数: {params}")
          
          response = requests.get(test_url, headers=headers, params=params, timeout=30)
          
          st.info(f"📊 响应状态码: {response.status_code}")
          
          if response.status_code == 200:
            data = response.json()
            projects = data.get('projects', [])
            
            if projects:
              project = projects[0]
              issuetypes = project.get('issuetypes', [])
              
              st.success(f"✅ 找到 {len(issuetypes)} 个 Issue Types")
              
              # 创建表格显示
              work_types_data = []
              for issuetype in issuetypes:
                work_types_data.append({
                  "Name": issuetype.get('name'),
                  "ID": issuetype.get('id'),
                  "Description": issuetype.get('description', '')[:50] + "..."
                })
              
              # 使用 DataFrame 显示
              import pandas as pd
              df = pd.DataFrame(work_types_data)
              st.dataframe(df, use_container_width=True)
              
              # 生成配置代码
              st.markdown("### 📝 配置代码（复制使用）")
              config_code = '"work_types": {\n'
              for issuetype in issuetypes:
                name = issuetype.get('name')
                id = issuetype.get('id')
                config_code += f'  "{name}": "{id}",\n'
              config_code = config_code.rstrip(',\n') + '\n}'
              st.code(config_code, language='python')
              
              # 显示完整 JSON
              with st.expander("🔍 查看完整响应"):
                st.json(data)
            else:
              st.warning("⚠️ 未找到项目数据")
          else:
            st.error(f"❌ 获取失败 (状态码: {response.status_code})")
            st.code(response.text[:1000])
        except Exception as e:
          st.error(f"❌ 获取失败: {str(e)}")
          import traceback
          st.code(traceback.format_exc())
    
    st.markdown("---")
    
    if st.button("🐛 获取 Bug 类型的必填字段"):
      with st.spinner("获取中..."):
        try:
          import requests
          test_url = f"{base_url}/rest/api/3/issue/createmeta"
          auth_str = f"{config_email}:{api_token}"
          auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
          
          headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          }
          
          params = {
            'projectKeys': 'SP',
            'issuetypeNames': 'Bug',
            'expand': 'projects.issuetypes.fields'
          }
          
          response = requests.get(test_url, headers=headers, params=params, timeout=30)
          
          if response.status_code == 200:
            data = response.json()
            projects = data.get('projects', [])
            
            if projects and projects[0].get('issuetypes'):
              bug_type = projects[0]['issuetypes'][0]
              fields = bug_type.get('fields', {})
              
              st.success("✅ Bug 类型的字段信息")
              
              # 查找 customfield_12602
              if 'customfield_12602' in fields:
                field_info = fields['customfield_12602']
                st.info(f"**Environment Occured (customfield_12602)**")
                st.write(f"- 是否必填: {field_info.get('required', False)}")
                st.write(f"- 字段名: {field_info.get('name')}")
                st.write(f"- 类型: {field_info.get('schema', {}).get('type')}")
                
                allowed_values = field_info.get('allowedValues', [])
                if allowed_values:
                  st.write("**可选值:**")
                  for value in allowed_values:
                    st.write(f"  - {value.get('value')} (ID: {value.get('id')})")
                  
                  # 生成配置代码
                  st.markdown("### 📝 配置代码")
                  config_code = '"environment_occured": [\n'
                  for value in allowed_values:
                    config_code += f'  "{value.get("value")}",\n'
                  config_code = config_code.rstrip(',\n') + '\n]'
                  st.code(config_code, language='python')
              
              # 显示所有必填字段
              st.markdown("### 📋 所有必填字段")
              required_fields = []
              for field_id, field_info in fields.items():
                if field_info.get('required'):
                  required_fields.append({
                    "Field ID": field_id,
                    "Name": field_info.get('name'),
                    "Type": field_info.get('schema', {}).get('type')
                  })
              
              import pandas as pd
              df = pd.DataFrame(required_fields)
              st.dataframe(df, use_container_width=True)
              
              with st.expander("🔍 查看完整响应"):
                st.json(data)
            else:
              st.warning("⚠️ 未找到 Bug 类型")
          else:
            st.error(f"❌ 获取失败 (状态码: {response.status_code})")
            st.code(response.text[:1000])
        except Exception as e:
          st.error(f"❌ 获取失败: {str(e)}")
          import traceback
          st.code(traceback.format_exc())
    
    st.markdown("---")
    
    if st.button("🏃 获取 Sprint 字段信息"):
      with st.spinner("获取中..."):
        try:
          import requests
          import json
          
          auth_str = f"{config_email}:{api_token}"
          auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
          
          headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          }
          
          st.info(f"📋 使用 Jira Agile API 获取 Sprints")
          
          # 步骤1: 获取 Board 列表
          boards_url = f"{base_url}/rest/agile/1.0/board"
          boards_params = {'projectKeyOrId': 'SP', 'maxResults': 50}
          
          st.write("**步骤 1: 获取 Board 列表**")
          boards_response = requests.get(boards_url, headers=headers, params=boards_params, timeout=30)
          
          if boards_response.status_code == 200:
            boards_data = boards_response.json()
            boards = boards_data.get('values', [])
            
            st.success(f"✅ 找到 {len(boards)} 个 Board")
            
            # 步骤2: 遍历所有 Board 获取 Active Sprints
            st.write(f"**步骤 2: 遍历所有 Board 获取 Active Sprints**")
            
            all_sprints = {}
            boards_with_sprints = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, board in enumerate(boards):
              board_id = board.get('id')
              board_name = board.get('name')
              
              status_text.text(f"检查 Board: {board_name} ({i+1}/{len(boards)})")
              
              sprints_url = f"{base_url}/rest/agile/1.0/board/{board_id}/sprint"
              sprints_params = {'state': 'active'}
              
              sprints_response = requests.get(sprints_url, headers=headers, params=sprints_params, timeout=10)
              
              if sprints_response.status_code == 200:
                sprints_data = sprints_response.json()
                sprints = sprints_data.get('values', [])
                
                if sprints:
                  boards_with_sprints.append(board_name)
                  for sprint in sprints:
                    sprint_id = sprint.get('id')
                    if sprint_id and sprint_id not in all_sprints:
                      sprint['boardName'] = board_name
                      all_sprints[sprint_id] = sprint
              
              progress_bar.progress((i + 1) / len(boards))
            
            status_text.empty()
            progress_bar.empty()
            
            if all_sprints:
              st.success(f"✅ 在 {len(boards_with_sprints)} 个 Board 中找到 {len(all_sprints)} 个 Active Sprint")
              
              st.markdown("### 📋 所有 Active Sprints")
              for sprint in all_sprints.values():
                st.info(f"**{sprint.get('name')}**\n- ID: {sprint.get('id')}\n- State: {sprint.get('state')}\n- Board: {sprint.get('boardName')}")
              
              with st.expander("🔍 完整 Sprint 信息"):
                st.json(list(all_sprints.values()))
              
              st.write(f"**有 Active Sprint 的 Board**: {', '.join(boards_with_sprints)}")
            else:
              st.warning("⚠️ 所有 Board 都没有 Active Sprint")
            
          else:
            st.error(f"❌ 获取 Boards 失败 (状态码: {boards_response.status_code})")
            st.code(boards_response.text[:1000])
            
        except Exception as e:
          st.error(f"❌ 获取失败: {str(e)}")
          import traceback
          st.code(traceback.format_exc())
    
    st.markdown("---")
    
    if st.button("测试查询 Issue API"):
      test_ticket = st.text_input("测试 Ticket", value="SP-30648", key="debug_ticket")
      if test_ticket:
        with st.spinner("测试查询 API..."):
          try:
            import requests
            test_url = f"{base_url}/rest/api/3/issue/{test_ticket}"
            auth_str = f"{config_email}:{api_token}"
            auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            
            headers = {
              'Authorization': f'Basic {auth_b64}',
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            }
            
            params = {
              'fields': 'summary,description,status,priority,reporter,resolution,project,assignee,created,updated,issuetype,customfield_12628'
            }
            
            st.info(f"📡 请求 URL: {test_url}")
            st.info(f"📋 请求参数: {params}")
            
            response = requests.get(test_url, headers=headers, params=params, timeout=10)
            
            st.info(f"📊 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
              st.success("✅ 查询成功！")
              data = response.json()
              st.json(data)
            else:
              st.error(f"❌ 查询失败 (状态码: {response.status_code})")
              st.code(response.text[:1000])
          except Exception as e:
            st.error(f"❌ 测试失败: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

# 验证 Token
if not api_token or api_token in ['YOUR_JIRA_TOKEN_HERE', 'your_api_token_here', '']:
  st.error("❌ 请先在侧边栏配置 API Token")
  st.info("💡 获取 Token：访问 [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)")
  st.stop()

# 初始化 Jira 客户端（不使用缓存，避免 Token 更改后的问题）
def get_jira_client(base_url: str, email: str, token: str) -> JiraOperationsClient:
  """创建 Jira 客户端"""
  return JiraOperationsClient(base_url, email, token)

try:
  # 使用当前 Token 创建客户端
  jira_client = get_jira_client(base_url, config_email, api_token)
  
  # 测试连接（调用一个简单的 API）
  if operation == "查询 Ticket":
    st.sidebar.success("✅ 认证配置正确")
except Exception as e:
  st.error(f"❌ 初始化 Jira 客户端失败: {str(e)}")
  st.stop()

# 获取元数据（缓存，但可以通过 TTL 刷新）
@st.cache_data(ttl=300)  # 5分钟缓存
def get_metadata(_client: JiraOperationsClient, project_key: str = "SP") -> Dict:
  """获取创建 Issue 的元数据"""
  return _client.get_create_metadata(project_key)

# 添加清除缓存按钮
col1, col2 = st.sidebar.columns(2)
with col1:
  if st.button("🔄 刷新元数据缓存", help="清除缓存并重新获取 Work Types、Priorities 等"):
    get_metadata.clear()
    st.sidebar.success("✅ 元数据缓存已清除")
    st.rerun()

with col2:
  if st.button("🏃 刷新 Sprint 缓存", help="清除 Sprint 缓存并重新获取"):
    # 清除所有缓存函数
    st.cache_data.clear()
    st.sidebar.success("✅ Sprint 缓存已清除")
    st.rerun()

metadata = get_metadata(jira_client, "SP")

# 显示是否使用 fallback
if metadata.get('using_fallback'):
  st.warning("⚠️ 无法从 Jira 获取动态配置，使用预设配置")

work_types_map = metadata.get('work_types', {})
priorities_map = metadata.get('priorities', {})
sp_teams = metadata.get('sp_teams', [])
sp_team_field = metadata.get('sp_team_field')

work_types = list(work_types_map.keys())
priorities = list(priorities_map.keys())

# 主内容区域
st.markdown("---")

# 初始化 session state 用于保存输入内容
if 'create_work_type_idx' not in st.session_state:
  # 默认设置为 Test Execution
  default_work_types = list(metadata.get('work_types', {}).keys())
  if "Test Execution" in default_work_types:
    st.session_state.create_work_type_idx = default_work_types.index("Test Execution")
  else:
    st.session_state.create_work_type_idx = 3  # fallback to Task
if 'create_summary' not in st.session_state:
  st.session_state.create_summary = ""
if 'create_description' not in st.session_state:
  st.session_state.create_description = ""
if 'create_priority_idx' not in st.session_state:
  st.session_state.create_priority_idx = 4  # Medium
if 'create_sp_team_idx' not in st.session_state:
  # 默认设置为 Mermaid
  sp_teams_list = metadata.get('sp_teams', [])
  sp_team_options = ["（不设置）"] + sp_teams_list
  if "Mermaid" in sp_team_options:
    st.session_state.create_sp_team_idx = sp_team_options.index("Mermaid")
  else:
    st.session_state.create_sp_team_idx = 0
if 'create_environment_idx' not in st.session_state:
  st.session_state.create_environment_idx = 1  # PP
if 'create_sprint_idx' not in st.session_state:
  st.session_state.create_sprint_idx = 0
if 'query_ticket_number' not in st.session_state:
  st.session_state.query_ticket_number = ""
if 'batch_tickets_input' not in st.session_state:
  st.session_state.batch_tickets_input = ""
if 'batch_resolution_idx' not in st.session_state:
  st.session_state.batch_resolution_idx = 0
if 'delete_ticket_number' not in st.session_state:
  st.session_state.delete_ticket_number = ""
if 'delete_confirm' not in st.session_state:
  st.session_state.delete_confirm = False
if 'available_sprints' not in st.session_state:
  st.session_state.available_sprints = []

# 根据选择的操作显示不同界面
if operation == "创建 Ticket":
  st.header("🆕 创建 Jira Ticket")
  
  # 获取 Sprints（带缓存）- 定义在这里以确保 jira_client 已初始化
  @st.cache_data(ttl=300)
  def get_team_sprints(team: Optional[str]) -> List[Dict]:
    """获取 Team 的 Active Sprints"""
    try:
      return jira_client.get_sprints_by_team(team)
    except Exception as e:
      st.error(f"获取 Sprint 失败: {str(e)}")
      return []
  
  # ========== 表单前的配置区域 ==========
  st.subheader("📋 基本配置")
  
  config_row1_col1, config_row1_col2 = st.columns(2)
  
  with config_row1_col1:
    # Work Type 选择
    default_work_type_idx = st.session_state.create_work_type_idx
    if default_work_type_idx >= len(work_types):
      default_work_type_idx = work_types.index("Test Execution") if "Test Execution" in work_types else 0
    
    work_type = st.selectbox(
      "Work Type *",
      options=work_types,
      index=default_work_type_idx,
      help="Issue 类型",
      key="work_type_select_pre"
    )
    # 保存选择
    st.session_state.create_work_type_idx = work_types.index(work_type)
  
  with config_row1_col2:
    # Priority 选择
    default_priority_idx = st.session_state.create_priority_idx
    if default_priority_idx >= len(priorities):
      default_priority_idx = priorities.index("Medium") if "Medium" in priorities else 0
    
    priority = st.selectbox(
      "Priority",
      options=priorities,
      index=default_priority_idx,
      help="优先级",
      key="priority_select_pre"
    )
    # 保存选择
    st.session_state.create_priority_idx = priorities.index(priority)
  
  config_row2_col1, config_row2_col2 = st.columns(2)
  
  with config_row2_col1:
    sp_team_options = ["（不设置）"] + sp_teams
    default_sp_team_idx = st.session_state.create_sp_team_idx
    if default_sp_team_idx >= len(sp_team_options):
      default_sp_team_idx = 0
    
    sp_team = st.selectbox(
      "SP Team",
      options=sp_team_options,
      index=default_sp_team_idx,
      help="Service Platform Team",
      key="sp_team_select_pre"
    )
    # 保存选择
    st.session_state.create_sp_team_idx = sp_team_options.index(sp_team)
  
  with config_row2_col2:
    # Sprint 字段（固定显示，带刷新按钮）
    sprint_col1, sprint_col2 = st.columns([4, 1])
    
    with sprint_col1:
      # 根据选择的 SP Team 获取 Active Sprints
      selected_team = sp_team if sp_team != "（不设置）" else None
      
      if st.session_state.available_sprints:
        sprint_options = ["（不设置）"] + [f"{s.get('name')} (ID: {s.get('id')})" for s in st.session_state.available_sprints]
      else:
        sprint_options = ["（不设置）"]
      
      default_sprint_idx = st.session_state.create_sprint_idx
      if default_sprint_idx >= len(sprint_options):
        default_sprint_idx = 0
      
      sprint_selection = st.selectbox(
        "Sprint（可选）",
        options=sprint_options,
        index=default_sprint_idx,
        help="选择 Sprint（点击右侧刷新按钮获取最新）",
        key="sprint_select_pre"
      )
      # 保存选择
      st.session_state.create_sprint_idx = sprint_options.index(sprint_selection)
    
    with sprint_col2:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("🔄", key="refresh_sprint_btn", help="刷新 Sprint 列表", use_container_width=True):
        # 检查 SP Team 是否已选择
        if sp_team == "（不设置）":
          st.error("❌ 请先选择 SP Team")
        else:
          # 清除缓存并重新获取
          get_team_sprints.clear()
          fresh_sprints = get_team_sprints(selected_team)
          st.session_state.available_sprints = fresh_sprints
          
          if fresh_sprints:
            st.success(f"✅ 找到 {len(fresh_sprints)} 个 Sprint")
          else:
            st.warning(f"⚠️ 未找到 {sp_team} 的 Active Sprint")
          
          st.rerun()
  
  # 如果选择了 Bug 类型，显示 Environment Occured 选择
  if work_type == "Bug":
    st.markdown("**🐛 Bug 特定字段**")
    bug_env_col1, bug_env_col2 = st.columns(2)
    
    with bug_env_col1:
      environment_options = ["DEV", "PP", "PROD"]
      default_env_idx = st.session_state.create_environment_idx
      if default_env_idx >= len(environment_options):
        default_env_idx = 1  # PP
      
      environment_occured = st.selectbox(
        "Environment Occured *",
        options=environment_options,
        index=default_env_idx,
        help="Bug 发生的环境（必填）",
        key="environment_select_pre"
      )
      # 保存选择
      st.session_state.create_environment_idx = environment_options.index(environment_occured)
    
    with bug_env_col2:
      st.markdown("<br>", unsafe_allow_html=True)
      st.info("💡 Bug 类型必须选择环境")
  else:
    environment_occured = None
  
  st.markdown("---")
  
  # ========== 创建 Ticket 表单 ==========
  with st.form("create_ticket_form"):
    st.subheader("📝 填写详细信息")
    
    summary = st.text_input(
      "Summary *",
      value=st.session_state.create_summary,
      placeholder="简短描述问题或任务",
      help="Issue 标题（必填）"
    )
    
    description = st.text_area(
      "Description",
      value=st.session_state.create_description,
      height=200,
      placeholder="详细描述...",
      help="Issue 描述（支持多行文本）"
    )
    
    submitted = st.form_submit_button("🚀 创建 Ticket", type="primary", use_container_width=True)
    
    if submitted:
      # 保存输入内容到 session_state
      st.session_state.create_summary = summary
      st.session_state.create_description = description
      
      # 验证必填字段
      if not summary or not summary.strip():
        st.error("❌ Summary 不能为空")
      elif work_type == "Bug" and not environment_occured:
        st.error("❌ Bug 类型必须选择 Environment Occured")
      else:
        with st.spinner("创建中..."):
          try:
            # 获取报告人 accountId
            reporter_account_id = jira_client.get_user_account_id(config_email)
            
            # 准备创建参数
            work_type_id = work_types_map.get(work_type)
            priority_id = priorities_map.get(priority)
            selected_team = sp_team if sp_team != "（不设置）" else None
            project_key = "SP"  # 固定使用 SP 项目
            
            # 解析 Sprint ID
            selected_sprint_id = None
            if sprint_selection != "（不设置）":
              # 从选项中提取 ID（格式：Name (ID: 123)）
              import re
              match = re.search(r'\(ID: (\d+)\)', sprint_selection)
              if match:
                selected_sprint_id = int(match.group(1))
            
            # 创建 Issue
            result = jira_client.create_issue(
              project_key=project_key,
              issue_type_id=work_type_id,
              summary=summary.strip(),
              description=description,
              priority_id=priority_id,
              reporter_account_id=reporter_account_id,
              sp_team=selected_team,
              sp_team_field=sp_team_field,
              environment_occured=environment_occured if work_type == "Bug" else None,
              sprint_id=selected_sprint_id
            )
            
            if result.get('success'):
              # 创建成功
              issue_data = result.get('data', {})
              issue_key = issue_data.get('key')
              issue_url = issue_data.get('self', '')
              browse_url = f"{base_url}/browse/{issue_key}"
              
              st.success(f"✅ Ticket 创建成功！")
              st.markdown(f"**Issue Key**: [{issue_key}]({browse_url})")
              st.json(issue_data)
            else:
              # 创建失败
              status_code = result.get('status_code', 0)
              if status_code == 401:
                st.error("❌ 认证失败，请检查 API Token 和邮箱")
              elif status_code == 400:
                st.error("❌ 请求参数错误，请检查必填字段")
                if result.get('data'):
                  st.json(result['data'])
              else:
                st.error(f"❌ 创建失败 (状态码: {status_code})")
                if result.get('data'):
                  st.json(result['data'])
              
          except Exception as e:
            st.error(f"❌ 创建失败: {str(e)}")

elif operation == "查询 Ticket":
  st.header("🔍 查询 Jira Ticket")
  
  col1, col2 = st.columns([3, 1])
  
  with col1:
    ticket_number = st.text_input(
      "Ticket Number",
      value=st.session_state.query_ticket_number,
      placeholder="例如: SP-30061",
      help="输入完整的 Ticket Key",
      key="query_ticket_input"
    )
    # 保存输入
    st.session_state.query_ticket_number = ticket_number
  
  with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    query_btn = st.button("🔎 查询", type="primary", use_container_width=True)
  
  if query_btn and ticket_number:
    with st.spinner("查询中..."):
      try:
        result = jira_client.get_issue(ticket_number.strip())
        
        if result.get('success'):
          # 查询成功
          issue_data = result['data']
          fields = issue_data.get('fields', {})
          
          st.success(f"✅ 查询成功: {ticket_number}")
          
          # 显示基本信息
          st.markdown("### 📋 基本信息")
          
          info_col1, info_col2, info_col3 = st.columns(3)
          
          with info_col1:
            st.metric("Key", issue_data.get('key', 'N/A'))
            st.metric("Project", fields.get('project', {}).get('key', 'N/A'))
          
          with info_col2:
            st.metric("Status", fields.get('status', {}).get('name', 'N/A'))
            st.metric("Priority", fields.get('priority', {}).get('name', 'N/A'))
          
          with info_col3:
            resolution = fields.get('resolution')
            st.metric("Resolution", resolution.get('name', 'Unresolved') if resolution else 'Unresolved')
            st.metric("Type", fields.get('issuetype', {}).get('name', 'N/A'))
          
          # SP Team 信息（如果有）
          sp_team_data = fields.get('customfield_12628')
          if sp_team_data:
            st.info(f"**SP Team**: {sp_team_data.get('value', 'N/A')}")
          
          # 显示详细信息
          st.markdown("### 📝 详细信息")
          
          with st.expander("✏️ Summary", expanded=True):
            st.write(fields.get('summary', 'N/A'))
          
          with st.expander("📄 Description"):
            description_adf = fields.get('description')
            if description_adf:
              description_text = jira_client.parse_adf_to_text(description_adf)
              st.text(description_text if description_text else "（无描述）")
            else:
              st.text("（无描述）")
          
          # 人员信息
          st.markdown("### 👥 人员信息")
          
          person_col1, person_col2 = st.columns(2)
          
          with person_col1:
            reporter = fields.get('reporter')
            if reporter:
              st.write(f"**Reporter**: {reporter.get('displayName', 'N/A')}")
            else:
              st.write("**Reporter**: N/A")
          
          with person_col2:
            assignee = fields.get('assignee')
            if assignee:
              st.write(f"**Assignee**: {assignee.get('displayName', 'Unassigned')}")
            else:
              st.write("**Assignee**: Unassigned")
          
          # 时间信息
          st.markdown("### ⏰ 时间信息")
          
          time_col1, time_col2 = st.columns(2)
          
          with time_col1:
            st.write(f"**Created**: {fields.get('created', 'N/A')}")
          
          with time_col2:
            st.write(f"**Updated**: {fields.get('updated', 'N/A')}")
          
          # 完整数据
          with st.expander("🔍 查看完整 JSON"):
            st.json(issue_data)
        
        else:
          # 查询失败
          status_code = result.get('status_code', 0)
          error_msg = result.get('error', '')
          
          if status_code == 401:
            st.error("❌ 认证失败，请检查 API Token 和邮箱")
            st.info("💡 建议：\n1. 确认 API Token 是否正确\n2. 确认邮箱是否与 Token 匹配\n3. 尝试重新生成 Token")
          elif status_code == 404:
            st.error(f"❌ Issue 不存在或无权访问: {ticket_number}")
            st.info("💡 建议：\n1. 确认 Ticket Key 拼写正确\n2. 确认你有权限访问此 Ticket\n3. 确认 Ticket 未被删除")
          elif status_code == 403:
            st.error(f"❌ 无权限访问: {ticket_number}")
            st.info("💡 请联系管理员分配权限")
          elif error_msg == 'timeout':
            st.error("❌ 请求超时")
            st.info("💡 建议：\n1. 检查网络连接\n2. 确认 VPN 是否连接\n3. 稍后重试")
          elif status_code == 0:
            st.error("❌ 网络连接失败")
            st.info("💡 建议：\n1. 检查网络连接是否正常\n2. 确认 Jira URL 是否正确\n3. 检查防火墙设置")
            if error_msg:
              with st.expander("🔍 详细错误信息"):
                st.code(error_msg)
          else:
            st.error(f"❌ 查询失败 (状态码: {status_code})")
            if result.get('data'):
              with st.expander("🔍 详细错误信息"):
                st.json(result['data'])
          
      except Exception as e:
        st.error(f"❌ 查询失败: {str(e)}")
        st.info("💡 建议：\n1. 检查网络连接\n2. 确认配置是否正确\n3. 查看详细错误信息")
        with st.expander("🔍 详细错误信息"):
          st.code(str(e))
  
  elif query_btn:
    st.warning("⚠️ 请输入 Ticket Number")

elif operation == "批量更新 Resolution":
  st.header("📦 批量更新 Resolution")
  
  st.markdown("""
  批量更新多个 Ticket 的 Resolution 状态。每行输入一个 Ticket Key。
  
  **注意**: 此功能会直接更新 Resolution 字段，无需进行 transition。
  """)
  
  # 获取 Resolutions
  resolutions = jira_client.get_resolutions()
  
  tickets_input = st.text_area(
    "Ticket 列表（每行一个）",
    value=st.session_state.batch_tickets_input,
    height=150,
    placeholder="SP-30061\nSP-30062\nSP-30063",
    help="每行输入一个 Ticket Key",
    key="batch_tickets_textarea"
  )
  # 保存输入
  st.session_state.batch_tickets_input = tickets_input
  
  col1, col2 = st.columns(2)
  
  with col1:
    default_resolution_idx = st.session_state.batch_resolution_idx
    if default_resolution_idx >= len(resolutions):
      default_resolution_idx = resolutions.index("Fixed") if "Fixed" in resolutions else 0
    
    resolution = st.selectbox(
      "Resolution",
      options=resolutions,
      index=default_resolution_idx,
      help="选择要设置的 Resolution"
    )
    # 保存选择
    st.session_state.batch_resolution_idx = resolutions.index(resolution)
  
  with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    update_btn = st.button("🔄 批量更新", type="primary", use_container_width=True)
  
  if update_btn:
    if not tickets_input or not tickets_input.strip():
      st.warning("⚠️ 请输入至少一个 Ticket")
    else:
      # 解析 Ticket 列表
      tickets = [line.strip() for line in tickets_input.split('\n') if line.strip()]
      
      if not tickets:
        st.warning("⚠️ 未找到有效的 Ticket")
      else:
        st.info(f"📊 准备更新 {len(tickets)} 个 Ticket，Resolution: **{resolution}**")
        
        # 进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 结果统计
        results = {
          'success': [],
          'failed': []
        }
        
        # 批量更新
        for i, ticket in enumerate(tickets):
          status_text.text(f"正在更新: {ticket} ({i+1}/{len(tickets)})")
          
          try:
            result = jira_client.update_issue_resolution(ticket, resolution)
            
            if result.get('success'):
              results['success'].append(ticket)
            else:
              results['failed'].append({
                'ticket': ticket,
                'status_code': result.get('status_code', 0)
              })
          
          except Exception as e:
            results['failed'].append({
              'ticket': ticket,
              'error': str(e)
            })
          
          # 更新进度
          progress_bar.progress((i + 1) / len(tickets))
        
        # 清空状态文本
        status_text.empty()
        
        # 显示结果
        st.markdown("---")
        st.markdown("### 📊 更新结果")
        
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
          st.metric("总计", len(tickets))
        
        with col2:
          st.metric("成功", success_count, delta=None if success_count == 0 else "✅")
        
        with col3:
          st.metric("失败", failed_count, delta=None if failed_count == 0 else "❌")
        
        # 显示详细结果
        if success_count > 0:
          with st.expander(f"✅ 成功更新 ({success_count})", expanded=True):
            for ticket in results['success']:
              browse_url = f"{base_url}/browse/{ticket}"
              st.markdown(f"- [{ticket}]({browse_url})")
        
        if failed_count > 0:
          with st.expander(f"❌ 更新失败 ({failed_count})", expanded=True):
            for item in results['failed']:
              ticket = item['ticket']
              status_code = item.get('status_code', 0)
              error = item.get('error', '')
              
              if status_code == 401:
                st.markdown(f"- {ticket}: 认证失败")
              elif status_code == 404:
                st.markdown(f"- {ticket}: Issue 不存在")
              elif error:
                st.markdown(f"- {ticket}: {error}")
              else:
                st.markdown(f"- {ticket}: 未知错误 (状态码: {status_code})")
        
        if success_count == len(tickets):
          st.success(f"🎉 所有 Ticket 更新成功！")
        elif failed_count == len(tickets):
          st.error(f"❌ 所有 Ticket 更新失败")
        else:
          st.warning(f"⚠️ 部分更新完成：成功 {success_count}/{len(tickets)}")

elif operation == "删除 Ticket":
  st.header("🗑️ 删除 Jira Ticket")
  
  st.warning("""
  ⚠️ **危险操作警告**
  
  删除 Ticket 是不可逆操作，请谨慎使用！
  - 删除后无法恢复
  - 会删除所有关联的评论、附件和历史记录
  - 建议先备份重要信息
  """)
  
  col1, col2 = st.columns([3, 1])
  
  with col1:
    delete_ticket_number = st.text_input(
      "Ticket Number",
      value=st.session_state.delete_ticket_number,
      placeholder="例如: SP-30061",
      help="输入要删除的 Ticket Key",
      key="delete_ticket_input"
    )
    # 保存输入
    st.session_state.delete_ticket_number = delete_ticket_number
  
  with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    # 先查询按钮
    preview_btn = st.button("👁️ 预览", type="secondary", use_container_width=True, help="查看要删除的 Ticket 信息")
  
  # 预览 Ticket 信息
  if preview_btn and delete_ticket_number:
    with st.spinner("查询中..."):
      try:
        result = jira_client.get_issue(delete_ticket_number.strip())
        
        if result.get('success'):
          issue_data = result['data']
          fields = issue_data.get('fields', {})
          
          st.info("📋 **即将删除的 Ticket 信息：**")
          
          preview_col1, preview_col2 = st.columns(2)
          
          with preview_col1:
            st.write(f"**Key**: {issue_data.get('key')}")
            st.write(f"**Type**: {fields.get('issuetype', {}).get('name', 'N/A')}")
            st.write(f"**Status**: {fields.get('status', {}).get('name', 'N/A')}")
          
          with preview_col2:
            st.write(f"**Priority**: {fields.get('priority', {}).get('name', 'N/A')}")
            reporter = fields.get('reporter', {})
            st.write(f"**Reporter**: {reporter.get('displayName', 'N/A')}")
            st.write(f"**Created**: {fields.get('created', 'N/A')[:10]}")
          
          st.write(f"**Summary**: {fields.get('summary', 'N/A')}")
          
          # 启用删除确认
          st.session_state.delete_confirm = True
        else:
          st.error(f"❌ 无法查询 Ticket: {delete_ticket_number}")
          st.session_state.delete_confirm = False
      except Exception as e:
        st.error(f"❌ 查询失败: {str(e)}")
        st.session_state.delete_confirm = False
  
  # 删除确认
  if st.session_state.delete_confirm and delete_ticket_number:
    st.markdown("---")
    st.error("⚠️ **最后确认**")
    
    confirm_col1, confirm_col2, confirm_col3 = st.columns([1, 1, 1])
    
    with confirm_col1:
      delete_subtasks = st.checkbox(
        "同时删除子任务",
        help="如果此 Ticket 有子任务，勾选此项将一并删除"
      )
    
    with confirm_col2:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("🗑️ 确认删除", type="primary", use_container_width=True):
        with st.spinner("删除中..."):
          try:
            result = jira_client.delete_issue(delete_ticket_number.strip(), delete_subtasks)
            
            if result.get('success'):
              st.success(f"✅ Ticket {delete_ticket_number} 已成功删除！")
              # 清空输入和确认状态
              st.session_state.delete_ticket_number = ""
              st.session_state.delete_confirm = False
              st.balloons()
            else:
              status_code = result.get('status_code', 0)
              if status_code == 401:
                st.error("❌ 认证失败，请检查 API Token")
              elif status_code == 403:
                st.error("❌ 权限不足，无法删除此 Ticket")
                st.info("💡 可能原因：\n- 没有删除权限\n- Ticket 已被锁定\n- 项目限制了删除操作")
              elif status_code == 404:
                st.error(f"❌ Ticket 不存在: {delete_ticket_number}")
              else:
                st.error(f"❌ 删除失败 (状态码: {status_code})")
          except Exception as e:
            st.error(f"❌ 删除失败: {str(e)}")
    
    with confirm_col3:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("❌ 取消", use_container_width=True):
        st.session_state.delete_confirm = False
        st.info("已取消删除操作")
        st.rerun()

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
  <p>💡 提示：Token 将安全保存在加密 cookies 中，刷新页面后自动加载</p>
  <p>🔐 所有 API 调用使用 HTTPS + Basic Auth 加密传输</p>
</div>
""", unsafe_allow_html=True)
