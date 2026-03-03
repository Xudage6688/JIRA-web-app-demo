# 🛠️ DevOps 工具集

一个基于 Streamlit 的 DevOps 自动化工具平台，集成 Jira 分析、Jira 工单管理、镜像查询和 CircleCI Pipeline 管理功能。

## 🎯 工具列表

| 工具 | 功能说明 |
|------|---------|
| 📊 Jira Affects Project | Jira 问题影响项目分析，支持项目映射和智能去重 |
| 🐳 Services Images Extractor | 从 GitHub 提取容器镜像版本，支持多环境对比 |
| 🌐 Open PR Url | PR 链接快速打开工具 |
| 🚀 CircleCI Pipeline 管理 | Pipeline 触发、查询、监控和审批管理 |
| 📝 Jira Operations Tool | Jira 工单管理工具，支持创建、查询、批量更新 Resolution |

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

### 1. 用户配置文件
复制示例文件并编辑：
```bash
cp config/users_config.json.example config/users_config.json
```

配置格式：
```json
{
  "users": {
    "username": {
      "display_name": "显示名称",
      "jira": {
        "api_token": "your-jira-token",
        "email": "user@example.com"
      },
      "circleci": {
        "api_token": "your-circleci-token",
        "organization": "asiainspection",
        "vcs_type": "github",
        "default_project": "back-office-cloud",
        "default_branch": "master"
      }
    }
  }
}
```

### 2. 服务列表配置
编辑 `config/circleci-services.txt`，每行一个服务名称。

---

## 🔑 获取 API Tokens

### Jira API Token
1. 访问 https://id.atlassian.com/manage-profile/security/api-tokens
2. 点击 "Create API token"
3. 复制生成的 Token

### CircleCI API Token
1. 登录 CircleCI → User Settings → Personal API Tokens
2. 创建新 Token
3. 复制保存

### GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. 勾选 `repo` 权限
4. 复制生成的 Token（格式：`ghp_xxx...`）

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
- 下拉选择项目（74个服务，支持输入过滤）
- 输入分支名称
- 一键触发

#### 查询 Pipeline 列表
- 并发查询（5-10秒完成）
- 显示 Preprod Approval 信息
- 审批人自动识别（UUID → 用户名）
- 北京时间 + 相对时间显示

#### 实时监控
- Pipeline/Workflow/Jobs 详细状态
- Jobs 统计面板（成功/失败/运行中/待审批）
- 运行时长显示
- Git 提交信息

#### 审批管理
- 查找待审批的 Jobs
- 一键审批
- Preprod Jobs 自动展开
- 审批时长显示

### 📝 Jira Operations Tool

#### 创建 Ticket
- 快速创建 Issue，支持自定义字段
- Work Type 选择（Task/Bug/Story/Epic 等）
- Priority、SP Team 等字段设置
- 自动转换 ADF 格式描述

#### 查询 Ticket
- 输入 Ticket Key 快速查询
- 显示完整 Issue 信息
- 包含 Summary、Description、Status、Resolution 等
- 支持查看完整 JSON 数据

#### 批量更新 Resolution
- 支持批量更新多个 Ticket
- 进度条实时显示
- 详细结果统计（成功/失败）
- 自动识别错误原因

---

## 📁 项目结构

```
jira-web-app/
├── app.py                          # 主应用
├── requirements.txt                # 依赖
├── README.md                       # 文档
├── config/                         # 配置
│   ├── users_config.json           # 用户配置
│   ├── circleci-services.txt       # 服务列表
│   └── README-circleci.md          # 说明
├── pages/                          # 页面
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   └── 5_📝_Jira_Operations.py
├── modules/                        # 模块
│   ├── jira_extractor.py
│   ├── jira_operations_helper.py
│   ├── github_kustomize_client.py
│   ├── argocd_client.py
│   └── user_config_loader.py
└── circleCi/                       # CircleCI
    ├── triggerJob.py
    ├── monitoring.py
    └── config_loader.py
```

---

## 🎮 使用技巧

### CircleCI Pipeline 管理

1. **快速触发**
   - 在下拉框中输入关键字快速过滤项目
   - 触发后 ID 自动传递到监控和审批页面

2. **高效查询**
   - 并发查询提升速度（20秒 → 5秒）
   - 用户信息自动缓存，避免重复 API 调用
   - 可在侧边栏查看缓存统计并清空

3. **状态保持**
   - 切换 Tab 不丢失输入
   - 刷新页面重置为默认值

4. **Pipeline ID 传递**
   - 触发成功 → 自动填充到监控/审批
   - 列表点"监控" → 自动填充到监控/审批

---

## 🔧 故障排除

| 问题 | 解决方案 |
|------|---------|
| API Token 无效 | 检查 `config/users_config.json` 配置 |
| 服务列表为空 | 确保 `config/circleci-services.txt` 存在 |
| 并发查询报错 | 检查网络连接和 API 速率限制 |
| 审批人显示异常 | 应用会自动查询转换，失败时显示"已审批" |

---

## 📞 技术支持

- CircleCI API: https://circleci.com/docs/api/v2/
- Streamlit 文档: https://docs.streamlit.io/

**版本**: 2.0  
**最后更新**: 2026-01-27  
**维护者**: Daisy Liu
