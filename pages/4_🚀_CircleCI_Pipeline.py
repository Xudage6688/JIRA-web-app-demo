import streamlit as st
import sys
import os
from pathlib import Path
import time
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入CircleCI模块
from circleCi.triggerJob import trigger_circleci_pipeline, validate_project_slug
from circleCi.monitoring import (
    get_pipeline_status, 
    get_pipeline_workflows,
    format_status,
    monitor_pipeline,
    monitor_by_pipeline_number
)
from modules.user_config_loader import get_circleci_config, get_user_config_loader

# CircleCI API基础URL
CIRCLECI_API_BASE = 'https://circleci.com/api/v2'

# 设置页面配置
st.set_page_config(
    page_title="CircleCI Pipeline管理",
    page_icon="🚀",
    layout="wide"
)

# 检查当前用户
if 'current_user' not in st.session_state or not st.session_state.current_user:
    st.error("❌ 未选择使用者，请返回主页选择你的身份")
    st.stop()

current_user = st.session_state.current_user

# 从用户配置加载CircleCI配置
user_circleci_config = get_circleci_config(current_user)

if not user_circleci_config:
    st.error(f"❌ 未找到用户 {current_user} 的 CircleCI 配置")
    st.info("请联系管理员在 config/users_config.json 中配置你的信息")
    st.stop()

# 使用用户配置
CIRCLECI_API_TOKEN = user_circleci_config.get('api_token', '')
VCS_TYPE = user_circleci_config.get('vcs_type', 'github')
ORGANIZATION = user_circleci_config.get('organization', 'asiainspection')
DEFAULT_PROJECT = user_circleci_config.get('default_project', 'back-office-cloud')
DEFAULT_BRANCH = user_circleci_config.get('default_branch', 'master')

# 辅助函数：调用 CircleCI API
def call_circleci_api(endpoint, method='GET', data=None, params=None):
    """调用 CircleCI API"""
    url = f"{CIRCLECI_API_BASE}/{endpoint}"
    headers = {
        'Circle-Token': CIRCLECI_API_TOKEN,
        'Content-Type': 'application/json'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=10)
        else:
            return None
            
        if response.status_code < 500:
            return response
        return None
    except Exception as e:
        st.error(f"API 调用失败: {str(e)}")
        return None

def query_pipelines(project_slug, branch=None, show_progress=False):
    """查询项目的 Pipeline 列表"""
    params = {}
    if branch:
        params['branch'] = branch
    
    response = call_circleci_api(f"project/{project_slug}/pipeline", params=params)
    
    if response and response.status_code == 200:
        data = response.json()
        pipelines = data.get('items', [])[:10]  # 只取前10个
        
        # 从 project_slug 中提取项目名称
        project_name = project_slug.split('/')[-1] if '/' in project_slug else project_slug
        
        total = len(pipelines)
        if show_progress:
            print(f"📊 开始处理 {total} 个 Pipeline（并发模式）")
        
        # 使用并发获取审批信息
        def fetch_pipeline_data(p, idx):
            """获取单个 pipeline 的完整数据"""
            pipeline_id = p.get('id')
            pipeline_number = p.get('number')
            
            if show_progress:
                print(f"  [{idx+1}/{total}] Processing Pipeline #{pipeline_number}")
            
            # 获取 preprod approval 信息
            preprod_approval_info = get_preprod_approval_info(pipeline_id, project_name)
            
            if show_progress and preprod_approval_info:
                print(f"  ✓ Found preprod approval for #{pipeline_number}")
            
            return {
                'id': pipeline_id,
                'number': pipeline_number,
                'state': p.get('state'),
                'created_at': p.get('created_at'),
                'updated_at': p.get('updated_at'),
                'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
                'branch': p.get('vcs', {}).get('branch'),
                'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
                'revision': p.get('vcs', {}).get('revision'),
                'preprod_approval': preprod_approval_info,
                'project_name': project_name
            }
        
        # 使用线程池并发处理（最多5个并发）
        formatted = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 提交所有任务
            futures = {executor.submit(fetch_pipeline_data, p, idx): idx 
                      for idx, p in enumerate(pipelines)}
            
            # 按提交顺序收集结果
            results = [None] * total
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"Error processing pipeline {idx}: {e}")
                    # 即使出错也添加基本信息
                    p = pipelines[idx]
                    results[idx] = {
                        'id': p.get('id'),
                        'number': p.get('number'),
                        'state': p.get('state'),
                        'created_at': p.get('created_at'),
                        'updated_at': p.get('updated_at'),
                        'actor': p.get('trigger', {}).get('actor', {}).get('login', 'Unknown'),
                        'branch': p.get('vcs', {}).get('branch'),
                        'commit_subject': p.get('vcs', {}).get('commit', {}).get('subject'),
                        'revision': p.get('vcs', {}).get('revision'),
                        'preprod_approval': None,
                        'project_name': project_name
                    }
            
            formatted = [r for r in results if r is not None]
        
        if show_progress:
            print(f"✅ 完成！共处理 {len(formatted)} 个 Pipeline")
        
        return formatted
    return None

def get_user_info_by_id(user_id):
    """
    通过用户 UUID 获取用户信息（用户名）
    使用缓存避免重复 API 调用
    
    Args:
        user_id: 用户的 UUID
        
    Returns:
        用户名（login）或 None
    """
    # 确保缓存已初始化（防止并发调用时出错）
    if 'user_cache' not in st.session_state:
        st.session_state.user_cache = {}
    
    # 检查缓存
    if user_id in st.session_state.user_cache:
        return st.session_state.user_cache[user_id]
    
    try:
        endpoint = f'user/{user_id}'
        response = call_circleci_api(endpoint)
        
        if response and response.status_code == 200:
            user_data = response.json()
            # 尝试多个可能的字段
            login = user_data.get('login') or user_data.get('username') or user_data.get('name')
            
            # 缓存结果
            if login:
                st.session_state.user_cache[user_id] = login
            
            return login
        
        # 缓存失败结果，避免重复请求
        st.session_state.user_cache[user_id] = None
        return None
    except Exception as e:
        print(f"Error fetching user info for {user_id}: {e}")
        # 缓存失败结果
        st.session_state.user_cache[user_id] = None
        return None

