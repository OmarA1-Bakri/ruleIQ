import { describe, it, expect } from 'vitest';
import {
  PolicyCategory,
  PolicyStatus,
  RiskLevel,
  EvidenceType,
  EvidenceStatus,
  RiskCategory,
  RiskStatus,
  UserRole,
} from '@/lib/api/types';

describe('PolicyCategory enum', () => {
  it('has all expected values', () => {
    expect(PolicyCategory.DATA_PROTECTION).toBe('data_protection');
    expect(PolicyCategory.SECURITY).toBe('security');
    expect(PolicyCategory.PRIVACY).toBe('privacy');
    expect(PolicyCategory.COMPLIANCE).toBe('compliance');
    expect(PolicyCategory.OPERATIONAL).toBe('operational');
    expect(PolicyCategory.FINANCIAL).toBe('financial');
  });

  it('has exactly 6 values', () => {
    const values = Object.values(PolicyCategory);
    expect(values).toHaveLength(6);
  });
});

describe('PolicyStatus enum', () => {
  it('has all expected values', () => {
    expect(PolicyStatus.DRAFT).toBe('draft');
    expect(PolicyStatus.PENDING_APPROVAL).toBe('pending_approval');
    expect(PolicyStatus.UNDER_REVIEW).toBe('under_review');
    expect(PolicyStatus.APPROVED).toBe('approved');
    expect(PolicyStatus.PUBLISHED).toBe('published');
    expect(PolicyStatus.ARCHIVED).toBe('archived');
  });

  it('has exactly 6 values', () => {
    const values = Object.values(PolicyStatus);
    expect(values).toHaveLength(6);
  });
});

describe('RiskLevel enum', () => {
  it('has all expected values', () => {
    expect(RiskLevel.LOW).toBe('low');
    expect(RiskLevel.MEDIUM).toBe('medium');
    expect(RiskLevel.HIGH).toBe('high');
    expect(RiskLevel.CRITICAL).toBe('critical');
  });

  it('has exactly 4 values', () => {
    const values = Object.values(RiskLevel);
    expect(values).toHaveLength(4);
  });
});

describe('EvidenceType enum', () => {
  it('has all expected values', () => {
    expect(EvidenceType.DOCUMENT).toBe('document');
    expect(EvidenceType.SCREENSHOT).toBe('screenshot');
    expect(EvidenceType.LOG).toBe('log');
    expect(EvidenceType.AUDIT_REPORT).toBe('audit_report');
    expect(EvidenceType.CERTIFICATE).toBe('certificate');
    expect(EvidenceType.OTHER).toBe('other');
  });
});

describe('EvidenceStatus enum', () => {
  it('has all expected values', () => {
    expect(EvidenceStatus.PENDING).toBe('pending');
    expect(EvidenceStatus.UNDER_REVIEW).toBe('under_review');
    expect(EvidenceStatus.VERIFIED).toBe('verified');
    expect(EvidenceStatus.REJECTED).toBe('rejected');
    expect(EvidenceStatus.EXPIRED).toBe('expired');
  });
});

describe('RiskCategory enum', () => {
  it('has all expected values', () => {
    expect(RiskCategory.STRATEGIC).toBe('strategic');
    expect(RiskCategory.OPERATIONAL).toBe('operational');
    expect(RiskCategory.FINANCIAL).toBe('financial');
    expect(RiskCategory.COMPLIANCE).toBe('compliance');
    expect(RiskCategory.REPUTATIONAL).toBe('reputational');
    expect(RiskCategory.TECHNOLOGICAL).toBe('technological');
  });

  it('has exactly 6 values', () => {
    const values = Object.values(RiskCategory);
    expect(values).toHaveLength(6);
  });
});

describe('RiskStatus enum', () => {
  it('has all expected values', () => {
    expect(RiskStatus.IDENTIFIED).toBe('identified');
    expect(RiskStatus.ASSESSED).toBe('assessed');
    expect(RiskStatus.MONITORING).toBe('monitoring');
    expect(RiskStatus.MITIGATED).toBe('mitigated');
    expect(RiskStatus.ACCEPTED).toBe('accepted');
    expect(RiskStatus.CLOSED).toBe('closed');
  });
});

describe('UserRole enum', () => {
  it('has all expected values', () => {
    expect(UserRole.ADMIN).toBe('admin');
    expect(UserRole.MANAGER).toBe('manager');
    expect(UserRole.USER).toBe('user');
    expect(UserRole.VIEWER).toBe('viewer');
    expect(UserRole.AUDITOR).toBe('auditor');
    expect(UserRole.COMPLIANCE_OFFICER).toBe('compliance_officer');
  });

  it('has exactly 6 values', () => {
    const values = Object.values(UserRole);
    expect(values).toHaveLength(6);
  });
});
