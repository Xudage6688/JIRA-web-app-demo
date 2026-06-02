# QA DevOps Toolkit

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-orange)
![Test Coverage](https://img.shields.io/badge/Coverage-87%25-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

> 📖 **Languages:** [English](./README.md) | [中文](./README.zh.md)

---

**QA DevOps Toolkit** is a Streamlit-based DevOps automation platform that integrates Jira analysis, CircleCI pipeline management, and Jenkins deployment capabilities.

## Tools

| Tool | Description |
|------|-------------|
| 📊 Jira Affects Project | Analyze Jira issues affecting projects with smart deduplication |
| 🐳 Services Images Extractor | Extract container image versions from GitHub with multi-environment comparison |
| 🌐 Open PR Url | Quick-open tool for PR links |
| 🚀 CircleCI Pipeline | Pipeline triggering, querying, monitoring, and approval management |
| 📝 Jira Operations | Issue management supporting create, search, and batch Resolution updates |
| 🔧 Jenkins Deploy | One-click deployment supporting sequential/concurrent modes with live logs |
| 🧪 Test Tools | Collection of daily testing utilities, all running locally |

---

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
streamlit run app.py
```

### Access

```
http://localhost:8501
```

---

## Configuration

Edit `config/users_config_example.json` to configure authentication credentials for each user:

```json
{
  "users": {
    "username": {
      "display_name": "Your Name",
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

Service list configuration: Edit `config/circleci-services.txt`, one CircleCI service name per line.

---

## Screenshots

### 📊 Jira Affects Project

Analyze Jira issues affecting projects with smart deduplication

![Jira Affects Project](docs/images/Jira%20Affects%20Project.gif)

### 🐳 Services Images Extractor

Extract container image versions from GitHub with multi-environment comparison

![Services Images](docs/images/Services%20Images.gif)

### 🌐 Open PR Url

Quick-open tool for PR links

![Open PR Url](docs/images/PRs%20open.gif)

### 🚀 CircleCI Pipeline

Pipeline triggering, querying, monitoring, and approval management

![CircleCI Pipeline](docs/images/CircleCI%20Pipeline.gif)

### 📝 Jira Operations Tool

Issue management supporting create, search, and batch Resolution updates

![Jira Operations](docs/images/Jira%20Operations.gif)

### 🔧 Jenkins Deploy

One-click deployment supporting sequential/concurrent modes with live logs

![Jenkins Deploy](docs/images/Jenkins%20Deploy.gif)

### 🧪 Test Tools

Collection of daily testing utilities, all running locally

![Test Tools](docs/images/Test%20tools.png)

---

## Project Structure

```
qa-toolkit-demo/
├── app.py                           # Main application entry point
├── requirements.txt                 # Dependencies
├── README.md                        # Project documentation (English)
├── README.zh.md                     # 项目文档（中文）
├── config/                          # Configuration directory
│   ├── users_config_example.json   # User config template with placeholders
│   ├── circleci-services.txt       # CircleCI service list
│   └── argocd_config.example.json  # ArgoCD config template
├── pages/                           # Streamlit multi-page app
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   ├── 6_🔧_Jenkins_Deploy.py
│   └── 7_🧪_Test_Tools.py
├── modules/                         # Shared modules
│   ├── user_config_loader.py        # Multi-user config loader + auth builder
│   ├── jira_extractor.py           # Jira data extractor (with SafeLogger)
│   ├── jira_operations_helper.py   # Jira business operations helper
│   ├── test_case_importer.py       # Test Cases import UI layer
│   ├── _test_case_importer_logic.py # Test Cases import pure function layer
│   ├── github_kustomize_client.py  # GitHub Kustomize image query
│   └── _test_tools/                # Test utilities (9 tools)
│       ├── _api_perf_test.py
│       ├── _create_aca_account.py
│       ├── _generate_pdf.py
│       └── ...
├── circleCi/                        # CircleCI tools module
│   ├── triggerJob.py
│   ├── monitoring.py
│   ├── batch_operations.py
│   ├── config_loader.py
│   └── ...
└── tests/                           # Unit tests
    ├── test_user_config_loader.py
    ├── test_jira_extractor.py
    ├── test_test_case_importer_logic.py
    ├── test_commit_search.py
    ├── test_services_images_extractor.py
    └── test_batch_operations.py
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_commit_search.py -v
```

**Coverage Includes:**
- Authentication builders: `build_jira_auth_headers`, `build_jenkins_auth`, `build_circleci_headers`
- `SafeLogger` log downgrade
- `JiraExtractor` core methods
- `UserConfigLoader` full functionality
- Test Cases import pure function layer
- Commit ID search functionality
- Multi-environment approval info retrieval
- Batch triggering and approval functions

**Current Coverage:** 87%

---

## Documentation

- [Development Guide](./docs/guides/development.md) - Setup and development
- [开发指南](./docs/guides/development.zh.md) - 环境配置与开发

---

## Changelog

### v5.0 (2026-06-02)
- **Open Source Version**: Renamed to QA DevOps Toolkit
- **Full Sanitization**: Removed all company-specific domain references
- **Config Templates**: Provided `config/users_config_example.json` configuration template

### v4.5 (2026-06-01)
- Added shields.io badges for visual enhancement
- Added functional demo GIFs/PNGs for all 7 tool pages
- GIFs distributed under each tool's detailed description for easy reference

### v4.4 (2026-05-11)
- Batch Operations (Tab5): New Tab 5, support batch triggering multiple services to specified branch
- Service List Text Input: Support pasting multi-line service names for quick selection
- Batch Approve Preprod: Scan and one-click approve all pending Jobs
- Batch Operations Module: Added `circleCi/batch_operations.py` pure function layer
- Unit Tests: Added 17 batch operation tests, coverage increased from 85% to 87%
- Security Fix: Removed Token fragment display in sidebar to prevent sensitive info leakage

### v4.3 (2026-04-27)
- Commit ID Search (Tab4): New Tab 4, support cross-service search for pipeline by commit hash prefix
- Multi-environment Approval Display: Support dev/staging/preprod/uat/prod environment approval status
- Logging System Upgrade: All `print()` replaced with `logging` module
- Coverage Improvement: Added 51 unit tests, coverage increased from 66% to 85%

### v4.0 (2026-03-24)
- Unified Authentication System: Jira/Jenkins/CircleCI authentication logic consolidated to `user_config_loader.py`
- Test Cases Module Refactoring: UI layer and business logic layer separated, supporting unit testing
- Sprint Query Concurrency: Board Sprint query changed to 10-thread concurrent, 33 Board scenario reduced from seconds to sub-second
- Test Coverage Established: Added 58 unit tests

---

**Version**: 5.0 | **Last Updated**: 2026-06-02 | **Maintainer**: Daisy Liu