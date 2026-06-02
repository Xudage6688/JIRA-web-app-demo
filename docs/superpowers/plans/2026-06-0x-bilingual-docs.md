# Bilingual Documentation Implementation Plan

> **For agentic workers:** This plan can be executed inline. All tasks use simple file operations.

**Goal:** Make project documentation primarily in English while providing Chinese (中文) versions for accessibility.

**Architecture:** Dual-file approach with English as primary and Chinese as secondary. Code comments remain in original language for code readability.

**Tech Stack:** Markdown, Minimal tools (translation as needed)

---

## Documentation Audit

First, identify all documentation files:

```bash
find . -name "*.md" -not -path "./.git/*" | head -20
```

Current documentation files:
| File | Priority | Status |
|------|----------|--------|
| `README.md` | HIGH | Needs bilingual |
| `docs/superpowers/plans/2026-06-02-qa-toolkit-integration.md` | MEDIUM | Keep as working notes |
| `docs/superpowers/specs/2026-06-02-qa-toolkit-integration-design.md` | MEDIUM | Keep as working notes |
| `LICENSE` | HIGH | Already English |

---

## Phase 1: README Strategy

### Task 1: Create Bilingual README Structure

**Files:**
- Modify: `README.md` (English primary)
- Create: `README.zh.md` (Chinese version)

**Step 1: Review current README**

Read current `README.md` structure and content.

**Step 2: Create English version as primary (README.md)**

Ensure main README is comprehensive:
- Project title and badges
- Features list (7 tools)
- Quick start
- Configuration structure (no real tokens)
- Project structure
- Testing instructions
- Contributing guidelines
- License

**Step 3: Create Chinese version (README.zh.md)**

Translate key sections:
- 项目简介
- 功能特点
- 快速开始
- 配置说明
- 项目结构
- 测试说明
- 贡献指南
- 开源许可

**Step 4: Add language indicator badge**

In both files, add language selector note:
```markdown
> 📖 Languages: [English](./README.md) | [中文](./README.zh.md)
```

---

## Phase 2: Documentation Organization

### Task 2: Organize Project Documentation

**Files:**
- Create: `docs/README.md` (project overview in English)
- Create: `docs/README.zh.md` (project overview in Chinese)
- Modify: `docs/guides/` if needed

**Step 1: Create docs folder structure if needed**

```bash
mkdir -p docs/guides
```

**Step 2: Create development guides**

English first, then Chinese translation:
- `docs/guides/development.en.md` or `docs/guides/development.md`
- `docs/guides/development.zh.md`

**Step 3: Add docs index**

```bash
docs/
├── README.md           # This file structure explanation
├── README.en.md        # Project overview (English)
├── README.zh.md        # Project overview (Chinese)
├── guides/
│   ├── development.md   # Dev guide (English)
│   └── development.zh.md # Dev guide (Chinese)
└── superpowers/         # Internal dev notes (keep as is)
    ├── plans/
    └── specs/
```

---

## Phase 3: Internal Documentation

### Task 3: Handle Existing Chinese Documentation

**Decision:** Internal dev docs in superpowers/ are working documents. Keep as-is.

Current internal docs serve the development workflow. They don't need translation since they:
- Are temporary working notes
- Are in the dev docs folder
- Can be expanded later if needed

**Files:**
- Keep: `docs/superpowers/plans/*.md`
- Keep: `docs/superpowers/specs/*.md`

---

## Phase 4: Code Documentation

### Task 4: Code Comments Strategy

**Decision:** Keep code comments in Chinese

Rationale:
- Code is read with IDE/tool support
- Chinese comments help Chinese-speaking collaborators
- English documentation covers usage
- This is a resume showcase project

No changes needed to code comments.

---

## Implementation Tasks Summary

| # | Task | Files | Action |
|---|------|-------|--------|
| 1 | Review current README | README.md | Read |
| 2 | Enhance English README | README.md | Modify |
| 3 | Create Chinese README | README.zh.md | Create |
| 4 | Add language selector | README.md, README.zh.md | Modify |
| 5 | Create docs folder | docs/ | Create |
| 6 | Create docs README files | docs/README*.md | Create |
| 7 | Commit changes | - | Commit |

---

## Validation

After implementation:

1. **Check bilingual coverage:**
```bash
ls *.md README*.md docs/*.md docs/guides/*.md 2>/dev/null | head -20
```

2. **Verify language selector works:**
```markdown
> 📖 Languages: [English](./README.md) | [中文](./README.zh.md)
```

3. **Verify no token leakage in docs:**
```bash
grep -r "token\|password\|secret\|key" docs/ README*.md --include="*.md" | grep -v ".example"
```
Expected: No matches

---

**Plan complete.** Ready to execute in ~30 minutes.

**Two options for execution:**

1. **Same session execution** - I execute tasks directly now
2. **Subagent-driven** - Dispatch subagent per task with reviews

Which approach?