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
import {
  MessageType,
  TrustLevel,
} from '@/lib/websocket/types';

// ============================================================================
// PolicyCategory
// ============================================================================

describe('PolicyCategory', () => {
  it('DATA_PROTECTION = "data_protection"', () => expect(PolicyCategory.DATA_PROTECTION).toBe('data_protection'));
  it('SECURITY = "security"', () => expect(PolicyCategory.SECURITY).toBe('security'));
  it('PRIVACY = "privacy"', () => expect(PolicyCategory.PRIVACY).toBe('privacy'));
  it('COMPLIANCE = "compliance"', () => expect(PolicyCategory.COMPLIANCE).toBe('compliance'));
  it('OPERATIONAL = "operational"', () => expect(PolicyCategory.OPERATIONAL).toBe('operational'));
  it('FINANCIAL = "financial"', () => expect(PolicyCategory.FINANCIAL).toBe('financial'));

  it('has exactly 6 values', () => {
    const values = Object.values(PolicyCategory);
    expect(values.length).toBe(6);
  });
});

// ============================================================================
// PolicyStatus
// ============================================================================

describe('PolicyStatus', () => {
  it('DRAFT = "draft"', () => expect(PolicyStatus.DRAFT).toBe('draft'));
  it('PENDING_APPROVAL = "pending_approval"', () => expect(PolicyStatus.PENDING_APPROVAL).toBe('pending_approval'));
  it('UNDER_REVIEW = "under_review"', () => expect(PolicyStatus.UNDER_REVIEW).toBe('under_review'));
  it('APPROVED = "approved"', () => expect(PolicyStatus.APPROVED).toBe('approved'));
  it('PUBLISHED = "published"', () => expect(PolicyStatus.PUBLISHED).toBe('published'));
  it('ARCHIVED = "archived"', () => expect(PolicyStatus.ARCHIVED).toBe('archived'));

  it('has exactly 6 values', () => {
    expect(Object.values(PolicyStatus).length).toBe(6);
  });
});

// ============================================================================
// RiskLevel
// ============================================================================

describe('RiskLevel', () => {
  it('LOW = "low"', () => expect(RiskLevel.LOW).toBe('low'));
  it('MEDIUM = "medium"', () => expect(RiskLevel.MEDIUM).toBe('medium'));
  it('HIGH = "high"', () => expect(RiskLevel.HIGH).toBe('high'));
  it('CRITICAL = "critical"', () => expect(RiskLevel.CRITICAL).toBe('critical'));

  it('has exactly 4 values', () => {
    expect(Object.values(RiskLevel).length).toBe(4);
  });
});

// ============================================================================
// EvidenceType
// ============================================================================

describe('EvidenceType', () => {
  it('DOCUMENT = "document"', () => expect(EvidenceType.DOCUMENT).toBe('document'));
  it('SCREENSHOT = "screenshot"', () => expect(EvidenceType.SCREENSHOT).toBe('screenshot'));
  it('LOG = "log"', () => expect(EvidenceType.LOG).toBe('log'));
  it('AUDIT_REPORT = "audit_report"', () => expect(EvidenceType.AUDIT_REPORT).toBe('audit_report'));
  it('CERTIFICATE = "certificate"', () => expect(EvidenceType.CERTIFICATE).toBe('certificate'));
  it('OTHER = "other"', () => expect(EvidenceType.OTHER).toBe('other'));

  it('has exactly 6 values', () => {
    expect(Object.values(EvidenceType).length).toBe(6);
  });
});

// ============================================================================
// EvidenceStatus
// ============================================================================

describe('EvidenceStatus', () => {
  it('PENDING = "pending"', () => expect(EvidenceStatus.PENDING).toBe('pending'));
  it('UNDER_REVIEW = "under_review"', () => expect(EvidenceStatus.UNDER_REVIEW).toBe('under_review'));
  it('VERIFIED = "verified"', () => expect(EvidenceStatus.VERIFIED).toBe('verified'));
  it('REJECTED = "rejected"', () => expect(EvidenceStatus.REJECTED).toBe('rejected'));
  it('EXPIRED = "expired"', () => expect(EvidenceStatus.EXPIRED).toBe('expired'));

  it('has exactly 5 values', () => {
    expect(Object.values(EvidenceStatus).length).toBe(5);
  });
});

// ============================================================================
// RiskCategory
// ============================================================================

