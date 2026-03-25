"""
Services Images Extractor - Streamlit 页面
从 qcore-apps-descriptors GitHub 仓库读取 kustomization.yml 获取镜像信息
"""

import streamlit as st
import pandas as pd
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加 modules 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.github_kustomize_client import GitHubKustomizeClient
from modules.user_config_loader import UserConfigLoader

# 页面配置
st.set_page_config(
    page_title="Services Images Extractor",
    page_icon="🐳",
    layout="wide"
)

# 配置文件路径
SERVICES_CONFIG_FILE = "config/argocd_config.json"
CIRCLECI_SERVICES_FILE = "config/circleci-services.txt"

DEFAULT_CONFIG = {
    'environment': 'preprod',
    'services': []
}


# 加载配置
def load_config():
    """加载服务列表配置文件"""
    try:
        if os.path.exists(SERVICES_CONFIG_FILE):
            with open(SERVICES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_CONFIG[key]
                return config
    except Exception as e:
        st.error(f"加载配置失败: {e}")
    return DEFAULT_CONFIG.copy()


# 保存配置
def save_config(config):
    """保存服务列表配置文件"""
    try:
        os.makedirs(os.path.dirname(SERVICES_CONFIG_FILE), exist_ok=True)
        
        with open(SERVICES_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存配置失败: {e}")
        return False


# 对比功能函数
def compare_results(current_results, previous_results):
    """对比当前结果与上次结果"""
    if not previous_results or 'success' not in previous_results:
        return None
    
    comparison = {
        "added": {},      # 新增的服务
        "updated": {},    # 更新的服务（镜像标签变化）
        "unchanged": {},  # 未变化的服务
        "removed": {}     # 移除的服务
    }
    
    current_services = current_results.get('success', {})
    previous_services = previous_results.get('success', {})
    
    # 对比逻辑
    all_services = set(current_services.keys()) | set(previous_services.keys())
    
    for service in all_services:
        current_version = current_services.get(service)
        previous_version = previous_services.get(service)
        
        if current_version and previous_version:
            if current_version != previous_version:
                comparison["updated"][service] = {
                    "previous": previous_version,
                    "current": current_version
                }
            else:
                comparison["unchanged"][service] = current_version
        elif current_version and not previous_version:
            comparison["added"][service] = current_version
        elif not current_version and previous_version:
            comparison["removed"][service] = previous_version
    
    return comparison


def highlight_comparison(row, comparison):
    """为 DataFrame 行添加高亮样式"""
    service_name = row['service']
    
    if comparison:
        if service_name in comparison.get('added', {}):
            return ['background-color: #d4edda; color: #155724'] * len(row)  # 绿色 - 新增
        elif service_name in comparison.get('updated', {}):
            return ['background-color: #fff3cd; color: #856404'] * len(row)  # 黄色 - 更新
        elif service_name in comparison.get('removed', {}):
            return ['background-color: #f8d7da; color: #721c24'] * len(row)  # 红色 - 移除
    
    return [''] * len(row)  # 无变化


# Token 验证函数
def validate_token_and_save(environment, token):
    """
    验证token并保存结果到session_state
    
    Args:
        environment: 环境名称
        token: GitHub Personal Access Token
        
    Returns:
        (is_valid, message): 验证结果和消息
    """
    if not token:
        st.session_state.token_validation_result = None
        st.session_state.token_last_checked = None
        return False, "Token为空"
    
    try:
        client = GitHubKustomizeClient(environment, token)
        is_valid, message = client.validate_token()
        
        # 保存验证结果
        st.session_state.token_validation_result = {
            'is_valid': is_valid,
            'message': message
        }
        st.session_state.token_last_checked = datetime.now()
        
        return is_valid, message
    except Exception as e:
        error_msg = f"Token验证失败: {str(e)}"
        st.session_state.token_validation_result = {
            'is_valid': False,
            'message': error_msg
        }
        st.session_state.token_last_checked = datetime.now()
        return False, error_msg


# 初始化 session state（统一入口）
if 'argocd_config' not in st.session_state:
    st.session_state.argocd_config = load_config()
if 'user_config_loader' not in st.session_state:
    st.session_state.user_config_loader = UserConfigLoader()
if 'current_user' not in st.session_state:
    st.session_state.current_user = st.session_state.user_config_loader.get_default_user()
if 'query_results' not in st.session_state:
    st.session_state.query_results = None
if 'previous_results' not in st.session_state:
    st.session_state.previous_results = None
if 'last_query_time' not in st.session_state:
    st.session_state.last_query_time = None
if 'comparison_data' not in st.session_state:
    st.session_state.comparison_data = None
if 'token_validation_result' not in st.session_state:
    st.session_state.token_validation_result = None
if 'token_last_checked' not in st.session_state:
    st.session_state.token_last_checked = None
if 'user_entered_token' not in st.session_state:
    st.session_state.user_entered_token = False


# 主标题
st.title("🐳 Services Images Extractor")
st.markdown("从 **qcore-apps-descriptors** GitHub 仓库提取和追踪容器镜像版本")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置设置")
    
    # 用户选择
    st.subheader("👤 用户身份")
    available_users = st.session_state.user_config_loader.get_users_list()
    
    selected_user = st.selectbox(
        "选择使用者",
        available_users,
        index=available_users.index(st.session_state.current_user) if st.session_state.current_user in available_users else 0,
        key="user_select"
    )
    
    # 如果用户切换，更新 session state 并清空验证结果
    if selected_user != st.session_state.current_user:
        st.session_state.current_user = selected_user
        st.session_state.token_validation_result = None
        st.session_state.token_last_checked = None
        st.session_state.user_entered_token = False
    
    # 获取用户配置
    user_config = st.session_state.user_config_loader.get_user_config(selected_user)
    if user_config:
        user_info = user_config.get('display_name', selected_user)
        user_email = user_config.get('email', '')
        st.info(f"👤 当前用户: {user_info}\n📧 {user_email}")
    
    st.markdown("---")
    
    # 环境选择
    st.subheader("🌍 环境配置")
    def on_env_change():
        st.session_state.argocd_config['environment'] = st.session_state.environment_select
        # 切换环境后清空查询结果，避免旧环境数据残留
        st.session_state.query_results = None
        st.session_state.previous_results = None
        st.session_state.comparison_data = None

    environment = st.selectbox(
        "选择环境",
        GitHubKustomizeClient.list_environments(),
        index=GitHubKustomizeClient.list_environments().index(st.session_state.argocd_config.get('environment', 'preprod')),
        key="environment_select",
        on_change=on_env_change
    )
    
    # 显示环境信息
    env_config = GitHubKustomizeClient.get_environment_config(environment)
    if env_config:
        st.info(f"🌐 环境: {env_config['display_name']} - {env_config['description']}")
    
    # Token 输入
    st.subheader("🔐 GitHub 认证设置")
    
    # 从用户配置读取 GitHub Token
    github_token_from_config = ''
    if user_config and 'github' in user_config:
        github_token_from_config = user_config['github'].get('token', '')
    
    # 从 session_state 读取 stored token（跨请求持久化）
    stored_token = st.session_state.get('github_token', '')
    stored_env = st.session_state.get('github_token_env', '')
    stored_user = st.session_state.get('github_token_user', '')
    
    # 获取默认 token 值（优先级：用户配置 > cookies）
    default_token = ''
    if not st.session_state.get('user_entered_token', False):
        if github_token_from_config:
            default_token = github_token_from_config
            st.success(f"✅ 已从用户配置自动加载 {selected_user} 的 GitHub Token")
        elif stored_token and stored_user == selected_user:
            default_token = stored_token
            if stored_env == environment:
                st.success("✅ 已从浏览器缓存自动加载 Token")
    
    # Token 输入框
    token = st.text_input(
        "GitHub Personal Access Token",
        type="password",
        value=default_token,
        help="输入您的 GitHub Personal Access Token（可选，用于提高速率限制）",
        key="token_input"
    )
    
    # 标记用户是否手动输入了 token
    if token and token != default_token:
        st.session_state['user_entered_token'] = True
    
    # 保存到session_state以便主区域访问
    st.session_state.current_token = token if token else None
    
    # 如果用户输入了新token，自动保存到cookies
    if st.session_state.get('user_entered_token', False) and token:
        st.session_state.github_token = token
        st.session_state.github_token_env = environment
        st.session_state.github_token_user = selected_user
    
    # Token 验证（使用session_state避免重复验证）
    if token:
        # 检查是否需要重新验证（token变化或首次验证）
        current_token_key = f"{environment}_{token}"
        if (st.session_state.token_validation_result is None or 
            st.session_state.get('last_validated_token_key') != current_token_key):
            # 执行验证
            is_valid, message = validate_token_and_save(environment, token)
            st.session_state.last_validated_token_key = current_token_key
        else:
            # 使用缓存的验证结果
            result = st.session_state.token_validation_result
            is_valid = result['is_valid']
            message = result['message']
        
        # 显示验证结果
        if is_valid:
            st.success(f"✅ {message}")
        else:
            st.error(f"❌ {message}")
            st.info("💡 如需获取新 Token，请访问 GitHub Settings > Developer settings > Personal access tokens")
    else:
        st.warning("⚠️ 无 GitHub Token（公共仓库模式，速率限制: 60请求/小时）")
        st.info("💡 提供 Token 可提高速率限制至 5000请求/小时")
        # 清空验证结果
        st.session_state.token_validation_result = None
        st.session_state.token_last_checked = None
    
    # Token 获取帮助
    with st.expander("📖 如何获取 GitHub Token？"):
        st.markdown("""
        ### 获取 GitHub Personal Access Token 步骤：
        
        1. 访问 GitHub 网站并登录
        2. 点击右上角头像 → **Settings**
        3. 左侧菜单 → **Developer settings**
        4. 选择 **Personal access tokens** → **Tokens (classic)**
        5. 点击 **Generate new token** → **Generate new token (classic)**
        6. 设置 Token 名称和过期时间
        7. 勾选权限：
           - `repo` (完整访问私有仓库)
           - 或仅 `public_repo` (只访问公共仓库)
        8. 点击 **Generate token**
        9. 复制生成的 Token（只显示一次！）
        10. 粘贴到左侧输入框
        
        **注意事项：**
        - Token 生成后只显示一次，请妥善保存
        - 本工具不会将 Token 保存到文件
        - Token 仅存储在浏览器缓存中
        - 建议设置较短的过期时间以提高安全性
        """)
    
    st.markdown("---")
    
    # 服务列表管理
    st.subheader("📋 服务列表")
    
    # 从 circleci-services.txt 加载服务列表
    project_root = Path(__file__).parent.parent
    services_file = project_root / CIRCLECI_SERVICES_FILE
    available_services = []
    
    try:
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                available_services = [line.strip() for line in f if line.strip()]
            st.caption(f"📁 已加载 {len(available_services)} 个可用服务")
        else:
            st.warning(f"⚠️ 服务列表文件不存在: {CIRCLECI_SERVICES_FILE}")
            # 使用默认服务列表作为备用
            available_services = [
                "aims-service-cloud",
                "aims-web-cloud",
                "aca-new",
                "program-service-cloud",
                "program-web-cloud",
                "lt-external-service-cloud",
                "psi-web-cloud",
                "food-certification-service-cloud",
                "food-certification-app",
                "customer-service-cloud"
            ]
    except Exception as e:
        st.error(f"❌ 加载服务列表失败: {str(e)}")
        available_services = []
    
    # 从配置中加载已保存的服务列表
    saved_services = st.session_state.argocd_config.get('services', [])
    
    # 使用 multiselect（支持输入过滤）
    st.markdown("**选择服务：**")
    st.caption("💡 提示：可以直接输入关键字快速过滤服务列表")
    
    selected_services = st.multiselect(
        "选择要查询的服务（支持输入过滤）",
        options=available_services,
        default=[s for s in saved_services if s in available_services],
        help="从列表中选择服务，或直接输入关键字快速过滤",
        key="selected_services"
    )
    
    # 自定义服务输入（用于添加不在列表中的服务）
    st.markdown("---")
    st.markdown("**添加自定义服务：**")
    st.caption("如果需要的服务不在上面列表中，可以在这里手动添加")
    
    # 如果session_state中没有自定义服务，使用配置中不在列表中的服务
    if 'custom_services_text' not in st.session_state:
        custom_in_config = [s for s in saved_services if s not in available_services]
        if custom_in_config:
            st.session_state.custom_services_text = '\n'.join(custom_in_config)
        else:
            st.session_state.custom_services_text = ''
    
    custom_services_input = st.text_area(
        "输入服务名称（每行一个）",
        height=100,
        help="输入不在列表中的服务名称，应与 qcore-apps-descriptors 仓库中的目录名一致",
        key="custom_services_text"
    )
    
    # 合并服务列表
    # 合并选择的服务和自定义服务
    services_list = list(selected_services)
    if custom_services_input:
        custom_list = [s.strip() for s in custom_services_input.split('\n') if s.strip()]
        services_list.extend(custom_list)
    
    # 去重
    services_list = list(dict.fromkeys(services_list))
    
    # 保存到session_state以便主区域访问
    st.session_state.current_services_list = services_list
    
    st.info(f"📊 已选择 {len(services_list)} 个服务")
    
    # 服务名称验证提示
    if services_list:
        st.caption("💡 提示：查询时会自动检查服务名称是否存在于仓库中")
    
    st.markdown("---")
    
    # 配置管理
    st.subheader("💾 配置管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 保存", use_container_width=True):
            config = {
                'environment': environment,
                'services': services_list
            }
            if save_config(config):
                st.session_state.argocd_config = config
                # 确保token保存到session_state
                if token:
                    st.session_state.github_token = token
                    st.session_state.github_token_env = environment
                    st.session_state.github_token_user = selected_user
                st.success("✅ 配置已保存")
                st.rerun()
    
    with col2:
        if st.button("🔄 重置", use_container_width=True):
            st.session_state.argocd_config = DEFAULT_CONFIG.copy()
            save_config(DEFAULT_CONFIG)
            st.success("🔄 配置已重置")
            st.rerun()


# 主区域
# Token 状态显示
st.header("🔐 Token 状态")
# 从session_state获取当前token和环境
token = st.session_state.get('current_token', '')
# 获取当前环境（从侧边栏的selectbox）
current_environment = st.session_state.get('environment_select', st.session_state.argocd_config.get('environment', 'preprod'))

col1, col2 = st.columns([3, 1])

with col1:
    # 显示token验证结果
    if st.session_state.token_validation_result:
        result = st.session_state.token_validation_result
        if result['is_valid']:
            st.text(f"✅ {result['message']}")
        else:
            st.text(f"❌ {result['message']}")
    else:
        if token:
            st.text("⏳ 未验证")
        else:
            st.text("ℹ️ 公共仓库模式（无Token）")
    
    # 显示上次检查时间
    if st.session_state.token_last_checked:
        check_time = st.session_state.token_last_checked.strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"最后检查时间: {check_time}")

with col2:
    if st.button("🔄 刷新", use_container_width=True, key="refresh_token_btn"):
        # 重新验证token（如果有）
        if token:
            is_valid, message = validate_token_and_save(current_environment, token)
        st.rerun()

st.markdown("---")

# 查询按钮
# 获取服务列表
services_list = st.session_state.get('current_services_list', [])

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    # 清空历史结果按钮
    if st.button("🗑️ 清空历史结果", use_container_width=True, help="清空 results 目录文件和浏览器对比数据"):
        results_dir = "results"
        file_count = 0
        
        # 1. 清空 results 目录中的文件
        if os.path.exists(results_dir):
            try:
                import glob
                files = glob.glob(os.path.join(results_dir, "*"))
                file_count = len(files)
                if files:
                    for file in files:
                        try:
                            os.remove(file)
                        except Exception as e:
                            st.error(f"删除文件 {os.path.basename(file)} 失败: {e}")
            except Exception as e:
                st.error(f"❌ 清空文件失败: {e}")
        
        # 2. 清空浏览器 session_state 中的对比数据
        st.session_state.query_results = None
        st.session_state.previous_results = None
        st.session_state.comparison_data = None
        st.session_state.last_query_time = None
        
        # 显示清空结果
        if file_count > 0:
            st.success(f"✅ 已清空 {file_count} 个历史文件 + 浏览器对比数据")
        else:
            st.success("✅ 已清空浏览器对比数据")
        st.info("💡 提示：所有历史数据已清空，可以开始全新的提取")
        st.rerun()

with col2:
    query_button = st.button(
        "🚀 开始提取镜像版本",
        type="primary",
        use_container_width=True,
        disabled=not services_list
    )

with col3:
    # 查看历史结果
    if os.path.exists("results"):
        files = [f for f in os.listdir("results") if f.endswith(('.csv', '.json'))]
        if files:
            st.caption(f"📁 历史文件: {len(files)} 个")
        else:
            st.caption("📁 历史文件: 0 个")

# 执行查询
if query_button:
    if not services_list:
        st.error("❌ 请至少选择一个服务")
    else:
        try:
            # 保存上次结果用于对比（在开始新查询前保存）
            if st.session_state.query_results:
                st.session_state.previous_results = st.session_state.query_results
            
            # 创建客户端（使用current_environment，从session_state获取）
            client = GitHubKustomizeClient(current_environment, token)
            
            # 显示查询进度
            st.subheader(f"🔍 查询 {current_environment.upper()} 环境")

            # 并发查询所有服务（复用 client 已有 query_multiple_services）
            results = {
                'success': {},
                'failed': {},
                'details': [],
                'warnings': []
            }
            with st.spinner("🚀 正在并发查询所有服务..."):
                batch_results = client.query_multiple_services(services_list)
            results['success'] = batch_results.get('success', {})
            results['failed'] = batch_results.get('failed', {})
            results['warnings'] = batch_results.get('warnings', [])

            # 重建 details 列表（供表格渲染用）
            for svc, tag in results['success'].items():
                results['details'].append({
                    'service': svc,
                    'version': tag,
                    'status': '✅ 成功',
                    'environment': current_environment.upper()
                })
            for svc, err in results['failed'].items():
                results['details'].append({
                    'service': svc,
                    'version': 'N/A',
                    'status': f'❌ {err[:50]}...' if len(err) > 50 else f'❌ {err}',
                    'environment': current_environment.upper()
                })
            
            # 执行对比（如果有上次结果）
            comparison = None
            if st.session_state.previous_results:
                comparison = compare_results(results, st.session_state.previous_results)
                st.session_state.comparison_data = comparison
            
            # 保存当前结果
            st.session_state.query_results = results
            st.session_state.last_query_time = datetime.now()
            
            # 显示警告（如果有服务名称不匹配）
            if results['warnings']:
                for warning in results['warnings']:
                    st.warning(warning)
                st.info(f"💡 提示：请确认服务名称与 GitHub 仓库 `{GitHubKustomizeClient.get_repo_url()}` 中的目录名一致")
            
            # 显示成功提示
            if comparison:
                total_changes = len(comparison['added']) + len(comparison['updated']) + len(comparison['removed'])
                if total_changes > 0:
                    st.success(f"✅ 提取完成！发现 {total_changes} 个变化")
                else:
                    st.success(f"✅ 提取完成！无变化")
            else:
                st.success(f"✅ 提取完成！成功: {len(results['success'])}, 失败: {len(results['failed'])}")
            
        except Exception as e:
            st.error(f"❌ 提取失败: {str(e)}")


# 显示查询结果
if st.session_state.query_results:
    results = st.session_state.query_results
    
    st.markdown("---")
    st.subheader("📊 提取结果")
    
    # 统计信息
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 提取服务数", len(services_list))
    
    with col2:
        st.metric("✅ 成功", len(results['success']))
    
    with col3:
        st.metric("❌ 失败", len(results['failed']))
    
    with col4:
        success_rate = len(results['success']) / len(services_list) * 100 if services_list else 0
        st.metric("📈 成功率", f"{success_rate:.1f}%")
    
    # 结果表格
    if results['details']:
        st.markdown("### 📝 详细结果")
        
        # 如果有对比数据，显示对比分析
        comparison = st.session_state.comparison_data
        if comparison:
            total_changes = len(comparison['added']) + len(comparison['updated']) + len(comparison['removed'])
            
            if total_changes > 0:
                st.markdown("#### 🔍 部署对比分析")
                
                # 变化统计
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🆕 新增", len(comparison['added']), delta=len(comparison['added']) if len(comparison['added']) > 0 else None)
                with col2:
                    st.metric("🔄 更新", len(comparison['updated']), delta=len(comparison['updated']) if len(comparison['updated']) > 0 else None)
                with col3:
                    st.metric("✅ 不变", len(comparison['unchanged']))
                with col4:
                    st.metric("🗑️ 移除", len(comparison['removed']), delta=-len(comparison['removed']) if len(comparison['removed']) > 0 else None, delta_color="inverse")
                
                st.markdown("---")
                
                # 显示具体变化
                if comparison['updated']:
                    with st.expander(f"🔄 更新的服务 ({len(comparison['updated'])} 个)", expanded=True):
                        for service, versions in sorted(comparison['updated'].items()):
                            st.warning(f"""
                            **{service}**  
                            📜 之前: `{versions['previous']}`  
                            🆕 现在: `{versions['current']}`
                            """)
                
                if comparison['added']:
                    with st.expander(f"🆕 新增的服务 ({len(comparison['added'])} 个)", expanded=False):
                        for service, version in sorted(comparison['added'].items()):
                            st.success(f"**{service}**: `{version}`")
                
                if comparison['removed']:
                    with st.expander(f"🗑️ 移除的服务 ({len(comparison['removed'])} 个)", expanded=False):
                        for service, version in sorted(comparison['removed'].items()):
                            st.error(f"**{service}**: `{version}` (已移除)")
        
        # 显示数据表格（带高亮）
        st.markdown("#### 📋 完整服务列表")
        df = pd.DataFrame(results['details'])
        
        # 如果有对比数据，应用高亮样式
        if comparison:
            styled_df = df.style.apply(lambda row: highlight_comparison(row, comparison), axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # 添加图例说明
            st.markdown("""
            **图例说明:**  
            🟢 绿色 = 新增服务 | 🟡 黄色 = 版本更新 | 🔴 红色 = 已移除
            """)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info("💡 提示：再次提取后将显示与本次结果的对比")
        
        # 导出功能
        st.markdown("---")
        st.subheader("💾 导出数据")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV 导出（None 值替换为空字符串，避免 "None" 字符串）
            csv = df.fillna('').to_csv(index=False, encoding='utf-8-sig')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "📥 下载 CSV",
                csv,
                f"services_images_{current_environment}_{timestamp}.csv",
                "text/csv",
                use_container_width=True
            )

        with col2:
            # JSON 导出
            json_data = {
                "environment": current_environment.upper(),
                "query_time": st.session_state.last_query_time.strftime("%Y-%m-%d %H:%M:%S"),
                "results": results['success'],
                "failed": results['failed']
            }
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 下载 JSON",
                json_str,
                f"services_images_{current_environment}_{timestamp}.json",
                "application/json",
                use_container_width=True
            )
    
    # 失败详情
    if results['failed']:
        st.markdown("---")
        st.subheader("⚠️ 失败详情")
        
        with st.expander("查看失败的服务", expanded=True):
            for service, error in results['failed'].items():
                st.error(f"**{service}**: {error}")


