# Contributing Guide

Thank you for your interest in contributing to QA DevOps Toolkit! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Git Workflow](#git-workflow)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Format](#commit-message-format)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please be considerate of others and follow standard open-source community guidelines.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment
4. Create a feature branch
5. Make your changes
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.8 or higher
- pip or poetry
- Git

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/devops-toolkit.git
cd devops-toolkit

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks (optional but recommended)
pre-commit install

# Run tests to verify setup
pytest tests/ -v
```

### Dependencies

| Package | Purpose |
|---------|---------|
| streamlit | Web framework |
| requests | HTTP client |
| pytest | Testing framework |
| pytest-cov | Coverage reporting |
| black | Code formatting |
| ruff | Linting |

## Git Workflow

### Branch Naming Convention

```
feature/description    # New features
fix/description        # Bug fixes
refactor/description   # Code refactoring
docs/description       # Documentation updates
test/description       # Test additions/updates
chore/description      # Maintenance tasks
```

### Branch Workflow

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

### Keep Your Branch Updated

```bash
git checkout main
git pull upstream main
git checkout feature/your-feature-name
git rebase main
```

## Pull Request Process

### Before Submitting

- [ ] Code follows project coding standards
- [ ] All tests pass locally
- [ ] New features have corresponding tests
- [ ] Test coverage remains at 80% or above
- [ ] Documentation updated if needed
- [ ] Commit messages follow convention

### PR Checklist

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Coverage >= 80%

## Screenshots (if applicable)
```

### Review Process

1. Submit PR against `main` branch
2. Automated checks must pass (tests, lint, coverage)
3. At least one approval required
4. Squash merge to main

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) guidelines
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use double quotes for strings

### Function Structure

```python
def process_data(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process input data and return results.
    
    Args:
        input_data: Dictionary containing input parameters
        
    Returns:
        Dictionary containing processed results
        
    Raises:
        ValueError: If input_data is invalid
    """
    # Implementation
    pass
```

### File Organization

- One class per file for complex classes
- Related functions can share a file
- Keep files under 400 lines
- Functions under 50 lines

### Import Order

```python
# Standard library
import os
import sys

# Third-party packages
import requests
import streamlit as st

# Local imports
from core.http_pool import get_session
from modules.jira.logic import fetch_boards
```

## Testing Guidelines

### Test Structure

```python
# tests/test_module.py

import pytest
from unittest.mock import Mock, patch


class TestFeature:
    """Test suite for feature X."""
    
    def test_normal_case(self):
        """Test normal operation."""
        pass
    
    def test_edge_case(self):
        """Test edge conditions."""
        pass
    
    def test_error_handling(self):
        """Test error scenarios."""
        pass
```

### Test Naming Convention

```python
# Pattern: test_<function>_<scenario>_<expected_result>

def test_fetch_boards_when_api_returns_data_returns_list():
    pass

def test_fetch_boards_when_api_fails_raises_exception():
    pass

def test_fetch_boards_with_empty_response_returns_empty_list():
    pass
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_jira.py

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run with verbose output
pytest tests/ -v -s
```

### Coverage Requirements

- Overall coverage: **minimum 80%**
- New code: **minimum 80%**
- Critical paths: **minimum 90%**

## Commit Message Format

### Format

```
<type>: <subject>

<body>

<footer>
```

### Types

| Type | Description |
|------|-------------|
| feat | New feature |
| fix | Bug fix |
| refactor | Code refactoring |
| docs | Documentation |
| test | Test additions |
| chore | Maintenance |
| perf | Performance |
| ci | CI/CD changes |

### Examples

```bash
# Feature
feat: add batch operations tab for multi-service deployment

# Bug fix
fix: resolve token display issue in sidebar

# Refactor
refactor: separate UI and logic in test cases module

# Documentation
docs: update README with new configuration options

# Test
test: add 17 tests for batch operations module
```

### Subject Guidelines

- Use imperative mood ("add" not "added")
- Don't capitalize first letter
- No period at the end
- Maximum 72 characters

## Questions?

If you have questions, feel free to:

1. Open a GitHub Issue
2. Contact the maintainer: demo@example.com

---

Thank you for contributing!