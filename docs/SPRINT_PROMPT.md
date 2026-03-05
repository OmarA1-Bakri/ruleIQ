Read the recent checkpoint and memory files first. When complete, please proceed to the next step.

run the following prompt precisely:

# ruleIQ Production Sprint — Full Codebase Review & Completion

You are executing a multi-phase production sprint on the ruleIQ codebase. This is a long-running autonomous session with hard quality gates, parallel agent teams using **git worktree isolation**, iterative review loops, and context handoffs. You may NOT skip phases or gates. Every phase must produce verifiable artifacts before advancing.

> **Resuming?** If picking up a previously started sprint, run `git log --oneline -20` and `ls docs/SPRINT_*.md docs/FIX_PLAN.md 2>/dev/null` to determine which phase was last completed. Skip to the next uncompleted gate.

---

## REPO FACTS (Read Before Anything Else)

These are ground truth. Do NOT deviate from them.

| Fact | Value |
|------|-------|
| **Repo root** | `C:\Users\OmarAl-Bakri\ruleIQ` |
| **Backend location** | Root level — NO `backend/` dir. Python code lives in `api/`, `services/`, `models/`, `core/`, `middleware/`, `utils/`, `database/`, `langgraph_agent/` |
| **Backend entrypoint** | `api.main:app` — **NOT** `main.py` (deprecated) |
| **Backend activation** | `source .venv/bin/activate` (REQUIRED before any Python command) |
| **Backend linter** | `ruff` (NOT flake8, NOT mypy). Config: `ruff.toml` |
| **Backend tests** | `pytest` via Makefile: `make test-groups-parallel`, `make test-group-unit`, etc. 1884+ tests, 234 test files |
| **Frontend location** | `frontend/` |
| **Frontend package manager** | `pnpm` (NOT bun, NOT npm). Lock file: `frontend/pnpm-lock.yaml` |
| **Frontend framework** | Next.js 15 + React 19 + TailwindCSS + shadcn/ui |
| **Frontend test framework** | Vitest (unit) + Playwright (e2e). Config: `vitest.config.ts`, `playwright.config.ts` |
| **Frontend linter** | ESLint (`eslint.config.mjs`) + Prettier |
| **Env templates** | `env.template`, `env.comprehensive.template` (NOT `.env.example`) |
| **Design system** | Teal migration 65% complete. Primary: `--teal-600: #2C7A7B` |
| **Known P0s** | Hardcoded passwords in neo4j_service.py, compliance_ingestion_pipeline.py, ingestion_fixed.py |
| **Known debt** | `services/ai/assistant.py` — 4,031 line god object. 458 TODO comments. |
| **Existing docs** | `docs/` has 20+ files. Root has 25+ analysis/refactoring .md files. READ THEM FIRST. |

### Correct Commands Reference

```bash
# Backend
source .venv/bin/activate                                    # ALWAYS first
uvicorn api.main:app --host 0.0.0.0 --port 8000            # Start server
python -c "from api.main import app; print('Backend: OK')"  # Import check
ruff check .                                                 # Lint
ruff format .                                                # Format
bandit -r api/ services/ core/ middleware/ models/ utils/    # Security linter
make test-groups-parallel                                    # All tests
make test-group-unit                                         # Unit tests only
pytest tests/path/to/test.py -v                             # Single test

# Frontend (always cd frontend first)
pnpm install                    # Install deps
pnpm build                     # Production build
pnpm typecheck                 # tsc --noEmit
pnpm lint                      # ESLint
pnpm format                    # Prettier
pnpm test                      # Vitest unit tests
pnpm test:coverage             # With coverage
pnpm test:e2e                  # Playwright e2e
pnpm audit                     # Security audit

# Code quality (backend)
pip check                       # Verify installed deps
pip audit                       # Security audit
```

### Valid Conventional Commit Scopes

```
api, frontend, db, auth, config, infra, tests, docs, security, services, models, middleware, langgraph
```

---

## HARDCODED SECRET REMEDIATION PROTOCOL

**Every hardcoded secret discovered during the sprint MUST be remediated using this protocol. No exceptions.**

1. **Env var naming**: `RULEIQ_` prefix + `SERVICE_CREDENTIAL_TYPE` pattern (e.g., `RULEIQ_NEO4J_PASSWORD`, `RULEIQ_REDIS_URL`)
2. **Template updates**: Add every new env var to BOTH `env.template` AND `env.comprehensive.template` with a placeholder and comment
3. **Fail-fast pattern**: Replace hardcoded values with:
   ```python
   value = os.environ["RULEIQ_SERVICE_KEY"]  # KeyError = fail-fast, no silent defaults for secrets
   ```
4. **Pre-commit hook**: Install `detect-secrets` to prevent future leaks:
   ```bash
   pip install detect-secrets
   detect-secrets scan > .secrets.baseline
   ```
5. **Branch deletion**: After merging any branch that contained hardcoded secrets, delete it immediately: `git branch -d <branch>`
6. **Rotation alert**: For secrets found in git history, add to `docs/SECRETS_ROTATION_NEEDED.md` with service name, file path, and commit hash

---

## WORKTREE ISOLATION STRATEGY

**All parallel write phases (3, 4, 5, 6) MUST use git worktrees** to prevent file conflicts between agents. Read-only phases (1, 2) do not need worktrees.

### Setup (Phase 0)

```bash
mkdir -p .worktrees
git check-ignore -q .worktrees 2>/dev/null || echo ".worktrees/" >> .gitignore
```

### Worktree Agent Setup

