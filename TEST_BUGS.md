# Test Bug Documentation

## Critical Database Schema Mismatch - AssessmentLead Model

**Problem**: The `AssessmentLead` SQLAlchemy model definition does not match the actual database table schema.

**Impact**: ALL tests that create `AssessmentLead` instances fail with `psycopg2.errors.UndefinedColumn` errors.

**Evidence**:
- Model defines fields like: `first_name`, `last_name`, `company_name`, `marketing_consent`, `ip_address`, `referrer_url`, `landing_page`
- Database table has fields like: `consent_marketing`, `source_ip`, `referrer` (missing many fields entirely)

**Error Example**:
```
psycopg2.errors.UndefinedColumn: column "first_name" of relation "assessment_leads" does not exist
```

**Affected Test Files**:
- `tests/database/test_freemium_models.py` - ALL AssessmentLead tests
- Any other tests that create AssessmentLead instances

**Recommended Fix**: 
1. Run database migration to add missing columns, OR
2. Update model definition to match actual database schema, OR  
3. Skip all AssessmentLead tests until schema is aligned

**Tests Marked as SKIPPED**: All AssessmentLead tests in test_freemium_models.py due to this schema mismatch.

---

## Database Teardown Issues

**Problem**: Foreign key constraints prevent clean database teardown during test cleanup.

**Error Example**:
```
psycopg2.errors.DependentObjectsStillExist: cannot drop table users because other objects depend on it
DETAIL: constraint integration_configurations_user_id_fkey on table integration_configurations depends on table users
HINT: Use DROP ... CASCADE to drop the dependent objects too.
```

**Recommended Fix**: Update test database cleanup to use CASCADE when dropping tables.