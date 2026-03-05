/**
 * Business Profile Field Mapping Layer
 *
 * This mapper handles the translation between our clean frontend field names
 * and the backend's truncated field names. This abstraction ensures our
 * frontend code remains readable and self-documenting while seamlessly
 * integrating with the backend API.
 *
 * Backend Constraints:
 * - Database column names are truncated due to length limitations
 * - API responses use these truncated names
 *
 * Frontend Benefits:
 * - Clean, descriptive field names
 * - Self-documenting code
 * - Better developer experience
 * - Type safety with meaningful names
 */

import { type BusinessProfile } from '@/types/business-profile';

export class BusinessProfileFieldMapper {
  /**
   * Bidirectional field mapping between frontend (descriptive) and backend (truncated) names
   */
  public static readonly fieldMap = {
    // Boolean fields - Business characteristics
    handles_personal_data: 'handles_persona',
    processes_payments: 'processes_payme',
    stores_health_data: 'stores_health_d',
    provides_financial_services: 'provides_financ',
    operates_critical_infrastructure: 'operates_critic',
    has_international_operations: 'has_internation',

    // Array fields - Technology and compliance
    existing_frameworks: 'existing_framew',
    planned_frameworks: 'planned_framewo',
    development_tools: 'development_too',

    // String fields - Compliance planning
    compliance_budget: 'compliance_budg',
    compliance_timeline: 'compliance_time',
  } as const;

  /**
   * Convert clean frontend data to API format
   *
   * @param data - Frontend data with descriptive field names
   * @returns API-compatible data with truncated field names
   */
  static toAPI<T extends Partial<BusinessProfile>>(data: T): any {
    if (!data) return data;

    const mapped: any = {};

    Object.entries(data).forEach(([key, value]) => {
      // Map frontend field to API field, or use original if no mapping exists
      const apiKey = this.fieldMap[key as keyof typeof this.fieldMap] || key;

      // Handle type conversions
      if (key === 'compliance_budget' && typeof value === 'string') {
        // Convert string to number for API
        const numValue = parseFloat(value);
        mapped[apiKey] = isNaN(numValue) ? 0 : numValue;
      } else {
        mapped[apiKey] = value;
      }
    });

    return mapped;
  }

  /**
   * Convert API response to clean frontend format
   *
   * @param data - API response with truncated field names
   * @returns Frontend data with descriptive field names
   */
  static fromAPI(data: unknown): BusinessProfile | null {
    if (!data) return null;

    const mapped: any = {};

    // Reverse map API fields to frontend fields
    Object.entries(data).forEach(([key, value]) => {
      // Find if this is a mapped field by looking for the API key in our mapping
      const frontendKey =
        Object.entries(this.fieldMap).find(([_, apiKey]) => apiKey === key)?.[0] || key;

      // Handle type conversions from API to frontend
      if (frontendKey === 'compliance_budget' && typeof value === 'number') {
        // Convert number to string for frontend
        mapped[frontendKey] = value.toString();
      } else {
        mapped[frontendKey] = value;
      }
    });

    return mapped as BusinessProfile;
  }

  /**
   * Get API field name for a frontend field
   *
   * @param frontendField - Frontend field name
   * @returns Corresponding API field name
   */
  static getAPIField(frontendField: keyof BusinessProfile): string {
    return this.fieldMap[frontendField as keyof typeof this.fieldMap] || frontendField;
  }

  /**
   * Get frontend field name for an API field
   *
   * @param apiField - API field name
   * @returns Corresponding frontend field name
   */
  static getFrontendField(apiField: string): string {
    const entry = Object.entries(this.fieldMap).find(([_, api]) => api === apiField);
    return entry ? entry[0] : apiField;
  }

  /**
   * Validate that all required mappings are present
   * Used for development/testing to ensure mapping completeness
   */
  static validateMappings(): { isValid: boolean; missingMappings: string[] } {
    const requiredBackendFields = [
      'handles_persona',
      'processes_payme',
      'stores_health_d',
      'provides_financ',
      'operates_critic',
      'has_internation',
      'existing_framew',
      'planned_framewo',
      'development_too',
      'compliance_budg',
      'compliance_time',
    ];

    const mappedBackendFields = Object.values(this.fieldMap);
    const missingMappings = requiredBackendFields.filter(
      (field) => !mappedBackendFields.includes(field as any),
    );

    return {
      isValid: missingMappings.length === 0,
      missingMappings,
    };
  }