**Every agent spawned into a worktree MUST run these dependency installation steps as its first action.** Dependencies are not inherited from the main worktree.

**Backend agents** (any agent touching Python code):
```bash
cd <worktree-path>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "from api.main import app; print('Worktree backend deps: OK')"
```

**Frontend agents** (any agent touching frontend/ code):
```bash
cd <worktree-path>/frontend
pnpm install
pnpm typecheck 2>&1 | tail -5
```

### Merge-Back Protocol

After each parallel phase completes:
```bash
# Tag the sprint branch before merging (checkpoint for rollback)
git checkout sprint/production-ready
git tag checkpoint/before-phase-N

# Per-worktree tests BEFORE merging (in each worktree directory)
# Backend: source .venv/bin/activate && make test-group-unit
# Frontend: cd frontend && pnpm test --run

# Merge each worktree branch (one at a time, in dependency order)
git merge --no-ff <worktree-branch-1> -m "merge: Phase N - <description>"
git merge --no-ff <worktree-branch-2> -m "merge: Phase N - <description>"

# Delete merged branches immediately
git branch -d <worktree-branch-1>
git branch -d <worktree-branch-2>

# Clean up worktrees
git worktree remove .worktrees/<name-1>
git worktree remove .worktrees/<name-2>

# Verify merged state
source .venv/bin/activate
python -c "from api.main import app; print('Backend: OK')"
cd frontend && pnpm build
```

### Conflict Resolution Guide

| Conflict Type | Resolution Strategy |
|---------------|---------------------|
| **Import conflicts** (same file, different imports) | Keep both, remove duplicates, sort alphabetically |
| **Config/settings conflicts** | Accept BOTH changes — config values are usually additive |
| **Route registration conflicts** | Keep both routes; verify no path collisions |
| **Component conflicts** (React) | Prefer the change that passes TypeScript check; if both valid, keep both |
| **Migration conflicts** (Alembic) | STOP — never auto-resolve. Create merge migration: `alembic merge heads` |
| **Test conflicts** | Keep both test cases; deduplicate fixtures |

If a conflict cannot be confidently resolved, report to me before proceeding.

### Agent Tool Integration

When spawning parallel agents, pass the worktree path via the agent's prompt — do **NOT** use `isolation: "worktree"` (which creates an uncontrolled second worktree). The lead creates worktrees manually with `git worktree add` to control branch names and merge order.

```
Agent(
  subagent_type="general-purpose",
  prompt="Working directory: C:\\Users\\OmarAl-Bakri\\ruleIQ\\.worktrees\\<name>\n..."
)
```

### File Partition Rules

Agents MUST respect these boundaries to minimize merge conflicts:

| Domain | Owned Files | Agent Assignment |
|--------|-------------|------------------|
| **Backend API** | `api/`, `middleware/`, `models/` | API team only |
| **Backend Services** | `services/`, `core/`, `langgraph_agent/` | Services/DB team only |
| **Backend Utilities** | `utils/` | Backend API team |
| **Database** | `database/`, `alembic/` | DB team only |
| **Frontend** | `frontend/**` | Frontend team only |
| **Config** | `config/`, `docker*`, `Dockerfile*`, `requirements*.txt` | Lead only (sequential) |
| **Tests** | `tests/` | Test agent only |
| **Docs** | `docs/`, root `*.md` files | Docs agent only |

**Cross-partition access**: The DB team agent may **read** (not write) `services/neo4j_service.py` to understand query patterns, but changes to that file must be coordinated with the Services team.

---

## PHASE 0 — SESSION BOOTSTRAP (Gate: Environment Verified)

**Objective**: Establish working environment, worktree infrastructure, and persistent tracking.

1. Run `git status`, `git log --oneline -20`, `git branch -a` to understand repo state
2. Create a working branch: `git checkout -b sprint/production-ready`
3. **Database backup** (safety net before any changes):
   ```bash
   pg_dump ruleiq > .worktrees/ruleiq_backup_$(date +%Y%m%d).sql 2>/dev/null || echo "No local DB to backup (cloud-only via Neon)"
   ```
4. Set up worktree directory:
   ```bash
   mkdir -p .worktrees
   git check-ignore -q .worktrees 2>/dev/null || (echo ".worktrees/" >> .gitignore && git add .gitignore && git commit -m "chore: add .worktrees to gitignore")
   ```
5. Install security scanning baseline:
   ```bash
   source .venv/bin/activate
   pip install detect-secrets bandit 2>/dev/null
   which gitleaks >/dev/null 2>&1 || echo "WARN: gitleaks not found — install via brew/scoop/go for git-history scanning"
   detect-secrets scan > .secrets.baseline
   gitleaks detect --no-git -v 2>/dev/null > .gitleaks-baseline.json || echo "gitleaks baseline skipped (not installed)"
   git add .secrets.baseline .gitleaks-baseline.json 2>/dev/null && git commit -m "chore(security): add secrets baseline"
   ```
6. Verify all prerequisites:
   ```bash
   python3 --version          # Expect 3.11+
   node --version             # Expect 18+
   pnpm --version             # Expect 8+
   ls env.template env.comprehensive.template
   source .venv/bin/activate && python -c "import fastapi; print('venv OK')"
   ```
7. Read existing documentation inventory:
   ```bash
   ls docs/
   ls *.md | head -30
   ```
8. Create the team: use `TeamCreate` with name `ruleiq-sprint`
9. Create a master task list using `TaskCreate` for every phase below (Phases 1–7), with dependencies set via `addBlockedBy`