describe('RiskCategory', () => {
  it('STRATEGIC = "strategic"', () => expect(RiskCategory.STRATEGIC).toBe('strategic'));
  it('OPERATIONAL = "operational"', () => expect(RiskCategory.OPERATIONAL).toBe('operational'));
  it('FINANCIAL = "financial"', () => expect(RiskCategory.FINANCIAL).toBe('financial'));
  it('COMPLIANCE = "compliance"', () => expect(RiskCategory.COMPLIANCE).toBe('compliance'));
  it('REPUTATIONAL = "reputational"', () => expect(RiskCategory.REPUTATIONAL).toBe('reputational'));
  it('TECHNOLOGICAL = "technological"', () => expect(RiskCategory.TECHNOLOGICAL).toBe('technological'));

  it('has exactly 6 values', () => {
    expect(Object.values(RiskCategory).length).toBe(6);
  });
});

// ============================================================================
// RiskStatus
// ============================================================================

describe('RiskStatus', () => {
  it('IDENTIFIED = "identified"', () => expect(RiskStatus.IDENTIFIED).toBe('identified'));
  it('ASSESSED = "assessed"', () => expect(RiskStatus.ASSESSED).toBe('assessed'));
  it('MONITORING = "monitoring"', () => expect(RiskStatus.MONITORING).toBe('monitoring'));
  it('MITIGATED = "mitigated"', () => expect(RiskStatus.MITIGATED).toBe('mitigated'));
  it('ACCEPTED = "accepted"', () => expect(RiskStatus.ACCEPTED).toBe('accepted'));
  it('CLOSED = "closed"', () => expect(RiskStatus.CLOSED).toBe('closed'));

  it('has exactly 6 values', () => {
    expect(Object.values(RiskStatus).length).toBe(6);
  });
});

// ============================================================================
// UserRole
// ============================================================================

describe('UserRole', () => {
  it('ADMIN = "admin"', () => expect(UserRole.ADMIN).toBe('admin'));
  it('MANAGER = "manager"', () => expect(UserRole.MANAGER).toBe('manager'));
  it('USER = "user"', () => expect(UserRole.USER).toBe('user'));
  it('VIEWER = "viewer"', () => expect(UserRole.VIEWER).toBe('viewer'));
  it('AUDITOR = "auditor"', () => expect(UserRole.AUDITOR).toBe('auditor'));
  it('COMPLIANCE_OFFICER = "compliance_officer"', () => expect(UserRole.COMPLIANCE_OFFICER).toBe('compliance_officer'));

  it('has exactly 6 values', () => {
    expect(Object.values(UserRole).length).toBe(6);
  });
});

// ============================================================================
// MessageType (websocket/types.ts)
// ============================================================================

describe('MessageType', () => {
  it('CHAT = "chat"', () => expect(MessageType.CHAT).toBe('chat'));
  it('SYSTEM = "system"', () => expect(MessageType.SYSTEM).toBe('system'));
  it('STATUS = "status"', () => expect(MessageType.STATUS).toBe('status'));
  it('CONTROL = "control"', () => expect(MessageType.CONTROL).toBe('control'));
  it('TYPING = "typing"', () => expect(MessageType.TYPING).toBe('typing'));
  it('ERROR = "error"', () => expect(MessageType.ERROR).toBe('error'));
  it('HEARTBEAT = "heartbeat"', () => expect(MessageType.HEARTBEAT).toBe('heartbeat'));

  it('has exactly 7 values', () => {
    expect(Object.values(MessageType).length).toBe(7);
  });
});

// ============================================================================
// TrustLevel (websocket/types.ts)
// ============================================================================

describe('TrustLevel', () => {
  it('L0_OBSERVED = 0', () => expect(TrustLevel.L0_OBSERVED).toBe(0));
  it('L1_ASSISTED = 1', () => expect(TrustLevel.L1_ASSISTED).toBe(1));
  it('L2_SUPERVISED = 2', () => expect(TrustLevel.L2_SUPERVISED).toBe(2));
  it('L3_DELEGATED = 3', () => expect(TrustLevel.L3_DELEGATED).toBe(3));
  it('L4_AUTONOMOUS = 4', () => expect(TrustLevel.L4_AUTONOMOUS).toBe(4));

  it('levels are numerically ordered 0-4', () => {
    expect(TrustLevel.L0_OBSERVED).toBeLessThan(TrustLevel.L1_ASSISTED);
    expect(TrustLevel.L1_ASSISTED).toBeLessThan(TrustLevel.L2_SUPERVISED);
    expect(TrustLevel.L2_SUPERVISED).toBeLessThan(TrustLevel.L3_DELEGATED);
    expect(TrustLevel.L3_DELEGATED).toBeLessThan(TrustLevel.L4_AUTONOMOUS);
  });
});
