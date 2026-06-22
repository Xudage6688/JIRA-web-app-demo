# QA Toolkit Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将原项目 `jira-web-app` 的代码同步到 `qa-toolkit-demo`，完成去敏化处理和资源文件整理。

**Architecture:** 采用文件同步策略：从原项目复制必要文件到 demo，执行脱敏替换，更新 README 引用路径，最后验证功能完整性。

**Tech Stack:** Python, Streamlit, pytest, gifsicle (GIF 压缩)

---

## 文件映射关系

| 原项目路径 | 目标路径 |
|-----------|---------|
| `pages/{1-7}_*.py` | `pages/{1-7}_*.py` |
| `modules/*` | `modules/*` |
| `modules/_test_tools/*` | `modules/_test_tools/*` |
| `circleCi/*` | `circleCi/*` |
| `tests/*` | `tests/*` |
| `app.py` | `app.py` |
| `requirements.txt` | `requirements.txt` |
| `config/*.example.*` | `config/*.example.*` |

**保留文件（不覆盖）：**
- `project_mapping.json`（无敏感信息）
- `docs/superpowers/*`（开发文档）

---

## Phase 1: 备份与准备

### Task 1: 创建备份目录并备份现有文件

**Files:**
- Create: `backup_20260602/` (目录)

- [ ] **Step 1: 创建备份目录**

Command:
```bash
cd "C:/Users/Daisy Liu/cv/myProjects/qa-toolkit-demo"
mkdir -p backup_20260602
```

- [ ] **Step 2: 备份现有 pages 文件**

```bash
cp -r pages/ backup_20260602/pages/
```

- [ ] **Step 3: 备份现有 modules 文件**

```bash
cp -r modules/ backup_20260602/modules/
```

- [ ] **Step 4: 备份现有 circleCi 文件**

```bash
cp -r circleCi/ backup_20260602/circleCi/
```

- [ ] **Step 5: 备份现有 tests 文件**

```bash
cp -r tests/ backup_20260602/tests/
```

- [ ] **Step 6: 备份 app.py 和 requirements.txt**

```bash
cp app.py backup_20260602/app.py
cp requirements.txt backup_20260602/requirements.txt
```

- [ ] **Step 7: 提交备份**

```bash
git add backup_20260602/
git commit -m "chore: backup existing files before integration"
```

---

## Phase 2: 文件同步

### Task 2: 同步页面文件（7个）

**Files:**
- Create: `pages/1_📊_Jira_Affects_Project.py`
- Create: `pages/2_🐳_Services_Images_Extractor.py`
- Create: `pages/3_🌐_Open_PR_Url.py`
- Create: `pages/4_🚀_CircleCI_Pipeline.py`
- Create: `pages/5_📝_Jira_Operations.py`
- Create: `pages/6_🔧_Jenkins_Deploy.py`
- Create: `pages/7_🧪_Test_Tools.py`