**GATE 0**: Print environment summary table. List every tool version, branch name, worktree dir status, secrets baseline status, and confirm task list is created. Do NOT proceed until all checks pass. Ask me to confirm: **"Environment verified. Worktrees configured. Permission to begin Phase 1?"**

---

## PHASE 1 — DEEP CODEBASE RECONNAISSANCE (Gate: Architecture Map Approved)

**Objective**: Build a complete mental model of the entire codebase before touching anything.

**No worktrees needed** — this phase is read-only.

**FIRST**: Read all existing analysis docs to avoid duplicate work:
```bash
cat CODEBASE_ANALYSIS.md
cat EXECUTION_PLAN.md
cat TODO_INVENTORY_INITIAL.md
cat REFACTORING_SUMMARY.md
cat docs/COVERAGE_BASELINE.md
cat docs/API_ENDPOINTS_DOCUMENTATION.md
```

Launch **4 parallel Explore agents** simultaneously:

### Agent 1: Backend Recon
```
Explore the ruleIQ backend at C:\Users\OmarAl-Bakri\ruleIQ (Python at ROOT, no backend/ dir). Map:
- All Python files in: api/, services/, core/, middleware/, models/, utils/, database/, langgraph_agent/, config/
- FastAPI routes in api/routers/ (56+ routers, all /api/v1/ pattern)
- Database models in database/ (PostgreSQL/Neon via SQLAlchemy, Neo4j, Redis)
- Authentication: JWT-only (30min access, 7day refresh, bcrypt, Redis blacklist)
- Background tasks, workers, queues
- GraphRAG: langgraph_agent/, services/neo4j_service.py, PPALE loop
- Config: config/settings.py, env.template, env.comprehensive.template
- KNOWN ISSUE: services/ai/assistant.py is 4,031 lines — document its responsibilities
- Every import that fails or references missing modules
Report: file tree, route map, dependency graph, list of ALL broken imports/missing modules.
```

### Agent 2: Frontend Recon
```
Explore the ruleIQ frontend at C:\Users\OmarAl-Bakri\ruleIQ\frontend. Map:
- Next.js 15 App Router: app/ directory, pages, layouts, route groups
- React 19 components: components/ (200+ components, shadcn/ui based)
- State: Zustand stores, TanStack Query, React Hook Form
- API layer: lib/api/client.ts (auto /api/v1/ normalization)
- Styling: TailwindCSS + teal design system (65% migrated from purple/cyan)
- Build: next.config.ts, tsconfig.json, pnpm-workspace.yaml
- Test infra: vitest.config.ts, playwright.config.ts
- Sentry: sentry.client.config.ts, sentry.server.config.ts, sentry.edge.config.ts
- QA tooling: scripts/qa-*.ts (health check, flaky detector, quality dashboard)
- Every TypeScript error, missing type, or broken import
Report: component tree, page routes, API call inventory, ALL TypeScript/build errors.
```

### Agent 3: Infrastructure & Config Recon
```
Explore all infrastructure and configuration in ruleIQ at C:\Users\OmarAl-Bakri\ruleIQ. Map:
- Docker: Dockerfile, Dockerfile.freemium, Dockerfile.production, docker-compose*.yml (7 variants)
- CI/CD: .github/workflows/ (GitHub Actions with SonarCloud)
- Cloud: cloudbuild.yaml, cloud-run-service.yaml, deploy_production.sh, deployment/
- Database migrations: alembic/, alembic.ini
- Environment variables: grep ALL os.environ, os.getenv, process.env across codebase
- Makefile targets (important — test commands live here)
- Security: CORS config, CSP headers, rate limiting (5/min auth, 100/min general, 20/min AI)
- Monitoring: monitoring/ directory
Report: infra map, env var registry, migration status, deployment readiness gaps.
```

### Agent 4: Test & Quality Recon
```
Explore all tests and quality tooling in ruleIQ at C:\Users\OmarAl-Bakri\ruleIQ. Map:
- Backend: tests/ directory (234 files, 1884+ tests). Read pytest.ini config.
- Backend coverage: docs/COVERAGE_BASELINE.md, coverage.json
- Frontend: frontend/tests/ (562+ test files). Vitest + Playwright configs.
- Frontend QA scripts: frontend/scripts/qa-*.ts
- Linting: ruff.toml (backend), eslint.config.mjs (frontend), prettier
- Which modules have tests vs which don't — compute gap analysis
- Test fixtures, factories, mocks
- Read docs/TESTING_GUIDE.md for existing test strategy
Report: test inventory, coverage gaps, untested critical paths, quality tooling status.
```

After all 4 agents complete, **synthesize** into a single Architecture Document. **Append to** (not overwrite) existing docs:

Use `Write` to save to `docs/SPRINT_ARCHITECTURE.md` with:
- System Overview (incorporating existing CODEBASE_ANALYSIS.md findings)
- Backend Architecture (routes, models, services)
- Frontend Architecture (components, pages, state)
- Data Flow (frontend → API → backend → databases)
- Infrastructure & Deployment
- Test Coverage Map
- **Critical Issues Registry** (every broken import, missing module, type error, failing test — MERGE with known P0s)

**GATE 1**: Present the Architecture Document summary. List the top 20 critical issues found. Ask: **"Architecture mapped. [N] critical issues found. Permission to begin Phase 2 triage?"**

---

## PHASE 2 — ISSUE TRIAGE & PRIORITIZATION (Gate: Fix Plan Approved)

**Objective**: Classify every issue and create a prioritized fix plan.

**No worktrees needed** — this phase is analysis-only.