def get_preprod_approval_info(pipeline_id, project_name=None):
    """
    获取 Pipeline 中 preprod approval 的信息
    pipeline_id: Pipeline ID
    project_name: 项目名称（用于匹配对应的 approval job）
    返回：{'approved_by': '审批人', 'approved_at': '审批时间', 'status': '状态'} 或 None
    """
    try:
        # 获取 workflows
        workflows = get_pipeline_workflows(pipeline_id, api_token=CIRCLECI_API_TOKEN, silent=True)
        
        if not workflows:
            return None
        
        # 收集所有 preprod approval jobs
        all_preprod_approvals = []
        
        # 遍历 workflows，查找 preprod 相关的 approval job
        for workflow in workflows:
            workflow_id = workflow.get('id')
            workflow_name = workflow.get('name', '').lower()
            
            # 获取该 workflow 的 jobs
            response = call_circleci_api(f"workflow/{workflow_id}/job")
            
            if not response or response.status_code != 200:
                continue
            
            data = response.json()
            all_jobs = data.get('items', [])
            
            # 查找 approval 类型的 job
            for job in all_jobs:
                job_name = job.get('name', '').lower()
                job_type = job.get('type', '')
                
                # 检查是否是 preprod 的 approval job
                if job_type == 'approval' and 'preprod' in job_name:
                    status = job.get('status')
                    
                    approval_info = {
                        'approved_by': None,
                        'approved_at': None,
                        'job_name': job.get('name'),
                        'status': status,
                        'job_name_lower': job_name
                    }
                    
                    # 根据状态填充信息
                    if status == 'success':
                        # CircleCI 的 approval job 的 approved_by 是用户 UUID
                        # 需要通过 API 将 UUID 转换为用户名
                        
                        approved_by_data = job.get('approved_by')
                        approver_name = None
                        
                        if isinstance(approved_by_data, str) and approved_by_data:
                            # 检查是否是 UUID 格式（包含多个破折号）
                            if approved_by_data.count('-') >= 4:
                                # 这是一个 UUID，需要查询用户信息
                                print(f"  Fetching user info for UUID: {approved_by_data}")
                                approver_name = get_user_info_by_id(approved_by_data)
                                if approver_name:
                                    print(f"  ✓ Found username: {approver_name}")
                                else:
                                    print(f"  ✗ Could not resolve UUID to username")
                            else:
                                # 不是 UUID，可能已经是用户名
                                approver_name = approved_by_data
                        elif isinstance(approved_by_data, dict):
                            # 如果是字典，尝试获取 login 字段
                            approver_name = approved_by_data.get('login') or approved_by_data.get('username')
                        
                        # 设置审批人信息
                        if approver_name:
                            approval_info['approved_by'] = approver_name
                        else:
                            approval_info['approved_by'] = '已审批'
                            approval_info['note'] = '无法获取审批者信息'
                        
                        approval_info['approved_at'] = job.get('stopped_at', job.get('approved_at'))
                        approval_info['status'] = 'approved'
                        
                    elif status == 'on_hold':
                        approval_info['approved_by'] = 'Pending'
                        approval_info['approved_at'] = None
                        approval_info['status'] = 'pending'
                    else:
                        approval_info['approved_by'] = 'N/A'
                        approval_info['approved_at'] = job.get('stopped_at')
                    
                    all_preprod_approvals.append(approval_info)
        
        if not all_preprod_approvals:
            return None
        
        # 如果提供了项目名称，尝试匹配相关的 approval
        if project_name:
            # 从 project_slug 中提取项目名称（例如：github/asiainspection/aca-new -> aca-new）
            if '/' in project_name:
                project_name = project_name.split('/')[-1]
            
            project_name_lower = project_name.lower()
            
            # 查找 job 名称中包含项目名称的 approval
            matched_approvals = [
                approval for approval in all_preprod_approvals
                if project_name_lower in approval['job_name_lower']
            ]
            
            if matched_approvals:
                # 优先返回已审批的，否则返回第一个匹配的
                approved_ones = [a for a in matched_approvals if a['status'] == 'approved']
                if approved_ones:
                    result = approved_ones[0].copy()
                    del result['job_name_lower']
                    return result
                else:
                    result = matched_approvals[0].copy()
                    del result['job_name_lower']
                    return result
        
        # 如果没有匹配的或没有提供项目名称，返回第一个已审批的，否则返回第一个
        approved_ones = [a for a in all_preprod_approvals if a['status'] == 'approved']
        if approved_ones:
            result = approved_ones[0].copy()
            del result['job_name_lower']
            return result
        else:
            result = all_preprod_approvals[0].copy()
            del result['job_name_lower']
            return result
        
    except Exception as e:
        # 返回错误信息而不是 None，方便调试
        return {
            'error': str(e),
            'approved_by': 'Error',
            'approved_at': None,
            'job_name': 'Error fetching approval info',
            'status': 'error'
        }

def get_workflow_jobs(workflow_id):
    """获取 Workflow 的 Jobs（包括 approval jobs）"""
    response = call_circleci_api(f"workflow/{workflow_id}/job")
    
    if response and response.status_code == 200:
        data = response.json()
        jobs = data.get('items', [])
        
        # 筛选出 approval 类型的 job
        approval_jobs = [
            {**job, 'workflow_id': workflow_id}
            for job in jobs
            if job.get('type') == 'approval' and job.get('status') == 'on_hold'
        ]
        
        return {
            'jobs': jobs,
            'approval_jobs': approval_jobs
        }
    return None

def approve_job(workflow_id, approval_request_id):
    """审批一个 Job"""
    endpoint = f"workflow/{workflow_id}/approve/{approval_request_id}"
    response = call_circleci_api(endpoint, method='POST', data={})
    
    if response and response.status_code < 400:
        return {'success': True, 'message': '审批成功'}
    else:
        return {
            'success': False, 
            'error': response.json().get('message', '审批失败') if response else '网络错误'
        }

def format_duration(started_at, stopped_at=None):
    """
    格式化持续时间
    如果 stopped_at 为 None，则计算从 started_at 到现在的时间
    """
    if not started_at:
        return 'N/A'
    
    try:
        from datetime import datetime, timezone
        
        # 解析 started_at
        if isinstance(started_at, str):
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        else:
            start = started_at
        
        # 确定结束时间
        if stopped_at:
            if isinstance(stopped_at, str):
                end = datetime.fromisoformat(stopped_at.replace('Z', '+00:00'))
            else:
                end = stopped_at
        else:
            # 如果没有 stopped_at，使用当前时间
            end = datetime.now(timezone.utc)
        
        # 计算时间差
        duration = end - start
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 0:
            return 'N/A'
        
        # 格式化显示
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception as e:
        return 'N/A'

def convert_utc_to_beijing(utc_time_str):
    """
    将 UTC 时间转换为北京时间（UTC+8）
    """
    if not utc_time_str:
        return None
    
    try:
        from datetime import datetime, timedelta
        
        # 解析 UTC 时间
        if isinstance(utc_time_str, str):
            dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        else:
            dt = utc_time_str
        
        # 转换为北京时间 (UTC+8)
        beijing_time = dt + timedelta(hours=8)
        
        # 格式化返回
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return utc_time_str

