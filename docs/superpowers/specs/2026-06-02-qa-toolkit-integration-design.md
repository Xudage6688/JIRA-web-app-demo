# 2026-06-02-qa-toolkit-integration-design

## 概述

将原项目 `C:\Users\Daisy Liu\PythonProject\jira-web-app` 的代码整合到 `qa-toolkit-demo`，作为简历展示版本。

## 设计原则

1. **保留原项目完整性** - 所有文件同步，不丢失功能
2. **去敏化处理** - 移除所有公司环境信息，使用通用占位符
3. **与原项目对齐** - 结构、命名与原项目保持一致
4. **一键同步** - 自动化脚本减少手动错误

## 同步策略

### 第一阶段：文件同步

```
同步文件清单（按优先级）：

1. 页面文件（7个）
   - pages/1_📊_Jira_Affects_Project.py
   - pages/2_🐳_Services_Images_Extractor.py
   - pages/3_🌐_Open_PR_Url.py
   - pages/4_🚀_CircleCI_Pipeline.py
   - pages/5_📝_Jira_Operations.py
   - pages/6_🔧_Jenkins_Deploy.py
   - pages/7_🧪_Test_Tools.py

2. 核心模块（含 Test Tools）
   - modules/_test_tools/          # 9个测试工具
   - modules/                      # 其他核心逻辑

3. CircleCI 模块
   - circleCi/                     # 完整模块

4. 测试文件
   - tests/                        # 全部测试

5. 应用入口
   - app.py                        # 原项目版本

6. 配置文件结构
   - requirements.txt
   - config/                        # 示例配置
```

### 第二阶段：脱敏处理

| 类型 | 原始值 | 替换值 |
|------|--------|--------|
| Jira 域名 | `qima.atlassian.net` | `your-jira.atlassian.net` |
| CircleCI 组织 | `asiainspection` | `your-org` |
| CircleCI 项目 | `back-office-cloud` | `your-project` |
| Jenkins URL | `jenkins.qima.com` | `jenkins.example.com` |
| GitHub 仓库 | `qcore-apps-descriptors` | `your-org/your-repo` |
| 配置 Token | 真实 token | `# YOUR_TOKEN_HERE` |
| 默认分支 | `master` | `main` |

### 第三阶段：资源处理

1. **GIF 压缩**：使用 gifsicle 压缩所有 GIF 文件
   - 目标：减少 30-50% 体积
   - 位置：`docs/images/`

2. **图片清单**：
   - `CircleCI Pipeline.gif`
   - `Jenkins Deploy.gif`
   - `Jira Affects Project.gif`
   - `Jira Operations.gif`
   - `PRs open.gif`
   - `Services Images.gif`
   - `Test tools.png`

### 第四阶段：配置示例简化

README 中的配置示例：
- 仅保留 JSON 结构
- 移除具体字段值说明
- 指向 `config/users_config_example.json`

## 保留的配置

| 文件 | 说明 |
|------|------|
| `project_mapping.json` | 保留（无敏感信息） |
| `config/circleci-services.example.txt` | 简化服务列表 |
| `config/users_config_example.json` | 完全去敏版本 |

## 移除的文件

| 文件 | 原因 |
|------|------|
| `circleCi/batch_ops_view.py` | 可能需要检查是否必要 |
| `circleCi/commit_search_view.py` | 可能需要检查是否必要 |

## 验证清单

- [ ] 所有 7 个页面可启动访问
- [ ] README 中的图片路径正确
- [ ] 配置示例不包含真实 token
- [ ] 测试可运行（pytest）
- [ ] Streamlit 应用可正常启动

## 实施顺序

1. 备份现有文件到 `backup/`
2. 复制原项目文件
3. 执行脱敏脚本
4. 压缩并复制图片
5. 更新 README
6. 验证功能

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 遗漏敏感信息 | 手动检查关键文件（user_config_loader, README） |
| GIF 压缩失败 | 保留原文件，失败则直接复制 |
| 同步冲突 | 先备份，冲突时以原项目为准 |