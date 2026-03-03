# Sprint Architecture Document — Phase 1 Reconnaissance

**Date**: 2026-03-03
**Branch**: `sprint/production-ready`
**Sprint Phase**: Phase 1 — Deep Codebase Reconnaissance

---

## 1. System Overview

RuleIQ is an enterprise-grade agentic AI compliance automation platform for UK SMBs. It uses GraphRAG-powered compliance orchestration with LangGraph workflows.

### Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + FastAPI | 3.11 / 0.110.0 |
| Frontend | Next.js + React | 15.4.7 / 19 |
| Database | PostgreSQL (Neon) | via SQLAlchemy 2.0.27 |
| Graph DB | Neo4j | GraphRAG knowledge graph |
| Cache | Redis | 5.0.1 |
| AI Orchestration | LangGraph | (replaced Celery) |
| AI Providers | Google Gemini, OpenAI, Anthropic | google-generativeai 0.8.6 (DEPRECATED) |
| Frontend Styling | TailwindCSS + shadcn/ui | Teal design (65% migrated) |
| Package Manager | pnpm | 10.30.1 |

---

## 2. Backend Architecture

### File Counts (454 Python files total)

| Directory | Files | Purpose |
|-----------|-------|---------|
| `api/` | 108 | FastAPI routers, dependencies, schemas, integrations |
| `services/` | 191 | Business logic, AI, compliance, caching, monitoring |
| `langgraph_agent/` | 51 | Multi-agent workflows, PPALE loop |
| `database/` | 44 | SQLAlchemy models, migrations, Redis client |
| `config/` | 26 | Settings, logging, feature flags |
| `middleware/` | 15 | Auth, rate limiting, security headers |
| `core/` | 9 | Core monitoring, constants |
| `models/` | 6 | Pydantic request/response schemas |
| `utils/` | 4 | Input validation, utilities |

### Router Map (52 router files, 39 with `from __future__ import annotations` BUG)

**Routers with `from __future__ import annotations` (P0 — breaks FastAPI+Pydantic v2):**
```
api/routers/admin/data_access.py
api/routers/admin/token_management.py
api/routers/admin/user_management.py
api/routers/agentic_rag.py
api/routers/ai_assessments.py
api/routers/ai_cost_monitoring.py
api/routers/ai_cost_websocket.py
api/routers/ai_optimization.py
api/routers/ai_policy.py
api/routers/api_keys.py
api/routers/audit_export.py
api/routers/auth.py
api/routers/business_profiles.py       ← CONFIRMED: crashes app import
api/routers/compliance.py
api/routers/dashboard.py
api/routers/evidence.py
api/routers/evidence_collection.py
api/routers/feedback.py
api/routers/foundation_evidence.py
api/routers/frameworks.py
api/routers/freemium.py
api/routers/google_auth.py
api/routers/implementation.py
api/routers/integrations.py
api/routers/iq_agent.py
api/routers/monitoring.py
api/routers/optimization.py
api/routers/payment.py
api/routers/performance_monitoring.py
api/routers/policies.py
api/routers/rbac_auth.py
api/routers/readiness.py
api/routers/reports.py
api/routers/secrets_vault.py
api/routers/security.py
api/routers/test_utils.py
api/routers/uk_compliance.py
api/routers/usage_dashboard.py
api/routers/users.py
api/routers/webhooks.py
```

**Routers WITHOUT the bug (safe):**
- `api/routers/assessments.py` (already fixed in Phase 0)
- `api/routers/chat.py` and `api/routers/chat/*.py` (modular package)
- `api/routers/health.py`
- `api/routers/chat_backup.py`

### Services Architecture

Key service modules:
- `services/ai/` — 60+ files: AI providers, assessment tools, compliance ingestion, circuit breaker
- `services/ai/assistant.py` — backward-compat shim → `assistant_facade.py`
- `services/ai/assistant_facade.py` — ComplianceAssistant facade (imports deprecated `google.generativeai`)
- `services/agents/` — Agent orchestration, trust algorithm, session management
- `services/compliance/` — UK compliance engine, GDPR, GraphRAG research
- `services/caching/` — Cache manager, invalidator, warmer, metrics
- `services/reporting/` — PDF generator, report scheduler, templates
- `services/security/` — Audit logging, authentication, authorization, encryption

### LangGraph Agent (51 files)

```
langgraph_agent/
├── agents/          — agent_core, memory_manager, rag_adapter, rag_system, tool_manager
├── core/            — constants, models
├── evals/           — metrics
├── graph/           — app, complete_graph, enhanced_app, error_handler, state management
├── models/          — compliance_state
├── nodes/           — compliance, evidence, notification, rag, reporting, task_scheduler
├── scheduler/       — task_scheduler
├── services/        — ai_service, compliance_analyzer, evidence_collector
├── tests/           — 7 test files
└── utils/           — cost_tracking
```

