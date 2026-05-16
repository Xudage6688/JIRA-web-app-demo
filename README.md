# QA DevOps Toolkit

A DevOps automation platform built with Streamlit, integrating Jira analytics, Docker registry queries, CircleCI pipeline management, and Jenkins deployments. Designed for QA team daily operations at a French inspection company.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-orange)
![Test Coverage](https://img.shields.io/badge/Coverage-87%25-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Screenshots

<!-- Add your screenshots here -->
```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                   [Screenshots Placeholder]             │
│                                                         │
│    Dashboard │ Jira Analytics │ Pipeline Management     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Features

| Module | Description |
|--------|-------------|
| Jira Analytics | Scrum board queries, sprint tracking, test case management |
| Docker Registry | Image queries, tag management, registry browsing |
| CircleCI Integration | Pipeline monitoring, workflow jobs, branch deployment |
| Jenkins Deployment | Service deployment, branch triggering, batch operations |
| Batch Operations | Multi-service deployment, bulk approvals |
| Commit ID Search | Cross-service pipeline search by commit ID |

## Tech Highlights

### Architecture

- **Multi-user Authentication**: Unified auth builder with per-user isolated tokens
- **HTTP Session Pooling**: Connection pool optimization, reducing TCP handshake overhead
- **Concurrent Queries**: ThreadPoolExecutor with 10 threads, enabling sub-second queries for 33+ Scrum boards
- **Safe Logger**: Streamlit stderr safe handling with file fallback for exception scenarios
- **UI/Logic Separation**: Pure function logic layer for easy unit testing
- **Multi-API Fallback**: Enhanced JQL → Legacy API → JQL Direct query strategy

### Testing

- **87% Test Coverage**: 58+ unit tests covering core business logic
- **TDD Workflow**: Test-first development methodology
- **Pytest Framework**: Comprehensive test suite with fixtures and mocks

## Quick Start

### Prerequisites

- Python 3.8+
- pip or poetry for dependency management

### Installation

```bash
# Clone the repository
git clone https://github.com/demo-developer/devops-toolkit.git
cd devops-toolkit

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Jira Configuration
JIRA_BASE_URL=https://demo.example.com
JIRA_USER_EMAIL=demo@example.com

# CircleCI Configuration
CIRCLECI_API_URL=https://circleci.example.com/api/v2

# Jenkins Configuration
JENKINS_URL=https://jenkins.example.com

# Docker Registry
REGISTRY_URL=https://registry.example.com
```

### Run the Application

```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`.

## Project Structure

```
devops-toolkit/
├── app.py                    # Main Streamlit application
├── auth/                     # Authentication module
│   └── builder.py           # Unified auth builder
├── core/                     # Core utilities
│   ├── http_pool.py         # HTTP session pooling
│   ├── safe_logger.py       # Safe logging handler
│   └── concurrency.py       # ThreadPoolExecutor utilities
├── modules/                   # Feature modules
│   ├── jira/                # Jira integration
│   │   ├── ui.py           # UI components
│   │   └── logic.py        # Business logic
│   ├── circleci/           # CircleCI integration
│   ├── jenkins/             # Jenkins integration
│   └── registry/            # Docker registry
├── tests/                    # Test suite
│   ├── conftest.py          # Pytest fixtures
│   ├── test_jira.py
│   ├── test_circleci.py
│   └── test_batch.py
├── requirements.txt          # Dependencies
└── pyproject.toml           # Project configuration
```

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

Coverage report will be generated at `htmlcov/index.html`.

### Test Structure

| Category | Tests | Coverage |
|----------|-------|----------|
| Authentication | 8 | 92% |
| Jira Module | 15 | 88% |
| CircleCI Module | 12 | 85% |
| Batch Operations | 17 | 87% |
| Core Utilities | 6 | 95% |

## Development

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for public functions
- Keep functions under 50 lines

### Commit Convention

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf, ci
```

### Branch Strategy

- `main` - Stable release branch
- `develop` - Development branch
- `feature/*` - Feature branches
- `hotfix/*` - Hotfix branches

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:

- Fork and branch workflow
- Pull request process
- Code review guidelines
- Testing requirements

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built for QA team automation at a French inspection company.

---

**Maintainer**: Demo Developer  
**Contact**: demo@example.com  
**Repository**: https://github.com/demo-developer/devops-toolkit