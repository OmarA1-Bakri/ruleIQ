import { apiClient } from './client';

export interface AWSConfiguration {
  auth_type: 'access_key' | 'role_assumption';
  access_key_id?: string;
  secret_access_key?: string;
  role_arn?: string;
  external_id?: string;
  region: string;
}

export interface OktaConfiguration {
  domain: string;
  api_token: string;
}

export interface GoogleWorkspaceConfiguration {
  domain: string;
  client_id: string;
  client_secret: string;
  refresh_token: string;
}

export interface MicrosoftConfiguration {
  tenant_id: string;
  client_id: string;
  client_secret: string;
  refresh_token?: string;
}

export interface FoundationEvidenceRequest {
  framework_id: string;
  business_profile: Record<string, any>;
  evidence_types?: string[];
  collection_mode?: 'immediate' | 'scheduled' | 'streaming';
  quality_requirements?: Record<string, any>;
}

export interface EvidenceCollectionResponse {
  collection_id: string;
  status: string;
  message: string;
  estimated_duration: string;
  evidence_types: string[];
  created_at: string;
}

export interface EvidenceCollectionStatus {
  collection_id: string;
  status: string;
  progress_percentage: number;
  evidence_collected: number;
  total_expected: number;
  quality_score: number;
  started_at: string;
  estimated_completion?: string;
  current_activity: string;
  errors: string[];
}

export interface CollectedEvidence {
  evidence_id: string;
  evidence_type: string;
  source_system: string;
  resource_id: string;
  resource_name: string;
  compliance_controls: string[];
  quality_score: number;
  collected_at: string;
  data_summary: Record<string, any>;
}

export interface IntegrationHealth {
  integration_id: string;
  provider: string;
  status: 'healthy' | 'unhealthy' | 'error';
  response_time?: number;
  account_id?: string;
  region?: string;
  domain?: string;
  error?: string;
  timestamp: string;
}

class FoundationEvidenceService {
  /**
   * Configure AWS integration
   */
  async configureAWS(config: AWSConfiguration): Promise<{
    integration_id: string;
    provider: string;
    status: string;
    account_id?: string;
    region: string;
    capabilities: string[];
    message: string;
  }> {
    const response = await apiClient.post<any>('/foundation/evidence/aws/configure', config);
    return response;
  }

  /**
   * Configure Okta integration
   */
  async configureOkta(config: OktaConfiguration): Promise<{
    integration_id: string;
    provider: string;
    status: string;
    domain: string;
    capabilities: string[];
    message: string;
  }> {
    const response = await apiClient.post<any>('/foundation/evidence/okta/configure', config);
    return response;
  }

  /**
   * Configure Google Workspace integration
   */
  async configureGoogleWorkspace(config: GoogleWorkspaceConfiguration): Promise<{
    integration_id: string;
    provider: string;
    status: string;
    domain: string;
    capabilities: string[];
    message: string;
  }> {
    const response = await apiClient.post<any>('/foundation/evidence/google/configure', config);
    return response;
  }

  /**
   * Configure Microsoft 365/Azure AD integration
   */
  async configureMicrosoft(config: MicrosoftConfiguration): Promise<{
    integration_id: string;
    provider: string;
    status: string;
    tenant_id: string;
    capabilities: string[];
    message: string;
  }> {
    const response = await apiClient.post<any>('/foundation/evidence/microsoft/configure', config);
    return response;
  }

  /**
   * Start foundation evidence collection
   */
  async startCollection(request: FoundationEvidenceRequest): Promise<EvidenceCollectionResponse> {
    const response = await apiClient.post<EvidenceCollectionResponse>(
      '/foundation/evidence/collect',
      request,
    );
    return response;
  }

  /**
   * Get collection status
   */
  async getCollectionStatus(collectionId: string): Promise<EvidenceCollectionStatus> {
    const response = await apiClient.get<EvidenceCollectionStatus>(
      `/foundation/evidence/collect/${collectionId}/status`,
    );
    return response;
  }

  /**
   * Get collection results
   */
  async getCollectionResults(
    collectionId: string,
    options?: {
      evidence_type?: string;
      page?: number;
      page_size?: number;
    },
  ): Promise<{
    collection_id: string;
    status: string;
    total_evidence: number;
    page: number;
    page_size: number;
    evidence: CollectedEvidence[];
  }> {
    const params = new URLSearchParams();
    if (options?.evidence_type) params.append('evidence_type', options.evidence_type);
    if (options?.page) params.append('page', options.page.toString());
    if (options?.page_size) params.append('page_size', options.page_size.toString());

    const response = await apiClient.get<any>(
      `/foundation/evidence/collect/${collectionId}/results?${params}`,
    );
    return response;
  }