def format_time_ago(utc_time_str):
    """计算相对时间（多久之前）"""
    if not utc_time_str:
        return ""
    try:
        from datetime import datetime, timezone
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - utc_time
        
        if delta.days > 0:
            return f"{delta.days}天前"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}小时前"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except Exception as e:
        return ""

# 初始化session state
if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False
if 'pipeline_history' not in st.session_state:
    st.session_state.pipeline_history = []
if 'current_pipeline_id' not in st.session_state:
    st.session_state.current_pipeline_id = None
if 'monitoring_status' not in st.session_state:
    st.session_state.monitoring_status = []
if 'show_pipelines_list' not in st.session_state:
    st.session_state.show_pipelines_list = False
if 'selected_pipeline_for_detail' not in st.session_state:
    st.session_state.selected_pipeline_for_detail = None
if 'queried_pipelines' not in st.session_state:
    st.session_state.queried_pipelines = None
if 'query_project_slug' not in st.session_state:
    st.session_state.query_project_slug = None
if 'approval_workflows' not in st.session_state:
    st.session_state.approval_workflows = None
if 'approval_search_pipeline_id' not in st.session_state:
    st.session_state.approval_search_pipeline_id = None

# 添加用户信息缓存（避免重复 API 调用）
if 'user_cache' not in st.session_state:
    st.session_state.user_cache = {}

# 初始化各个输入框的状态（保持输入值，切换Tab不丢失）
if 'trigger_project' not in st.session_state:
    st.session_state.trigger_project = DEFAULT_PROJECT
if 'trigger_branch' not in st.session_state:
    st.session_state.trigger_branch = DEFAULT_BRANCH
if 'query_project' not in st.session_state:
    st.session_state.query_project = DEFAULT_PROJECT
if 'query_branch' not in st.session_state:
    st.session_state.query_branch = ""

# 标题
st.title("🚀 CircleCI Pipeline 管理工具")

# 显示当前用户
user_display_name = get_user_config_loader().get_user_display_name(current_user)
st.info(f"👤 当前使用者: **{user_display_name}** ({current_user})")

st.markdown("---")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置")
    
    # API Token状态
    if CIRCLECI_API_TOKEN and CIRCLECI_API_TOKEN != 'YOUR_CIRCLECI_TOKEN_HERE':
        token_preview = CIRCLECI_API_TOKEN[:20] + "..." if len(CIRCLECI_API_TOKEN) > 20 else CIRCLECI_API_TOKEN
        st.success(f"✅ API Token: {token_preview}")
    else:
        st.error("❌ 未配置API Token")
    
    st.markdown("---")
    
    # 默认配置显示
    st.subheader("📋 默认配置")
    st.info(f"**VCS**: {VCS_TYPE}")
    st.info(f"**组织**: {ORGANIZATION}")
    st.info(f"**项目**: {DEFAULT_PROJECT}")
    st.info(f"**分支**: {DEFAULT_BRANCH}")
    
    st.markdown("---")
    
    # 历史记录
    st.subheader("📜 触发历史")
    if st.session_state.pipeline_history:
        for i, history in enumerate(reversed(st.session_state.pipeline_history[-5:])):
            with st.expander(f"Pipeline #{history['number']}"):
                st.write(f"**ID:** {history['id'][:16]}...")
                st.write(f"**分支:** {history['branch']}")
                st.write(f"**时间:** {history['time']}")
    else:
        st.write("暂无历史记录")

# 创建标签页导航
tab1, tab2, tab3, tab4 = st.tabs(["🎯 触发Pipeline", "📋 Pipeline列表", "📊 监控Pipeline", "✅ 审批管理"])

# 侧边栏设置
with st.sidebar:
    st.subheader("⚙️ 设置")
    
    # 显示缓存统计
    cached_users = len(st.session_state.get('user_cache', {}))
    if cached_users > 0:
        st.info(f"👤 已缓存 {cached_users} 个用户信息")
        if st.button("🗑️ 清空用户缓存", use_container_width=True):
            st.session_state.user_cache = {}
            st.success("✅ 缓存已清空")
            st.rerun()
    else:
        st.caption("暂无用户缓存")
    
    st.markdown("---")
    
    # API 信息
    st.caption(f"🔑 Token: {CIRCLECI_API_TOKEN[:15]}...")
    st.caption(f"🏢 Organization: {ORGANIZATION}")
    st.caption(f"📦 VCS: {VCS_TYPE}")

