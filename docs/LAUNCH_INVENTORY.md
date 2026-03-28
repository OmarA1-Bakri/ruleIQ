# RuleIQ Launch Inventory

This document defines the canonical v1 launch surface.

## Canonical Runtime

- Backend entrypoint: `api.main:app`
- Canonical API namespace: `/api/v1`
- Frontend launch surface:
  - Public and auth routes under `frontend/app`
  - Authenticated product routes under `frontend/app/(dashboard)`
- Hidden from GA:
  - `frontend/app/advanced-dashboard`
  - `frontend/app/dashboard`
  - `frontend/app/dashboard-2`
  - `frontend/app/demo`
  - `frontend/app/showcase`
  - `frontend/app/test-theme`
  - `frontend/app/_deprecated`
  - `frontend/app/design-system`
  - `frontend/app/neural-demo`
  - `frontend/app/editor`

## Launch Domains

### Identity and Access

- Frontend: auth flows in `frontend/app/(auth)`
- Backend:
  - `/api/v1/auth`
  - `/api/v1/admin`
  - `/api/v1/rbac`

### Onboarding and Business Profile

- Frontend:
  - `/onboarding`
  - business profile flows in the dashboard route group
- Backend:
  - `/api/v1/business-profiles`

### Assessments and Readiness

- Frontend:
  - assessment flows in the dashboard route group
- Backend:
  - `/api/v1/assessments`
  - `/api/v1/ai-assessments`
  - `/api/v1/readiness`
  - `/api/v1/compliance`
  - `/api/v1/frameworks`

### Policies and Implementation

- Frontend:
  - policies and implementation views in the dashboard route group
- Backend:
  - `/api/v1/policies`
  - `/api/v1/ai-policy`
  - `/api/v1/implementation`

### Evidence

- Frontend:
  - evidence views in the dashboard route group
- Backend:
  - `/api/v1/evidence`
  - `/api/v1/evidence-collection`
  - `/api/v1/foundation-evidence`

### Reporting

- Frontend:
  - `/reports`
- Backend:
  - `/api/v1/reports/history`
  - `/api/v1/reports/generate`
  - `/api/v1/reports/templates`
  - `/api/v1/reports/preview`
  - `/api/v1/reports/schedule`
  - `/api/v1/reports/scheduled`
  - `/api/v1/reports/analytics`
  - `/api/v1/reports/export-bundle`
  - `/api/v1/reports/upload`

### Chat and IQ

- Frontend:
  - `/chat`
- Backend:
  - `/api/v1/chat`
  - `/api/v1/iq-agent`

### Integrations

- Frontend:
  - integrations management in the dashboard route group
- Backend:
  - `/api/v1/integrations`
- Launch providers:
  - Google Workspace
  - Microsoft 365
  - GitHub
  - Jira
  - Slack

### Monitoring and Operations

- Frontend:
  - monitoring views in the dashboard route group
- Backend:
  - `/api/v1/monitoring`
  - `/api/v1/health`
  - `/api/v1/security`

### Billing

- Frontend:
  - `/checkout`
- Backend:
  - `/api/v1/payments`

## Launch Rules

- Demo, duplicate dashboard, showcase, deprecated, and design-system routes are not part of GA.
- Frontend services and hooks must consume the canonical `/api/v1` contracts only.
- New launch-critical integrations, billing, monitoring, and report changes must keep this inventory aligned.
