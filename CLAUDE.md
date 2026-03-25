# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Streamlit-based DevOps automation platform integrating Jira, CircleCI, GitHub, and Jenkins tools. Multi-user architecture with per-user authentication tokens stored in `config/users_config.json`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run app.py

# Run tests
pytest tests/ -v

# Run single test file
pytest tests/test_jira_extractor.py -v
```

## Architecture

### Multi-Page Streamlit Structure
- `app.py` - Main landing page with user selector and tool navigation
- `pages/` - Streamlit multi-page modules (1_*, 2_*, etc. prefix controls sidebar order)
- Pages access user config via `st.session_state.current_user`

### Core Modules (`modules/`)
| Module | Purpose |
|--------|---------|
| `user_config_loader.py` | **Auth centralization**: `build_jira_auth_headers()`, `build_jenkins_auth()`, `build_circleci_headers()` - all auth builders unified here |
| `jira_extractor.py` | Jira data extraction with `SafeLogger` (stderr-safe logging), `JiraExtractor` class with `requests.Session` |
| `jira_operations_helper.py` | Jira business operations (Sprint queries with 10-thread concurrency) |
| `github_kustomize_client.py` | GitHub Kustomize镜像查询 |
| `argocd_client.py` | ArgoCD service/image queries |
| `test_case_importer.py` | Test Cases import UI layer |
| `_test_case_importer_logic.py` | Test Cases import pure function logic (testable) |

### CircleCI Modules (`circleCi/`)
- `monitoring.py` - Pipeline status monitoring, workflow retrieval
- `triggerJob.py` - Pipeline triggering
- `config_loader.py` - CircleCI API config

### Configuration (`config/`)
- `users_config.json` - **Multi-user auth tokens** (Jira, CircleCI, GitHub, Jenkins per user)
- `circleci-services.txt` - CircleCI service list (one per line)
- `jira_config.json`, `argocd_config.json`, `circleci_config.json` - Service configs

### Authentication Pattern
All tools use `user_config_loader.py` auth builders:
```python
from modules.user_config_loader import build_jira_auth_headers, build_circleci_headers, build_jenkins_auth
headers = build_jira_auth_headers(email, api_token)  # Returns dict for requests
auth = build_jenkins_auth(username, token)  # Returns HTTPBasicAuth
```

### HTTP Session Pattern
Use `requests.Session()` for connection pooling. CircleCI API calls use session with `Circle-Token` header. Jira uses session with Basic Auth.

### Key Implementation Notes
- **Python 3.12+** required
- **PEP8**: 2-space indentation, camelCase functions, PascalCase classes
- **No hardcoded tokens** - always load via `user_config_loader.py`
- **Streamlit state** - use `st.session_state` for user selection persistence
- **Concurrent Sprint queries** use `ThreadPoolExecutor(max_workers=10)`
- **SafeLogger** in `jira_extractor.py` handles stderr-closed Streamlit environment with file fallback
