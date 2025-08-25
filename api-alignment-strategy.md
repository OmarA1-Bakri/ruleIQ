# API Alignment Strategy - RuleIQ

## Executive Summary
- **Current State**: Only 11.4% of frontend API calls properly connect to backend
- **Root Cause**: Multiple API naming conventions evolved independently
- **Impact**: 87 missing endpoints, 226 unused backend endpoints, 5 trailing slash issues
- **Solution**: Standardize on RESTful conventions with clear naming rules

## Current Problems

### 1. Naming Convention Conflicts
- Frontend expects: `/assessments`
- Client adds: `/api/v1` prefix
- Backend has: `/api/v1/assessments/` (with trailing slash)

### 2. Multiple API Prefixes
- `/api/v1/` - Main API endpoints
- `/api/admin/` - Admin endpoints
- `/api/ai/` - AI service endpoints
- `/api/freemium/` - Public endpoints
- No prefix - Some frontend expectations

### 3. Inconsistent Path Parameters
- Frontend: `/assessments/123`
- Backend: `/assessments/{session_id}`
- Mismatch in parameter naming

## Proposed Standard

### RESTful Naming Convention
```
/api/v1/{resource}              # List/Create
/api/v1/{resource}/{id}          # Get/Update/Delete
/api/v1/{resource}/{id}/{action} # Custom actions
/api/v1/{resource}/{id}/{nested} # Nested resources
```

### Rules
1. **No trailing slashes** - FastAPI will handle with/without
2. **Plural resource names** - `assessments` not `assessment`
3. **Kebab-case for multi-word** - `business-profiles` not `businessProfiles`
4. **Consistent ID parameters** - Always use `{id}` unless specific need
5. **Actions as POST endpoints** - `/assessments/{id}/complete` not PUT

## Implementation Plan

### Phase 1: Backend Standardization (Week 1)
1. Configure FastAPI to ignore trailing slashes
2. Standardize all endpoint paths
3. Create deprecation warnings for old endpoints
4. Add backward compatibility layer

### Phase 2: Frontend Alignment (Week 1-2)
1. Update API client to handle both old and new paths
2. Systematically update all service files
3. Add integration tests for each service

### Phase 3: Cleanup (Week 2)
1. Remove deprecated endpoints
2. Remove duplicate endpoints
3. Update OpenAPI documentation
4. Update Postman collections

## Endpoint Mapping

### Assessments
| Current Frontend | Current Backend | New Standard |
|-----------------|-----------------|--------------|
| `/assessments` | `/api/v1/assessments/` | `/api/v1/assessments` |
| `/assessments/${id}` | `/api/v1/assessments/{session_id}` | `/api/v1/assessments/{id}` |
| `/assessments/${id}/complete` | `/api/v1/assessments/{session_id}/complete` | `/api/v1/assessments/{id}/complete` |

### Business Profiles
| Current Frontend | Current Backend | New Standard |
|-----------------|-----------------|--------------|
| `/business-profiles` | `/api/v1/business-profiles/` | `/api/v1/business-profiles` |
| `/business-profiles/${id}` | N/A (Missing!) | `/api/v1/business-profiles/{id}` |

### Policies
| Current Frontend | Current Backend | New Standard |
|-----------------|-----------------|--------------|
| `/policies` | `/api/v1/policies/` | `/api/v1/policies` |
| `/policies/${id}` | N/A (Missing!) | `/api/v1/policies/{id}` |
| `/policies/generate` | `/api/v1/policies/generate` | `/api/v1/policies/generate` |

## Duplicates to Remove

### Backend Duplicates
1. `/api/admin/admin/users/` and `/api/v1/users/` - Consolidate to `/api/v1/admin/users`
2. `/api/ai/assessments/` and `/api/v1/assessments/ai/` - Consolidate to `/api/v1/assessments/ai`
3. Multiple chat endpoints spread across namespaces

### Frontend Duplicates
1. Multiple ways to call same endpoint in different services
2. Public vs authenticated versions of same calls

## Migration Strategy

### Step 1: Create Compatibility Layer
```python
# In FastAPI main.py
from fastapi import APIRouter

# Create router with both old and new paths
compatibility_router = APIRouter()

@compatibility_router.get("/api/v1/assessments/")
@compatibility_router.get("/api/v1/assessments")
async def get_assessments():
    # Single implementation
    pass
```

### Step 2: Update Frontend Services
```typescript
// Add compatibility in client.ts
const normalizeEndpoint = (endpoint: string): string => {
  // Remove trailing slashes
  endpoint = endpoint.replace(/\/$/, '');
  
  // Add API prefix if missing
  if (!endpoint.startsWith('/api')) {
    endpoint = `/api/v1${endpoint}`;
  }
  
  return endpoint;
};
```

### Step 3: Gradual Migration
1. Deploy compatibility layer
2. Update frontend one service at a time
3. Monitor for errors
4. Remove old endpoints after verification

## Success Metrics
- [ ] 100% API connection rate (up from 11.4%)
- [ ] 0 duplicate endpoints
- [ ] All endpoints follow naming convention
- [ ] Full test coverage for all endpoints
- [ ] Updated OpenAPI documentation
- [ ] Working Postman collection

## Risk Mitigation
1. **Backward Compatibility**: Keep old endpoints for 30 days
2. **Feature Flags**: Use flags to toggle between old/new
3. **Monitoring**: Track 404 errors and deprecated endpoint usage
4. **Rollback Plan**: Git tags at each phase for quick rollback

## Timeline
- **Day 1-2**: Backend compatibility layer
- **Day 3-5**: Frontend service updates
- **Day 6-7**: Testing and verification
- **Week 2**: Cleanup and documentation
- **Week 3-4**: Monitor and remove deprecated endpoints