# 使用说明
st.markdown("---")
with st.expander("📖 使用说明和最佳实践"):
    st.markdown(f"""
    ### 🎯 功能特性
    
    #### 数据来源
    - 本工具从 GitHub 仓库获取镜像信息
    - 仓库: [{GitHubKustomizeClient.REPO_OWNER}/{GitHubKustomizeClient.REPO_NAME}]({GitHubKustomizeClient.get_repo_url()})
    - 分支: {GitHubKustomizeClient.REPO_BRANCH}
    - 读取路径: `kustomize/overlays/<environment>/<service>/kustomization.yml`
    
    #### 多环境支持
    - **preprod**: 预生产环境
    - **staging**: 测试环境
    - **prod**: 生产环境
    
    #### 批量查询
    - 支持一次查询多个服务
    - 自动检查服务名称是否存在于仓库
    - 详细的错误信息提示
    
    #### 版本对比
    - 自动对比两次查询结果
    - 高亮显示新增、更新、移除的服务
    - 详细的变化统计
    
    #### 数据导出
    - CSV 格式：适合 Excel 分析
    - JSON 格式：适合程序处理
    
    #### 历史结果管理
    - 自动保存：每次提取结果自动保存到 `results` 目录
    - 清空功能：点击"清空历史结果"按钮清空 results 目录文件 + 浏览器对比数据
    - 文件计数：实时显示历史文件数量
    - 建议：定期清空历史结果，确保从零开始新的对比分析
    
    ### 🔐 安全说明
    
    - Token 完全隐藏，绝不显示明文
    - Token 不会保存到配置文件
    - Token 仅存储在浏览器缓存中
    - 无 Token 也可使用（公共仓库模式，但有速率限制）
    - 符合企业最高安全标准
    
    ### 📝 服务名称规范
    
    - 服务名称应与 GitHub 仓库中的目录名完全一致
    - 不含环境前后缀
    - 例如：`aca-new`、`aims-service-cloud`
    - 如果服务不存在，会收到警告提示
    
    ### ⚠️ 常见问题
    
    #### Q: 需要 GitHub Token 吗？
    A: 不是必需的。无 Token 时以公共仓库模式运行（速率限制 60请求/小时）。
       提供 Token 可提高速率限制至 5000请求/小时。
    
    #### Q: 如何获取 GitHub Token？
    A: 
    1. GitHub Settings → Developer settings → Personal access tokens
    2. Generate new token (classic)
    3. 勾选 `repo` 或 `public_repo` 权限
    4. 复制生成的 Token
    
    #### Q: 查询失败显示"文件不存在"？
    A: 检查：
    - 服务名称是否正确（区分大小写）
    - 该服务在当前环境是否已配置
    - 访问 [{GitHubKustomizeClient.get_repo_url()}]({GitHubKustomizeClient.get_repo_url()}) 确认
    
    #### Q: 如何对比不同环境？
    A: 分别查询不同环境，导出结果后使用 Excel 或其他工具对比。
    
    #### Q: 如何管理历史导出文件？
    A: 
    - 所有导出的文件保存在 `results` 目录
    - 点击"清空历史结果"按钮可一键清空：
      * results 目录中的所有文件
      * 浏览器内存中的对比数据（session_state）
    - 建议每次重要提取前先清空，确保从零开始
    - 右上角显示当前历史文件数量
    - 清空后再提取，不会显示对比结果（因为是首次提取）
    
    #### Q: GitHub API 速率限制怎么办？
    A: 
    - 提供 GitHub Personal Access Token
    - 或等待速率限制重置（每小时重置一次）
    """)

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>🐳 Services Images Extractor v3.0 | Powered by GitHub & Streamlit</p>
    <p>最后提取时间: {}</p>
    <p>数据来源: <a href="{}" target="_blank">{}/{}</a></p>
</div>
""".format(
    st.session_state.last_query_time.strftime("%Y-%m-%d %H:%M:%S") if st.session_state.last_query_time else "未提取",
    GitHubKustomizeClient.get_repo_url(),
    GitHubKustomizeClient.REPO_OWNER,
    GitHubKustomizeClient.REPO_NAME
), unsafe_allow_html=True)