# Tab 1: 触发 Pipeline
with tab1:
    st.header("🎯 触发 Pipeline")
    
    # 读取服务列表（从 config 目录）
    services_file = project_root / "config" / "circleci-services.txt"
    service_list_for_trigger = [DEFAULT_PROJECT]
    
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list_for_trigger = services
    except Exception as e:
        print(f"Warning: Could not load services list: {e}")
    
    with st.form("trigger_form"):
        # 项目名称选择（使用 session state 保持值）
        try:
            default_index = service_list_for_trigger.index(st.session_state.trigger_project)
        except (ValueError, AttributeError):
            default_index = service_list_for_trigger.index(DEFAULT_PROJECT) if DEFAULT_PROJECT in service_list_for_trigger else 0
        
        project_name = st.selectbox(
            "项目名称",
            options=service_list_for_trigger,
            index=default_index,
            help="选择项目或直接输入关键字快速过滤"
        )
        
        # 分支配置（使用 session state 保持值）
        branch = st.text_input(
            "分支名称",
            value=st.session_state.trigger_branch,
            placeholder="例如: master, develop, SP-12345",
            help="要触发的分支名称"
        )
        
        # 显示完整的 Project Slug（只读）
        full_project_slug = f"{VCS_TYPE}/{ORGANIZATION}/{project_name}"
        st.info(f"📝 完整项目路径: `{full_project_slug}`")
        
        # 提交按钮
        submit_button = st.form_submit_button("🚀 触发 Pipeline", type="primary", use_container_width=True)
        
        if submit_button:
            # 保存输入值到 session state（保持状态）
            st.session_state.trigger_project = project_name
            st.session_state.trigger_branch = branch
            
            # 构建完整的 project_slug
            project_slug = full_project_slug
            
            # 验证项目配置
            if not validate_project_slug(project_slug):
                st.error("❌ 项目 Slug 格式错误")
                st.info("请检查项目名称是否正确")
            else:
                with st.spinner("正在触发 Pipeline..."):
                    try:
                        # 触发pipeline，传入API Token
                        result = trigger_circleci_pipeline(
                            project_slug, 
                            branch,
                            api_token=CIRCLECI_API_TOKEN
                        )
                        
                        if result.get('success'):
                            pipeline_id = result.get('pipeline_id')
                            pipeline_number = result.get('pipeline_number')
                            
                            st.success(f"✅ Pipeline 触发成功!")
                            
                            # 显示完整的 Pipeline ID（可复制）
                            st.write("**Pipeline ID:**")
                            st.code(pipeline_id, language=None)
                            st.info(f"**Pipeline Number:** {pipeline_number}")
                            
                            # 保存到历史记录
                            st.session_state.pipeline_history.append({
                                'id': pipeline_id,
                                'number': pipeline_number,
                                'branch': branch,
                                'project': project_slug,
                                'time': time.strftime('%Y-%m-%d %H:%M:%S')
                            })
                            
                            # 设置当前pipeline ID
                            st.session_state.current_pipeline_id = pipeline_id
                            
                            # 提示用户可以使用其他功能
                            st.info("💡 **快速操作提示:**\n"
                                   "- 切换到「📊 监控Pipeline」标签页可以实时监控状态\n"
                                   "- 切换到「✅ 审批管理」标签页可以审批待处理的 Jobs\n"
                                   "- Pipeline ID 已自动填充到各个标签页")
                            
                            st.balloons()
                        else:
                            st.error("❌ Pipeline 触发失败")
                            
                            # 显示具体错误信息
                            error_msg = result.get('error', '未知错误')
                            status_code = result.get('status_code')
                            
                            if status_code:
                                st.error(f"HTTP状态码: {status_code}")
                            st.error(f"错误信息: {error_msg}")
                            
                            # 显示排查建议
                            with st.expander("🔍 故障排查建议"):
                                st.markdown("""
                                请检查以下几点：
                                - ✅ API Token 是否有效且未过期
                                - ✅ 项目 Slug 格式是否正确 (vcs-type/org-name/repo-name)
                                - ✅ 分支是否存在于仓库中
                                - ✅ API Token 是否有足够的权限触发 Pipeline
                                - ✅ 网络连接是否正常
                                """)
                                
                                st.info(f"当前配置:\n- 项目: {project_slug}\n- 分支: {branch}")
                    
                    except Exception as e:
                        import traceback
                        st.error(f"❌ 发生异常: {str(e)}")
                        with st.expander("🔍 查看详细错误"):
                            st.code(traceback.format_exc())

# Tab 2: Pipeline 列表
with tab2:
    st.header("📋 Pipeline 列表")
    
    # 读取服务列表（从 config 目录）
    services_file = project_root / "config" / "circleci-services.txt"
    service_list = [DEFAULT_PROJECT]  # 默认从配置的项目开始
    
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
                service_list = services  # 使用完整服务列表
    except Exception as e:
        print(f"Warning: Could not load services list: {e}")
    
    col_list1, col_list2 = st.columns([2, 1])
    
    with col_list1:
        # 下拉选择框（使用 session state 保持值）
        try:
            default_index = service_list.index(st.session_state.query_project)
        except (ValueError, AttributeError):
            default_index = service_list.index(DEFAULT_PROJECT) if DEFAULT_PROJECT in service_list else 0
        
        query_project = st.selectbox(
            "项目名称",
            options=service_list,
            index=default_index,
            help="选择项目或直接输入关键字快速过滤",
            key="query_project_select"
        )
    
    with col_list2:
        query_branch = st.text_input(
            "分支（可选）",
            value=st.session_state.query_branch,
            help="留空查询所有分支",
            key="query_branch_input"
        )
    
    col_btn1, col_btn2 = st.columns([3, 1])
    
    with col_btn1:
        query_btn = st.button("🔍 查询 Pipelines", type="primary", use_container_width=True)
    
    with col_btn2:
        if st.session_state.queried_pipelines:
            if st.button("🗑️ 清空", use_container_width=True, key="clear_pipelines_list"):
                st.session_state.queried_pipelines = None
                st.session_state.query_project_slug = None
                st.rerun()
    
    if query_btn:
        # 保存输入值到 session state（保持状态）
        st.session_state.query_project = query_project
        st.session_state.query_branch = query_branch
        
        if not query_project:
            st.warning("⚠️ 请先选择项目名称")
        else:
            full_slug = f"{VCS_TYPE}/{ORGANIZATION}/{query_project}"
            
            with st.spinner("🚀 正在查询 Pipeline 列表（预计 5-10 秒）..."):
                pipelines = query_pipelines(full_slug, query_branch if query_branch else None, show_progress=True)
            
            if pipelines:
                # 保存查询结果到 session_state
                st.session_state.queried_pipelines = pipelines
                st.session_state.query_project_slug = full_slug
                st.success(f"✅ 找到 {len(pipelines)} 个 Pipelines")
            else:
                st.session_state.queried_pipelines = None
                st.error("❌ 查询失败或未找到 Pipeline")
                st.info(f"项目路径: {full_slug}")
    
    # 显示查询结果（从 session_state 读取）
    if st.session_state.queried_pipelines:
        pipelines = st.session_state.queried_pipelines
        
        st.info(f"📊 显示 {len(pipelines)} 个 Pipeline（项目: {st.session_state.query_project_slug}）")
        
        # 显示 Pipeline 列表
        for i, p in enumerate(pipelines):
            # 准备 expander 标题，如果有 preprod approval 信息则显示
            title = f"Pipeline #{p['number']} - {p['state']} - {p['branch'] or 'N/A'}"
            
            with st.expander(title):
                col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                
                with col_p1:
                    st.write("**完整 ID:**")
                    st.code(p['id'], language=None)
                    st.write(f"**Number:** {p['number']}")
                    st.write(f"**状态:** {p['state']}")
                
                with col_p2:
                    st.write(f"**分支:** {p['branch'] or 'N/A'}")
                    st.write(f"**触发者:** {p['actor']}")
                    st.write(f"**提交:** {p['commit_subject'] or 'N/A'}")
                
                with col_p3:
                    if st.button("📊 监控", key=f"monitor_{i}", use_container_width=True, type="primary"):
                        st.session_state.current_pipeline_id = p['id']
                        st.success(f"✅ 已设置 Pipeline ID")
                        st.info("💡 **快速操作提示:**\n"
                               "- 切换到「📊 监控Pipeline」可实时监控\n"
                               "- 切换到「✅ 审批管理」可审批 Jobs\n"
                               "- Pipeline ID 已自动填充")
                
                # 显示 Preprod Approval 信息
                preprod_approval = p.get('preprod_approval')
                if preprod_approval:
                    st.markdown("---")
                    st.markdown("**🎯 Preprod Approval 信息:**")
                    
                    approval_status = preprod_approval.get('status', 'unknown')
                    
                    if approval_status == 'error':
                        st.error(f"⚠️ 获取审批信息失败: {preprod_approval.get('error', 'Unknown error')}")
                    else:
                        col_a1, col_a2 = st.columns(2)
                        
                        with col_a1:
                            approved_by = preprod_approval.get('approved_by', 'N/A')
                            if approved_by == 'Pending':
                                st.warning(f"👤 **审批人:** ⏳ 等待审批")
                            elif approved_by == 'Error':
                                st.error(f"👤 **审批人:** ❌ 获取失败")
                            elif approved_by == '已审批':
                                st.success(f"✅ **状态:** 已审批")
                                note = preprod_approval.get('note')
                                if note:
                                    st.caption(f"💡 {note}")
                            else:
                                st.info(f"👤 **审批人:** {approved_by}")
                        
                        with col_a2:
                            approved_at = preprod_approval.get('approved_at')
                            if approved_at:
                                # 转换为北京时间（UTC+8）
                                beijing_time = convert_utc_to_beijing(approved_at)
                                time_ago = format_time_ago(approved_at)
                                if beijing_time:
                                    st.info(f"⏰ **审批时间:** {beijing_time}\n📅 ({time_ago})")
                                else:
                                    st.info(f"⏰ **审批时间:** {approved_at}")
                            else:
                                st.warning(f"⏰ **审批时间:** ⏳ 待审批")
                        
                        # 显示 job 名称和状态
                        job_name = preprod_approval.get('job_name')
                        if job_name:
                            status_emoji = {
                                'approved': '✅',
                                'pending': '⏳',
                                'success': '✅',
                                'on_hold': '⏳',
                                'failed': '❌',
                                'error': '⚠️'
                            }.get(approval_status, '❓')
                            st.caption(f"{status_emoji} Job: {job_name} ({approval_status})")
                else:
                    # 没有 preprod approval 信息
                    st.markdown("---")
                    st.caption("ℹ️ 此 Pipeline 没有 Preprod Approval 步骤")
                
                st.caption(f"创建时间: {p['created_at']}")
                if p['revision']:
                    st.caption(f"Revision: {p['revision'][:8]}")

