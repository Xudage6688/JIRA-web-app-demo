# 🛠️ DevOps 工具集

一个基于 Streamlit 的 DevOps 自动化工具平台，集成 Jira 分析、Jira 工单管理、镜像查询、CircleCI Pipeline 管理和 Jenkins 部署功能。

## 🎯 工具列表

| 工具 | 功能说明 |
|------|---------|
| 📊 Jira Affects Project | Jira 问题影响项目分析，支持项目映射和智能去重 |
| 🐳 Services Images Extractor | 从 GitHub 提取容器镜像版本，支持多环境对比 |
| 🌐 Open PR Url | PR 链接快速打开工具 |
| 🚀 CircleCI Pipeline 管理 | Pipeline 触发、查询、监控和审批管理 |
| 📝 Jira Operations Tool | Jira 工单管理工具，支持创建、查询、批量更新 Resolution |
| 🔧 Jenkins 部署 | Jenkins 一键部署，支持顺序/并发模式，实时日志展示 |

---

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动应用
```bash
streamlit run app.py
```

### 访问地址
```
http://localhost:8501
```

---

## ⚙️ 配置说明

### 用户配置文件

编辑 `config/users_config.json`，为每位使用者配置各工具的认证信息：

```json
{
  "users": {
    "username": {
      "display_name": "显示名称",
      "email": "user@example.com",
      "jira": {
        "api_token": "your-jira-token",
        "base_url": "https://qima.atlassian.net",
        "filter_id": "20334",
        "field_id": "customfield_12605"
      },
      "circleci": {
        "api_token": "your-circleci-token",
        "vcs_type": "github",
        "organization": "asiainspection",
        "default_project": "back-office-cloud",
        "default_branch": "master"
      },
      "github": {
        "token": "ghp_xxx..."
      },
      "jenkins": {
        "username": "your-azure-ad-object-id",
        "api_token": "your-jenkins-api-token",
        "jenkins_url": "https://jenkins.qima.com"
      }
    }
  },
  "default_user": "username"
}
```

### 服务列表配置
编辑 `config/circleci-services.txt`，每行一个 CircleCI 服务名称。

---

## 🔑 获取 API Tokens

### Jira API Token
1. 访问 https://id.atlassian.com/manage-profile/security/api-tokens
2. 点击 "Create API token"，复制生成的 Token

### CircleCI API Token
1. 登录 CircleCI → User Settings → Personal API Tokens
2. 创建新 Token 并复制保存

### GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)，勾选 `repo` 权限
3. 复制生成的 Token（格式：`ghp_xxx...`）

### Jenkins API Token
1. 登录 Jenkins → 右上角用户名 → Configure
2. API Token → Add new Token → Generate
3. 复制生成的 Token（仅显示一次）
4. 用户名填写 Azure AD Object ID

---

## ✨ 主要功能

### 📊 Jira 工具
- 智能字段检测和批量数据提取
- 项目映射（如 `aca` → `aca-cn`）
- 多格式导出（JSON/CSV）

### 🐳 镜像查询工具
- GitHub 仓库集成（无需 ArgoCD 内网）
- 多环境支持（preprod/staging/prod）
- 部署对比分析（高亮变化）
- 服务下拉选择（支持输入过滤）

### 🚀 CircleCI Pipeline 管理

#### 触发 Pipeline
- 下拉选择项目（支持输入过滤）
- 输入分支名称，或点击 **"🔍 查最新"** 查询该项目最近构建的分支
- 分支下拉选择后自动填入输入框

#### 查询 Pipeline 列表
- 并发查询（HTTP Session 复用 + max_workers=10）
- 显示 Preprod Approval 信息
- 审批人自动识别（UUID → 用户名）
- 北京时间 + 相对时间显示
- **分支一键复制**按钮

#### 监控 Pipeline
- Pipeline/Workflow/Jobs 详细状态
- Jobs 统计面板（成功/失败/运行中/待审批）
- 运行时长显示，Git 提交信息
- Tab2 点击"监控"按钮自动查询（无需手动粘贴 ID）

#### 审批面板
- 集成在监控页内，无需切换 Tab
- 查找待审批的 Jobs，一键审批
- Preprod Jobs 自动展开
- Workflow Jobs 并发获取

### 📝 Jira Operations Tool

#### 创建 Ticket
- 快速创建 Issue，支持自定义字段
- Work Type 选择（Task/Bug/Story/Epic 等）
- 自动转换 ADF 格式描述

#### 查询 Ticket
- 输入 Ticket Key 快速查询，显示完整 Issue 信息
- 支持查看完整 JSON 数据

#### Sprint 查询
- 多 Board 并发查询（10 线程），33 Board 亚秒级完成
- Team 名称预过滤，减少无效 API 调用

