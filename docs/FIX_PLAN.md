# Fix Plan — ruleIQ Production Sprint

**Date**: 2026-03-03
**Branch**: `sprint/production-ready`
**Source**: Phase 2 Issue Triage & Prioritization

---

## Issue Summary

| Priority | Count | Description |
|----------|-------|-------------|
| **P0** | 5 | Blocks compilation/startup |
| **P1** | 5 | Blocks core functionality |
| **P2** | 3 | Blocks feature completeness |
| **P3** | 7 | Quality & polish |
| **Total** | **20** | |

---

## P0 — Blocks Compilation/Startup

### P0-1: `from __future__ import annotations` breaks 39 routers

**Files**: 39 router files in `api/routers/` (full list in `docs/SPRINT_ARCHITECTURE.md`)
**Root Cause**: `from __future__ import annotations` converts all annotations to strings. FastAPI+Pydantic v2 cannot resolve forward references at runtime, causing `PydanticUndefinedAnnotation: name 'X' is not defined`.
**Fix**: Remove `from __future__ import annotations` from all 39 files. This is a mechanical sed/replace — no logic changes needed.
**Risk**: LOW — removing the import restores standard Python annotation behavior. Pydantic v2 handles type resolution natively.
**Verification**: `python -c "from api.main import app; print('OK')"`
**Worktree**: `p0-backend`
**Estimated effort**: 10 minutes (batch replace)

### P0-2: Missing `frontend/lib/stores/freemium/` directory

**File**: `frontend/lib/stores/freemium-store.ts` line 21 exports from `./freemium/index`
**Root Cause**: The REFACTORING_SUMMARY.md says `freemium-store.ts` was refactored into 11 modules in `frontend/lib/stores/freemium/`, but the directory doesn't exist. The shim file was committed but the modular directory was not.
**Fix**: Either (a) create the `freemium/` directory with proper module files, or (b) revert `freemium-store.ts` to be self-contained (remove the re-export). Option (b) is safer for P0 — just make the existing code in `freemium.store.ts` the canonical store and remove the broken re-export from `freemium-store.ts`.
**Risk**: MEDIUM — need to check which file is actually imported by components.
**Verification**: `cd frontend && pnpm build`
**Worktree**: `p0-frontend`
**Estimated effort**: 30 minutes

### P0-3: Missing `frontend/lib/utils/export/` directory

**File**: `frontend/lib/utils/export.ts` line 8 exports from `./export/index`
**Root Cause**: Same pattern as P0-2. REFACTORING_SUMMARY.md says `export.ts` was refactored into 8 modules in `frontend/lib/utils/export/`, but the directory doesn't exist.
**Fix**: Same approach as P0-2 — revert `export.ts` to be self-contained or ensure the modular directory exists.
**Risk**: MEDIUM — need to check actual export usage.
**Verification**: `cd frontend && pnpm build`
**Worktree**: `p0-frontend`
**Estimated effort**: 30 minutes

### P0-4: `google.generativeai` deprecated

**File**: `services/ai/assistant_facade.py:13`
**Root Cause**: `from google.generativeai.types import HarmCategory, HarmBlockThreshold` — the `google-generativeai` package is deprecated in favor of `google-genai`.
**Fix**: For P0, add a try/except fallback or suppress the FutureWarning. Full migration to `google.genai` is P2 scope.
**Risk**: LOW — the package still works, it's just deprecated.
**Verification**: No crash on import.
**Worktree**: `p0-backend`
**Estimated effort**: 15 minutes

### P0-5: Stale celery services in docker-compose.yml

**File**: `docker-compose.yml`
**Root Cause**: Celery was replaced by LangGraph but compose file still defines celery_worker and celery_beat services.
**Fix**: Remove celery_worker and celery_beat service definitions.
**Risk**: LOW — these services can't start anyway (Celery config is deprecated).
**Verification**: `docker-compose config --quiet`
**Worktree**: Lead only (config file)
**Estimated effort**: 5 minutes

---

## P1 — Blocks Core Functionality

### P1-1: 823 TypeScript errors

**Location**: Frontend-wide. Top error sources:
- `tests/setup-broken.ts` (60 errors) — broken test setup file
- `tests/integration/freemium-user-journey.test.tsx` (39 errors)
- `tests/components/freemium/*.test.tsx` (57 errors)
- `lib/stores/chat.store.ts` (28 errors)
- `types/iq-agent.ts` (28 errors)

**Top error codes**:
- TS2339 (121): Property does not exist on type
- TS2345 (114): Argument type mismatch
- TS2322 (95): Type assignment errors
- TS18048 (84): Value possibly undefined
- TS2532 (50): Object possibly undefined
- TS2484 (50): Duplicate export declarations
- TS7006 (41): Parameter implicitly has 'any' type

**Fix**: Prioritize fixing source type files (`types/iq-agent.ts`, `types/assessment-results.ts`) first, then stores, then tests.
**Worktree**: `p1-frontend`
**Estimated effort**: 2-4 hours

### P1-2: 50 duplicate export declaration errors

**Files**: `types/iq-agent.ts`, `types/assessment-results.ts`
**Root Cause**: Types are defined AND re-exported in the same file, causing TS2484 conflicts.
**Fix**: Remove duplicate re-exports or consolidate type declarations.
**Worktree**: `p1-frontend`
**Estimated effort**: 30 minutes

### P1-3: 5,333 ruff lint errors (131 auto-fixable)