  /**
   * Check foundation integrations health
   */
  async checkHealth(): Promise<{
    overall_status: 'healthy' | 'degraded';
    integrations: IntegrationHealth[];
    total_integrations: number;
    healthy_integrations: number;
    timestamp: string;
  }> {
    const response = await apiClient.get<any>('/foundation/evidence/health');
    return response;
  }

  /**
   * Stream collection progress using Server-Sent Events
   */
  streamCollectionProgress(
    collectionId: string,
    onProgress: (status: Partial<EvidenceCollectionStatus>) => void,
    onError: (_error: Error) => void,
  ): EventSource {
    const eventSource = new EventSource(`/api/foundation/evidence/collect/${collectionId}/stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onProgress(data);
      } catch (_error) {
        onError(new Error('Failed to parse progress data'));
      }
    };

    eventSource.onerror = (_error) => {
      onError(new Error('Connection to progress stream failed'));
    };

    return eventSource;
  }

  /**
   * Get supported evidence types for a provider
   */
  getSupportedEvidenceTypes(
    provider: 'aws' | 'okta' | 'google_workspace' | 'microsoft_365',
  ): string[] {
    const evidenceTypes = {
      aws: [
        'iam_policies',
        'iam_users',
        'iam_roles',
        'security_groups',
        'vpc_configuration',
        'cloudtrail_logs',
        'config_rules',
        'guardduty_findings',
        'inspector_findings',
        's3_buckets',
        'ec2_instances',
      ],
      okta: [
        'users',
        'groups',
        'applications',
        'policies',
        'system_logs',
        'mfa_factors',
        'zones',
        'auth_servers',
      ],
      google_workspace: [
        'user_directory',
        'access_groups',
        'admin_activity_logs',
        'user_access_logs',
        'domain_configuration',
      ],
      microsoft_365: [
        'user_directory',
        'access_groups',
        'applications',
        'user_access_logs',
        'admin_activity_logs',
        'organization_configuration',
      ],
    };

    return evidenceTypes[provider] || [];
  }

  /**
   * Get compliance controls mapped to evidence types
   */
  getComplianceControlMapping(): Record<string, string[]> {
    return {
      // AWS Evidence Types
      iam_policies: ['CC6.1', 'CC6.2', 'CC6.3'],
      iam_users: ['CC6.1', 'CC6.2', 'CC6.7'],
      iam_roles: ['CC6.1', 'CC6.3'],
      security_groups: ['CC6.1', 'CC6.6'],
      cloudtrail_logs: ['CC6.1', 'CC7.2', 'CC7.3'],
      config_rules: ['CC7.1', 'CC7.2'],
      guardduty_findings: ['CC7.1', 'CC7.3'],

      // Okta Evidence Types
      users: ['CC6.1', 'CC6.2', 'CC6.7'],
      groups: ['CC6.1', 'CC6.2'],
      applications: ['CC6.1', 'CC6.2', 'CC6.8'],
      system_logs: ['CC6.1', 'CC7.2', 'CC7.3'],
      mfa_factors: ['CC6.1', 'CC6.7'],
      policies: ['CC6.1', 'CC6.2'],

      // Google Workspace Evidence Types
      user_directory: ['CC6.1', 'CC6.2', 'CC6.7'],
      access_groups: ['CC6.1', 'CC6.2', 'CC6.3'],
      admin_activity_logs: ['CC7.1', 'CC7.2', 'CC7.3'],
      user_access_logs: ['CC6.1', 'CC6.2', 'CC7.2'],
      domain_configuration: ['CC6.1', 'CC6.6'],

      // Microsoft 365 Evidence Types
      organization_configuration: ['CC6.1', 'CC6.6'],
    };
  }

  /**
   * Calculate evidence collection time estimate
   */
  estimateCollectionTime(evidenceTypes: string[]): {
    estimated_minutes: number;
    confidence: 'low' | 'medium' | 'high';
  } {
    // Base time estimates per evidence type (in minutes)
    const timeEstimates: Record<string, number> = {
      // AWS
      iam_policies: 2,
      iam_users: 3,
      iam_roles: 2,
      security_groups: 1,
      cloudtrail_logs: 5,
      config_rules: 3,
      guardduty_findings: 4,

      // Okta
      users: 4,
      groups: 2,
      applications: 3,
      system_logs: 6,
      mfa_factors: 1,
      policies: 2,
    };

    const totalMinutes = evidenceTypes.reduce((total, type) => {
      return total + (timeEstimates[type] || 3); // Default 3 minutes for unknown types
    }, 0);

    // Add overhead for parallel processing efficiency
    const parallelEfficiency = 0.7; // 70% efficiency due to API rate limits
    const estimatedMinutes = Math.ceil(totalMinutes * parallelEfficiency);

    // Determine confidence based on known evidence types
    const knownTypes = evidenceTypes.filter((type) => timeEstimates[type]);
    const confidence =
      knownTypes.length === evidenceTypes.length
        ? 'high'
        : knownTypes.length > evidenceTypes.length * 0.7
          ? 'medium'
          : 'low';

    return {
      estimated_minutes: estimatedMinutes,
      confidence,
    };
  }

  /**
   * Validate configuration before submission
   */
  validateAWSConfiguration(config: AWSConfiguration): string[] {
    const errors: string[] = [];

    if (!config.auth_type) {
      errors.push('Authentication type is required');
    }

    if (config.auth_type === 'access_key') {
      if (!config.access_key_id) {
        errors.push('Access Key ID is required for access key authentication');
      }
      if (!config.secret_access_key) {
        errors.push('Secret Access Key is required for access key authentication');
      }
    }

    if (config.auth_type === 'role_assumption') {
      if (!config.role_arn) {
        errors.push('Role ARN is required for role assumption authentication');
      }
    }

    if (!config.region) {
      errors.push('AWS region is required');
    }

    return errors;
  }

  /**
   * Validate Okta configuration
   */
  validateOktaConfiguration(config: OktaConfiguration): string[] {
    const errors: string[] = [];

    if (!config.domain) {
      errors.push('Okta domain is required');
    } else if (!config.domain.match(/^[a-zA-Z0-9-]+$/)) {
      errors.push('Invalid Okta domain format');
    }

    if (!config.api_token) {
      errors.push('Okta API token is required');
    }

    return errors;
  }

  /**
   * Validate Google Workspace configuration
   */
  validateGoogleWorkspaceConfiguration(config: GoogleWorkspaceConfiguration): string[] {
    const errors: string[] = [];

    if (!config.domain) {
      errors.push('Google Workspace domain is required');
    }

    if (!config.client_id) {
      errors.push('Google OAuth2 client ID is required');
    }

    if (!config.client_secret) {
      errors.push('Google OAuth2 client secret is required');
    }

    if (!config.refresh_token) {
      errors.push('Google OAuth2 refresh token is required');
    }

    return errors;
  }

  /**
   * Validate Microsoft configuration
   */
  validateMicrosoftConfiguration(config: MicrosoftConfiguration): string[] {
    const errors: string[] = [];

    if (!config.tenant_id) {
      errors.push('Azure AD tenant ID is required');
    }

    if (!config.client_id) {
      errors.push('Azure AD application client ID is required');
    }

    if (!config.client_secret) {
      errors.push('Azure AD application client secret is required');
    }

    return errors;
  }

  /**
   * Generate collection summary
   */
  generateCollectionSummary(results: CollectedEvidence[]): {
    total_evidence: number;
    by_type: Record<string, number>;
    by_system: Record<string, number>;
    by_controls: Record<string, number>;
    average_quality: number;
    coverage_by_framework: Record<string, number>;
  } {
    const summary = {
      total_evidence: results.length,
      by_type: {} as Record<string, number>,
      by_system: {} as Record<string, number>,
      by_controls: {} as Record<string, number>,
      average_quality: 0,
      coverage_by_framework: {} as Record<string, number>,
    };

    let totalQuality = 0;

    results.forEach((evidence) => {
      // Count by type
      summary.by_type[evidence.evidence_type] = (summary.by_type[evidence.evidence_type] || 0) + 1;

      // Count by system
      summary.by_system[evidence.source_system] =
        (summary.by_system[evidence.source_system] || 0) + 1;

      // Count by controls
      evidence.compliance_controls.forEach((control) => {
        summary.by_controls[control] = (summary.by_controls[control] || 0) + 1;
      });

      // Sum quality scores
      totalQuality += evidence.quality_score;
    });

    // Calculate average quality
    summary.average_quality = results.length > 0 ? totalQuality / results.length : 0;

    // Calculate framework coverage (simplified)
    const soc2Controls = [
      'CC6.1',
      'CC6.2',
      'CC6.3',
      'CC6.6',
      'CC6.7',
      'CC6.8',
      'CC7.1',
      'CC7.2',
      'CC7.3',
    ];
    const coveredControls = Object.keys(summary.by_controls);
    const soc2Coverage = coveredControls.filter((control) => soc2Controls.includes(control)).length;
    summary.coverage_by_framework['SOC2_TYPE2'] = (soc2Coverage / soc2Controls.length) * 100;

    return summary;
  }
}

export const foundationEvidenceService = new FoundationEvidenceService();
