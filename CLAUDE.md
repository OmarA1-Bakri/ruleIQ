# CLAUDE.md - Claude Code Optimization Guide

**Purpose**: Maximize Claude Code's performance when working with the ruleIQ codebase.

**Project Status**: 98% Production-Ready | 671+ Tests Passing | <200ms API Response | 8.5/10 Security Score

## 🚀 AUTOMATIC INITIALIZATION

### Serena MCP Auto-Check (Session Start)
```bash
# Status verification (auto-run at session start)
serena /check_onboarding_performed
serena /mcp-serena-initial-instruction

# Expected indicators:
# ✅ Active project: ruleIQ
# ✅ Active context: desktop-app
# ✅ Active modes: interactive, editing
# ✅ Tool stats collection: enabled
# ✅ Onboarding: completed
```

### 🔧 Serena MCP Reactivation
**Check before every user command:**
```bash
serena activate_project ruleIQ
serena check_onboarding_performed
```

## 🏗️ TECH STACK & ARCHITECTURE

### Stack Overview
- **Backend**: FastAPI (Python 3.11+) + Celery + Redis
- **Frontend**: Next.js 15.2.4 (TypeScript) with Turbopack
- **Database**: Neon PostgreSQL (Cloud) + Redis (Caching)
- **AI**: Google Gemini + OpenAI with Circuit Breaker Pattern
- **Auth**: JWT + AES-GCM + RBAC Middleware
- **Hosting**: Digital Ocean + Cloudflare

### Key Agents (4 Main + Specialized)
1. **IQ Agent**: Main AI compliance assistant
2. **RAG Agent**: Document analysis & retrieval
3. **Assessment Agent**: Compliance questionnaires
4. **Integration Agent**: External service connections
5. **Specialized**: GDPR, Companies House, Employment Law, etc.

## 🧠 SERENA MCP INTEGRATION

### Quick Reference
```bash
# Already activated for this project!
# Access memories with: mcp__serena__read_memory
# Key memories:
- ALWAYS_READ_FIRST          # Critical coding guidelines
- FRONTEND_CONDENSED_2025    # Frontend tasks & status
- BACKEND_CONDENSED_2025     # Backend reference
- MEMORY_CATEGORIES_2025     # Memory organization
```

### Serena Tools You'll Use Most
- `mcp__serena__find_symbol` - Find classes, functions, methods
- `mcp__serena__replace_symbol_body` - Edit code precisely
- `mcp__serena__search_for_pattern` - Search across codebase
- `mcp__serena__get_symbols_overview` - Understand file structure

### Memory Best Practices
1. Read `ALWAYS_READ_FIRST` at session start
2. Check condensed memories for area-specific work
3. Don't read same memory multiple times
4. Write new memories for significant discoveries

## ⚡ IMMEDIATE ACTIONS FOR ANY TASK

1. **Activate Environment**: `source /home/omar/Documents/ruleIQ/.venv/bin/activate`
2. **Check Serena MCP**: Already activated for enhanced code intelligence
3. **Read Relevant Memories**: Use `mcp__serena__read_memory` for context:
   - Frontend: `FRONTEND_CONDENSED_2025`
   - Backend: `BACKEND_CONDENSED_2025`
   - Critical: `ALWAYS_READ_FIRST`

## 🎯 TASK COMPLETION CHECKLIST

Before marking any task complete, ensure:
- [ ] Code compiles without errors
- [ ] Tests pass: `make test-fast` (backend) or `pnpm test` (frontend)
- [ ] Linting clean: `ruff check .` (backend) or `pnpm lint` (frontend)
- [ ] Type checking: `ruff check .` (backend) or `pnpm typecheck` (frontend)
- [ ] No hardcoded values or secrets
- [ ] Field mappers used for truncated DB columns
- [ ] Rate limiting considered for new endpoints

## 🛠️ ESSENTIAL COMMANDS

### Backend Commands (Python/FastAPI)
```bash
# ALWAYS START WITH:
source /home/omar/Documents/ruleIQ/.venv/bin/activate

# Development
python main.py                    # Start server (http://localhost:8000)
make test-fast                    # Quick tests (2-5 min) - RUN BEFORE COMMITS
ruff check . && ruff format .     # Lint & format - MUST BE CLEAN

# Database
alembic upgrade head              # Apply migrations
python database/init_db.py        # Initialize database

# Testing by type
pytest -m unit                    # Unit tests only
pytest -m api                     # API tests only
pytest -m security                # Security tests only
```

### Frontend Commands (Next.js/TypeScript)
```bash
cd frontend

# Development (Now with Turbopack!)
pnpm dev --turbo                  # Start dev server with Turbopack (http://localhost:3000)
pnpm test                         # Run tests - RUN BEFORE COMMITS
pnpm lint && pnpm typecheck       # Lint & type check - MUST BE CLEAN

# Build & Deploy
pnpm build                        # Production build
pnpm test:e2e                     # E2E tests with Playwright

# Theme Testing (Active Migration)
NEXT_PUBLIC_USE_NEW_THEME=true pnpm dev --turbo  # Test teal theme
```

## 🏗️ ARCHITECTURE QUICK REFERENCE