#### 批量更新 Resolution
- 批量更新多个 Ticket，进度条实时显示
- 详细结果统计（成功/失败），自动识别错误原因

### 🔧 Jenkins 部署工具

针对即将迁移至 EKS 的服务，提供简洁的 Jenkins 一键部署：

- **固定服务**：`pp-public-api`、`pp-psi-service`
- **顺序部署**：按顺序逐一触发，前一个完成才启动下一个，适合有依赖关系的服务
- **并发部署**：所有服务同时触发，互不等待，速度更快
- **实时日志**：逐行展示 Jenkins 控制台输出，部署过程一目了然
- **结果汇总**：清晰展示每个服务的成功/失败状态
- **侧边栏连接测试**：一键验证 Jenkins 认证配置是否有效

---

## 📁 项目结构

```
jira-web-app/
├── app.py                          # 主应用入口
├── requirements.txt                # 依赖声明
├── README.md                       # 项目文档
├── config/                         # 配置目录
│   ├── users_config.json           # 用户配置（含各工具 Token）
│   └── circleci-services.txt       # CircleCI 服务列表
├── pages/                          # Streamlit 多页面
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   └── 6_🔧_Jenkins_Deploy.py
├── modules/                        # 公共模块
│   ├── user_config_loader.py       # 多用户配置加载器 + 统一认证构建器
│   ├── jira_extractor.py          # Jira 数据提取器（含 SafeLogger）
│   ├── jira_operations_helper.py   # Jira 业务操作辅助（含 Sprint 并发查询）
│   ├── test_case_importer.py       # Test Cases 导入 UI 层
│   ├── _test_case_importer_logic.py # Test Cases 导入纯函数逻辑层
│   ├── github_kustomize_client.py  # GitHub Kustomize 镜像查询
│   └── argocd_client.py            # ArgoCD 服务镜像查询
├── circleCi/                       # CircleCI 工具模块
│   ├── triggerJob.py
│   ├── monitoring.py
│   └── config_loader.py
└── tests/                          # 单元测试
    ├── test_user_config_loader.py
    ├── test_jira_extractor.py
    └── test_test_case_importer_logic.py
```

---

## 🧪 测试

```bash
pytest tests/ -v
```

**覆盖范围**：
- `build_jira_auth_headers` / `build_jenkins_auth` / `build_circleci_headers` 认证构建
- `SafeLogger` 日志降级
- `JiraExtractor` 核心方法
- Test Cases 导入全部 8 个纯函数（Jira API mock）

---

## 🔧 故障排除

| 问题 | 解决方案 |
|------|---------|
| 页面显示"未选择使用者" | 返回主页选择身份后再进入工具页 |
| Jira / CircleCI Token 无效 | 检查 `config/users_config.json` 对应字段 |
| Jenkins 连接失败 | 使用侧边栏"连接测试"按钮排查，确认用户名为 Azure AD Object ID |
| 服务列表为空 | 确保 `config/circleci-services.txt` 文件存在 |
| 并发查询报错 | 检查网络连接和 API 速率限制 |
| 审批人显示异常 | 应用会自动查询转换，失败时显示"已审批" |

---

## 📞 参考文档

- CircleCI API: https://circleci.com/docs/api/v2/
- Jira REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- Streamlit 文档: https://docs.streamlit.io/

**版本**: 4.1
**最后更新**: 2026-03-25
**维护者**: Daisy Liu

---

## 📋 更新日志

### v4.1 (2026-03-25)
- **CircleCI Tab 重构**：Tab4 审批管理合并至 Tab3，页面从 4 Tab 简化为 3 Tab
- **Tab2 监控按钮**：点击自动跳转 Tab3 并触发查询，实现一键监控闭环
- **HTTP 连接池复用**：CircleCI 所有 API 调用改用 `requests.Session()`，Pipeline 列表查询速度提升
- **分支复制按钮**：Tab2 结果列表每个分支增加一键复制（`components.html` JS）
- **Workflow Jobs 并发获取**：审批面板 Workflow Jobs 查询改为 10 线程并发

### v4.0 (2026-03-24)
- **认证体系统一**：Jira / Jenkins / CircleCI 认证逻辑收敛到 `user_config_loader.py`，消除跨页重复代码
- **静默异常修复**：`jira_extractor.py` SafeLogger 异常降级 + 多处 `except: pass` 改为 `logging.warning`
- **Test Cases 模块重构**：UI 层 (`test_case_importer.py`) 与业务逻辑层 (`_test_case_importer_logic.py`) 分离，支持单元测试
- **Sprint 查询并发**：Board Sprint 查询由串行改为 `ThreadPoolExecutor(max_workers=10)` 并发，33 Board 场景从数秒降至亚秒级
- **测试覆盖建立**：新增 58 个单元测试，覆盖认证构建器、日志器、JiraExtractor、Test Cases 逻辑函数
