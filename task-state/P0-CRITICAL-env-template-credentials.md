# P0 CRITICAL: Credentials Leaked in env.template

## Severity: P0 — IMMEDIATE ACTION REQUIRED

The file `env.template` contains what appear to be **real production/development credentials** instead of placeholders:

### Affected Lines

| Line | Variable | Issue |
|------|----------|-------|
| ~47 | `DATABASE_URL` | Contains real Neon PostgreSQL password `npg_s0JhnfGNy3Ze` pointing to `eastus2.azure.neon.tech` |
| ~78 | `NEXT_PUBLIC_STACK_PROJECT_ID` | Real Stack Auth project ID |
| ~79 | `NEXT_PUBLIC_STACK_PUBLISHABLE_CLIENT_KEY` | Real Stack Auth client key |
| ~80 | `STACK_SECRET_SERVER_KEY` | Real Stack Auth **server secret key** |
| ~84 | `JWT_SECRET` | Real JWT signing secret `nTDlGluRj39drsQ+...` |
| ~132 | `FERNET_KEY` | Real Fernet encryption key `PiuMdniC0TBtnLTa...` |

### Required Fixes

Replace ALL real credentials with clearly marked placeholders:

```bash
# DATABASE_URL — line ~47
DATABASE_URL=postgresql+asyncpg://your_user:your_password@your-host.neon.tech/your_db?sslmode=require

# Stack Auth — lines ~78-80
NEXT_PUBLIC_STACK_PROJECT_ID=your-stack-project-id
NEXT_PUBLIC_STACK_PUBLISHABLE_CLIENT_KEY=pck_your-publishable-client-key
STACK_SECRET_SERVER_KEY=ssk_your-secret-server-key

# JWT — line ~84
JWT_SECRET=generate-with-openssl-rand-base64-32

# Fernet — line ~132
FERNET_KEY=generate-with-python-cryptography-fernet-generate-key
```

### Immediate Actions

1. **Rotate ALL exposed credentials NOW** — assume they are compromised since this file is in the repo
   - Regenerate Neon DB password at https://console.neon.tech
   - Regenerate Stack Auth keys at Stack Auth dashboard
   - Generate new JWT_SECRET: `openssl rand -base64 32`
   - Generate new FERNET_KEY: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. **Replace credentials in env.template** with the placeholder values above
3. **Search git history** for other credential exposures: `git log --all -p -- env.template | grep -i "password\|secret\|key"`
4. **Run the secret scanner**: `python3 scripts/ci/scan_secrets.py`

### Prevention

The `pre-commit` hook with `scan_secrets.py` should catch this. Verify it is active:
```bash
pre-commit run --all-files
```