# Tab 3: 监控Pipeline
with tab3:
    st.header("📊 监控 Pipeline")
    
    # 监控方式选择
    monitor_mode = st.radio(
        "监控方式",
        ["Pipeline ID", "Pipeline Number"],
        horizontal=True
    )
    
    if monitor_mode == "Pipeline ID":
        # 使用Pipeline ID监控
        pipeline_id_input = st.text_input(
            "Pipeline ID",
            value=st.session_state.current_pipeline_id if st.session_state.current_pipeline_id else "",
            help="输入要监控的 Pipeline ID"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            check_status_btn = st.button("🔍 查看状态", use_container_width=True)
        with col_btn2:
            monitor_btn = st.button("📊 开始监控", use_container_width=True, type="primary")
        
        if check_status_btn and pipeline_id_input:
            with st.spinner("正在获取详细状态..."):
                # 获取pipeline状态，传入API Token
                pipeline_data = get_pipeline_status(pipeline_id_input, api_token=CIRCLECI_API_TOKEN)
                
                if pipeline_data:
                    st.success("✅ 状态获取成功")
                    
                    # 显示基本信息（扩展）
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("Pipeline Number", f"#{pipeline_data.get('number', 'N/A')}")
                        st.metric("状态", pipeline_data.get('state', 'unknown').upper())
                    with col_info2:
                        st.metric("VCS 分支", pipeline_data.get('vcs', {}).get('branch', 'N/A'))
                        trigger_actor = pipeline_data.get('trigger', {}).get('actor', {}).get('login', 'Unknown')
                        st.metric("触发者", trigger_actor)
                    with col_info3:
                        created_at = pipeline_data.get('created_at', '')
                        if created_at:
                            beijing_time = convert_utc_to_beijing(created_at)
                            time_ago = format_time_ago(created_at)
                            st.metric("创建时间", f"{time_ago}")
                            st.caption(beijing_time)
                        else:
                            st.metric("创建时间", "N/A")
                        
                        project_slug = pipeline_data.get('project_slug', 'N/A')
                        project_name = project_slug.split('/')[-1] if '/' in project_slug else project_slug
                        st.metric("项目", project_name)
                    
                    # 显示提交信息
                    st.markdown("---")
                    st.subheader("📝 Git 提交信息")
                    vcs = pipeline_data.get('vcs', {})
                    col_vcs1, col_vcs2 = st.columns([2, 1])
                    with col_vcs1:
                        commit_subject = vcs.get('commit', {}).get('subject', 'N/A')
                        st.write(f"**提交消息:** {commit_subject}")
                        commit_body = vcs.get('commit', {}).get('body', '')
                        if commit_body:
                            with st.expander("查看完整提交信息"):
                                st.code(commit_body)
                    with col_vcs2:
                        revision = vcs.get('revision', 'N/A')
                        st.code(f"Revision: {revision[:8]}...", language="text")
                        branch = vcs.get('branch', 'N/A')
                        st.code(f"Branch: {branch}", language="text")
                    
                    # 获取workflows状态（详细）
                    st.markdown("---")
                    workflows = get_pipeline_workflows(pipeline_id_input, api_token=CIRCLECI_API_TOKEN)
                    if workflows:
                        st.subheader(f"🔄 Workflows ({len(workflows)})")
                        
                        for idx, workflow in enumerate(workflows):
                            workflow_id = workflow.get('id', 'N/A')
                            workflow_name = workflow.get('name', 'Unknown')
                            workflow_status = workflow.get('status', 'unknown')
                            display_text, emoji = format_status(workflow_status)
                            
                            # 计算workflow时长
                            started_at = workflow.get('started_at')
                            stopped_at = workflow.get('stopped_at')
                            duration_str = format_duration(started_at, stopped_at) if started_at else 'N/A'
                            
                            with st.expander(f"{emoji} **{workflow_name}** - {display_text} (⏱️ {duration_str})", expanded=(idx==0)):
                                # Workflow详细信息
                                col_w1, col_w2 = st.columns(2)
                                with col_w1:
                                    st.write(f"**Workflow ID:** `{workflow_id[:16]}...`")
                                    st.write(f"**状态:** {display_text} {emoji}")
                                with col_w2:
                                    if started_at:
                                        beijing_start = convert_utc_to_beijing(started_at)
                                        st.write(f"**开始时间:** {beijing_start}")
                                    if stopped_at:
                                        beijing_stop = convert_utc_to_beijing(stopped_at)
                                        st.write(f"**结束时间:** {beijing_stop}")
                                
                                # 获取并显示Jobs
                                st.write("---")
                                st.write("**📋 Jobs:**")
                                try:
                                    response = call_circleci_api(f"workflow/{workflow_id}/job")
                                    if response and response.status_code == 200:
                                        jobs_data = response.json()
                                        jobs = jobs_data.get('items', [])
                                        
                                        if jobs:
                                            # 统计信息
                                            job_stats = {
                                                'success': 0,
                                                'running': 0,
                                                'failed': 0,
                                                'on_hold': 0,
                                                'other': 0
                                            }
                                            
                                            for job in jobs:
                                                status = job.get('status', 'unknown')
                                                if status == 'success':
                                                    job_stats['success'] += 1
                                                elif status in ['running', 'queued']:
                                                    job_stats['running'] += 1
                                                elif status in ['failed', 'failing']:
                                                    job_stats['failed'] += 1
                                                elif status == 'on_hold':
                                                    job_stats['on_hold'] += 1
                                                else:
                                                    job_stats['other'] += 1
                                            
                                            # 显示统计
                                            col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
                                            with col_stat1:
                                                st.metric("✅ 成功", job_stats['success'])
                                            with col_stat2:
                                                st.metric("🔄 运行中", job_stats['running'])
                                            with col_stat3:
                                                st.metric("❌ 失败", job_stats['failed'])
                                            with col_stat4:
                                                st.metric("⏸️ 待审批", job_stats['on_hold'])
                                            with col_stat5:
                                                st.metric("📊 总计", len(jobs))
                                            
                                            # 显示Job列表
                                            st.write("")
                                            for job in jobs:
                                                job_name = job.get('name', 'Unknown')
                                                job_status = job.get('status', 'unknown')
                                                job_type = job.get('type', 'build')
                                                job_number = job.get('job_number', 'N/A')
                                                
                                                job_display, job_emoji = format_status(job_status)
                                                
                                                # 计算Job时长
                                                job_started = job.get('started_at')
                                                job_stopped = job.get('stopped_at')
                                                job_duration = format_duration(job_started, job_stopped) if job_started else 'N/A'
                                                
                                                # 根据类型显示不同图标
                                                type_icon = "🔧" if job_type == "build" else "✅" if job_type == "approval" else "📦"
                                                
                                                st.write(f"{type_icon} {job_emoji} **{job_name}** (#{job_number}) - {job_display} - ⏱️ {job_duration}")
                                        else:
                                            st.info("暂无 Jobs 信息")
                                    else:
                                        st.warning("无法获取 Jobs 信息")
                                except Exception as e:
                                    st.error(f"获取 Jobs 信息失败: {str(e)}")
                    else:
                        st.info("暂无 Workflows 信息")
                else:
                    st.error("❌ 无法获取 Pipeline 状态")
        
        if monitor_btn and pipeline_id_input:
            st.info("📊 开始实时监控...")
            
            # 创建状态显示区域
            status_placeholder = st.empty()
            progress_placeholder = st.empty()
            
            # 监控参数
            check_interval = 5
            max_checks = 360  # 最多检查30分钟
            
            # 监控循环
            start_time = time.time()
            check_count = 0
            previous_status = None
            
            final_statuses = ['success', 'failing', 'failed', 'error', 'canceled']
            
            while check_count < max_checks:
                check_count += 1
                elapsed_time = int(time.time() - start_time)
                
                # 获取状态
                pipeline_data = get_pipeline_status(pipeline_id_input, silent=True, api_token=CIRCLECI_API_TOKEN)
                
                if pipeline_data:
                    workflows = get_pipeline_workflows(pipeline_id_input, silent=True, api_token=CIRCLECI_API_TOKEN)
                    
                    # 获取实际状态
                    if workflows and len(workflows) > 0:
                        statuses = [w.get('status', 'unknown') for w in workflows]
                        if 'running' in statuses:
                            current_status = 'running'
                        elif 'on_hold' in statuses:
                            current_status = 'on_hold'
                        else:
                            current_status = statuses[-1]
                    else:
                        current_status = pipeline_data.get('state', 'unknown')
                    
                    # 检查是否有 "Do you want to deploy" 的 approval job 成功完成
                    deploy_approval_completed = False
                    if workflows:
                        for workflow in workflows:
                            workflow_id = workflow.get('id')
                            if workflow_id:
                                jobs_data = get_workflow_jobs(workflow_id)
                                if jobs_data and 'jobs' in jobs_data:
                                    for job in jobs_data['jobs']:
                                        job_name = job.get('name', '')
                                        job_status = job.get('status', '')
                                        # 检查是否是部署审批 job 且已成功
                                        if 'Do you want to deploy' in job_name and job_status == 'success':
                                            deploy_approval_completed = True
                                            break
                            if deploy_approval_completed:
                                break
                    
                    # 显示状态
                    display_text, emoji = format_status(current_status)
                    
                    status_msg = f"{emoji} **当前状态:** {display_text}\n\n"
                    status_msg += f"**运行时间:** {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒)\n\n"
                    status_msg += f"**检查次数:** {check_count}"
                    
                    if deploy_approval_completed:
                        status_msg += "\n\n🎯 **部署审批已完成**"
                    
                    status_placeholder.info(status_msg)
                    
                    # 显示进度条
                    if current_status == 'running':
                        progress_placeholder.progress(min(check_count / max_checks, 1.0))
                    
                    # 检查是否完成：优先检查部署审批是否完成
                    if deploy_approval_completed:
                        status_placeholder.success(f"✅ 部署审批已完成！Pipeline 可以继续部署到 Preprod")
                        st.info(f"总耗时: {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒)")
                        break
                    elif current_status in final_statuses:
                        # 如果 pipeline 已结束但没有找到部署审批完成，说明可能失败了
                        if current_status == 'success':
                            status_placeholder.success(f"✅ Pipeline 完成: {display_text}")
                        else:
                            status_placeholder.error(f"❌ Pipeline 完成但未找到部署审批: {display_text}")
                        
                        st.info(f"总耗时: {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒)")
                        break
                    
                    previous_status = current_status
                else:
                    status_placeholder.warning(f"⚠️ 无法获取状态，继续重试... (第{check_count}次)")
                
                # 等待下一次检查
                time.sleep(check_interval)
            
            if check_count >= max_checks:
                st.warning("⏱️ 达到最大监控时长")
    
    else:
        # 使用Pipeline Number监控
        col_input1, col_input2 = st.columns(2)
        with col_input1:
            pipeline_number = st.number_input(
                "Pipeline Number",
                min_value=1,
                value=1,
                help="输入要监控的 Pipeline Number"
            )
        with col_input2:
            monitor_project = st.text_input(
                "项目名称",
                value=DEFAULT_PROJECT,
                help="项目名称（不是完整路径）"
            )
        
        if st.button("📊 开始监控 (通过Number)", use_container_width=True, type="primary"):
            # 构建完整的 project_slug
            full_slug = f"{VCS_TYPE}/{ORGANIZATION}/{monitor_project}"
            
            with st.spinner(f"正在查找 Pipeline #{pipeline_number}..."):
                # 导入函数
                from circleCi.monitoring import get_pipeline_id_by_number
                
                # 查找Pipeline ID
                pipeline_id = get_pipeline_id_by_number(full_slug, pipeline_number, api_token=CIRCLECI_API_TOKEN)
                
                if pipeline_id:
                    st.success(f"✅ 找到 Pipeline #{pipeline_number}")
                    st.info(f"**Pipeline ID:** {pipeline_id}")
                    
                    # 保存到session state
                    st.session_state.current_pipeline_id = pipeline_id
                    
                    # 开始监控
                    st.info("📊 开始实时监控...")
                    
                    # 创建状态显示区域
                    status_placeholder = st.empty()
                    progress_placeholder = st.empty()
                    
                    # 监控参数
                    check_interval = 5
                    max_checks = 360
                    
                    start_time = time.time()
                    check_count = 0
                    previous_status = None
                    final_statuses = ['success', 'failing', 'failed', 'error', 'canceled']
                    
                    while check_count < max_checks:
                        check_count += 1
                        elapsed_time = int(time.time() - start_time)
                        
                        # 获取状态
                        pipeline_data = get_pipeline_status(pipeline_id, silent=True, api_token=CIRCLECI_API_TOKEN)
                        
                        if pipeline_data:
                            workflows = get_pipeline_workflows(pipeline_id, silent=True, api_token=CIRCLECI_API_TOKEN)
                            
                            # 获取实际状态
                            if workflows and len(workflows) > 0:
                                statuses = [w.get('status', 'unknown') for w in workflows]
                                if 'running' in statuses:
                                    current_status = 'running'
                                elif 'on_hold' in statuses:
                                    current_status = 'on_hold'
                                else:
                                    current_status = statuses[-1]
                            else:
                                current_status = pipeline_data.get('state', 'unknown')
                            
                            # 显示状态
                            display_text, emoji = format_status(current_status)
                            
                            status_placeholder.info(
                                f"{emoji} **当前状态:** {display_text}\n\n"
                                f"**Pipeline Number:** #{pipeline_number}\n\n"
                                f"**运行时间:** {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒)\n\n"
                                f"**检查次数:** {check_count}"
                            )
                            
                            # 显示进度条
                            if current_status == 'running':
                                progress_placeholder.progress(min(check_count / max_checks, 1.0))
                            
                            # 检查是否完成
                            if current_status in final_statuses:
                                if current_status in ['success', 'failing']:
                                    status_placeholder.success(f"✅ Pipeline #{pipeline_number} 完成: {display_text}")
                                else:
                                    status_placeholder.error(f"❌ Pipeline #{pipeline_number} 完成: {display_text}")
                                
                                st.info(f"总耗时: {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒)")
                                break
                            
                            previous_status = current_status
                        else:
                            status_placeholder.warning(f"⚠️ 无法获取状态，继续重试... (第{check_count}次)")
                        
                        # 等待下一次检查
                        time.sleep(check_interval)
                    
                    if check_count >= max_checks:
                        st.warning("⏱️ 达到最大监控时长")
                        
                else:
                    st.error(f"❌ 未找到 Pipeline #{pipeline_number}")
                    st.info(f"项目: {full_slug}")
                    st.warning("可能的原因：\n- Pipeline Number 不存在\n- Pipeline 不在最近的30个记录中\n- 项目名称或组织名称不正确")

# Tab 4: 审批管理
with tab4:
    st.header("✅ 审批管理")
    
    st.info("💡 此功能用于审批 CircleCI 中处于等待状态（on_hold）的 approval jobs")
    
    # 显示当前 Pipeline ID 来源提示
    if st.session_state.current_pipeline_id:
        st.success(f"✅ 已自动填充 Pipeline ID（来自触发/监控/列表）")
        st.code(st.session_state.current_pipeline_id, language=None)
    
    # 输入 Pipeline ID - 移除固定 key，让它根据 value 自动更新
    approval_pipeline_id = st.text_input(
        "Pipeline ID",
        value=st.session_state.current_pipeline_id if st.session_state.current_pipeline_id else "",
        help="输入要查找 approval jobs 的 Pipeline ID（已自动填充最近操作的 Pipeline ID）",
        placeholder="输入或从其他标签页自动填充 Pipeline ID"
    )
    
    col_search, col_clear = st.columns([3, 1])
    
    with col_search:
        search_btn = st.button("🔍 查找待审批的 Jobs", type="primary", use_container_width=True)
    
    with col_clear:
        if st.session_state.approval_workflows:
            if st.button("🗑️ 清空", use_container_width=True, key="clear_approval_results"):
                st.session_state.approval_workflows = None
                st.session_state.approval_search_pipeline_id = None
                st.rerun()
    
    if search_btn:
        if not approval_pipeline_id:
            st.warning("⚠️ 请输入 Pipeline ID")
        else:
            with st.spinner("正在查找待审批的 Jobs..."):
                # 获取 workflows
                workflows = get_pipeline_workflows(approval_pipeline_id, api_token=CIRCLECI_API_TOKEN)
                
                if workflows:
                    # 保存到 session_state
                    st.session_state.approval_workflows = workflows
                    st.session_state.approval_search_pipeline_id = approval_pipeline_id
                    st.success(f"✅ 找到 {len(workflows)} 个 Workflows")
                else:
                    st.session_state.approval_workflows = None
                    st.error("❌ 无法获取 Pipeline 的 Workflows")
                    st.info(f"Pipeline ID: {approval_pipeline_id}")
    
    # 显示查询结果（从 session_state 读取）
    if st.session_state.approval_workflows:
        workflows = st.session_state.approval_workflows
        search_pipeline_id = st.session_state.approval_search_pipeline_id
        
        st.info(f"📊 显示 {len(workflows)} 个 Workflows（Pipeline ID: {search_pipeline_id[:16]}...）")
        
        all_approval_jobs = []
        
        # 遍历每个 workflow 查找 approval jobs
        for workflow in workflows:
            workflow_id = workflow.get('id')
            workflow_name = workflow.get('name')
            workflow_status = workflow.get('status')
            
            st.subheader(f"🔄 Workflow: {workflow_name}")
            st.write(f"**状态:** {workflow_status}")
            st.write(f"**ID:** `{workflow_id}`")
            
            # 获取该 workflow 的 jobs
            jobs_data = get_workflow_jobs(workflow_id)
            
            if jobs_data:
                approval_jobs = jobs_data.get('approval_jobs', [])
                all_jobs = jobs_data.get('jobs', [])
                
                st.write(f"**总 Jobs 数:** {len(all_jobs)}")
                st.write(f"**待审批 Jobs 数:** {len(approval_jobs)}")
                
                if approval_jobs:
                    st.success(f"🎯 找到 {len(approval_jobs)} 个待审批的 Jobs")
                    
                    for job in approval_jobs:
                        # 判断是否是 Preprod 环境：检查 workflow 名称或 job 名称中是否包含 preprod（不区分大小写）
                        is_preprod = (
                            'preprod' in workflow_name.lower() or 
                            'preprod' in job.get('name', '').lower()
                        )
                        
                        # 计算 Duration 用于标题显示
                        started_at = job.get('started_at')
                        stopped_at = job.get('stopped_at')
                        duration = format_duration(started_at, stopped_at)
                        
                        # 只展开 Preprod 环境的 Jobs
                        with st.expander(
                            f"✋ {job.get('name')} - {job.get('status')} - ⏱️ {duration}", 
                            expanded=is_preprod
                        ):
                            col_j1, col_j2 = st.columns([3, 1])
                            
                            with col_j1:
                                st.write(f"**Job ID:** `{job.get('id')}`")
                                st.write(f"**Job Name:** {job.get('name')}")
                                st.write(f"**Job Type:** {job.get('type')}")
                                st.write(f"**状态:** {job.get('status')}")
                                
                                # 计算并显示 Duration
                                started_at = job.get('started_at')
                                stopped_at = job.get('stopped_at')
                                duration = format_duration(started_at, stopped_at)
                                st.write(f"**Duration:** {duration}")
                                
                                st.write(f"**Approval Request ID:** `{job.get('approval_request_id')}`")
                            
                            with col_j2:
                                # 使用唯一的 key，结合 workflow_id 和 job id
                                approve_key = f"approve_{workflow_id}_{job.get('id')}"
                                if st.button(
                                    "✅ 审批",
                                    key=approve_key,
                                    type="primary",
                                    use_container_width=True
                                ):
                                    with st.spinner("正在审批..."):
                                        result = approve_job(
                                            workflow_id,
                                            job.get('approval_request_id')
                                        )
                                        
                                        if result.get('success'):
                                            st.success("✅ 审批成功！")
                                            st.info("💡 请稍等几秒钟后重新查找，查看审批后的状态")
                                            st.balloons()
                                            # 清空缓存，让用户重新查询看到最新状态
                                            time.sleep(2)
                                            st.session_state.approval_workflows = None
                                            st.rerun()
                                        else:
                                            st.error(f"❌ 审批失败: {result.get('error')}")
                    
                    all_approval_jobs.extend(approval_jobs)
                else:
                    st.info("ℹ️ 该 Workflow 没有待审批的 Jobs")
            else:
                st.warning(f"⚠️ 无法获取 Workflow {workflow_name} 的 Jobs")
            
            st.markdown("---")
        
        if not all_approval_jobs:
            st.info("ℹ️ 该 Pipeline 没有待审批的 Jobs")
    
    st.markdown("---")
    st.markdown("""
    ### 📖 审批说明
    
    **什么是 Approval Job？**
    - Approval Job 是 CircleCI 中需要人工确认才能继续执行的步骤
    - 通常用于部署到生产环境等关键操作前的确认
    
    **如何使用审批功能？**
    1. 输入 Pipeline ID（可以从触发历史或监控页面获取）
    2. 点击"查找待审批的 Jobs"按钮
    3. 查看所有处于等待状态（on_hold）的 approval jobs
    4. 点击"✅ 审批"按钮完成审批
    5. 审批成功后会自动刷新，可重新查找查看最新状态
    
    **注意事项:**
    - 只有状态为 `on_hold` 的 approval 类型 job 才会显示
    - 审批后需要等待几秒钟，Pipeline 才会继续执行
    - 审批成功后，建议重新查找以确认状态变化
    - 请确保您有权限审批该 Pipeline
    """)

# 底部信息
st.markdown("---")
st.markdown("""
### 💡 功能说明

#### 🎯 触发 Pipeline
1. 输入项目名称（例如：`back-office-cloud`）
2. 输入分支名称（例如：`master`, `develop`, `SP-12345`）
3. 系统会自动拼接完整路径：`github/asiainspection/项目名`
4. 点击"触发 Pipeline"按钮
5. 等待触发结果

#### 📋 Pipeline 列表
1. 输入项目名称
2. 可选：输入分支名称（留空查询所有分支）
3. 点击"查询 Pipelines"查看最近的 Pipeline 列表
4. 可以查看每个 Pipeline 的详细信息
5. 点击"查看详情"可以将 Pipeline ID 保存到监控页面

#### 📊 监控 Pipeline
**通过 Pipeline ID 监控：**
- 输入 Pipeline ID（可以从触发结果或列表中获取）
- 点击"查看状态"查看当前状态
- 点击"开始监控"进行实时监控

**通过 Pipeline Number 监控：**
- 选择"Pipeline Number"监控方式
- 输入 Pipeline Number（例如：14689）
- 输入项目名称
- 点击"开始监控 (通过Number)"
- 系统会自动查找对应的 Pipeline ID 并开始监控

#### ✅ 审批管理
1. 输入 Pipeline ID
2. 点击"查找待审批的 Jobs"
3. 查看所有需要审批的 Jobs
4. 点击"✅ 审批"按钮完成审批
5. 审批后 Pipeline 会自动继续执行

#### 💡 简化输入说明
- ✅ **只需输入项目名**: `back-office-cloud`（不是完整路径）
- ✅ **自动拼接**: 系统自动组合为 `github/asiainspection/back-office-cloud`
- ✅ **配置预设**: VCS 类型和组织名已在配置中预设

#### ⚙️ 注意事项
- 确保在 `users_config.json` 中配置了正确的 API Token
- 监控会自动刷新，最长监控30分钟
- 可以在侧边栏查看最近5次触发的历史记录
- 审批功能需要相应的权限
""")
