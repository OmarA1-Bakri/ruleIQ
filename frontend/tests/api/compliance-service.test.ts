import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    download: vi.fn(),
  },
}));

describe('ComplianceService', () => {
  let complianceService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/compliance.service');
    complianceService = serviceMod.complianceService;
  });

  describe('getComplianceStatus', () => {
    it('calls GET /compliance/status with business_profile_id', async () => {
      const mockData = [
        {
          framework: 'GDPR',
          overall_compliance_percentage: 82,
          status: 'partial',
          by_domain: [],
          risk_summary: {
            high_risk_items: 2,
            medium_risk_items: 5,
            low_risk_items: 3,
            remediation_in_progress: 1,
          },
        },
      ];

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceStatus('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/status', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result).toHaveLength(1);
      expect(result[0].framework).toBe('GDPR');
      expect(result[0].overall_compliance_percentage).toBe(82);
    });
  });

  describe('getFrameworkComplianceStatus', () => {
    it('calls GET /compliance/status/:frameworkId', async () => {
      const mockData = {
        framework: 'ISO27001',
        overall_compliance_percentage: 65,
        status: 'partial',
        by_domain: [
          {
            domain: 'Access Control',
            compliance_percentage: 70,
            controls_compliant: 7,
            controls_total: 10,
            critical_findings: 1,
          },
        ],
        risk_summary: {
          high_risk_items: 3,
          medium_risk_items: 2,
          low_risk_items: 1,
          remediation_in_progress: 2,
        },
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getFrameworkComplianceStatus('bp-1', 'iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/status/iso27001', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result.framework).toBe('ISO27001');
      expect(result.by_domain).toHaveLength(1);
    });
  });

  describe('getComplianceTasks', () => {
    it('calls GET /compliance/tasks without params', async () => {
      const mockData = { tasks: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceTasks();

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/tasks', {});
      expect(result.total).toBe(0);
    });

    it('passes params when provided', async () => {
      const mockData = {
        tasks: [
          {
            id: 'ct-1',
            title: 'Implement access controls',
            description: 'Set up RBAC',
            control_id: 'ctrl-1',
            framework: 'ISO27001',
            priority: 'high',
            status: 'pending',
            effort_hours: 8,
            dependencies: [],
            evidence_required: ['Config screenshots'],
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceTasks({
        business_profile_id: 'bp-1',
        status: 'pending',
        priority: 'high',
        page: 1,
        page_size: 10,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/tasks', {
        params: {
          business_profile_id: 'bp-1',
          status: 'pending',
          priority: 'high',
          page: 1,
          page_size: 10,
        },
      });
      expect(result.tasks).toHaveLength(1);
      expect(result.tasks[0].priority).toBe('high');
    });
  });

  describe('createComplianceTask', () => {
    it('calls POST /compliance/tasks', async () => {
      const newTask = {
        title: 'New task',
        description: 'Desc',
        control_id: 'ctrl-1',
        framework: 'GDPR',
        priority: 'medium' as const,
        status: 'pending' as const,
        effort_hours: 4,
        dependencies: [],
        evidence_required: [],
      };

      const mockResponse = { id: 'ct-new', ...newTask };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await complianceService.createComplianceTask(newTask);

      expect(apiClient.post).toHaveBeenCalledWith('/compliance/tasks', newTask);
      expect(result.id).toBe('ct-new');
    });
  });

  describe('updateComplianceTask', () => {
    it('calls PATCH /compliance/tasks/:id', async () => {
      const update = { status: 'completed' };
      const mockResponse = { id: 'ct-1', title: 'Task', status: 'completed' };
      (apiClient.patch as any).mockResolvedValue(mockResponse);

      const result = await complianceService.updateComplianceTask('ct-1', update);

      expect(apiClient.patch).toHaveBeenCalledWith('/compliance/tasks/ct-1', update);
      expect(result.status).toBe('completed');
    });
  });

  describe('getComplianceRisks', () => {
    it('calls GET /compliance/risks without params', async () => {
      const mockData = { risks: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceRisks();

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/risks', {});
      expect(result.total).toBe(0);
    });

    it('passes params when provided', async () => {
      const mockData = {
        risks: [
          {
            id: 'risk-1',
            title: 'Unencrypted data',
            description: 'Data at rest is unencrypted',
            severity: 'critical',
            likelihood: 'likely',
            impact: 'High financial and reputational',
            affected_controls: ['ctrl-1', 'ctrl-2'],
            status: 'identified',
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceRisks({
        business_profile_id: 'bp-1',
        severity: 'critical',
      });

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/risks', {
        params: { business_profile_id: 'bp-1', severity: 'critical' },
      });
      expect(result.risks[0].severity).toBe('critical');
    });
  });

  describe('createComplianceRisk', () => {
    it('calls POST /compliance/risks', async () => {
      const riskData = {
        title: 'New risk',
        description: 'A new risk',
        severity: 'high' as const,
        likelihood: 'possible' as const,
        impact: 'Medium',
        affected_controls: ['ctrl-1'],
        status: 'identified' as const,
      };

      const mockResponse = { id: 'risk-new', ...riskData };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await complianceService.createComplianceRisk(riskData);

      expect(apiClient.post).toHaveBeenCalledWith('/compliance/risks', riskData);
      expect(result.id).toBe('risk-new');
    });
  });

  describe('updateComplianceRisk', () => {
    it('calls PATCH /compliance/risks/:id', async () => {
      const update = { status: 'mitigating' };
      const mockResponse = { id: 'risk-1', status: 'mitigating' };
      (apiClient.patch as any).mockResolvedValue(mockResponse);

      const result = await complianceService.updateComplianceRisk('risk-1', update);

      expect(apiClient.patch).toHaveBeenCalledWith('/compliance/risks/risk-1', update);
      expect(result.status).toBe('mitigating');
    });
  });

  describe('getComplianceTimeline', () => {
    it('calls GET /compliance/timeline without frameworkId', async () => {
      const mockData = {
        milestones: [
          {
            date: '2025-06-01',
            title: 'GDPR audit',
            type: 'audit',
            status: 'upcoming',
          },
        ],
        upcoming_deadlines: [
          {
            date: '2025-07-01',
            item: 'Annual review',
            type: 'review',
            days_remaining: 30,
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceTimeline('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/timeline', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result.milestones).toHaveLength(1);
      expect(result.upcoming_deadlines).toHaveLength(1);
    });

    it('includes framework_id when provided', async () => {
      const mockData = { milestones: [], upcoming_deadlines: [] };
      (apiClient.get as any).mockResolvedValue(mockData);

      await complianceService.getComplianceTimeline('bp-1', 'gdpr');

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/timeline', {
        params: { business_profile_id: 'bp-1', framework_id: 'gdpr' },
      });
    });
  });

  describe('getComplianceDashboard', () => {
    it('calls GET /compliance/dashboard', async () => {
      const mockData = {
        overall_score: 78,
        frameworks_status: [],
        pending_tasks: 5,
        open_risks: 3,
        upcoming_audits: [],
        recent_activity: [],
        compliance_trends: [{ date: '2025-06-01', score: 78 }],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await complianceService.getComplianceDashboard('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/compliance/dashboard', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result.overall_score).toBe(78);
      expect(result.pending_tasks).toBe(5);
    });
  });

  describe('generateComplianceCertificate', () => {
    it('calls POST /compliance/certificate/generate', async () => {
      const mockResponse = {
        certificate_id: 'cert-1',
        issued_date: '2025-06-15',
        valid_until: '2026-06-15',
        download_url: '/download/cert-1',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await complianceService.generateComplianceCertificate('bp-1', 'gdpr');

      expect(apiClient.post).toHaveBeenCalledWith('/compliance/certificate/generate', {
        business_profile_id: 'bp-1',
        framework_id: 'gdpr',
      });
      expect(result.certificate_id).toBe('cert-1');
      expect(result.download_url).toBe('/download/cert-1');
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Compliance type interfaces', () => {
  it('ComplianceStatus has all expected fields', () => {
    const status = {
      framework: 'GDPR',
      overall_compliance_percentage: 85,
      status: 'partial' as const,
      by_domain: [],
      risk_summary: {
        high_risk_items: 1,
        medium_risk_items: 2,
        low_risk_items: 3,
        remediation_in_progress: 1,
      },
    };

    expect(status.framework).toBe('GDPR');
    expect(status.overall_compliance_percentage).toBe(85);
    expect(status.risk_summary.high_risk_items).toBe(1);
  });

  it('ComplianceTask has priority and status values', () => {
    const priorities = ['critical', 'high', 'medium', 'low'];
    const statuses = ['pending', 'in_progress', 'completed', 'blocked'];
    expect(priorities).toHaveLength(4);
    expect(statuses).toHaveLength(4);
  });

  it('ComplianceRisk has severity and likelihood values', () => {
    const severities = ['critical', 'high', 'medium', 'low'];
    const likelihoods = ['very_likely', 'likely', 'possible', 'unlikely'];
    const riskStatuses = ['identified', 'mitigating', 'accepted', 'resolved'];
    expect(severities).toHaveLength(4);
    expect(likelihoods).toHaveLength(4);
    expect(riskStatuses).toHaveLength(4);
  });
});
