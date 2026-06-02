# Development Guide

> 📖 **Languages:** [English](./development.md) | [中文](./development.zh.md)

---

## Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- **Git** (version control)

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd qa-toolkit-demo
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configuration

### Copy and Configure User Settings

```bash
# Copy example config
cp config/users_config_example.json config/users_config.json

# Edit with your credentials
# IMPORTANT: Never commit users_config.json to version control
```

### Configuration File Structure

```json
{
  "users": {
    "your_username": {
      "display_name": "Your Name",
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

## Running the Application

### Start Streamlit

```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`

### Running in Headless Mode

```bash
streamlit run app.py --server.headless true --server.port 8501
```

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### Run Specific Test File

```bash
pytest tests/test_jira_extractor.py -v
```

### Test Files

| File | Description |
|------|-------------|
| `test_user_config_loader.py` | User config loader tests |
| `test_jira_extractor.py` | Jira extractor tests |
| `test_test_case_importer_logic.py` | Test case import logic tests |
| `test_commit_search.py` | Commit search tests |
| `test_services_images_extractor.py` | Services images tests |
| `test_batch_operations.py` | Batch operations tests |

---

## Project Structure

```
qa-toolkit-demo/
├── app.py                    # Main Streamlit app
├── pages/                    # Multi-page app pages
│   ├── 1_📊_Jira_Affects_Project.py
│   ├── 2_🐳_Services_Images_Extractor.py
│   ├── 3_🌐_Open_PR_Url.py
│   ├── 4_🚀_CircleCI_Pipeline.py
│   ├── 5_📝_Jira_Operations.py
│   ├── 6_🔧_Jenkins_Deploy.py
│   └── 7_🧪_Test_Tools.py
├── modules/                  # Business logic modules
│   ├── _test_tools/         # Test utilities
│   └── *.py
├── circleCi/                # CircleCI tools
└── tests/                    # Unit tests
```

---

## Adding a New Tool

### 1. Create Page File

Create a new file in `pages/` with naming convention:

```bash
pages/8_🔮_New_Tool.py
```

### 2. Page Template

```python
import streamlit as st

st.set_page_config(
    page_title="New Tool",
    page_icon="🔮",
    layout="wide"
)

st.title("🔮 New Tool")

# Your tool implementation here

if __name__ == "__main__":
    # Page-specific startup logic (if needed)
    pass
```

### 3. Add to Test Tools if Needed

If it's a test utility, add module to `modules/_test_tools/`.

---

## Code Standards

- **Python Style**: Follow PEP 8
- **Type Hints**: Use type hints for function parameters and returns
- **Docstrings**: Add docstrings for public functions
- **Testing**: Maintain 80%+ test coverage for new code
- **Error Handling**: Always handle exceptions gracefully

---

## Security Notes

- **Never commit real credentials** to version control
- Use environment variables for sensitive data in production
- The `users_config_example.json` contains placeholders only
- API tokens are masked in the UI when displayed

---

## Common Issues

### Module Not Found

```bash
pip install -r requirements.txt
```

### Port Already in Use

```bash
streamlit run app.py --server.port 8502
```

### Test Import Errors

Ensure all dependencies are installed:
```bash
pip install pytest pytest-cov
```

---

## Contributing

1. Create a feature branch: `git checkout -b feature/new-feature`
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Commit with clear message: `git commit -m "feat: add new feature"`
5. Push and create Pull Request

---

**For questions or issues, please check the main [README.md](./README.md) or [submit an issue](https://github.com/your-repo/issues).**