### Database Layer (44 files)

**SQLAlchemy models** (in `database/`):
- User, BusinessProfile, ComplianceFramework, AssessmentSession, AssessmentQuestion
- EvidenceItem, GeneratedPolicy, ChatConversation, ChatMessage, AICostModels
- FreemiumAssessmentSession, LeadScoringEvent, ConversionEvent, ReportSchedule
- ReadinessAssessment, ImplementationPlan, RBAC models
- **DUPLICATE**: `database/models.py` has Evidence model that duplicates `database/models/evidence.py`

**Alembic migrations**: 17 migration files in `alembic/versions/`

**Redis**: `database/redis_client.py` — sessions, JWT blacklist, rate limiting, cache

---

## 3. Frontend Architecture

### Pages (61 page.tsx files)

**Route Groups:**
- `(auth)` — login, register, signup, forgot-password, reset-password, onboarding
- `(dashboard)` — assessments, chat, evidence, policies, reports, risks, analytics, settings
- `(public)` — freemium assessment flow
- `(requirements)` — wireframe creation
- `_deprecated` — legacy auth pages

### Components (283 .tsx files across 28 directories)

| Directory | Purpose |
|-----------|---------|
| `ui/` | shadcn/ui base components |
| `assessments/` | Assessment wizard, results, AI help |
| `chat/` | IQ Agent chat interface |
| `dashboard/` | Dashboard widgets, analytics |
| `evidence/` | Evidence collection, management |
| `freemium/` | Freemium assessment flow |
| `auth/` | Authentication forms |
| `marketing/` | Landing pages, hero sections |
| `layout/`, `layouts/` | Page layouts (duplicate dirs!) |
| `navigation/` | Sidebar, header, breadcrumbs |

### State Management

**Zustand stores** (14 files in `lib/stores/`):
- app, assessment, auth, business-profile, chat, dashboard
- evidence, evidence-collection, freemium, layout, voice
- **DUPLICATE**: `freemium.store.ts` AND `freemium-store.ts` (shim → missing dir)

**TanStack Query**: `lib/tanstack-query/` — hooks for assessments, compliance, frameworks, etc.

### API Layer (28 service files in `lib/api/`)

Services: auth, assessments, assessments-ai, business-profiles, chat, compliance, dashboard, evidence, evidence-collection, foundation-evidence, frameworks, freemium, implementation, integrations, layouts, monitoring, payment, policies, readiness, reports

---

## 4. Infrastructure

### Docker (12 files)
- `Dockerfile` — uses `requirements-cloudrun.txt` (KNOWN: missing ~15 deps)
- `Dockerfile.freemium` — freemium variant
- `Dockerfile.production` — production variant
- `Dockerfile.sprint` — uses full `requirements.txt` (created in Phase 0)
- `docker-compose.yml` — **STALE**: has celery_worker/celery_beat services
- 7 other compose variants: ci, freemium, monitoring, neon, preprod, prod, test

### CI/CD (19 workflow files in `.github/workflows/`)
Key workflows: backend-tests, frontend-tests, coverage-report, security, codeql, deploy-cloud-run-doppler, deploy-vercel

### Requirements
- `requirements.txt` — 70+ packages (full)
- `requirements-cloudrun.txt` — reduced subset for Cloud Run

### Dependency Conflicts (from pip install)
```
google-genai 1.58.0 requires httpx>=0.28.1 (have 0.27.0)
google-genai 1.58.0 requires pydantic>=2.9.0 (have 2.7.4)
graphiti-core 0.28.1 requires openai>=1.91.0 (have 1.58.1)
graphiti-core 0.28.1 requires pydantic>=2.11.5 (have 2.7.4)
mcp 1.26.0 requires httpx>=0.27.1 (have 0.27.0)
mcp 1.26.0 requires pydantic>=2.11.0 (have 2.7.4)
sse-starlette 3.3.2 requires starlette>=0.49.1 (have 0.36.3)
```

---

## 5. Test Coverage

### Backend Tests
- **210 test files** in `tests/` across 17 subdirectories
- Directories: ai, base, database, docs, e2e, fixtures, integration, load, mocks, models, monitoring, performance, security, testsprite_generated, test-utility-scripts, unit, utils
- Makefile targets: test-group-unit (2-3 min), test-group-ai (3-4 min), test-group-api (4-5 min), etc.
- **Coverage baseline**: 3.13% line coverage (CRITICAL — needs improvement)