1. Using the Critical Issues Registry from Phase 1, classify every issue:
   - **P0 — Blocks compilation/startup** (missing imports, syntax errors, broken configs, hardcoded passwords)
   - **P1 — Blocks core functionality** (broken routes, DB connection failures, auth broken)
   - **P2 — Blocks feature completeness** (incomplete implementations, TODO/FIXME items)
   - **P3 — Quality & polish** (type errors, lint warnings, missing tests, documentation)

2. Grep the ENTIRE codebase and **save counts as baseline** for Gate 5 verification:
   ```bash
   grep -rn "TODO\|FIXME\|HACK\|XXX\|BROKEN" --include="*.py" --include="*.ts" --include="*.tsx" .
   grep -rn "NotImplementedError\|raise NotImplementedError" --include="*.py" .
   grep -rn "pass$\|pass  #" --include="*.py" .

   # Save baseline counts
   echo "TODO_BASELINE=$(grep -rn 'TODO\|FIXME\|HACK\|XXX\|BROKEN' --include='*.py' --include='*.ts' --include='*.tsx' . | wc -l)" > docs/PHASE2_BASELINE.txt
   echo "NOT_IMPL_BASELINE=$(grep -rn 'NotImplementedError' --include='*.py' . | wc -l)" >> docs/PHASE2_BASELINE.txt
   git add docs/PHASE2_BASELINE.txt && git commit -m "docs: save Phase 2 baseline counts"
   ```

3. Run diagnostic commands and capture ALL output:
   ```bash
   # Backend diagnostics
   source .venv/bin/activate
   pip check 2>&1
   python -c "from api.main import app; print('Backend imports OK')" 2>&1
   ruff check . --statistics 2>&1
   bandit -r api/ services/ core/ middleware/ models/ utils/ --severity-level medium 2>&1

   # Frontend diagnostics
   cd frontend && pnpm install 2>&1
   pnpm build 2>&1
   pnpm typecheck 2>&1
   pnpm lint 2>&1
   ```

4. Create `TaskCreate` entries for every P0 and P1 issue individually. Group P2 issues by module. Group P3 issues by type.

5. Write the full fix plan to `docs/FIX_PLAN.md` with:
   - Issue count by priority
   - Estimated fix order (dependency-aware)
   - Which issues can be fixed in parallel vs sequential
   - **Worktree assignment** — which worktree branch handles which issues
   - Risk assessment for each fix

**GATE 2**: Present the fix plan summary. Show P0 count, P1 count, P2 count, P3 count. Ask: **"Fix plan ready. [N] total issues across [M] modules. Permission to begin fixes?"**

---

## PHASE 3 — P0 FIXES: MAKE IT COMPILE (Gate: Clean Build)

**Objective**: Fix every P0 issue. The app must start without errors.

**WORKTREE ISOLATION REQUIRED** — 2 parallel worktrees.

**Rules**: Fix ONLY P0 issues. No refactoring, no improvements, no features. See OPERATING RULES for commit discipline. All agents: see Worktree Agent Setup for mandatory dependency installation.

### Setup Worktrees
```bash
git worktree add .worktrees/p0-backend -b fix/p0-backend
git worktree add .worktrees/p0-frontend -b fix/p0-frontend
```

### Backend P0 Fixes (worktree: p0-backend)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p0-backend
FIRST: Set up dependencies per Worktree Agent Setup (python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt).

Fix all P0 (compilation-blocking) issues in the ruleIQ backend.
Reference docs/FIX_PLAN.md for the issue list.
Respect file partition rules. Remediate hardcoded secrets per the Secret Remediation Protocol (see sprint prompt).
After each fix: source .venv/bin/activate && python -c "from api.main import app; print('OK')"
Commit after each logical fix unit. Conventional commits with valid scopes (see REPO FACTS).
Report every file changed and every fix applied.
```

### Frontend P0 Fixes (worktree: p0-frontend)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p0-frontend
FIRST: Set up dependencies per Worktree Agent Setup (cd frontend && pnpm install).

Fix all P0 (compilation-blocking) issues in the ruleIQ frontend.
Reference docs/FIX_PLAN.md for the issue list.
Respect file partition rules.
After each fix: cd frontend && pnpm typecheck
Commit after each logical fix unit. Conventional commits with scope: frontend.
Report every file changed and every fix applied.
```

### After Both Teams Complete — Merge Back

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-3

# Per-worktree tests before merge
(cd .worktrees/p0-backend && source .venv/bin/activate && python -c "from api.main import app; print('Backend worktree: OK')")
(cd .worktrees/p0-frontend/frontend && pnpm typecheck)

# Merge
git merge --no-ff fix/p0-backend -m "merge: Phase 3 - backend P0 fixes"
git merge --no-ff fix/p0-frontend -m "merge: Phase 3 - frontend P0 fixes"

# Cleanup
git branch -d fix/p0-backend
git branch -d fix/p0-frontend
git worktree remove .worktrees/p0-backend
git worktree remove .worktrees/p0-frontend

