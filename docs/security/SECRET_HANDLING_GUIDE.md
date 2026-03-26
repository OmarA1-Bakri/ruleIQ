# Secret Handling Guardrails

This document explains the day-to-day guardrails that keep RuleIQ free from
credential leaks and security vulnerabilities.

## Required Environment Variables

The following environment variables are **REQUIRED** and the application will fail to start if they are not set:

### Database Credentials
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `NEO4J_URI` - Neo4j database URI
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password ⚠️ **NEVER use default passwords**

### Authentication & Encryption
- `JWT_SECRET` - JWT token signing key
- `SECRET_KEY` - Application secret key
- `FERNET_KEY` - Encryption key for sensitive data

### AI Services (at least one required)
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key (optional)
- `GOOGLE_AI_API_KEY` - Google AI API key (optional)

### Validation
Run `python scripts/validate_required_env_vars.py` to check your configuration.

## Local Development
- Install pre-commit once by running `pip install pre-commit && pre-commit install`.
- Commit workflows automatically run `scripts/ci/scan_secrets.py`. You can run it on demand via
  `python3 scripts/ci/scan_secrets.py`.
- Store real secrets in Doppler, environment managers, or local `.env.local` files that are **never**
  committed. Use the provided templates (`env.template`) with placeholder values only.
- Replace any static tokens in tests/fixtures with obvious placeholders (e.g., `mock-access`,
  `dummy-refresh`). If a test genuinely requires a long-lived credential, fetch it from the runtime
  environment inside the test setup instead of hard coding it.

## CI Expectations
- The GitHub Actions workflow (`.github/workflows/security.yml`) executes multiple security scans:
  - **Custom Secret Scanner** (`scripts/ci/scan_secrets.py`) - **BLOCKING**
  - **Gitleaks** - Detects secrets in git history - **BLOCKING**
  - **Default Password Detection** - Checks for `os.getenv()` with password defaults - **BLOCKING**
- These scans will **FAIL THE BUILD** if violations are detected
- No code with hardcoded secrets or default passwords can be merged
- Pre-commit hooks run the same scanner locally to catch issues before push

## Common Violations and Fixes

### ❌ Default Password in os.getenv()
```python
# BAD - Application runs with insecure default
password = os.getenv('NEO4J_PASSWORD')
```

```python
# GOOD - Application fails fast with clear error
password = os.getenv('NEO4J_PASSWORD')
if not password:
    raise ValueError(
        "NEO4J_PASSWORD environment variable is required. "
        "Set it via Doppler or environment: doppler run -- python main.py"
    )
```

### ❌ Hardcoded Credentials
```python
# BAD
self.password = 'ruleiq123'
```

```python
# GOOD
self.password = os.getenv('NEO4J_PASSWORD')
if not self.password:
    raise ValueError("NEO4J_PASSWORD is required")
```

### ✅ Test Files Exception
Test files (in `tests/` directory) may use non-secret placeholder constants or load credentials
from environment variables/fixtures. Tests **must remain non-interactive** so they can run
unattended in CI without hanging.

```python
# ACCEPTABLE in tests/test_something.py — hardcoded placeholder (not a real secret)
TEST_PASSWORD = "test-password-placeholder"

# ALSO ACCEPTABLE — load from environment variable with a safe fallback for CI
TEST_PASSWORD = os.getenv("TEST_NEO4J_PASSWORD", "test-password-placeholder")
```

**Never use `getpass()` or any other interactive prompt in tests.** Interactive prompts block
automated runs and will cause CI pipelines to hang indefinitely.

## Responding to Findings
1. Investigate the file/location reported by the scanner.
2. If the value is a real secret, rotate it immediately (see `SECRET_ROTATION_PLAN.md`) and replace
   it with a placeholder.
3. If the finding is a false positive, do one of the following:
   - Shorten the placeholder so it looks less like a credential (`mock-access` instead of
     `mock-access-token-123`).
   - Update the scanner heuristics only when the placeholder pattern is expected to recur across the
     repository.
4. Re-run `python3 scripts/ci/scan_secrets.py` to confirm a clean result before committing.

## Doppler Setup (Recommended)

Doppler is the recommended way to manage secrets for RuleIQ.

### Installation
```bash
# macOS
brew install doppler

# Linux
curl -Ls https://cli.doppler.com/install.sh | sh
```

### Configuration
```bash
# Login to Doppler
doppler login

# Setup project
doppler setup

# Run application with Doppler
doppler run -- python main.py
```

### Verify Configuration
```bash
# Check what secrets Doppler will provide
doppler secrets

# Validate all required variables are set
doppler run -- python scripts/validate_required_env_vars.py
```

_Last updated: 2025-09-30_
