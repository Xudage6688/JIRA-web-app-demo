"""
DevOps 工具集主入口
多页面 Streamlit 应用的 Landing Page
"""

import streamlit as st

# 页面配置
st.set_page_config(
    page_title="DevOps 工具集",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .tool-card {
        padding: 2rem;
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        background: #ffffff;
        transition: all 0.3s ease;
    }
    .tool-card:hover {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
        transform: translateY(-2px);
    }
    .metric-card {
        text-align: center;
        padding: 1rem;
        border-radius: 8px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# 主标题
st.markdown('<h1 class="main-header">🛠️ DevOps 工具集</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">提升团队效率的 DevOps 自动化工具平台</p>', unsafe_allow_html=True)
st.markdown("---")

# 工具展示区
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container():
        st.markdown("### 📊 Jira Affects Project 分析工具")
        st.markdown("""
        快速提取和分析 Jira 问题影响的项目列表，帮助团队进行影响范围评估和发版规划。
        
        **核心功能：**
        - 🔍 **自动字段检测** - 智能识别 Affects Project 字段ID
        - 🧹 **智能去重映射** - 自动去重并应用项目映射规则
        - 📥 **多格式导出** - 支持 JSON 和 CSV 格式下载
        - 🔐 **企业级安全** - API Token 完全隐藏，最高安全标准
        - 💾 **配置持久化** - 本地配置存储，刷新不丢失
        
        **适用场景：**
        - 🚀 发版影响范围分析
        - 🔗 项目依赖关系追踪
        - 👥 团队协作沟通支持
        - 📊 问题统计和报表生成
        
        **最新特性 v2.3：**
        - ✅ 精确项目映射，修复NA误触发bug
        - ✅ 支持新JQL API，性能更优
        - ✅ ADF格式内容解析
        """)
        
        st.markdown("")
        if st.button("🚀 打开 Jira 工具", key="jira_btn", use_container_width=True, type="primary"):
            st.switch_page("pages/1_📊_Jira_Affects_Project.py")

with col2:
    with st.container():
        st.markdown("### 🐳 ArgoCD 镜像版本查询工具")
        st.markdown("""
        查询和追踪 ArgoCD 应用部署的容器镜像版本，支持多环境对比和历史追踪。
        
        **核心功能：**
        - 🌍 **多环境支持** - 支持 preprod/staging/prod 环境切换
        - 📋 **批量服务查询** - 一次查询多个服务的镜像版本
        - 🔄 **部署历史对比** - 自动对比部署变化，识别差异
        - ⏰ **Token 智能验证** - 自动检测 Token 有效期
        - 📊 **可视化展示** - 清晰的表格和图表展示
        
        **适用场景：**
        - 📦 版本追踪和管理
        - ✅ 部署验证和确认
        - 🔍 环境差异对比分析
        - 📈 部署历史趋势分析
        
        **技术特性 v2.1：**
        - ✅ JWT Token 自动验证
        - ✅ 智能服务映射
        - ✅ 增量对比分析
        """)
        
        st.markdown("")
        if st.button("🚀 打开 ArgoCD 工具", key="argocd_btn", use_container_width=True, type="primary"):
            st.switch_page("pages/2_🐳_ArgoCD_Images.py")

# 功能亮点
st.markdown("---")
st.markdown("## ✨ 平台特性")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="metric-card">
        <h2>🛠️</h2>
        <h3>2+</h3>
        <p>可用工具</p>
        <small>持续增加中</small>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <h2>⚡</h2>
        <h3>&lt;2s</h3>
        <p>平均响应</p>
        <small>快速高效</small>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <h2>🔐</h2>
        <h3>企业级</h3>
        <p>安全标准</p>
        <small>最高保护</small>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="metric-card">
        <h2>💰</h2>
        <h3>免费</h3>
        <p>使用成本</p>
        <small>零投入</small>
    </div>
    """, unsafe_allow_html=True)

# 快速开始指南
st.markdown("---")
st.markdown("## 🚀 快速开始")

tab1, tab2, tab3 = st.tabs(["📖 新手指南", "🔐 安全说明", "❓ 常见问题"])

with tab1:
    st.markdown("""
    ### 🎯 快速开始指南
    
    #### 步骤 1: 选择工具
    从主页选择你需要的工具：
    - **📊 Jira Affects Project** - 用于处理 Jira 数据和项目影响分析
    - **🐳 ArgoCD 镜像查询** - 用于查询容器镜像部署信息
    
    #### 步骤 2: 配置认证
    根据工具要求配置相应的认证信息：
    
    **Jira 工具：**
    - API Token：从 [Atlassian 账户设置](https://id.atlassian.com/manage-profile/security/api-tokens) 获取
    - 邮箱地址：你的 Jira 账户邮箱
    - 过滤器 ID：要分析的 Jira 过滤器
    
    **ArgoCD 工具：**
    - Bearer Token：从 ArgoCD Web 界面的 Settings → Tokens 获取
    - 环境选择：选择目标环境（preprod/staging/prod）
    
    #### 步骤 3: 执行操作
    1. 按照页面提示输入必要信息
    2. 点击执行按钮开始查询
    3. 等待处理完成
    4. 查看结果和统计信息
    
    #### 步骤 4: 导出数据
    将查询结果导出为：
    - **JSON 格式** - 适合程序处理和数据集成
    - **CSV 格式** - 适合 Excel 分析和报表制作
    
    ### 💡 使用技巧
    
    - **保存配置**：所有工具都支持配置持久化，设置一次即可
    - **批量操作**：尽量使用批量查询功能提高效率
    - **定期检查**：建议定期更新 Token 确保安全性
    - **结果对比**：导出历史数据进行对比分析
    """)

with tab2:
    st.markdown("""
    ### 🔐 安全说明
    
    我们非常重视您的数据安全和隐私保护，采用业界最高安全标准。
    
    #### Token 安全管理
    
    **完全隐藏保护：**
    - ✅ 所有 Token 使用密码输入框，**永不显示明文**
    - ✅ Token 不会保存到本地配置文件
    - ✅ Session 结束后自动清除内存中的 Token
    - ✅ 防止屏幕截图、共享屏幕泄露
    
    **安全传输：**
    - ✅ 所有 API 调用使用 HTTPS 加密
    - ✅ Token 仅在请求头中传输
    - ✅ 不在日志中记录敏感信息
    
    #### 数据隐私保护
    
    **本地存储：**
    - ✅ 配置文件仅保存非敏感信息
    - ✅ 查询结果仅在 Session 中保存
    - ✅ 不进行任何用户行为追踪
    - ✅ 不上传数据到第三方服务器
    
    **访问控制：**
    - ✅ 需要有效的企业账户认证
    - ✅ 遵循最小权限原则
    - ✅ 每次操作都需要 Token 验证
    - ✅ 支持 Token 过期自动检测
    
    #### 合规性
    
    - ✅ 符合 GDPR 数据保护要求
    - ✅ 符合企业信息安全政策
    - ✅ 支持审计日志追踪
    - ✅ 定期进行安全审查
    
    #### 最佳安全实践
    
    1. **定期更新 Token**：建议每月更换一次
    2. **不要共享 Token**：每个用户使用自己的 Token
    3. **及时撤销**：不用时及时在 Jira/ArgoCD 撤销 Token
    4. **权限最小化**：Token 只授予必要的权限
    5. **安全环境**：在安全的网络环境中使用
    """)

with tab3:
    st.markdown("""
    ### ❓ 常见问题解答
    
    #### 🔑 关于认证和 Token
    
    **Q: 如何获取 Jira API Token？**
    
    A: 访问步骤：
    1. 登录 [Atlassian 账户](https://id.atlassian.com)
    2. 点击 Security → API tokens
    3. 点击 "Create API token"
    4. 为 Token 命名并创建
    5. 立即复制（只显示一次）
    
    **Q: 如何获取 ArgoCD Token？**
    
    A: 获取步骤：
    1. 登录 ArgoCD Web 界面
    2. 点击右上角用户头像
    3. 选择 Settings
    4. 切换到 Tokens 标签
    5. 点击 Generate New 创建
    6. 复制生成的 Token
    
    **Q: Token 过期了怎么办？**
    
    A: 系统会自动检测 Token 有效性，如果过期：
    - Jira Token：重新生成并输入
    - ArgoCD Token：重新创建并输入
    - 建议设置提醒定期更新
    
    #### 🛠️ 关于功能使用
    
    **Q: 支持哪些环境？**
    
    A: 
    - Jira 工具：支持 Jira Cloud 和 Server 8.0+
    - ArgoCD 工具：支持 preprod、staging、prod 环境
    
    **Q: 可以一次查询多个服务吗？**
    
    A: 可以！所有工具都支持批量操作：
    - Jira：通过过滤器批量获取问题
    - ArgoCD：支持选择多个服务同时查询
    
    **Q: 查询结果可以导出吗？**
    
    A: 支持多种格式导出：
    - JSON：适合程序处理
    - CSV：适合 Excel 分析
    - 文本：适合复制粘贴
    
    #### 🔧 关于故障排查
    
    **Q: 为什么查询失败？**
    
    A: 常见原因和解决方法：
    1. **Token 无效**：重新获取 Token
    2. **权限不足**：联系管理员分配权限
    3. **网络问题**：检查 VPN 和网络连接
    4. **服务不存在**：确认服务名称拼写正确
    
    **Q: 如何报告问题？**
    
    A: 请通过以下方式反馈：
    - 📧 Email: daisy.liu@qima.com
    - 💬 内部协作平台
    - 📝 详细描述问题和截图
    
    #### 💡 关于性能优化
    
    **Q: 查询速度慢怎么办？**
    
    A: 优化建议：
    - 减少批量查询的数量
    - 避免高峰期使用
    - 清除浏览器缓存
    - 使用更快的网络连接
    
    **Q: 为什么有些功能暂时不可用？**
    
    A: 可能原因：
    - API 服务维护中
    - Token 权限不足
    - 环境暂时不可访问
    - 请稍后重试或联系支持
    """)

# 更新日志
st.markdown("---")
with st.expander("📋 版本更新日志"):
    st.markdown("""
    ### v2.0.0 (2025-11-20) - 重大架构升级
    
    #### 🎉 新增功能
    - ✅ **多页面架构**：采用 Streamlit Pages 实现模块化设计
    - ✅ **ArgoCD 集成**：新增容器镜像版本查询工具
    - ✅ **统一入口**：Landing Page 提供清晰的功能导航
    - ✅ **配置隔离**：各工具独立配置管理
    
    #### 🔧 架构优化
    - ✅ 代码模块化重构
    - ✅ 统一的错误处理机制
    - ✅ 改进的缓存策略
    - ✅ 优化的用户界面设计
    
    #### 📚 文档完善
    - ✅ 详细的部署指南
    - ✅ 完整的使用说明
    - ✅ 安全最佳实践
    - ✅ 常见问题解答
    
    ---
    
    ### v1.x (历史版本)
    
    #### v1.3.0 - Jira 工具增强
    - 🔐 API Token 完全隐藏保护
    - 🔗 项目映射管理功能
    - 📊 数据去重和展示优化
    
    #### v1.2.0 - 稳定性提升
    - 🛡️ 增强的错误处理
    - 💾 配置持久化
    - 🎨 UI/UX 改进
    
    #### v1.0.0 - 首次发布
    - 📊 Jira Affects Project 基础功能
    - 🔍 自动字段检测
    - 📥 数据导出功能
    """)

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0;">
    <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">🛠️ DevOps 工具集 v2.0.0</p>
    <p style="margin-bottom: 0.5rem;">Powered by <strong>Streamlit</strong> | Built with ❤️ by DevOps Team</p>
    <p style="font-size: 0.9rem;">👩‍💻 维护者: Daisy Liu | 📧 daisy.liu@qima.com</p>
    <p style="font-size: 0.8rem; margin-top: 1rem; color: #999;">
        © 2025 QIMA. All rights reserved. | 
        <a href="https://github.com/Daisy-liu822/jiraWeb" target="_blank" style="color: #667eea;">GitHub</a> | 
        <a href="mailto:daisy.liu@qima.com" style="color: #667eea;">Support</a>
    </p>
</div>
""", unsafe_allow_html=True)

# 侧边栏信息
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📌 快速链接")
    
    st.markdown("""
    - [📖 使用文档](https://github.com/Daisy-liu822/jiraWeb)
    - [🐛 问题反馈](mailto:daisy.liu@qima.com)
    - [💡 功能建议](mailto:daisy.liu@qima.com)
    - [🔐 安全政策](https://github.com/Daisy-liu822/jiraWeb)
    """)
    
    st.markdown("---")
    st.markdown("### ℹ️ 系统信息")
    st.info(f"""
    **平台版本**: v2.0.0
    **Streamlit**: {st.__version__}
    **Python**: 3.9+
    **部署**: Streamlit Cloud
    """)
    
    st.markdown("---")
    st.success("✅ 系统运行正常")