# Verify merged state
source .venv/bin/activate
python -c "from api.main import app; print('Backend: OK')"
cd frontend && pnpm build
echo "=== P0 VERIFICATION COMPLETE ==="
```

**GATE 3**: Show build output for both backend and frontend on the **merged sprint branch**. Both must succeed with zero errors. Ask: **"Clean build achieved. Backend and frontend compile. Permission to begin P1 fixes?"**

---

## PHASE 4 — P1 FIXES: MAKE IT WORK (Gate: Core Flows Pass)

**Objective**: Fix every P1 issue. All core user flows must function.

**WORKTREE ISOLATION REQUIRED** — 3 parallel worktrees. All agents: see Worktree Agent Setup for dependency installation. Respect file partition rules.

### Setup Worktrees
```bash
git worktree add .worktrees/p1-database -b fix/p1-database
git worktree add .worktrees/p1-api -b fix/p1-api-routes
git worktree add .worktrees/p1-frontend -b fix/p1-frontend-integration
```

### Database & Data Layer Fixes (worktree: p1-database)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p1-database
FIRST: Set up dependencies per Worktree Agent Setup.

Fix all database and data layer issues in ruleIQ.
Respect file partition rules. You may READ services/neo4j_service.py for context but do NOT modify it.
Databases: PostgreSQL (Neon) via SQLAlchemy, Neo4j (GraphRAG), Redis (cache/sessions).
For each issue:
1. Verify Alembic migrations are consistent with SQLAlchemy models
2. Fix ORM model issues (missing fields, wrong types)
3. Verify Neo4j Cypher queries are syntactically correct
4. Verify Redis operations (session store, JWT blacklist, rate limiting)
5. Check connection pooling and error handling
Commit after each fix. Use: fix(db): description
```

### API Route Fixes (worktree: p1-api)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p1-api
FIRST: Set up dependencies per Worktree Agent Setup.

Fix all broken API routes in ruleIQ backend.
Respect file partition rules. Entrypoint: api.main:app. All routes: /api/v1/ pattern.
For each route:
1. Verify the route handler exists and is properly decorated
2. Verify request/response Pydantic models are complete
3. Verify database queries work (SQLAlchemy models match schema)
4. Verify JWT auth middleware is applied (30min access, 7day refresh)
5. Write a basic smoke test for each fixed route in tests/
Commit after each route group fix. Use: fix(api): description
```

### Frontend Integration Fixes (worktree: p1-frontend)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p1-frontend
FIRST: Set up dependencies per Worktree Agent Setup.

Fix all frontend-to-backend integration issues in ruleIQ.
Respect file partition rules. API client: frontend/lib/api/client.ts (auto /api/v1/ normalization).
State: Zustand stores, TanStack Query.
For each integration point:
1. Verify every API call matches an existing backend route
2. Fix request/response type mismatches
3. Fix JWT token handling (access + refresh flow)
4. Fix error handling and loading states
5. Verify all pages render without runtime errors
Commit after each component group fix. Use: fix(frontend): description
```

### After All Teams Complete — Merge Back

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-4

# Per-worktree tests
(cd .worktrees/p1-database && source .venv/bin/activate && make test-group-unit 2>&1 | tail -5)
(cd .worktrees/p1-api && source .venv/bin/activate && make test-group-unit 2>&1 | tail -5)
(cd .worktrees/p1-frontend/frontend && pnpm test --run 2>&1 | tail -5)

# Merge in dependency order: database → api-routes → frontend
git merge --no-ff fix/p1-database -m "merge: Phase 4 - database fixes"
git merge --no-ff fix/p1-api-routes -m "merge: Phase 4 - API route fixes"
git merge --no-ff fix/p1-frontend-integration -m "merge: Phase 4 - frontend integration fixes"

# Cleanup
git branch -d fix/p1-database
git branch -d fix/p1-api-routes
git branch -d fix/p1-frontend-integration
git worktree remove .worktrees/p1-database
git worktree remove .worktrees/p1-api
git worktree remove .worktrees/p1-frontend

# Integration verification on merged state
source .venv/bin/activate
python -c "from api.main import app; print('Backend: OK')"
make test-group-unit 2>&1 || echo "Unit tests need attention"
cd frontend && pnpm build && pnpm test --run 2>&1
```

**GATE 4**: Show test results and route verification from **merged sprint branch**. List remaining failures. Ask: **"Core functionality restored. [N/M] routes working, [X] tests passing. Permission to begin P2 completion?"**

---

## PHASE 5 — P2 FIXES: MAKE IT COMPLETE (Gate: Feature Checklist Signed Off)

**Objective**: Complete all incomplete implementations. Every feature stub becomes real code.

**WORKTREE ISOLATION REQUIRED** — up to 4 parallel worktrees, partitioned by module. All agents: see Worktree Agent Setup for dependency installation. Respect file partition rules.

**Scope cap**: Any TODO/FIXME item requiring >50 new lines of code OR an architectural decision (new database table, new API pattern, new state management approach) is **DEFERRED**. Create a GitHub issue: `gh issue create --title "DEFERRED: <description>" --body "<context>" --label "tech-debt"`.

1. Build a **Feature Completeness Checklist** from the TODO/FIXME/NotImplementedError scan in Phase 2
2. Group features by module (services, api, frontend, langgraph)
3. Create one worktree per module:
   ```bash
   git worktree add .worktrees/p2-services -b feat/p2-services
   git worktree add .worktrees/p2-api -b feat/p2-api
   git worktree add .worktrees/p2-frontend -b feat/p2-frontend
   git worktree add .worktrees/p2-langgraph -b feat/p2-langgraph
   ```

### Services Completion (worktree: p2-services)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p2-services
FIRST: Set up dependencies per Worktree Agent Setup.

Complete all TODO/FIXME/NotImplementedError items in services/, core/, and utils/.
Respect file partition rules. Scope cap: items requiring >50 lines or architectural decisions → DEFERRED (create GitHub issue via gh CLI).
For each item:
1. Read surrounding code to understand intent
2. Implement the missing functionality fully
3. Add input validation and error handling
4. Write at least one test per completed function
5. Update related docstrings
Commit after each completed feature. Use: feat(services): description
```

