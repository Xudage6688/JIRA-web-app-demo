# Operations Runbook

## Application Overview

**Application**: QA DevOps Toolkit
**Technology**: Streamlit (Python)
**Port**: 9999 (configured in `.streamlit/config.toml`)
**Configuration**: JSON-based multi-user config

---

## Deployment Procedures

### Local Development Deployment

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure user credentials
# Copy config/users_config.example.json to config/users_config.json
# Edit with your API tokens

# 3. Start application
streamlit run app.py

# 4. Access at http://localhost:9999
```

### Production Deployment (Streamlit Cloud)

```bash
# 1. Ensure requirements.txt is updated
pip freeze > requirements.txt

# 2. Push to connected repository
git push origin main

# 3. Streamlit Cloud auto-deploys
```

### Rollback Procedure

```bash
# 1. Identify stable commit
git log --oneline -10

# 2. Revert to previous version
git revert HEAD

# 3. Or reset to specific commit
git reset --hard <commit-hash>

# 4. Force push (if needed)
git push --force origin main
```

---

## Monitoring and Health Checks

### Application Health

| Check | Method | Expected |
|-------|--------|----------|
| Application running | `curl localhost:8501` | HTTP 200 |
| User config loaded | Check sidebar | Shows user list |
| API tokens valid | Use sidebar connection test | Success message |

### Key Metrics to Monitor

| Metric | Tool | Threshold |
|--------|------|-----------|
| Page load time | Browser DevTools | < 3 seconds |
| API response time | Network tab | < 10 seconds |
| Error rate | Application logs | < 5% |

### Log Locations

| Log Type | Location |
|----------|----------|
| Application logs | Console output |
| Error logs | `logs/app.log` (fallback) |
| API errors | Network tab + console |

---

## Common Issues and Fixes

### Issue: "User not selected" Error

**Symptoms**: Page shows error about user not selected

**Fix**:
1. Navigate to main page (`app.py`)
2. Select user from sidebar dropdown
3. Proceed to tool page

---

### Issue: API Token Invalid

**Symptoms**: Tool shows authentication errors

**Fix**:
1. Check `config/users_config.json`
2. Verify token format (Jira, CircleCI, GitHub, Jenkins)
3. Regenerate token if expired
4. Update config file

---

### Issue: Jenkins Connection Failed

**Fix**:
1. Use sidebar connection test button
2. Verify username format
3. Check Jenkins URL is correct
4. Regenerate API token from Jenkins

---

### Issue: CircleCI Pipeline Query Timeout

**Fix**:
1. Reduce service selection
2. Check network connectivity
3. Verify CircleCI API token valid
4. Check for API rate limits

---

### Issue: Test Cases Import Fails

**Fix**:
1. Check Excel/template format matches expected
2. Verify Xray client credentials in config
3. Check Jira project exists
4. Verify test set key is valid

---

### Issue: Batch Operations Timeout

**Fix**:
1. Reduce number of services (recommended max 20)
2. Check network connectivity
3. Verify CircleCI API token valid
4. Retry with smaller batch size

---

## Security Considerations

### Token Management

| Best Practice | Description |
|---------------|-------------|
| Never commit tokens | Use `gitignore` for config files |
| Rotate tokens regularly | Refresh every 90 days |
| Use minimal scope | Only required permissions |
| Audit access | Review who has tokens |

---

## Performance Optimization

### Concurrent API Calls

The application uses `ThreadPoolExecutor(max_workers=10)` for:
- CircleCI pipeline queries
- Sprint board queries
- Workflow jobs fetching

---

## Maintenance Tasks

### Weekly Tasks

| Task | Command/Action |
|------|----------------|
| Check test coverage | `pytest tests/ --cov=. --cov-report=term` |
| Update dependencies | `pip list --outdated` |
| Review error logs | Check console for warnings |

### Monthly Tasks

| Task | Action |
|------|--------|
| Rotate API tokens | Regenerate and update config |
| Review user access | Audit users_config.json |
| Update documentation | Sync with code changes |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/users_config.json` | User credentials and tokens |
| `config/circleci-services.txt` | CircleCI service list |

---

## API Rate Limits

| API | Rate Limit | Handling |
|-----|------------|----------|
| Jira | 100 req/min | Sequential calls |
| CircleCI | No documented limit | 10 concurrent workers |
| GitHub | 5000 req/hour | Minimal usage |
| Jenkins | No documented limit | Sequential calls |

---

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| v4.4 | 2026-05-11 | Batch operations feature, batch trigger/approve |
| v4.3 | 2026-04-27 | Commit ID search feature, multi-environment approvals |
| v4.2 | 2026-04-08 | Clipboard import for test cases |
| v4.1 | 2026-03-25 | CircleCI tab refactoring, HTTP session reuse |
| v4.0 | 2026-03-24 | Auth consolidation, test coverage establishment |