# API Alignment Migration Plan

## Overview
This plan outlines the step-by-step migration to fix API naming inconsistencies between frontend and backend, ensuring zero downtime and full rollback capability.

## Current State (As of 2024-01-24)
- **Connection Rate**: 11.4% (only 12 of 105 frontend calls properly connect)
- **Total Backend Endpoints**: 166
- **Total Frontend Calls**: 112
- **Issues Fixed**: 6 trailing slashes, standardized parameter names
- **Duplicates Identified**: 18 endpoints ready for removal

## Migration Phases

### Phase 1: Backend Fixes ✅ COMPLETED
**Status**: Completed on fix/api-alignment-naming branch
**Changes Made**:
1. Removed trailing slashes from 6 endpoints
2. Standardized parameter names ({session_id} → {id}, {profile_id} → {id})
3. Tested backend still starts and responds

**Rollback**: `git revert 48a4fe1`

### Phase 2: Duplicate Cleanup (CURRENT)
**Timeline**: Day 1-2
**Actions**:
1. Execute cautious cleanup to remove semantic duplicates
2. Comment out deprecated namespaces
3. Test all remaining endpoints
4. Document removed endpoints for reference

**Commands**:
```bash
# Execute cleanup
python scripts/cleanup-duplicates.py --execute

# Test endpoints
pytest tests/test_api_endpoints.py -v

# Verify OpenAPI spec
curl http://localhost:8000/openapi.json | jq '.paths | keys | length'
```

**Rollback**: 
```bash
git stash  # Save any uncommitted changes
git checkout HEAD~1  # Go back one commit
```

### Phase 3: Frontend Service Updates
**Timeline**: Day 2-3
**Actions**:
1. Update API client to handle both old and new patterns
2. Update each service file systematically:
   - assessments.service.ts
   - policies.service.ts
   - evidence.service.ts
   - business-profiles.service.ts
3. Add compatibility layer in client.ts

**Compatibility Layer** (frontend/lib/api/client.ts):
```typescript
const normalizeEndpoint = (endpoint: string): string => {
  // Remove trailing slashes
  endpoint = endpoint.replace(/\/$/, '');
  
  // Standardize parameter names
  endpoint = endpoint.replace(/\{session_id\}/, '{id}');
  endpoint = endpoint.replace(/\{profile_id\}/, '{id}');
  endpoint = endpoint.replace(/\{policy_id\}/, '{id}');
  
  // Add API prefix if missing
  if (!endpoint.startsWith('/api')) {
    endpoint = `/api/v1${endpoint}`;
  }
  
  return endpoint;
};
```

**Testing**:
```bash
cd frontend
pnpm test
pnpm test:e2e
```

### Phase 4: Integration Testing
**Timeline**: Day 3-4
**Actions**:
1. Run full integration test suite
2. Test critical user flows:
   - User registration and login
   - Assessment creation and completion
   - Policy generation
   - Evidence upload
3. Monitor error logs for 404s
4. Check browser console for failed API calls

**Test Commands**:
```bash
# Backend tests
make test-integration

# Frontend E2E tests
cd frontend && pnpm test:e2e

# API contract tests
python scripts/test-api-contracts.py
```

### Phase 5: Production Deployment
**Timeline**: Day 4-5
**Pre-deployment Checklist**:
- [ ] All tests passing
- [ ] No 404 errors in logs
- [ ] Frontend properly connects to all endpoints
- [ ] OpenAPI documentation updated
- [ ] Postman collection updated
- [ ] Team notified of changes

**Deployment Steps**:
1. Deploy backend with backward compatibility
2. Monitor for 30 minutes
3. Deploy frontend updates
4. Monitor for 1 hour
5. Remove backward compatibility layer (optional, after 1 week)

**Rollback Plan**:
```bash
# Quick rollback (within 1 hour)
git revert HEAD  # Revert last commit
git push origin fix/api-alignment-naming --force-with-lease

# Full rollback (if issues discovered later)
git checkout main
git revert merge-commit-sha
git push origin main
```

## Success Metrics
- [ ] 100% API connection rate (up from 11.4%)
- [ ] 0 duplicate endpoints (down from 18)
- [ ] All endpoints follow RESTful naming convention
- [ ] <5ms added latency from compatibility layer
- [ ] 0 production incidents during migration

## Risk Mitigation

### Risk 1: Breaking Frontend Functionality
**Mitigation**: 
- Compatibility layer in client.ts handles both patterns
- Feature flags to toggle between old/new
- Gradual rollout by feature area

### Risk 2: Third-party Integrations Break
**Mitigation**:
- Maintain old endpoints as aliases for 30 days
- Document changes in API changelog
- Notify integration partners 1 week before

### Risk 3: Performance Degradation
**Mitigation**:
- Load test with new endpoint structure
- Monitor response times during rollout
- Have database indexes ready for new query patterns

## Monitoring Plan

### Key Metrics to Track
1. **API Response Times**: Should remain <200ms
2. **404 Error Rate**: Should be 0
3. **Frontend Error Rate**: Should not increase
4. **User Sessions**: Should not see drops
5. **Database Query Performance**: Should not degrade

### Alerting Thresholds
- 404 rate > 1% → Immediate investigation
- Response time > 500ms → Warning
- Error rate > 5% → Rollback consideration
- User session drops > 10% → Immediate rollback

## Communication Plan

### Internal Team
- Daily standup updates during migration
- Slack channel: #api-migration
- Documentation in Confluence/Wiki

### External Stakeholders
- Email notification 1 week before
- API changelog update
- Support team briefing

## Post-Migration Tasks
1. Remove deprecated code (after 30 days)
2. Update all documentation
3. Create new Postman collection
4. Archive old API documentation
5. Conduct retrospective

## Emergency Contacts
- Backend Lead: [Contact]
- Frontend Lead: [Contact]
- DevOps: [Contact]
- On-call Engineer: [Contact]

## Appendix

### Changed Endpoints Reference
See `api-alignment-report.json` for complete list

### Rollback Scripts
Located in `scripts/rollback/`

### Test Coverage Report
Current coverage: 85%
Target coverage: 95%

---

**Last Updated**: 2024-01-24
**Status**: Phase 2 - Duplicate Cleanup
**Next Review**: Before Phase 3 execution