### API Completion (worktree: p2-api)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p2-api
FIRST: Set up dependencies per Worktree Agent Setup.

Complete all TODO/FIXME/NotImplementedError items in api/ and middleware/.
Respect file partition rules. Scope cap: items requiring >50 lines or architectural decisions → DEFERRED (create GitHub issue).
For each item:
1. Read surrounding code to understand intent
2. Implement the missing route handler or middleware logic
3. Add input validation and proper error responses
4. Write at least one test per completed endpoint
5. Verify: source .venv/bin/activate && python -c "from api.main import app; print('OK')"
Commit after each completed feature. Use: feat(api): description
```

### Frontend Completion (worktree: p2-frontend)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p2-frontend
FIRST: Set up dependencies per Worktree Agent Setup.

Complete all TODO/FIXME items in frontend/.
Respect file partition rules. Scope cap: items requiring >50 lines or architectural decisions → DEFERRED (create GitHub issue).
For each item:
1. Read surrounding code to understand intent
2. Implement the missing UI component or feature logic
3. Add proper TypeScript types, error handling, loading states
4. Write at least one Vitest test per completed component
5. Verify: pnpm typecheck && pnpm test --run
Commit after each completed feature. Use: feat(frontend): description
```

### LangGraph Completion (worktree: p2-langgraph)
Spawn a `general-purpose` agent:
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p2-langgraph
FIRST: Set up dependencies per Worktree Agent Setup.

Complete all TODO/FIXME/NotImplementedError items in langgraph_agent/.
Respect file partition rules. Scope cap: items requiring >50 lines or architectural decisions → DEFERRED (create GitHub issue).
For each item:
1. Read surrounding code to understand the PPALE loop and graph structure
2. Implement the missing agent node, tool, or graph edge
3. Add input validation and error handling
4. Write at least one test per completed function
5. Verify: source .venv/bin/activate && python -c "import langgraph_agent; print('OK')"
Commit after each completed feature. Use: feat(langgraph): description
```

### After All Modules Complete — Sequential Merge

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-5

# Per-worktree tests
(cd .worktrees/p2-services && source .venv/bin/activate && make test-group-unit 2>&1 | tail -5)
(cd .worktrees/p2-api && source .venv/bin/activate && make test-group-unit 2>&1 | tail -5)
(cd .worktrees/p2-frontend/frontend && pnpm test --run 2>&1 | tail -5)
(cd .worktrees/p2-langgraph && source .venv/bin/activate && pytest tests/ -x -q 2>&1 | tail -5)

# Merge in dependency order: services → api → langgraph → frontend
git merge --no-ff feat/p2-services -m "merge: Phase 5 - services completion"
git merge --no-ff feat/p2-api -m "merge: Phase 5 - API completion"
git merge --no-ff feat/p2-langgraph -m "merge: Phase 5 - langgraph completion"
git merge --no-ff feat/p2-frontend -m "merge: Phase 5 - frontend completion"

# Cleanup
git branch -d feat/p2-services
git branch -d feat/p2-api
git branch -d feat/p2-langgraph
git branch -d feat/p2-frontend
git worktree remove .worktrees/p2-services
git worktree remove .worktrees/p2-api
git worktree remove .worktrees/p2-frontend
git worktree remove .worktrees/p2-langgraph

# Feature verification on merged state
source .venv/bin/activate
make test-groups-parallel 2>&1
cd frontend && pnpm test --run && pnpm build 2>&1
```

**GATE 5**: Show the Feature Completeness Checklist with all items checked or deferred. Run fresh verification on merged branch:
```bash
cat docs/PHASE2_BASELINE.txt
echo "CURRENT_TODO=$(grep -rn 'TODO\|FIXME\|HACK\|XXX\|BROKEN' --include='*.py' --include='*.ts' --include='*.tsx' . | wc -l)"
echo "CURRENT_NOT_IMPL=$(grep -rn 'NotImplementedError' --include='*.py' . | wc -l)"
```
Show test results and TODO/NotImplementedError reduction. Ask: **"All features implemented or deferred. [N/N] complete, [D] deferred, [X] tests passing. TODO count reduced from [baseline] to [current]. Permission to begin quality hardening?"**

---

## PHASE 6 — P3 FIXES: MAKE IT PRODUCTION-GRADE (Gate: Quality Audit Passed)

**Objective**: Harden everything for production. Security, performance, reliability.

**WORKTREE ISOLATION REQUIRED** — 2 waves plus a between-wave step. All agents: see Worktree Agent Setup for dependency installation. Respect file partition rules.

### Wave 1 (Parallel — Low Conflict Risk)

```bash
git worktree add .worktrees/p3-lint -b fix/p3-type-safety
git worktree add .worktrees/p3-docs -b fix/p3-documentation
```

#### Type Safety & Linting Agent (worktree: p3-lint)
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p3-lint
FIRST: Set up dependencies per Worktree Agent Setup.

Fix all type errors and lint warnings in ruleIQ.
Backend: Run `ruff check . --fix` and `ruff format .`. Fix remaining errors manually.
Frontend: Run `pnpm typecheck`, fix all errors. Run `pnpm lint --fix`, fix remaining.
Add missing type annotations to all public functions.
Fix any remaining `type: ignore` or `@ts-ignore` comments with proper types.
Commit fixes grouped by module. Use: fix(scope): lint and type fixes
```

#### Documentation Agent (worktree: p3-docs)
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p3-docs
FIRST: Set up dependencies per Worktree Agent Setup.

Update production documentation for ruleIQ.
Respect file partition rules (docs/, README.md — DO NOT overwrite, append/update).
- Verify OpenAPI docs load at /docs when server runs
- Update README.md: setup instructions, architecture overview, deployment guide
- Create docs/ENV_VARS.md: every env var, purpose, required/optional, example
- Update docs/API_ENDPOINTS_DOCUMENTATION.md with any new/changed routes
- Create docs/DEPLOYMENT_RUNBOOK.md
Commit: docs: update [document]
```