### Critical Patterns to Follow
- **AI Services**: Circuit breaker with fallback (see `services/ai/`)
- **Auth**: JWT + AES-GCM encryption + RBAC middleware
- **State**: Zustand (client) + TanStack Query (server) - DON'T MIX
- **Database**: Field mappers for truncated columns
- **Rate Limits**: General 100/min, AI 20/min, Auth 5/min

### Key Files & Locations
```
Backend:
- API Routes: api/routers/*.py
- Business Logic: services/*.py
- AI Services: services/ai/*.py (circuit breaker, fallback, optimizer)
- RBAC: api/middleware/rbac_*.py
- Models: database/models.py

Frontend:
- Pages: frontend/app/(dashboard)/
- Components: frontend/components/ui/ (shadcn/ui based)
- API Clients: frontend/lib/api/
- State: frontend/lib/stores/ (Zustand)
- Hooks: frontend/lib/tanstack-query/hooks/
```

## ⚠️ CRITICAL KNOWN ISSUES

### 1. Database Column Truncation
**Problem**: Legacy columns truncated to 16 chars  
**Examples**: `handles_persona` → `handles_personal_data`  
**SOLUTION**: ALWAYS use field mappers: `frontend/lib/api/business-profile/field-mapper.ts`

### 2. Frontend Teal Migration (65% Complete)
**Problem**: Mixed purple/cyan legacy colors  
**SOLUTION**: Check `FRONTEND_CONDENSED_2025` memory for migration tasks

### 3. Celery Worker Rate Limiting
**Problem**: 529 API overload errors  
**SOLUTION**: Rate limits already configured (see `celery_app.py`)

## 📋 COMMON WORKFLOWS

### Adding New API Endpoint
```bash
1. Create router: api/routers/new_feature.py
2. Add service: services/new_feature_service.py
3. Define schemas: api/schemas/new_feature.py
4. Add tests: tests/test_new_feature.py
5. Add rate limiting in api/middleware/rate_limiter.py
6. RUN: make test-fast
```

### Adding New Frontend Page
```bash
1. Create page: frontend/app/(dashboard)/new-page/page.tsx
2. Add API client: frontend/lib/api/new-feature.ts
3. Add store (if needed): frontend/lib/stores/new-feature-store.ts
4. Add hooks: frontend/lib/tanstack-query/hooks/use-new-feature.ts
5. Add tests: frontend/tests/new-feature.test.tsx
6. RUN: cd frontend && pnpm test
```

### Working with AI Services
- ALWAYS use circuit breaker pattern (see `services/ai/circuit_breaker.py`)
- ALWAYS provide fallback responses
- ALWAYS implement caching for similar requests
- Test with: `pytest -m ai`

## 🔐 SECURITY & ENVIRONMENT

### Environment Variables
```bash
# Generate JWT secret
python generate_jwt_secret.py

# Required vars (see .env.template)
DATABASE_URL=postgresql://...@ep-*-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
REDIS_URL=redis://...
GOOGLE_API_KEY=...
JWT_SECRET_KEY=...
ALLOWED_ORIGINS=http://localhost:3000
```

### Security Checklist
- [ ] Input validation on ALL endpoints
- [ ] Rate limiting configured
- [ ] No secrets in code
- [ ] Field mappers for DB columns
- [ ] RBAC permissions checked

## 🚨 TROUBLESHOOTING

### Common Issues & Solutions

**Backend Won't Start**
```bash
# Check environment
source /home/omar/Documents/ruleIQ/.venv/bin/activate
# Check Redis (Neon is cloud-based)
docker-compose ps
# Initialize DB if needed
python database/init_db.py
```

**Frontend Build Errors**
```bash
cd frontend
pnpm install  # Reinstall dependencies
rm -rf .next  # Clear build cache
pnpm dev --turbo  # Restart with Turbopack
```

**Test Failures**
```bash
# Backend: Run specific test
pytest tests/test_specific.py::test_name -v
# Frontend: Debug mode
cd frontend && pnpm test -- --reporter=verbose
```

**Celery Worker Issues**
```bash
# Check worker logs
docker-compose logs celery_worker
# Restart worker
docker-compose restart celery_worker
```

## 📚 QUICK LINKS

- **Full Plan**: `frontend/FRONTEND_DESIGN_COMPLIANCE_PLAN.md`
- **API Docs**: http://localhost:8000/docs (when running)
- **Frontend Preview**: http://localhost:3000
- **Test Coverage**: Run `make test-coverage` or `pnpm test:coverage`

## 🧪 CURRENT STATUS

### Latest Updates (2025-08-15)
- ✅ Turbopack enabled for faster development
- ✅ Free Compliance Health Check banner added
- ✅ Landing page optimizations (logo size, navigation, scroll indicator)
- ✅ Sentry SDK updated with onRequestError handler
- 🔧 Frontend Teal Migration: 65% complete
- 🔧 TypeScript errors: Being resolved

### Marketing Page Teal Migration (READY FOR TESTING)
- **File**: `frontend/app/marketing/page.tsx`
- **Status**: Cleaned up, teal design system implemented
- **Test Command**: `cd frontend && pnpm dev --turbo` then visit `/marketing`
- **Verify**: All colors use teal palette, no Aceternity components

---

**Remember**: This file is optimized for Claude Code performance. Keep it updated with critical patterns and always run tests before marking tasks complete!