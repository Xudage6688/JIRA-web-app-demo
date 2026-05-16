# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v4.4] - 2026-05-11

### Added
- **Batch Operations Tab**: New module for bulk service operations
  - Text input for service list
  - Batch trigger multiple services to specified branch
  - Batch approval for Preprod environment
- Pure function logic layer for batch operations
- 17 new batch operation tests

### Changed
- Test coverage improved from 85% to 87%

### Fixed
- **Security**: Removed token fragment display from sidebar
- Exception handling optimization for batch operations

---

## [v4.3] - 2026-04-27

### Added
- **Commit ID Search Tab**: Cross-service pipeline search functionality
  - Search pipelines by commit ID across all services
  - Multi-environment approval status display
- Enhanced logging system with log level management

### Changed
- Test coverage improved from 66% to 85%
- Refactored search logic for better performance

---

## [v4.2] - 2026-04-08

### Added
- Clipboard import for Test Cases
  - Direct paste from clipboard
  - Auto-formatting and validation

---

## [v4.1] - 2026-03-25

### Added
- CircleCI Tab refactoring with enhanced UI
- Branch copy button for quick branch selection

### Changed
- HTTP connection pool reuse optimization
- Workflow Jobs concurrent fetching with ThreadPoolExecutor

### Performance
- Reduced API call latency through connection pooling

---

## [v4.0] - 2026-03-24

### Added
- Unified authentication system architecture
  - Per-user isolated token management
  - Centralized auth builder
- SafeLogger module for Streamlit stderr safe handling
  - File fallback for exception scenarios
  - Graceful degradation on logging errors

### Changed
- **Major Refactoring**: Test Cases module restructure
  - UI components separated from business logic
  - Pure function architecture for testability
- Sprint query optimization with concurrent execution
  - 10-thread ThreadPoolExecutor
  - Sub-second response for 33+ Scrum boards

### Added
- Test coverage foundation established
- Initial unit test suite

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| v4.4 | 2026-05-11 | Batch Operations, Security Fix |
| v4.3 | 2026-04-27 | Commit ID Search, 85% Coverage |
| v4.2 | 2026-04-08 | Clipboard Import |
| v4.1 | 2026-03-25 | CircleCI Refactor, Connection Pool |
| v4.0 | 2026-03-24 | Auth System, SafeLogger, TDD Foundation |

---

[Unreleased]: https://github.com/demo-developer/devops-toolkit/compare/v4.4...HEAD
[v4.4]: https://github.com/demo-developer/devops-toolkit/compare/v4.3...v4.4
[v4.3]: https://github.com/demo-developer/devops-toolkit/compare/v4.2...v4.3
[v4.2]: https://github.com/demo-developer/devops-toolkit/compare/v4.1...v4.2
[v4.1]: https://github.com/demo-developer/devops-toolkit/compare/v4.0...v4.1
[v4.0]: https://github.com/demo-developer/devops-toolkit/releases/tag/v4.0