# QA DevOps Toolkit

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-orange)
![测试覆盖率](https://img.shields.io/badge/Coverage-87%25-green)
![许可证](https://img.shields.io/badge/License-MIT-yellow)

> 📖 **语言:** [English](./README.md) | [中文](./README.zh.md)

---

**QA DevOps Toolkit** 是一个基于 Streamlit 的 DevOps 自动化工具平台，集成 Jira 分析、CircleCI Pipeline 管理和 Jenkins 部署功能。

## 工具列表

| 工具 | 功能说明 |
|------|---------|
| 📊 Jira Affects Project | Jira 问题影响项目分析，支持项目映射和智能去重 |
| 🐳 Services Images Extractor | 从 GitHub 提取容器镜像版本，支持多环境对比 |
| 🌐 Open PR Url | PR 链接快速打开工具 |
| 🚀 CircleCI Pipeline | Pipeline 触发、查询、监控和审批管理 |
| 📝 Jira Operations | 工单管理，支持创建、查询、批量更新 Resolution |
| 🔧 Jenkins Deploy | 一键部署，支持顺序/并发模式，实时日志展示 |
| 🧪 Test Tools | 日常测试辅助工具集合，全部在本地运行 |

---

## 快速开始

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

## 配置说明

编辑 `config/users_config_example.json`，为每位使用者配置各工具的认证信息：

```json
{
  "users": {
    "username": {
      "display_name": "显示名称",
      "email": "user@example.com",
      "jira": {
        "api_token": "# YOUR_JIRA_TOKEN",
        "base_url": "https://your-jira.atlassian.net",
        "filter_id": "12345",
        "field_id": "customfield_xxxxx"
      },
      "circleci": {
        "api_token": "# YOUR_CIRCLECI_TOKEN",
        "vcs_type": "github",
        "organization": "your-org",
        "default_project": "your-project",
        "default_branch": "main"
      },
      "github": {
        "token": "# YOUR_GITHUB_TOKEN"
      },
      "jenkins": {
        "username": "# YOUR_JENKINS_USER",
        "api_token": "# YOUR_JENKINS_TOKEN",
        "jenkins_url": "https://jenkins.example.com"
      }
    }
  },
  "default_user": "username"
}
```

服务列表配置：编辑 `config/circleci-services.txt`，每行一个 CircleCI 服务名称。

---

## 功能截图

### 📊 Jira Affects Project

Jira 问题影响项目分析，支持项目映射和智能去重

![Jira Affects Project](docs/images/Jira%20Affects%20Project.gif)

### 🐳 Services Images Extractor

从 GitHub 提取容器镜像版本，支持多环境对比

![Services Images](docs/images/Services%20Images.gif)

### 🌐 Open PR Url

PR 链接快速打开工具

![Open PR Url](docs/images/PRs%20open.gif)

### 🚀 CircleCI Pipeline 管理

Pipeline 触发、查询、监控和审批管理

![CircleCI Pipeline](docs/images/CircleCI%20Pipeline.gif)

### 📝 Jira Operations Tool

工单管理，支持创建、查询、批量更新

![Jira Operations](docs/images/Jira%20Operations.gif)

### 🔧 Jenkins 部署

一键部署，支持顺序/并发模式，实时日志展示

![Jenkins Deploy](docs/images/Jenkins%20Deploy.gif)

### 🧪 Test Tools

日常测试辅助工具集合，全部在本地运行

![Test Tools](docs/images/Test%20tools.png)

---

## 项目结构

```
qa-toolkit-demo/
├── app.py                           # 主应用入口
├── requirements.txt                 # 依赖声明
├── README.md                        # 项目文档（英文）
├── README.zh.md                      # 项目文档（中文）
├── config/                          # 配置目录
│   ├── users_config_example.json   # 用户配置示例（含各工具 Token 占位符）
│   ├── circleci-services.txt       # CircleCI 服务列表
│   └── argocd_config.example.json   # ArgoCD 配置示例
├── pages/                           # Streamlit 多页面应用
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   ├── 6_🔧_Jenkins_Deploy.py
│   └── 7_🧪_Test_Tools.py
├── modules/                         # 公共模块
│   ├── user_config_loader.py        # 多用户配置加载器 + 统一认证构建器
│   ├── jira_extractor.py           # Jira 数据提取器（含 SafeLogger）
│   ├── jira_operations_helper.py   # Jira 业务操作辅助
│   ├── test_case_importer.py       # Test Cases 导入 UI 层
│   ├── _test_case_importer_logic.py # Test Cases 导入纯函数逻辑层
│   ├── github_kustomize_client.py  # GitHub Kustomize 镜像查询
│   └── _test_tools/                # 测试工具（9 个工具）
│       ├── _api_perf_test.py
│       ├── _create_aca_account.py
│       ├── _generate_pdf.py
│       └── ...
├── circleCi/                        # CircleCI 工具模块
│   ├── triggerJob.py
│   ├── monitoring.py
│   ├── batch_operations.py
│   ├── config_loader.py
│   └── ...
└── tests/                           # 单元测试
    ├── test_user_config_loader.py
    ├── test_jira_extractor.py
    ├── test_test_case_importer_logic.py
    ├── test_commit_search.py
    ├── test_services_images_extractor.py
    └── test_batch_operations.py
```

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 带覆盖率运行
pytest tests/ --cov=. --cov-report=term-missing

# 运行特定测试文件
pytest tests/test_commit_search.py -v
```

**测试覆盖范围：**
- 认证构建器：`build_jira_auth_headers`、`build_jenkins_auth`、`build_circleci_headers`
- `SafeLogger` 日志降级
- `JiraExtractor` 核心方法
- `UserConfigLoader` 完整功能
- Test Cases 导入纯函数逻辑层
- Commit ID 搜索功能
- 多环境审批信息获取
- 批量触发与审批功能

**当前测试覆盖率：** 87%

---

## 文档

- [开发指南](./docs/guides/development.md) - 环境配置与开发（英文）
- [Development Guide](./docs/guides/development.en.md) - Setup and development (English)

---

## 更新日志

### v5.0 (2026-06-02)
- **开源版本**：重命名为 QA DevOps Toolkit
- **完全脱敏**：移除所有公司特定域名的引用
- **配置模板**：提供 `config/users_config_example.json` 配置模板

### v4.5 (2026-06-01)
- 添加 shields.io 彩色 badges，优化视觉效果
- 为全部 7 个工具页面添加功能演示 GIF/PNG
- GIF 分散到各工具详细描述下方，便于对照参考

### v4.4 (2026-05-11)
- 批量操作 (Tab5)：新增第5个 Tab，支持批量触发多个服务到指定分支
- 文本输入服务列表：支持粘贴多行服务名快速选择
- 批量审批 Preprod：扫描并一键审批所有待审批 Jobs
- 批量操作模块：新增 `circleCi/batch_operations.py` 纯函数逻辑层
- 单元测试：新增 17 个批量操作测试，覆盖率从 85% 提升至 87%
- 安全修复：移除侧边栏 Token 片段显示，避免敏感信息泄露

### v4.3 (2026-04-27)
- Commit ID 搜索 (Tab4)：新增第4个 Tab，支持通过 commit hash 前缀跨服务搜索 Pipeline
- 多环境审批展示：支持 dev/staging/preprod/uat/prod 等多环境审批状态展示
- 日志系统升级：所有 `print()` 替换为 `logging` 模块
- 测试覆盖率提升：新增 51 个单元测试，覆盖率从 66% 提升至 85%

### v4.0 (2026-03-24)
- 认证体系统一：Jira / Jenkins / CircleCI 认证逻辑收敛到 `user_config_loader.py`
- Test Cases 模块重构：UI 层与业务逻辑层分离，支持单元测试
- Sprint 查询并发：Board Sprint 查询改为 10 线程并发，33 Board 场景从数秒降至亚秒级
- 测试覆盖建立：新增 58 个单元测试

---

**版本**: 5.0 | **最后更新**: 2026-06-02 | **维护者**: Daisy Liu