### Frontend Tests
- **99 test files** in `frontend/tests/`
- Vitest (unit) + Playwright (e2e)
- **Coverage baseline**: 0.00% (CRITICAL)

### LangGraph Tests
- 7 test files in `langgraph_agent/tests/`

---

## 6. Critical Issues Registry

### P0 — Blocks Compilation/Startup (MUST FIX FIRST)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| P0-1 | **`from __future__ import annotations` breaks FastAPI+Pydantic v2** | 39 router files (list above) | Backend cannot start — NameError on forward refs |
| P0-2 | **Missing `frontend/lib/stores/freemium/` directory** | `freemium-store.ts` line 21 | Frontend build fails — Module not found |
| P0-3 | **Missing `frontend/lib/utils/export/` directory** | `export.ts` line 8 | Frontend build fails — Module not found |
| P0-4 | **`google.generativeai` deprecated** | `services/ai/assistant_facade.py:13` | FutureWarning, will break in next version |
| P0-5 | **Stale celery services in docker-compose.yml** | `docker-compose.yml` | Docker startup includes dead services |

### P1 — Blocks Core Functionality

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| P1-1 | **823 TypeScript errors** | Frontend-wide (top files: setup-broken.ts, freemium tests, chat.store, iq-agent types) | Type safety broken |
| P1-2 | **50 duplicate export declaration errors** | `types/iq-agent.ts`, `types/assessment-results.ts` | Type conflicts in core types |
| P1-3 | **5,333 ruff lint errors** | Backend-wide (131 auto-fixable) | Code quality violations |
| P1-4 | **Dependency version conflicts** | pydantic 2.7.4 vs required 2.9+, httpx 0.27.0 vs required 0.28+ | May cause runtime errors |
| P1-5 | **6 NotImplementedError stubs** | AI providers (Anthropic, OpenAI, Gemini streaming) | Core AI features incomplete |

### P2 — Feature Completeness

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| P2-1 | **130 TODO/FIXME markers** remaining | Across Python and TypeScript files | Deferred work |
| P2-2 | **Duplicate layout directories** | `components/layout/` + `components/layouts/` | Confusion risk |
| P2-3 | **Duplicate model definitions** | `database/models.py` vs `database/models/evidence.py` | ORM confusion |

### P3 — Quality & Polish

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| P3-1 | **3.13% backend test coverage** | `docs/COVERAGE_BASELINE.md` | Far below 80% target |
| P3-2 | **0% frontend test coverage** | Coverage report | No measured coverage |
| P3-3 | **Sentry config deprecation** | `sentry.client.config.ts` | Needs migration to `instrumentation-client.ts` |
| P3-4 | **Teal migration 65% complete** | Frontend styling | Legacy purple/cyan colors remain |

---

## 7. Hardcoded Secrets Status

**PREVIOUSLY IDENTIFIED P0 SECRETS — STATUS:**

| File | Status | Notes |
|------|--------|-------|
| `services/neo4j_service.py` | **FIXED** | Now uses `os.getenv('NEO4J_PASSWORD')` with fail-fast |
| `services/ai/compliance_ingestion_pipeline.py` | **APPEARS FIXED** | No hardcoded password found in grep |
| `services/ai/evaluation/tools/ingestion_fixed.py` | **APPEARS FIXED** | No hardcoded password found in grep |

---

## 8. Build Status Summary

| Check | Status | Details |
|-------|--------|---------|
| Backend import (`from api.main import app`) | **FAIL** | `from __future__ import annotations` → PydanticUndefinedAnnotation |
| Frontend build (`pnpm build`) | **FAIL** | 2 missing module dirs (freemium/, export/) |
| Frontend typecheck (`pnpm typecheck`) | **FAIL** | 823 TypeScript errors |
| Backend lint (`ruff check .`) | **FAIL** | 5,333 errors (131 auto-fixable) |
| Backend tests | **BLOCKED** | Cannot run — app doesn't import |
| Frontend tests | **UNKNOWN** | Not yet attempted |

---

## 9. Fix Priority Order

1. **P0-1**: Remove `from __future__ import annotations` from 39 routers (mechanical batch fix)
2. **P0-2 + P0-3**: Restore `freemium/` and `export/` module directories or fix shim imports
3. **P0-4**: Migrate `google.generativeai` → `google.genai`
4. **P0-5**: Remove celery services from docker-compose.yml
5. **P1-1 + P1-2**: Fix TypeScript type errors (prioritize duplicate exports, then type mismatches)
6. **P1-3**: Run `ruff check . --fix` for auto-fixable lint errors
7. **P1-4**: Resolve dependency version conflicts (pydantic, httpx upgrades)
8. **P1-5**: Implement AI provider stubs or mark as intentionally unimplemented