### Wave 1 Merge

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-6-wave1
git merge --no-ff fix/p3-type-safety -m "merge: Phase 6 Wave 1 - type safety & lint"
git merge --no-ff fix/p3-documentation -m "merge: Phase 6 Wave 1 - documentation"
git branch -d fix/p3-type-safety
git branch -d fix/p3-documentation
git worktree remove .worktrees/p3-lint
git worktree remove .worktrees/p3-docs
```

### Test Coverage (between waves — depends on type-safety fixes being merged)

```bash
git worktree add .worktrees/p3-tests -b fix/p3-test-coverage
```

#### Test Coverage Agent (worktree: p3-tests)
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p3-tests
FIRST: Set up dependencies per Worktree Agent Setup.

Bring test coverage to >=80% for ruleIQ.
Respect file partition rules (tests/, frontend/tests/).
- Run coverage: `make test-group-unit` + `pnpm test:coverage`
- Read docs/COVERAGE_BASELINE.md for current state
- Write unit tests for untested service layer functions
- Write unit tests for untested API route handlers
- Write frontend component tests for untested components
- Add edge case tests for critical business logic
- All tests MUST be deterministic and isolated
Run final coverage report and save to docs/COVERAGE_REPORT.md
Commit: test(scope): add coverage for [module]
```

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-6-tests
git merge --no-ff fix/p3-test-coverage -m "merge: Phase 6 - test coverage"
git branch -d fix/p3-test-coverage
git worktree remove .worktrees/p3-tests
```

### Wave 2 (Parallel — Edits Existing Code, runs AFTER types + tests are merged)

```bash
git worktree add .worktrees/p3-security -b fix/p3-security
git worktree add .worktrees/p3-resilience -b fix/p3-resilience
```

#### Security Hardening Agent (worktree: p3-security)
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p3-security
FIRST: Set up dependencies per Worktree Agent Setup.

Perform a full security audit of ruleIQ.
Follow the HARDCODED SECRET REMEDIATION PROTOCOL for any secrets found.
- Scan for hardcoded secrets (KNOWN: neo4j_service.py, compliance_ingestion_pipeline.py, ingestion_fixed.py)
- Check CORS configuration in api/main.py middleware stack
- Verify JWT auth middleware on all 56+ routes
- Check for SQL injection in SQLAlchemy queries
- Check for XSS in frontend React components
- Run `pip audit` (backend) and `pnpm audit` (frontend)
- Verify environment variable handling: NO defaults for secrets, fail if not set
Fix all critical and high severity issues. Report medium/low for review.
Commit: fix(security): description
```

#### Error Handling & Resilience Agent (worktree: p3-resilience)
```
Working directory: C:\Users\OmarAl-Bakri\ruleIQ\.worktrees\p3-resilience
FIRST: Set up dependencies per Worktree Agent Setup.

Audit and fix error handling across ruleIQ. Respect file partition rules.
- Every API endpoint must return structured error responses (not bare 500s)
- Database operations must handle connection failures gracefully (PostgreSQL, Neo4j, Redis)
- External API calls (Gemini, OpenAI) must have timeout and retry logic
- Frontend must handle: loading, error, empty, offline states
- Add/verify global error boundary in frontend app layout
- Add structured logging (Python logging module, not print statements)
- Verify graceful shutdown handling in api/main.py
Commit: fix(scope): improve error handling for [area]
```

### Wave 2 Merge

```bash
git checkout sprint/production-ready
git tag checkpoint/before-phase-6-wave2
git merge --no-ff fix/p3-security -m "merge: Phase 6 Wave 2 - security hardening"
git merge --no-ff fix/p3-resilience -m "merge: Phase 6 Wave 2 - error handling & resilience"
git branch -d fix/p3-security
git branch -d fix/p3-resilience
git worktree remove .worktrees/p3-security
git worktree remove .worktrees/p3-resilience
```

### Production Readiness Audit (on merged sprint branch)

```bash
source .venv/bin/activate
pip audit 2>&1
bandit -r api/ services/ core/ middleware/ models/ utils/ --severity-level medium 2>&1
detect-secrets scan --baseline .secrets.baseline 2>&1
trivy fs . --severity HIGH,CRITICAL 2>/dev/null || echo "trivy not installed — SKIP container scan"
cd frontend && pnpm audit 2>&1
cd .. && ruff check . --statistics 2>&1
cd frontend && pnpm typecheck 2>&1
cd frontend && pnpm lint 2>&1
cd .. && make test-groups-parallel 2>&1
cd frontend && pnpm test:coverage 2>&1
cd frontend && pnpm build 2>&1
```

**GATE 6**: Show ALL audit results in a summary table:

| Check | Status | Details |
|-------|--------|---------|
| pip audit | PASS/FAIL | N vulnerabilities |
| pnpm audit | PASS/FAIL | N vulnerabilities |
| bandit | PASS/FAIL | N issues (high/medium/low) |
| detect-secrets | PASS/FAIL | N new secrets vs baseline |
| trivy | PASS/FAIL/SKIP | Container vulnerabilities |
| ruff check | PASS/FAIL | N errors, N warnings |
| pnpm typecheck | PASS/FAIL | N errors |
| pnpm lint | PASS/FAIL | N warnings |
| Backend tests | PASS/FAIL | N/N passing |
| Frontend tests | PASS/FAIL | N/N passing, X% coverage |
| Frontend build | PASS/FAIL | Build time |

