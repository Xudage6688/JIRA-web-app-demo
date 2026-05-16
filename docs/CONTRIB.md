# Contributing Guide

## Development Environment Setup

### Prerequisites
- Python 3.9+
- pip (Python package manager)

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd devops-toolkit
   ```

2. **Create virtual environment (recommended)**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure user credentials**
   ```bash
   # Copy example config
   cp config/users_config.example.json config/users_config.json
   
   # Edit with your credentials
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `streamlit run app.py` | Start the application locally |
| `pytest tests/ -v` | Run all tests with verbose output |
| `pytest tests/ --cov=. --cov-report=term-missing` | Run tests with coverage report |
| `pytest tests/test_batch_operations.py -v` | Run batch operations tests |
| `python -m py_compile pages/*.py` | Check Python syntax |

---

## Configuration

### User Configuration (`config/users_config.json`)

See `config/users_config.example.json` for the full configuration template.

Key sections:
- **jira**: API token, base URL, filter ID, field ID
- **circleci**: API token, VCS type, organization, default project/branch
- **github**: Personal access token with repo scope
- **jenkins**: Username, API token, server URL
- **xray**: Client ID and secret for test case import (optional)

---

## Obtaining API Tokens

### Jira API Token
1. Visit https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the generated token

### CircleCI API Token
1. Login to CircleCI → User Settings → Personal API Tokens
2. Create new token and copy it

### GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope
3. Copy the token

### Jenkins API Token
1. Login to Jenkins → Click username → Configure
2. API Token → Add new Token → Generate
3. Copy the token (shown only once)

---

## Testing

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_batch_operations.py -v
```

### Test Coverage Requirements
- Minimum coverage: **80%**
- Run coverage check: `pytest tests/ --cov=. --cov-fail-under=80`

### Adding New Tests
1. Create test file in `tests/` directory
2. Follow naming convention: `test_<module_name>.py`
3. Use pytest fixtures for common setup
4. Mock external API calls

---

## Project Structure

```
devops-toolkit/
├── app.py                          # Main application entry
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
├── CHANGELOG.md                    # Version history
├── CONTRIBUTING.md                 # Contribution guide
├── config/                         # Configuration files
│   ├── users_config.example.json   # User config template
│   ├── circleci-services.example.txt # Service list template
│   └── argocd_config.example.json  # ArgoCD config template
├── pages/                          # Streamlit pages
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   └── 6_🔧_Jenkins_Deploy.py
├── modules/                        # Shared modules
│   ├── user_config_loader.py
│   ├── jira_extractor.py
│   ├── jira_operations_helper.py
│   ├── test_case_importer.py
│   ├── _test_case_importer_logic.py
│   ├── github_kustomize_client.py
│   └── argocd_client.py
├── circleCi/                       # CircleCI modules
│   ├── triggerJob.py
│   ├── monitoring.py
│   ├── batch_operations.py
│   └── config_loader.py
├── tests/                          # Unit tests
└── docs/                           # Documentation
    ├── RUNBOOK.md
    └── CONTRIB.md
```

---

## Code Style

### Python
- Follow PEP 8 conventions
- Use type annotations on function signatures
- camelCase for functions, PascalCase for classes

### Logging
- Use `logging` module instead of `print()`

### Error Handling
- Handle errors explicitly at every level
- Provide user-friendly error messages in UI
- Log detailed error context on server side

---

## Pull Request Process

1. Create feature branch from `main`
2. Make changes and add tests
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure coverage >= 80%
5. Update documentation if needed
6. Submit pull request with description