- [ ] **Step 1: 复制所有页面文件**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/pages/"*.py pages/
```

- [ ] **Step 2: 验证文件数量**

Command: `ls -la pages/*.py | wc -l`
Expected: 7

- [ ] **Step 3: 提交**

```bash
git add pages/
git commit -m "feat: sync 7 page files from original project"
```

---

### Task 3: 同步核心模块

**Files:**
- Create: `modules/__init__.py`
- Create: `modules/_services_images_logic.py`
- Create: `modules/_test_case_importer_logic.py`
- Create: `modules/argocd_client.py`
- Create: `modules/circleci_pipeline_logic.py`
- Create: `modules/github_kustomize_client.py`
- Create: `modules/jira_extractor.py`
- Create: `modules/jira_operations_helper.py`
- Create: `modules/logging_config.py`
- Create: `modules/test_case_importer.py`
- Create: `modules/user_config_loader.py`

- [ ] **Step 1: 复制 modules 目录**

```bash
cp -r "C:/Users/Daisy Liu/PythonProject/jira-web-app/modules/"* modules/
```

- [ ] **Step 2: 验证核心文件数量**

Command: `ls modules/*.py | wc -l`
Expected: 11+ (含 __init__.py)

- [ ] **Step 3: 提交**

```bash
git add modules/
git commit -m "feat: sync core modules from original project"
```

---

### Task 4: 同步 Test Tools 模块

**Files:**
- Create: `modules/_test_tools/__init__.py`
- Create: `modules/_test_tools/_api_perf_test.py`
- Create: `modules/_test_tools/_clean_download.py`
- Create: `modules/_test_tools/_create_aca_account.py`
- Create: `modules/_test_tools/_create_prefilled_link.py`
- Create: `modules/_test_tools/_generate_pdf.py`
- Create: `modules/_test_tools/_generate_photo.py`
- Create: `modules/_test_tools/_get_photo_from_url.py`
- Create: `modules/_test_tools/_python_auto_gui.py`
- Create: `modules/_test_tools/_shein_order.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p modules/_test_tools
```

- [ ] **Step 2: 复制 Test Tools**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/modules/_test_tools/"*.py modules/_test_tools/
```

- [ ] **Step 3: 验证文件数量**

Command: `ls modules/_test_tools/*.py | wc -l`
Expected: 10

- [ ] **Step 4: 提交**

```bash
git add modules/_test_tools/
git commit -m "feat: add Test Tools module (9 tools)"
```

---

### Task 5: 同步 CircleCI 模块

**Files:**
- Create: `circleCi/__init__.py`
- Create: `circleCi/batch_operations.py`
- Create: `circleCi/batch_ops_view.py`
- Create: `circleCi/commit_search_view.py`
- Create: `circleCi/config_loader.py`
- Create: `circleCi/monitoring.py`
- Create: `circleCi/monitor_view.py`
- Create: `circleCi/pipeline_api.py`
- Create: `circleCi/pipeline_config.py`
- Create: `circleCi/pipeline_data.py`
- Create: `circleCi/pipeline_display.py`
- Create: `circleCi/pipeline_list_view.py`
- Create: `circleCi/triggerJob.py`
- Create: `circleCi/trigger_view.py`

- [ ] **Step 1: 保留原有的 __init__.py**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/circleCi/"*.py circleCi/
```

- [ ] **Step 2: 验证文件数量**

Command: `ls circleCi/*.py | wc -l`
Expected: 14+

- [ ] **Step 3: 提交**

```bash
git add circleCi/
git commit -m "feat: sync CircleCI module with new view components"
```

---

### Task 6: 同步测试文件

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_batch_operations.py`
- Create: `tests/test_jira_extractor.py`
- Create: `tests/test_services_images_extractor.py`
- Create: `tests/test_test_case_importer_logic.py`
- Create: `tests/test_user_config_loader.py`
- Create: `tests/test_commit_search.py`

- [ ] **Step 1: 复制测试文件**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/tests/"*.py tests/
```

- [ ] **Step 2: 检查 test_test_tools 目录**

```bash
cp -r "C:/Users/Daisy Liu/PythonProject/jira-web-app/tests/test_test_tools/" tests/ 2>/dev/null || echo "No test_test_tools dir"
```

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "test: sync tests including test_tools tests"
```

---

### Task 7: 替换 app.py 和 requirements.txt

**Files:**
- Modify: `app.py` (完全替换)
- Modify: `requirements.txt` (完全替换)

- [ ] **Step 1: 备份当前 app.py**

```bash
cp app.py backup_20260602/app.py.demo
```

- [ ] **Step 2: 复制新 app.py**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/app.py" app.py
```

- [ ] **Step 3: 复制 requirements.txt**

```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/requirements.txt" requirements.txt
```

- [ ] **Step 4: 根据 demo 需求调整 app.py 首页标题**

检查 app.py 中是否需要修改项目名称（如保持 qa-toolkit-demo），确认后提交

- [ ] **Step 5: 提交**

```bash
git add app.py requirements.txt
git commit -m "feat: replace app.py and requirements.txt from original"
```

---

### Task 8: 同步配置文件

**Files:**
- Create: `config/users_config_example.json` (完全重写)
- Create: `config/circleci-services.example.txt` (示例文件)
- Delete: `config/users_config.json` (如存在)

- [ ] **Step 1: 创建 users_config_example.json**

创建完全脱敏的配置示例：
```json
{
  "users": {
    "demo_user": {
      "display_name": "演示用户",
      "email": "demo@example.com",
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
  "default_user": "demo_user"
}
```

- [ ] **Step 2: 提交配置**

```bash
git add config/
git commit -m "config: add sanitized example configurations"
```

---

## Phase 3: 脱敏处理

### Task 9: 脱敏替换

**Files:**
- Modify: `modules/user_config_loader.py` (URL 占位符)
- Modify: `modules/jira_extractor.py` (URL 占位符)
- Modify: `modules/jira_operations_helper.py` (URL 占位符)
- Modify: `modules/github_kustomize_client.py` (仓库名占位符)
- Modify: `modules/argocd_client.py` (URL 占位符)
- Modify: `circleCi/triggerJob.py` (组织名占位符)
- Modify: `circleCi/pipeline_config.py` (组织名占位符)

- [ ] **Step 1: 检查需要脱敏的文件**

```bash
grep -l "qima" modules/*.py circleCi/*.py
```

- [ ] **Step 2: 执行脱敏替换**

使用 Edit 工具逐一替换：

| 原始值 | 替换值 |
|--------|--------|
| `qima.atlassian.net` | `your-jira.atlassian.net` |
| `asiainspection` | `your-org` |
| `back-office-cloud` | `your-project` |
| `jenkins.qima.com` | `jenkins.example.com` |
| `qcore-apps-descriptors` | `your-org/your-repo` |
| `master` | `main` |

**每个文件使用 Edit 工具的 replace_all 参数进行替换**

- [ ] **Step 3: 验证无遗漏**

Command: `grep -r "qima" modules/ circleCi/ --include="*.py"`
Expected: 无结果

- [ ] **Step 4: 提交**

```bash
git add modules/ circleCi/
git commit -m "refactor: sanitize sensitive information with placeholders"
```

---

## Phase 4: 资源处理

### Task 10: 创建图片目录并压缩复制图片

**Files:**
- Create: `docs/images/` (目录)
- Create: `docs/images/*.gif` (压缩后)
- Create: `docs/images/*.png`

- [ ] **Step 1: 创建目标目录**

```bash
mkdir -p docs/images
```

- [ ] **Step 2: 列出原项目图片**

```bash
ls -la "C:/Users/Daisy Liu/PythonProject/jira-web-app/docs/images/"
```

- [ ] **Step 3: 尝试压缩 GIF 文件**

检查 gifsicle 是否可用：
```bash
gifsicle --version 2>/dev/null || echo "gifsicle not available"
```

如果可用，压缩并复制：
```bash
for f in "C:/Users/Daisy Liu/PythonProject/jira-web-app/docs/images/"*.gif; do
  gifsicle --optimize=3 --colors 256 "$f" -o "docs/images/$(basename $f)"
done
```

如果不可用，直接复制：
```bash
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/docs/images/"*.gif docs/images/
cp "C:/Users/Daisy Liu/PythonProject/jira-web-app/docs/images/"*.png docs/images/
```

- [ ] **Step 4: 验证图片数量**

Command: `ls docs/images/ | wc -l`
Expected: 8

- [ ] **Step 5: 提交**

```bash
git add docs/images/
git commit -m "docs: add demo screenshots (8 images)"
```

---

## Phase 5: 更新 README

### Task 11: 更新 README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 读取原项目 README**

确认原项目 README 中的功能描述和截图引用

- [ ] **Step 2: 创建新的 README（完全重写）**

保留以下结构：
- 项目标题和徽章
- 功能列表（7个工具）
- 快速开始
- 配置说明（简化版，仅结构）
- 项目结构
- 测试说明

**关键替换：**
- `docs/images/*` 路径引用保持一致
- 移除具体的 URL/IP/域名
- 简化配置示例，只展示 JSON 结构

- [ ] **Step 3: 验证图片路径正确**

检查 README 中所有 `docs/images/` 引用对应的文件是否存在

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: update README with sanitized content and screenshots"
```

---

## Phase 6: 验证

### Task 12: 验证功能

- [ ] **Step 1: 语法检查**

```bash
python -m py_compile app.py pages/*.py modules/*.py modules/_test_tools/*.py circleCi/*.py
```

- [ ] **Step 2: 运行测试（可选）**

```bash
pytest tests/ -v --tb=short -x
```

- [ ] **Step 2: 尝试启动应用**

```bash
cd "C:/Users/Daisy Liu/cv/myProjects/qa-toolkit-demo"
streamlit run app.py --server.headless true --server.port 8501 &
sleep 5
curl -s http://localhost:8501 | grep -q "DevOps" && echo "App started successfully"
```

- [ ] **Step 4: 验证页面可访问**

检查 7 个页面文件都存在且无语法错误

- [ ] **Step 5: 提交最终验证**

```bash
git add -A
git commit -m "chore: complete integration verification"
```

---

## 自检清单

执行后验证：

1. **Spec coverage:** 每个设计要求都有对应的 task
2. **Placeholder scan:** 无 "TBD"、"TODO" 等占位符
3. **Type consistency:** 文件名、方法名一致
4. **功能完整:** 7 个页面、9 个 Test Tools、完整模块
5. **脱敏完成:** 所有 "qima" 域名已替换
6. **资源就位:** 8 张截图在 docs/images/

---

## 完成后清理

- [ ] 删除 `backup_20260602/` 目录

```bash
rm -rf backup_20260602/
```

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-02-qa-toolkit-integration.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?