**Location**: Backend-wide. Top violations:
- E501 (1,796): line too long
- PLR2004 (719): magic value comparison
- B008 (622): function-call-in-default-argument (FastAPI Depends() pattern — may need config)
- ANN001 (386): missing type annotations
- F821 (356): undefined name

**Fix**: Run `ruff check . --fix` for 131 auto-fixable. For B008, add `B008` to ruff.toml ignore list (FastAPI pattern). E501 and PLR2004 are style — can be ignored or fixed later.
**Worktree**: `p0-backend` (auto-fix only), remainder in `p3-lint`
**Estimated effort**: 30 min auto-fix, 4+ hours manual

### P1-4: Dependency version conflicts (9 conflicts)

**Conflicts**:
- pydantic 2.7.4 vs required >=2.9.0 (google-genai, graphiti-core, mcp)
- httpx 0.27.0 vs required >=0.28.1 (google-genai, mcp)
- openai 1.58.1 vs required >=1.91.0 (graphiti-core)
- uvicorn 0.27.0 vs required >=0.31.1 (mcp)
- starlette 0.36.3 vs required >=0.49.1 (sse-starlette)
- pydantic-settings 2.4.0 vs required >=2.5.2 (mcp)

**Fix**: Upgrade pinned versions in requirements.txt. WARNING: pydantic upgrade may break existing Pydantic v2 models. Must test thoroughly.
**Risk**: HIGH — version upgrades can introduce breaking changes.
**Worktree**: Lead only (requirements.txt is config)
**Estimated effort**: 1-2 hours (upgrade + test)

### P1-5: 6 NotImplementedError stubs in AI providers

**Files**:
- `services/ai/providers/anthropic_provider.py` (lines 30, 38)
- `services/ai/providers/openai_provider.py` (lines 30, 38)
- `services/ai/providers/gemini_provider.py` (line 215) — streaming only
- `app/core/monitoring/health.py` (line 77)

**Fix**: Implement the provider methods or mark as intentionally unsupported with proper error messages.
**Worktree**: `p2-services` (Phase 5)
**Estimated effort**: 2-4 hours per provider

---

## P2 — Feature Completeness

### P2-1: 1,252 TODO/FIXME/HACK/XXX/BROKEN markers
- Majority are "Replace with proper logging" in frontend
- Many are test TODOs and notes
- Scope cap: items requiring >50 lines → DEFERRED to GitHub issues

### P2-2: Duplicate layout directories
- `frontend/components/layout/` AND `frontend/components/layouts/`
- Consolidate into one

### P2-3: Duplicate Evidence model definitions
- `database/models.py` AND `database/models/evidence.py`
- Determine canonical model, remove duplicate

---

## P3 — Quality & Polish

### P3-1: Backend test coverage at 3.13%
### P3-2: Frontend test coverage at 0%
### P3-3: Sentry config deprecation warning
### P3-4: Teal migration 65% complete
### P3-5: 412 bare `pass` stubs in Python code
### P3-6: 4 ESLint warnings (unused vars)
### P3-7: Hardcoded secrets verification needed

---

## Fix Order (Dependency-Aware)

### Phase 3 — P0 Fixes (2 parallel worktrees)

**Worktree `p0-backend`** (fix/p0-backend):
1. P0-1: Remove `from __future__ import annotations` from 39 routers
2. P0-4: Suppress google.generativeai deprecation warning
3. Verify: `python -c "from api.main import app; print('OK')"`

**Worktree `p0-frontend`** (fix/p0-frontend):
1. P0-2: Fix freemium-store.ts broken re-export
2. P0-3: Fix export.ts broken re-export
3. Verify: `pnpm build`

**Lead (sequential, after merges)**:
1. P0-5: Remove celery services from docker-compose.yml

### Phase 4 — P1 Fixes (3 parallel worktrees)

**Worktree `p1-database`** (fix/p1-database):
1. Verify Alembic migrations consistent with models
2. Fix any ORM model issues

**Worktree `p1-api`** (fix/p1-api-routes):
1. Auto-fix ruff errors: `ruff check . --fix`
2. Update ruff.toml to ignore B008 (FastAPI Depends pattern)
3. Fix F821 undefined name errors

**Worktree `p1-frontend`** (fix/p1-frontend-integration):
1. P1-2: Fix duplicate exports in types/iq-agent.ts and types/assessment-results.ts
2. P1-1: Fix remaining TypeScript errors (prioritize stores → types → components → tests)

**Lead (sequential)**:
1. P1-4: Dependency version upgrades in requirements.txt (HIGH RISK — test after)

### Phase 5 — P2 Fixes (4 parallel worktrees)

Per-module completion as specified in sprint prompt.

### Phase 6 — P3 Fixes (2 waves)

Per-wave hardening as specified in sprint prompt.

---

## Risk Assessment

| Fix | Risk Level | Mitigation |
|-----|------------|------------|
| P0-1 future annotations removal | LOW | Mechanical change, well-understood |
| P0-2/P0-3 frontend module fixes | MEDIUM | Need to trace all import paths |
| P0-4 google.generativeai | LOW | Suppress warning only |
| P0-5 celery removal | LOW | Dead code removal |
| P1-1 TypeScript fixes | MEDIUM | 823 errors, some may cascade |
| P1-3 ruff auto-fix | LOW | Only safe auto-fixes |
| P1-4 dependency upgrades | **HIGH** | pydantic 2.7→2.9+ may break models |
| P1-5 AI provider implementation | MEDIUM | New code, needs testing |
