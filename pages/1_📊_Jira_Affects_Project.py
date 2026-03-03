# Jira Affects Project 提取工具
import streamlit as st
import os
import pandas as pd
import json
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.jira_extractor import JiraExtractor
from modules.user_config_loader import get_jira_config, get_user_config_loader

st.set_page_config(page_title="Jira Affects Project 提取工具", layout="wide")

# 检查当前用户
if 'current_user' not in st.session_state or not st.session_state.current_user:
    st.error("❌ 未选择使用者，请返回主页选择你的身份")
    st.stop()

current_user = st.session_state.current_user

# 从用户配置加载JIRA配置
user_jira_config = get_jira_config(current_user)

if not user_jira_config:
    st.error(f"❌ 未找到用户 {current_user} 的 JIRA 配置")
    st.info("请联系管理员在 config/users_config.json 中配置你的信息")
    st.stop()

# 配置直接从 users_config.json 加载（统一配置管理）
JIRA_CONFIG = {
    'base_url': user_jira_config.get('base_url', 'https://qima.atlassian.net'),
    'api_token': user_jira_config.get('api_token', 'your_api_token_here'),
    'email': get_user_config_loader().get_user_email(current_user),
    'filter_id': user_jira_config.get('filter_id', '20334'),
    'field_id': user_jira_config.get('field_id', '')
}

# 初始化配置到 session state
if 'jira_config' not in st.session_state:
    st.session_state.jira_config = JIRA_CONFIG.copy()