ALL must be PASS or ACCEPTABLE. Ask: **"Quality audit complete. Production readiness at [X]%. Permission to finalize?"**

---

## PHASE 7 — FINALIZATION (Gate: Ship It)

**Objective**: Final polish, commit hygiene, and delivery. No worktrees — all work on sprint branch.

1. **Final Secrets Scan**:
   ```bash
   detect-secrets scan --all-files 2>&1
   grep -n "password\|secret\|key\|token" env.template env.comprehensive.template | grep -vi "placeholder\|CHANGE_ME\|your_.*_here\|#"
   ```
2. **Env Var Completeness Check**:
   ```bash
   grep -rohn 'os\.environ\["[^"]*"\]\|os\.getenv("[^"]*")' --include="*.py" . | sort -u > /tmp/backend_envs.txt
   grep -rohn 'process\.env\.\w*' --include="*.ts" --include="*.tsx" frontend/ | sort -u > /tmp/frontend_envs.txt
   echo "=== Backend env vars NOT in templates ===" && comm -23 /tmp/backend_envs.txt <(grep -o '[A-Z_]*' env.template env.comprehensive.template | sort -u) || true
   ```
3. **Commit Hygiene**: `git log --oneline sprint/production-ready ^main`. Ensure conventional commit format. Flag non-conventional messages.
   - **NOTE**: Do NOT squash or rebase interactively — this destroys merge history.
4. **Final Full Test Run**:
   ```bash
   source .venv/bin/activate
   make test-groups-parallel 2>&1
   cd frontend && pnpm test --run && pnpm test:e2e 2>&1
   ```
   Zero failures required.
5. **Final Build**: `cd frontend && rm -rf .next && pnpm build 2>&1`
6. **Git Summary**:
   ```bash
   git diff main...HEAD --stat
   git log --oneline main...HEAD | wc -l
   ```
7. **PR Preparation**:
   ```
   ## Summary
   - Phase 1: Codebase reconnaissance — [N] issues catalogued
   - Phase 3: P0 fixes — [N] compilation blockers resolved
   - Phase 4: P1 fixes — [N] core functionality issues resolved
   - Phase 5: P2 fixes — [N] features completed, [D] deferred
   - Phase 6: P3 fixes — security, types, tests, docs, resilience

   ## Test plan
   - [ ] Backend: make test-groups-parallel (1884+ tests)
   - [ ] Frontend: pnpm test && pnpm test:e2e
   - [ ] Build: pnpm build succeeds
   - [ ] Security: pip audit && pnpm audit && detect-secrets clean
   ```

**GATE 7 (FINAL)**: Present:
- Total files changed
- Total commits on branch
- Total issues fixed (P0/P1/P2/P3 breakdown)
- Total deferred issues (with GitHub issue links)
- Test coverage percentage (backend + frontend)
- Build status (pass/fail)
- Secrets scan status (clean/issues)
- PR description draft

Ask: **"ruleIQ production sprint complete. Ready to push branch and create PR?"**

---

## OPERATING RULES (Apply to ALL phases)

### Commit Discipline
- Commit after every logical unit of work
- Never exceed 5 uncommitted files
- Use conventional commits: `type(scope): description` with valid scopes (see REPO FACTS)
- Never commit secrets, .env files, node_modules, .worktrees/

### Worktree Discipline
- ALL parallel write phases MUST use worktrees for isolation
- Worktrees are created manually by the lead — agents receive the path via prompt
- Each agent operates ONLY within its assigned worktree
- Merges happen ONLY on the sprint branch, ONLY by the lead
- Always verify builds pass on the merged sprint branch after merging
- Tag before every merge phase: `git tag checkpoint/before-phase-N`
- Delete branches after merge: `git branch -d <branch>`
- Clean up worktrees immediately after successful merge
- If merge conflicts occur: follow the Conflict Resolution Guide, re-run tests, report to me

### Quality Gates Are Non-Negotiable
- Do NOT proceed past any gate without my explicit approval
- If a gate fails, loop back and fix until it passes (max 3 retries per gate, then escalate)
- Show me tool output as proof — reasoning alone is insufficient
- Gates are verified on the **merged sprint branch**, not on individual worktree branches

### Parallel Execution
- Always launch independent agents in parallel
- Use `TeamCreate` and `TaskCreate`/`TaskUpdate` for coordination
- Agents must respect file partition rules (see table above)

### Context Handoffs
- Each phase must write its findings to `docs/` for the next phase to read
- Agents must read previous phase artifacts before starting
- The Critical Issues Registry (`docs/SPRINT_ARCHITECTURE.md`) is the single source of truth — update it as issues are fixed

### Error Recovery
- If an agent fails, retry once. If it fails again, report the failure and continue with remaining work
- If a build breaks during fixes, stop and fix the regression before continuing
- Never leave the codebase in a broken state between commits
- If a worktree merge creates conflicts that can't be auto-resolved, report to me before proceeding

### Gate Failure Protocol
- Retry fixes up to 3 times per gate
- After 3 failures, present a root cause analysis and ask for guidance
- Never loop indefinitely — budget max 45 min per phase before escalating

---

## BEGIN

Start with **Phase 0**. Execute each step. Report your environment summary. Then ask for Gate 0 approval.
