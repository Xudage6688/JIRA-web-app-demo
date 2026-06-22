# AGENTS.md — QA DevOps Toolkit

简历展示用 Streamlit demo 项目，敏感信息已脱敏。

## 运行命令

```bash
streamlit run app.py              # 启动（port 9999，配置在 .streamlit/config.toml）
pytest tests/ -v --tb=short       # 运行全部测试
pytest tests/test_xxx.py -v       # 运行单个测试文件
pytest tests/ --cov=. --cov-report=term-missing  # 覆盖率报告（目标 ≥80%）
```

## 项目结构要点

- **入口** `app.py` → 7 个页面在 `pages/`，命名格式 `N_<emoji>_<Name>.py`（Streamlit 自动发现）
- **`_` 前缀模块**（`_test_case_importer_logic.py`、`_services_images_logic.py`、`_test_tools/`）是纯函数层，不含 Streamlit 依赖，可直接单元测试
- **CircleCI 双层结构**：`circleCi/` 包（API 逻辑 + 视图）和 `modules/circleci_pipeline_logic.py`
- **认证集中式**：所有 auth builder（`build_jira_auth_headers` / `build_jenkins_auth` / `build_circleci_headers`）在 `modules/user_config_loader.py:135-156`，新 API 客户端需复用

## 配置与安全

- 需先 `cp config/users_config_example.json config/users_config.json`（后者已 gitignored）
- 所有 token 用 `st.text_input(type="password")` 隐藏
- 错误信息用 `sanitize_error_message()` 脱敏后再展示
- 两个日志系统：`modules/logging_config.py`（推荐新代码使用）和 `jira_extractor.py` 的 `SafeLogger`（旧代码，有文件降级）

## 测试注意

- 使用 `tempfile.NamedTemporaryFile` 而非 pytest `tmpdir` 做配置 mock
- 测试文件用 `sys.path.insert(0, str(project_root))` 导模块
- 19 个测试文件，全部 mock API 调用，无外部依赖

## 编码约定

- 约定式提交：`feat:` / `fix:` / `refactor:` / `test:` / `chore:` / `docs:`
- 连接池复用：CircleCI 模块用全局 `requests.Session()` 实例
