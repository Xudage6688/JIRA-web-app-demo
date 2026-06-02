# 开发指南

> 📖 **语言:** [English](./development.md) | [中文](./development.zh.md)

---

## 前置要求

- **Python 3.8+**
- **pip** (Python 包管理器)
- **Git** (版本控制)

---

## 项目初始化

### 1. 克隆仓库

```bash
git clone <仓库URL>
cd qa-toolkit-demo
```

### 2. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# Windows 激活
venv\Scripts\activate

# macOS/Linux 激活
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

---

## 配置

### 复制并配置用户设置

```bash
# 复制示例配置
cp config/users_config_example.json config/users_config.json

# 使用你的凭据编辑
# 重要：不要将 users_config.json 提交到版本控制
```

### 配置文件结构

```json
{
  "users": {
    "your_username": {
      "display_name": "你的名字",
      "email": "your.email@example.com",
      "jira": {
        "api_token": "YOUR_JIRA_TOKEN",
        "base_url": "https://your-company.atlassian.net",
        "filter_id": "YOUR_FILTER_ID",
        "field_id": "customfield_xxxxx"
      },
      "circleci": {
        "api_token": "YOUR_CIRCLECI_TOKEN",
        "vcs_type": "github",
        "organization": "your-org",
        "default_project": "your-project",
        "default_branch": "main"
      },
      "github": {
        "token": "YOUR_GITHUB_TOKEN"
      },
      "jenkins": {
        "username": "YOUR_JENKINS_USER",
        "api_token": "YOUR_JENKINS_TOKEN",
        "jenkins_url": "https://jenkins.example.com"
      }
    }
  },
  "default_user": "your_username"
}
```

---

## 运行应用

### 启动 Streamlit

```bash
streamlit run app.py
```

应用将在 `http://localhost:8501` 可访问

### 无头模式运行

```bash
streamlit run app.py --server.headless true --server.port 8501
```

---

## 测试

### 运行所有测试

```bash
pytest tests/ -v
```

### 带覆盖率运行

```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### 运行特定测试文件

```bash
pytest tests/test_jira_extractor.py -v
```

### 测试文件说明

| 文件 | 说明 |
|------|------|
| `test_user_config_loader.py` | 用户配置加载器测试 |
| `test_jira_extractor.py` | Jira 提取器测试 |
| `test_test_case_importer_logic.py` | 测试用例导入逻辑测试 |
| `test_commit_search.py` | Commit 搜索测试 |
| `test_services_images_extractor.py` | 服务镜像测试 |
| `test_batch_operations.py` | 批量操作测试 |

---

## 项目结构

```
qa-toolkit-demo/
├── app.py                    # 主应用入口
├── pages/                    # 多页面应用
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   ├── 6_🔧_Jenkins_Deploy.py
│   └── 7_🧪_Test_Tools.py
├── modules/                  # 业务逻辑模块
│   ├── _test_tools/         # 测试工具
│   └── *.py
├── circleCi/                # CircleCI 工具
└── tests/                    # 单元测试
```

---

## 添加新工具

### 1. 创建页面文件

在 `pages/` 中创建新文件，命名规范：

```bash
pages/8_🔮_New_Tool.py
```

### 2. 页面模板

```python
import streamlit as st

st.set_page_config(
    page_title="New Tool",
    page_icon="🔮",
    layout="wide"
)

st.title("🔮 New Tool")

# 在此实现你的工具

if __name__ == "__main__":
    # 页面特定启动逻辑（如需要）
    pass
```

### 3. 如需要添加到测试工具

如果是测试工具，请将模块添加到 `modules/_test_tools/`。

---

## 代码规范

- **Python 风格**: 遵循 PEP 8
- **类型提示**: 为函数参数和返回值使用类型提示
- **文档字符串**: 为公共函数添加文档字符串
- **测试**: 新代码保持 80%+ 测试覆盖率
- **错误处理**: 始终优雅地处理异常

---

## 安全注意事项

- **永远不要**将真实凭据提交到版本控制
- 生产环境使用环境变量存储敏感数据
- `users_config_example.json` 仅包含占位符
- UI 中显示时 API tokens 会被遮蔽

---

## 常见问题

### Module Not Found

```bash
pip install -r requirements.txt
```

### 端口已被占用

```bash
streamlit run app.py --server.port 8502
```

### 测试导入错误

确保所有依赖已安装：
```bash
pip install pytest pytest-cov
```

---

## 贡献指南

1. 创建功能分支: `git checkout -b feature/new-feature`
2. 进行你的更改
3. 运行测试: `pytest tests/ -v`
4. 提交并写清消息: `git commit -m "feat: add new feature"`
5. 推送并创建 Pull Request

---

**如有问题，请查看主 [README.zh.md](../README.zh.md) 或 [提交 issue](https://github.com/your-repo/issues)。**