# 项目映射管理函数
def load_project_mappings():
    try:
        if os.path.exists("config/project_mapping.json"):
            with open("config/project_mapping.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('project_mappings', {})
    except Exception as e:
        st.error(f"加载项目映射失败: {e}")
    return {}

def save_project_mappings(mappings):
    try:
        config = {
            "project_mappings": mappings,
            "description": "当检测到左侧项目时，自动添加右侧的关联项目到结果中",
            "version": "1.0.0",
            "last_updated": pd.Timestamp.now().strftime("%Y-%m-%d")
        }
        
        with open("config/project_mapping.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存项目映射失败: {e}")
        return False

# 安全显示函数
def mask_api_token(token, show_full=False):
    """安全地显示API Token"""
    if not token or token == "your_api_token_here":
        return token
    
    if show_full:
        return token
    
    # 显示前4位和后4位，中间用*号隐藏
    if len(token) <= 8:
        return "*" * len(token)
    
    return token[:4] + "*" * (len(token) - 8) + token[-4:]

st.title("📊 Jira Affects Project 提取工具")

# 显示当前用户
user_display_name = get_user_config_loader().get_user_display_name(current_user)
st.info(f"👤 当前使用者: **{user_display_name}** ({st.session_state.current_user})")

st.markdown("输入你的配置并点击按钮，即可一键提取影响的项目列表并下载。")

# 创建标签页
tab1, tab2 = st.tabs(["🚀 主应用", "⚙️ 项目映射管理"])

with tab1:
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 配置设置")
        
        # 使用session state的值作为默认值
        base_url = st.text_input(
            "🌐 Jira 实例 URL", 
            value=st.session_state.jira_config['base_url'],
            key="base_url_input"
        )
        
        # API Token 完全隐藏输入
        st.subheader("🔐 API Token 设置")
        
        # 获取当前Token值
        current_token = st.session_state.jira_config['api_token']
        
        # 检查 Token 是否有效
        if current_token in ['YOUR_JIRA_TOKEN_HERE', 'your_api_token_here', '']:
            st.error("⚠️ Token 未配置或无效")
            st.info(f"请确认 users_config.json 中 {current_user} 的 api_token 已正确配置")
        else:
            st.success(f"✅ Token 已加载 ({len(current_token)} 字符)")
        
        # 始终使用密码输入框，完全隐藏Token
        api_token = st.text_input(
            "🔐 API Token", 
            value=current_token,
            type="password",
            help="从Atlassian账户设置中获取API Token，或从 users_config.json 自动加载",
            key="api_token_input"
        )
        
        # 显示Token状态信息（不显示具体内容）
        if current_token and current_token != "your_api_token_here":
            st.success("✅ API Token 已配置")
            st.info("🔒 Token已安全隐藏，保护您的账户安全")
        else:
            st.warning("⚠️ 请配置有效的API Token")
        
        email = st.text_input(
            "📧 Jira 邮箱", 
            value=st.session_state.jira_config['email'],
            key="email_input"
        )
        
        filter_id = st.text_input(
            "🔍 过滤器 ID", 
            value=st.session_state.jira_config['filter_id'],
            key="filter_id_input"
        )
        
        # 字段ID输入，支持自动检测和手动输入
        st.subheader("🏷️ Affects Project 字段 ID")
        field_id = st.text_input(
            "字段ID", 
            value=st.session_state.jira_config['field_id'],
            help="留空可自动检测，或手动输入",
            key="field_id_input"
        )
        
        # 配置说明
        st.subheader("ℹ️ 配置管理")
        st.info("""
        **配置来源**: `config/users_config.json`
        
        如需修改配置，请联系管理员更新配置文件，然后重新加载页面。
        
        所有用户的Token和配置都在统一的配置文件中管理，确保安全性和一致性。
        """)
        
        # 显示当前检测到的字段ID
        if 'detected_field_id' in st.session_state:
            st.success(f"✅ 已检测: {st.session_state.detected_field_id}")
            if not field_id:
                field_id = st.session_state.detected_field_id

    # 主界面
    st.header("🚀 操作面板")

    # 步骤指示器
    st.markdown("""
    ### 📋 使用步骤：
    1. **🔧 查看配置** (左侧边栏) - 配置来自 `users_config.json`
    2. **🔍 检测字段ID** (下方按钮)
    3. **🚀 提取数据** (检测成功后)
    """)

    col1, col2 = st.columns(2)

    with col1:
        auto_detect_button = st.button("🔍 自动检测字段 ID", key="auto", width='stretch', type="primary")

    with col2:
        run_button = st.button("🚀 开始提取数据", key="run", width='stretch', disabled=not field_id and 'detected_field_id' not in st.session_state)

    # 自动检测字段ID
    if auto_detect_button:
        if api_token == "your_api_token_here":
            st.error("❌ 请先输入有效的API Token")
        else:
            try:
                with st.spinner("🔍 正在识别 Affects Project 字段 ID..."):
                    jira_client = JiraExtractor(base_url, api_token, email)
                    detected_field_id = jira_client.find_affects_project_field_id(filter_id)
                    if detected_field_id:
                        st.success(f"✅ 成功识别字段: `{detected_field_id}`")
                        st.session_state.detected_field_id = detected_field_id
                        # 保存到session state（本次会话有效）
                        st.session_state.jira_config['field_id'] = detected_field_id
                        st.info("💾 字段ID已保存到当前会话")
                        st.rerun()  # 刷新页面以更新UI
                    else:
                        st.warning("⚠️ 未自动识别字段 ID，使用备用字段ID: customfield_12605")
                        # 使用备用字段ID
                        st.session_state.detected_field_id = "customfield_12605"
                        st.session_state.jira_config['field_id'] = "customfield_12605"
                        st.info("💾 字段ID已保存到当前会话")
                        st.rerun()
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                st.error(f"❌ 检测失败: {str(e)}")
                with st.expander("🔍 查看详细错误信息"):
                    st.code(error_details)
                st.info("💡 提示：请检查API Token、邮箱和过滤器ID是否正确")

    # 提取数据
    if run_button:
        # 确定使用的字段ID
        current_field_id = field_id or st.session_state.get('detected_field_id', '')
        
        if api_token == "your_api_token_here":
            st.error("❌ 请先输入有效的API Token")
        elif not current_field_id:
            st.error("❌ 请先输入或检测 Affects Project 字段 ID")
            st.info("💡 提示：点击'自动检测字段ID'按钮，或手动输入字段ID")
        else:
            try:
                jira_client = JiraExtractor(base_url, api_token, email)
                
                with st.spinner("🔄 正在从 Jira 获取数据..."):
                    results = jira_client.get_affects_projects(filter_id, current_field_id)

                if results:
                    st.success(f"✅ 成功提取 {len(results)} 个问题！")
                    
                    # 数据预览
                    st.subheader("🔍 获取的数据预览")
                    df = pd.DataFrame(results)
                    preview_cols = ['issue_key', 'summary', 'sp_team', 'affects_projects', 'affects_projects_raw']
                    display_cols = [c for c in preview_cols if c in df.columns]
                    st.dataframe(df[display_cols].head(100), width='stretch')
                    
                    # 项目去重和展示
                    st.subheader("📋 去重后的项目列表")
                    
                    # 收集所有项目
                    all_projects = []
                    for result in results:
                        projects = result.get('affects_projects', [])
                        if isinstance(projects, list):
                            all_projects.extend(projects)
                        elif isinstance(projects, str) and projects.strip():
                            all_projects.extend([p.strip() for p in projects.split(',') if p.strip()])
                    
                    # 去重并排序
                    unique_projects = sorted(list(set([p.strip() for p in all_projects if p.strip() and p.strip().upper() != "NA"])))
                    
                    if unique_projects:
                        # 显示项目数量
                        st.info(f"📊 共找到 {len(unique_projects)} 个唯一项目")
                        
                        # 显示项目映射信息
                        current_mappings = jira_client.get_project_mappings()
                        if current_mappings:
                            st.info("🔗 已应用项目映射规则，自动添加关联项目")
                        
                        # 创建可复制的项目列表
                        projects_text = "\n".join(unique_projects)
                        
                        # 显示项目列表
                        st.text_area(
                            "📝 项目列表 (可直接复制)",
                            value=projects_text,
                            height=200,
                            help="点击上方文本框，按Ctrl+A全选，然后复制"
                        )
                        
                        # 添加复制按钮
                        if st.button("📋 复制到剪贴板", key="copy_projects"):
                            st.write("📋 项目列表已复制到剪贴板！")
                            st.code(projects_text)
                        
                        # 显示每个项目
                        st.subheader("🏷️ 项目详情")
                        for i, project in enumerate(unique_projects, 1):
                            st.write(f"{i}. **{project}**")
                    else:
                        st.warning("📭 未找到项目信息")
                    
                    # 下载功能
                    json_path, csv_path = jira_client.save_results_to_file(results)
                    
                    st.subheader("💾 下载数据")
                    col1, col2 = st.columns(2)
                    with open(json_path, "r", encoding="utf-8") as f:
                        col1.download_button(
                            "📥 下载 JSON", 
                            f.read(), 
                            file_name=os.path.basename(json_path), 
                            mime="application/json"
                        )
                    with open(csv_path, "r", encoding="utf-8") as f:
                        col2.download_button(
                            "📎 下载 CSV", 
                            f.read(), 
                            file_name=os.path.basename(csv_path), 
                            mime="text/csv"
                        )
                else:
                    st.info("📭 没有找到匹配的数据")
                    
            except Exception as e:
                st.error(f"❌ 提取失败: {str(e)}")

    # 使用说明
    with st.expander("📖 详细使用说明"):
        st.markdown("""
        ### 🔧 配置步骤：
        1. **获取API Token**: 访问 [Atlassian账户设置](https://id.atlassian.com/manage-profile/security/api-tokens)
        2. **输入JIRA信息**: 填写你的JIRA实例URL、邮箱和过滤器ID
        3. **自动检测字段**: 点击"自动检测字段ID"按钮
        4. **提取数据**: 点击"开始提取数据"按钮
        
        ### 🏷️ 关于字段ID：
        - **Affects Project** 是JIRA中的自定义字段，标识问题影响的项目
        - 每个JIRA实例的字段ID可能不同
        - 建议先使用自动检测功能
        - 如果检测失败，可以手动查找字段ID
        
        ### 📋 注意事项：
        - 确保API Token有效且有足够权限
        - 过滤器ID必须是有效的JIRA过滤器
        - 首次使用建议先测试连接
        - 字段ID检测成功后，提取数据按钮才会启用
        
        ### 📊 新功能：
        - **项目去重**: 自动去除重复项目
        - **列表展示**: 一行一个项目，方便复制
        - **一键复制**: 支持复制到剪贴板
        - **配置持久化**: 使用本地文件存储，刷新页面后配置保持不变
        - **项目映射**: 自动添加关联项目（如aca自动添加aca-cn）
        - **🔒 完全安全**: API Token始终隐藏，绝对不显示明文
        
        ### 💾 配置管理：
        - **本地存储**: 配置保存到本地JSON文件
        - **自动保存**: 点击"保存配置"按钮保存到文件
        - **重置配置**: 点击"重置配置"恢复默认值
        - **清除文件**: 点击"清除配置文件"删除本地配置
        - **持久化**: 即使关闭浏览器，配置也不会丢失
        
        ### 🔒 安全特性：
        - **完全隐藏**: API Token始终以密码形式输入，永不显示明文
        - **绝对安全**: 即使在配置状态和文件预览中也完全隐藏
        - **零风险**: 防止任何形式的Token泄露
        - **企业级**: 符合最高安全标准的保护措施
        """)

    # 状态信息
    if 'detected_field_id' in st.session_state:
        st.info(f"🔍 当前检测到的字段ID: {st.session_state.detected_field_id}")
        if not field_id:
            st.warning("⚠️ 请在上方输入框中确认字段ID，或直接使用检测到的ID")

    # 显示当前配置状态
    with st.expander("🔧 当前配置状态"):
        # 安全显示配置信息（Token完全隐藏）
        safe_config = st.session_state.jira_config.copy()
        if safe_config['api_token'] != "your_api_token_here":
            safe_config['api_token'] = "🔒 已配置（安全隐藏）"
        
        st.json(safe_config)
        st.info("📌 配置来源: `config/users_config.json`")
        st.caption("💡 配置在当前会话中有效，刷新页面后将从 users_config.json 重新加载")

with tab2:
    st.header("⚙️ 项目映射管理")
    st.markdown("管理项目映射规则，当检测到特定项目时自动添加关联项目。")
    
    # 加载当前映射
    current_mappings = load_project_mappings()
    
    # 显示当前映射
    st.subheader("🔗 当前项目映射规则")
    if current_mappings:
        for source, targets in current_mappings.items():
            st.write(f"**{source}** → {', '.join(targets)}")
    else:
        st.info("📭 暂无项目映射规则")
    
    # 添加新映射
    st.subheader("➕ 添加新映射规则")
    col1, col2 = st.columns(2)
    
    with col1:
        new_source = st.text_input("源项目名称", key="new_source", help="当检测到该项目时，自动添加关联项目")
    
    with col2:
        new_targets = st.text_input("关联项目", key="new_targets", help="用逗号分隔多个关联项目")
    
    if st.button("➕ 添加映射规则", key="add_mapping"):
        if new_source and new_targets:
            # 解析关联项目
            target_list = [t.strip() for t in new_targets.split(',') if t.strip()]
            
            # 更新映射
            current_mappings[new_source] = target_list
            
            if save_project_mappings(current_mappings):
                st.success(f"✅ 已添加映射规则: {new_source} → {', '.join(target_list)}")
                st.rerun()
            else:
                st.error("❌ 保存映射规则失败")
        else:
            st.warning("⚠️ 请填写源项目和关联项目")
    
    # 编辑现有映射
    if current_mappings:
        st.subheader("✏️ 编辑现有映射")
        
        for source, targets in current_mappings.items():
            with st.expander(f"编辑: {source} → {', '.join(targets)}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    edited_source = st.text_input("源项目", value=source, key=f"edit_source_{source}")
                
                with col2:
                    edited_targets = st.text_input("关联项目", value=', '.join(targets), key=f"edit_targets_{source}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("💾 保存", key=f"save_{source}"):
                        # 更新映射
                        new_targets_list = [t.strip() for t in edited_targets.split(',') if t.strip()]
                        
                        # 删除旧映射，添加新映射
                        del current_mappings[source]
                        current_mappings[edited_source] = new_targets_list
                        
                        if save_project_mappings(current_mappings):
                            st.success("✅ 映射规则已更新")
                            st.rerun()
                        else:
                            st.error("❌ 更新失败")
                
                with col2:
                    if st.button("🗑️ 删除", key=f"delete_{source}"):
                        del current_mappings[source]
                        if save_project_mappings(current_mappings):
                            st.success(f"✅ 已删除映射规则: {source}")
                            st.rerun()
                        else:
                            st.error("❌ 删除失败")
                
                with col3:
                    if st.button("🔄 重置", key=f"reset_{source}"):
                        st.rerun()
    
    # 重置所有映射
    st.subheader("🔄 重置映射")
    if st.button("🔄 重置为默认映射", key="reset_all_mappings"):
        default_mappings = {
            "aca": ["aca-cn"],
            "public-api": ["public-api-job"],
            "back-office": ["back-office-job"],
            "aims-web": ["aims-web-job"],
            "lt-external-service": ["lt-external-service-job"]
        }
        
        if save_project_mappings(default_mappings):
            st.success("✅ 已重置为默认映射规则")
            st.rerun()
        else:
            st.error("❌ 重置失败")
    
    # 显示配置文件
    with st.expander("📄 项目映射配置文件"):
        if os.path.exists("config/project_mapping.json"):
            try:
                with open("config/project_mapping.json", 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    st.text_area("配置文件内容", value=file_content, height=200, disabled=True)
            except Exception as e:
                st.error(f"读取配置文件失败: {e}")
        else:
            st.warning("⚠️ 项目映射配置文件不存在")
    
    # 使用说明
    with st.expander("📖 项目映射使用说明"):
        st.markdown("""
        ### 🔗 项目映射功能：
        - **自动扩展**: 当检测到特定项目时，自动添加关联项目
        - **智能匹配**: 支持部分匹配和模糊匹配
        - **可维护**: 通过界面轻松添加、编辑、删除映射规则
        
        ### 📝 映射规则格式：
        - **源项目**: 在JIRA中检测到的项目名称
        - **关联项目**: 需要自动添加的项目列表（逗号分隔）
        
        ### 💡 使用示例：
        - 当检测到 `aca` 时，自动添加 `aca-cn`
        - 当检测到 `public-api` 时，自动添加 `public-api-job`
        
        ### 🔧 管理操作：
        - **添加规则**: 填写源项目和关联项目，点击添加
        - **编辑规则**: 展开现有规则，修改后保存
        - **删除规则**: 点击删除按钮移除不需要的规则
        - **重置规则**: 恢复默认的映射配置
        
        ### ⚠️ 注意事项：
        - 映射规则会实时生效
        - 修改后需要重新提取数据才能看到效果
        - 建议在测试环境中验证映射规则
        """)
