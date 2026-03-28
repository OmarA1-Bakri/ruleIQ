# TODO Management Guide

Comprehensive guide for managing technical debt markers (TODO, FIXME, HACK, XXX, etc.) in the RuleIQ codebase.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [TODO Format Standard](#todo-format-standard)
- [Severity Levels](#severity-levels)
- [Workflow](#workflow)
- [Tools and Scripts](#tools-and-scripts)
- [Enforcement](#enforcement)
- [Migration Guide](#migration-guide)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Examples](#examples)

## Overview

### What is the TODO Management System?

The TODO Management System ensures all technical debt markers in the codebase are tracked, prioritized, and linked to GitHub issues. This prevents technical debt from accumulating silently and ensures systematic resolution.

### Benefits

- **Visibility**: All technical debt is tracked and visible in GitHub issues
- **Prioritization**: Severity levels help prioritize what to fix first
- **Accountability**: Issue assignment creates clear ownership
- **Prevention**: Pre-commit hooks prevent new untracked debt
- **Metrics**: Track technical debt trends over time

### Key Components

1. **Scanner** (`scan_todos.py`): Finds and categorizes all TODO markers
2. **Issue Creator** (`create_todo_issues.py`): Creates GitHub issues for TODOs
3. **Updater** (`update_todo_references.py`): Updates TODO comments with issue references
4. **Pre-commit Hooks**: Enforce policy before commits
5. **CI/CD Workflow**: Validate compliance in GitHub Actions

## Quick Start

### For New TODOs

When you need to add a TODO:

1. Create a GitHub issue describing the work
2. Add the TODO with issue reference:
   ```python
   # TODO(#123): Implement caching for this endpoint
   ```

### For Existing TODOs

To update an existing TODO without an issue reference:

```bash
# Interactive mode (recommended for a few TODOs)
python scripts/ci/update_todo_references.py --interactive

# Or specify directly
python scripts/ci/update_todo_references.py --file path/to/file.py --line 45 --issue 123
```

## TODO Format Standard

### Required Format

All TODO comments must follow this format:

```
MARKER(#ISSUE): Description
```

Where:
- `MARKER`: One of TODO, FIXME, HACK, XXX, OPTIMIZE, BUG, REFACTOR, NOTE
- `#ISSUE`: GitHub issue number (e.g., #123)
- `Description`: Brief description of what needs to be done

### Language-Specific Examples

**Python:**
```python
# TODO(#123): Implement retry logic for database connections
# FIXME(#456): Memory leak in conversation history storage
# HACK(#789): Temporary workaround for API rate limiting
```

**TypeScript/JavaScript:**
```typescript
// TODO(#123): Add input validation for email field
// FIXME(#456): Race condition in state update
/* TODO(#789): Refactor this component into smaller pieces */
```

**YAML:**
```yaml
# TODO(#123): Add production environment configuration
```

**HTML:**
```html
<!-- TODO(#123): Replace with dynamic content from API -->
```

## Severity Levels

### CRITICAL (FIXME, BUG)

**Description**: Broken functionality that needs immediate attention.

**Examples**:
- Memory leaks
- Race conditions
- Data corruption issues
- Security vulnerabilities
- Crashes or errors

**Policy**: **MUST** reference a GitHub issue. Commits blocked by pre-commit hooks.

**Example**:
```python
# FIXME(#234): Memory leak in conversation history - grows unbounded
```

### HIGH (HACK, XXX)

**Description**: Temporary workarounds or problematic code requiring proper solutions.

**Examples**:
- Hardcoded values that should be configurable
- Bypassed validation or security checks
- Temporary workarounds
- Code with known limitations

**Policy**: **MUST** reference a GitHub issue. Commits blocked by pre-commit hooks.

**Example**:
```python
# HACK(#345): Bypassing authentication for internal API calls
# XXX(#456): This approach won't scale beyond 1000 users
```

### MEDIUM (TODO, REFACTOR)

**Description**: Planned improvements or code that needs cleaning up.

**Examples**:
- Missing features
- Code that should be refactored
- Performance improvements (non-critical)
- Technical debt cleanup

**Policy**: Issue reference **recommended** but not enforced. Strong encouragement in code reviews.

**Example**:
```python
# TODO(#567): Add caching to reduce database queries
# REFACTOR(#678): Extract this into separate service class
```

### LOW (OPTIMIZE, NOTE)

**Description**: Nice-to-have optimizations or informational notes.

**Examples**:
- Minor performance optimizations
- Code documentation notes
- Future enhancement ideas

**Policy**: Issue reference **optional**.

**Example**:
```python
# OPTIMIZE: Could use binary search instead of linear scan
# NOTE: This assumes timezone is always UTC
```

## Workflow

### Adding a New TODO

**Step 1**: Assess the severity
- Is it broken? → FIXME/BUG (CRITICAL)
- Is it a workaround? → HACK/XXX (HIGH)
- Is it planned work? → TODO/REFACTOR (MEDIUM)
- Is it optional? → OPTIMIZE/NOTE (LOW)

**Step 2**: Create a GitHub issue (if CRITICAL or HIGH)
- Title: Brief description
- Labels: `technical-debt`, `todo`, severity label, area label
- Description: Detailed context, impact, suggested approach

**Step 3**: Add the TODO comment
```python
# MARKER(#issue): Description
```

**Step 4**: Commit (pre-commit hooks will validate)

### Resolving a TODO

**Step 1**: Implement the fix/feature

**Step 2**: Remove the TODO comment

**Step 3**: Close the GitHub issue with a reference in your commit:
```bash
git commit -m "fix: implement caching layer (closes #123)"
```

## Tools and Scripts

### scan_todos.py

**Purpose**: Scan codebase for TODO markers and generate reports.

**Basic Usage**:
```bash
# Generate markdown report
python scripts/ci/scan_todos.py --format markdown --output TODO_INVENTORY.md

# Show statistics only
python scripts/ci/scan_todos.py --stats-only

# Enforce policy (used in CI/CD)
python scripts/ci/scan_todos.py --enforce --severity CRITICAL --severity HIGH
```

**Advanced Options**:
```bash
# Filter by severity
python scripts/ci/scan_todos.py --severity CRITICAL

# Generate JSON for programmatic processing
python scripts/ci/scan_todos.py --format json --output todos.json

# Generate CSV for spreadsheet tracking
python scripts/ci/scan_todos.py --format csv --output todos.csv
```

### create_todo_issues.py

**Purpose**: Automatically create GitHub issues for TODOs without issue references.

**Setup**:
```bash
# Set GitHub token (required)
export GITHUB_TOKEN=<set-your-github-token-locally>
```

**Basic Usage**:
```bash
# Dry run to see what would be created
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --dry-run

# Create issues for CRITICAL severity
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --severity CRITICAL
```

**Advanced Options**:
```bash
# Batch similar TODOs into single issues
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --batch-similar

# Limit number of issues created
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --max-issues 20
```

### update_todo_references.py

**Purpose**: Update TODO comments to include GitHub issue references.

**Basic Usage**:
```bash
# Interactive mode (recommended)
python scripts/ci/update_todo_references.py --interactive

# Batch update from mapping file (after create_todo_issues.py)
python scripts/ci/update_todo_references.py --mapping issues.json

# Update specific TODO
python scripts/ci/update_todo_references.py \
  --file services/ai/assistant.py \
  --line 234 \
  --issue 567
```

**Advanced Options**:
```bash
# Dry run to preview changes
python scripts/ci/update_todo_references.py --mapping issues.json --dry-run

# Preview a specific update
python scripts/ci/update_todo_references.py \
  --file services/ai/assistant.py \
  --line 234 \
  --issue 567 \
  --preview
```

## Enforcement

### Pre-commit Hooks

**What they do**:
- Block commits with CRITICAL/HIGH severity TODOs without issue references
- Provide helpful error messages with fix instructions

**Installation**:
```bash
pip install pre-commit
pre-commit install
```

**Testing**:
```bash
# Run all hooks manually
pre-commit run --all-files

# Run TODO hooks specifically
pre-commit run enforce-todo-policy --all-files
pre-commit run validate-todo-format --all-files
```

**Example Error Message**:
```
❌ Found 2 non-compliant TODOs (missing issue references)
  services/ai/assistant.py:234 - FIXME: Memory leak in conversation history
  api/routers/chat.py:567 - HACK: Bypassing rate limit check

⚠️ Policy: CRITICAL and HIGH severity TODOs must reference a GitHub issue.
📝 Format: TODO(#123): Description
📖 See CONTRIBUTING.md for details
```

### CI/CD Workflow

**What it does**:
- Runs on every push and pull request
- Fails builds if policy is violated
- Generates weekly TODO inventory reports
- Posts helpful comments on PRs with violations

**Workflow File**: `.github/workflows/todo-enforcement.yml`

**Manual Trigger**:
```bash
# Generate report manually via GitHub UI:
# Actions → TODO Policy Enforcement → Run workflow → Check "generate_report"
```

## Migration Guide

### Migrating Existing TODOs

**Phase 1: Generate Inventory**

```bash
# Generate comprehensive TODO inventory
python scripts/ci/scan_todos.py --format markdown --output TODO_INVENTORY.md
python scripts/ci/scan_todos.py --format json --output TODO_INVENTORY.json
```

Review the inventory to understand the scope.

**Phase 2: Create Issues for High-Priority TODOs**

```bash
# CRITICAL severity (do this first)
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --severity CRITICAL

# HIGH severity
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --severity HIGH

# MEDIUM severity (batch similar ones)
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --severity MEDIUM \
  --batch-similar
```

**Phase 3: Update TODO Comments**

```bash
# Update TODOs with issue references (from mapping file)
python scripts/ci/update_todo_references.py --mapping issues.json

# Or use interactive mode for manual review
python scripts/ci/update_todo_references.py --interactive
```

**Phase 4: Verify and Commit**

```bash
# Verify no non-compliant TODOs remain
python scripts/ci/scan_todos.py --enforce --severity CRITICAL --severity HIGH

# Commit the updates
git add -A
git commit -m "docs: update TODO comments with GitHub issue references"
```

## Best Practices

### 1. Be Specific

❌ **Bad**:
```python
# TODO: Fix this
# TODO: Improve performance
```

✅ **Good**:
```python
# TODO(#123): Add input validation for email addresses (RFC 5322 compliance)
# TODO(#456): Replace O(n²) algorithm with binary search for 10x speedup
```

### 2. Include Context

❌ **Bad**:
```python
# TODO(#123): Add error handling
```

✅ **Good**:
```python
# TODO(#123): Add error handling for network timeouts
# Currently fails silently, causing data loss when API is slow
```

### 3. Group Related TODOs

When multiple TODOs are part of the same work, use the same issue number:

```python
# TODO(#789): Part 1 - Extract provider interface
class LLMProvider:
    pass

# TODO(#789): Part 2 - Implement OpenAI provider
class OpenAIProvider(LLMProvider):
    pass

# TODO(#789): Part 3 - Add provider factory
def get_provider(name: str) -> LLMProvider:
    pass
```

### 4. Keep TODOs Actionable

Each TODO should be something that can be clearly completed:

❌ **Bad**:
```python
# TODO(#123): Think about scalability
```

✅ **Good**:
```python
# TODO(#123): Add horizontal scaling support via Redis for session storage
```

### 5. Clean Up Completed TODOs

When you implement a TODO, remove the comment:

❌ **Bad**:
```python
# TODO(#123): Add caching - DONE
def get_user(user_id):
    return cache.get_or_fetch(user_id)
```

✅ **Good**:
```python
def get_user(user_id):
    return cache.get_or_fetch(user_id)
```

### 6. Prefer Fixing Over TODO

If a fix is small and straightforward, implement it immediately instead of adding a TODO:

❌ **Bad**:
```python
# TODO(#123): Fix typo in variable name
usr_id = get_user_id()
```

✅ **Good**:
```python
user_id = get_user_id()  # Fixed immediately
```

## Troubleshooting

### Pre-commit Hook Fails

**Problem**: "Found TODO without issue reference"

**Solution**:
1. Create a GitHub issue for the TODO
2. Update the TODO comment: `TODO(#123): Description`
3. Commit again

### Scan Script Not Finding TODOs

**Problem**: `scan_todos.py` reports 0 TODOs but you know they exist

**Possible Causes**:
1. File not tracked by git: `git add` the file
2. File in skip directory: Check `SKIP_DIRECTORIES` in script
3. File extension not scannable: Check `SCANNABLE_EXTENSIONS`

**Debug**:
```bash
# Check which files are being scanned
git ls-files | grep "your_file"

# Run with verbose output
python scripts/ci/scan_todos.py --format markdown -v
```

### Issue Creation Fails

**Problem**: `create_todo_issues.py` fails with authentication error

**Solution**:
1. Verify GitHub token: `echo $GITHUB_TOKEN`
2. Check token permissions: needs `repo` scope
3. Test token: `curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user`

### Update Script Doesn't Work

**Problem**: `update_todo_references.py` says "Could not find TODO marker pattern"

**Possible Causes**:
1. TODO already has issue reference
2. Unusual comment syntax
3. Line number changed

**Solution**:
```bash
# Use preview mode to see what would change
python scripts/ci/update_todo_references.py \
  --file path/to/file.py \
  --line 123 \
  --issue 456 \
  --preview
```

## FAQ

### Q: Do I need an issue for every TODO?

**A**: Only for CRITICAL and HIGH severity (FIXME, BUG, HACK, XXX). MEDIUM severity (TODO, REFACTOR) is strongly recommended. LOW severity (OPTIMIZE, NOTE) is optional.

### Q: Can I have multiple TODOs for the same issue?

**A**: Yes! Use the same issue number for related TODOs that will be addressed together.

### Q: What if I'm working on a feature branch?

**A**: The pre-commit hooks and CI/CD still run. You can temporarily disable them with `git commit --no-verify` if needed, but fix TODOs before merging to main.

### Q: How do I exclude a file from TODO scanning?

**A**: Add the file path or pattern to `IGNORE_PATTERNS` in `scripts/ci/scan_todos.py`.

### Q: Can I use different severity levels?

**A**: No, use the standard markers (TODO, FIXME, HACK, XXX, OPTIMIZE, BUG, REFACTOR, NOTE). The system categorizes them automatically.

### Q: What if I disagree with the severity categorization?

**A**: The severity is based on the marker you use. If a TODO should be CRITICAL, use FIXME or BUG instead of TODO.

### Q: How often are weekly reports generated?

**A**: Every Monday at 9 AM UTC via the scheduled GitHub Actions workflow.

## Examples

### Example 1: Adding a FIXME

```python
# 1. Found a memory leak
class ConversationManager:
    def __init__(self):
        self.history = []  # This grows unbounded!

# 2. Create GitHub issue
# Title: "Memory leak in ConversationManager"
# Labels: bug, technical-debt, critical, backend
# Description: "The conversation history list grows without bounds..."

# 3. Add FIXME with issue reference
class ConversationManager:
    def __init__(self):
        # FIXME(#234): Memory leak - conversation history grows unbounded
        # Need to implement cleanup of conversations older than 24 hours
        self.history = []
```

### Example 2: Batch Update Similar TODOs

```bash
# Scan and find 20 instances of "TODO: Replace with proper logging"
python scripts/ci/scan_todos.py --format markdown

# Create single issue for all of them
python scripts/ci/create_todo_issues.py \
  --token $GITHUB_TOKEN \
  --repo OmarA1-Bakri/ruleIQ \
  --batch-similar \
  --severity MEDIUM

# Output: Created issue #567 "Implement structured logging infrastructure (20 locations)"

# Update all 20 TODOs to reference issue #567
python scripts/ci/update_todo_references.py --mapping issues.json
```

### Example 3: Interactive Migration

```bash
$ python scripts/ci/update_todo_references.py --interactive

🔍 Scanning codebase for TODOs...

Found 45 TODOs without issue references

[1/45] services/ai/assistant.py:234
  FIXME: Memory leak in conversation history
  Severity: CRITICAL

  Context:
    def __init__(self):
        self.history = []  # FIXME: Memory leak
        self.context = {}

  Enter issue number (or 's' to skip, 'q' to quit): 234
  ✅ Updated with issue #234

[2/45] api/routers/chat.py:567
  TODO: Add rate limiting
  Severity: MEDIUM
  ...
```

---

For more information, see:
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Overall contribution guidelines
- [scripts/ci/README.md](../scripts/ci/README.md) - Detailed script documentation
- [EXECUTION_PLAN_TODO_MANAGEMENT.md](../EXECUTION_PLAN_TODO_MANAGEMENT.md) - Implementation roadmap