  /**
   * Get all field mappings for debugging/documentation
   */
  static getAllMappings(): Record<string, string> {
    return { ...this.fieldMap };
  }

  /**
   * Transform form data for API submission
   * Handles nested objects and arrays appropriately
   */
  static transformFormDataForAPI(formData: any): any {
    const transformed = this.toAPI(formData);

    // Ensure arrays are properly formatted
    const arrayFields = [
      'cloud_providers',
      'saas_tools',
      'development_too',
      'existing_framew',
      'planned_framewo',
    ];
    arrayFields.forEach((field) => {
      if (transformed[field] && !Array.isArray(transformed[field])) {
        transformed[field] = [];
      }
    });

    // Ensure boolean fields are properly typed
    const booleanFields = [
      'handles_persona',
      'processes_payme',
      'stores_health_d',
      'provides_financ',
      'operates_critic',
      'has_internation',
    ];
    booleanFields.forEach((field) => {
      if (transformed[field] !== undefined) {
        transformed[field] = Boolean(transformed[field]);
      }
    });

    return transformed;
  }

  /**
   * Transform API response for frontend consumption
   * Handles type conversion and default values
   */
  static transformAPIResponseForFrontend(apiData: any): BusinessProfile | null {
    if (!apiData) return null;

    const transformed = this.fromAPI(apiData);
    if (!transformed) return null;

    // Ensure arrays have default values
    const arrayFields: (keyof BusinessProfile)[] = [
      'data_types',
      'cloud_providers',
      'saas_tools',
      'development_tools',
      'existing_frameworks',
      'planned_frameworks',
    ];

    arrayFields.forEach((field) => {
      if (!Array.isArray(transformed[field])) {
        (transformed as any)[field] = [];
      }
    });

    // Ensure boolean fields have default values
    const booleanFields: (keyof BusinessProfile)[] = [
      'handles_personal_data',
      'processes_payments',
      'stores_health_data',
      'provides_financial_services',
      'operates_critical_infrastructure',
      'has_international_operations',
    ];

    booleanFields.forEach((field) => {
      if (transformed[field] === undefined || transformed[field] === null) {
        (transformed as any)[field] = false;
      }
    });

    // Set default values for other fields
    if (!transformed.data_sensitivity) {
      transformed.data_sensitivity = 'Low';
    }

    if (!transformed.country) {
      transformed.country = 'United Kingdom';
    }

    // Add frontend-specific properties that don't exist in API
    (transformed as any).assessment_completed = false;
    (transformed as any).assessment_data = {};

    return transformed;
  }

  /**
   * Create a partial update payload
   * Only includes changed fields to minimize API payload
   */
  static createUpdatePayload(original: BusinessProfile, updated: Partial<BusinessProfile>): any {
    const changes: any = {};

    Object.entries(updated).forEach(([key, value]) => {
      const originalValue = original[key as keyof BusinessProfile];

      // Check if value has actually changed
      if (JSON.stringify(originalValue) !== JSON.stringify(value)) {
        changes[key] = value;
      }
    });

    return this.toAPI(changes);
  }
}

/**
 * Type-safe field mapping utilities
 */
export type FrontendField = keyof BusinessProfile;
export type APIField =
  | (typeof BusinessProfileFieldMapper.fieldMap)[keyof typeof BusinessProfileFieldMapper.fieldMap]
  | string;

/**
 * Helper function to get mapped field name with type safety
 */
export function getAPIFieldName<T extends FrontendField>(field: T): string {
  return BusinessProfileFieldMapper.getAPIField(field);
}

/**
 * Helper function to validate field mapping during development
 */
export function validateFieldMappings(): void {
  if (process.env.NODE_ENV === 'development') {
    const validation = BusinessProfileFieldMapper.validateMappings();
    if (!validation.isValid) {
      // intentionally empty - validation result is informational in dev mode
    }
  }
}
