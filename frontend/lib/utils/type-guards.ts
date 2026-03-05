import { 
  BusinessProfileSchema,
  FreemiumAssessmentStartResponseSchema,
  ChatMessageSchema,
  EvidenceItemSchema,
  PolicyDocumentSchema,
  ComplianceRequirementSchema,
  AssessmentQuestionSchema,
  IntegrationSchema,
  AlertSchema,
  AIHelpResponseSchema,
  APIErrorResponseSchema,
  ApiResponseSchema,
  LeadCaptureRequestSchema,
  AssessmentStartRequestSchema,
  AssessmentAnswerRequestSchema
} from '../validation/zod-schemas';

// ===========================
// Business Profile Guards
// ===========================

export function isBusinessProfile(value: unknown): value is BusinessProfile {
  const result = BusinessProfileSchema.safeParse(value);
  return result.success;
}

export function isAssessmentData(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  return (
    ('responses' in obj || 'answers' in obj) &&
    ('completion_status' in obj || 'progress_percentage' in obj)
  );
}

// ===========================
// Freemium Assessment Guards
// ===========================

export function isFreemiumAssessmentResponse(value: unknown): boolean {
  const result = FreemiumAssessmentStartResponseSchema.safeParse(value);
  return result.success;
}

export function isLeadCaptureRequest(value: unknown): boolean {
  const result = LeadCaptureRequestSchema.safeParse(value);
  return result.success;
}

export function isAssessmentStartRequest(value: unknown): boolean {
  const result = AssessmentStartRequestSchema.safeParse(value);
  return result.success;
}

export function isAssessmentAnswerRequest(value: unknown): boolean {
  const result = AssessmentAnswerRequestSchema.safeParse(value);
  return result.success;
}

// ===========================
// Chat & Messaging Guards
// ===========================

export function isChatMessage(value: unknown): boolean {
  const result = ChatMessageSchema.safeParse(value);
  return result.success;
}

export function isChatMessageArray(value: unknown): value is ChatMessage[] {
  if (!Array.isArray(value)) return false;
  return value.every(item => isChatMessage(item));
}

// ===========================
// Evidence & Documents Guards
// ===========================

export function isEvidenceItem(value: unknown): boolean {
  const result = EvidenceItemSchema.safeParse(value);
  return result.success;
}

export function isPolicyDocument(value: unknown): boolean {
  const result = PolicyDocumentSchema.safeParse(value);
  return result.success;
}

// ===========================
// Compliance & Assessment Guards
// ===========================

export function isComplianceRequirement(value: unknown): boolean {
  const result = ComplianceRequirementSchema.safeParse(value);
  return result.success;
}

export function isAssessmentQuestion(value: unknown): boolean {
  const result = AssessmentQuestionSchema.safeParse(value);
  return result.success;
}

// ===========================
// Integration & Alert Guards
// ===========================

export function isIntegration(value: unknown): boolean {
  const result = IntegrationSchema.safeParse(value);
  return result.success;
}

export function isAlert(value: unknown): boolean {
  const result = AlertSchema.safeParse(value);
  return result.success;
}

// ===========================
// AI Response Guards
// ===========================

export function isAIHelpResponse(response: unknown): boolean {
  const result = AIHelpResponseSchema.safeParse(response);
  return result.success;
}

export function isAIAnalysisResponse(response: unknown): boolean {
  if (!response || typeof response !== 'object') return false;
  const obj = response as Record<string, unknown>;
  return 'analysis' in obj || ('results' in obj && 'confidence' in obj);
}

export function isAIErrorResponse(response: unknown): boolean {
  const result = APIErrorResponseSchema.safeParse(response);
  return result.success;
}

// ===========================
// API Response Guards
// ===========================

export function isApiResponse(value: unknown): boolean {
  // ApiResponseSchema is a function, not a schema, so we need a different approach
  return (
    typeof value === 'object' &&
    value !== null &&
    'success' in value &&
    typeof (value as any).success === 'boolean'
  );
}

export function isSuccessResponse(value: unknown): boolean {
  if (!isApiResponse(value)) return false;
  const response = value as { success: boolean; data?: unknown; error?: unknown };
  return response.success === true && response.data !== undefined;
}

export function isErrorResponse(value: unknown): boolean {
  if (!isApiResponse(value)) return false;
  const response = value as { success: boolean; data?: unknown; error?: unknown };
  return response.success === false && response.error !== undefined;
}

// ===========================
// Utility Type Guards
// ===========================

export function hasProperty<T extends string>(
  obj: unknown,
  prop: T
): obj is Record<T, unknown> {
  return obj !== null && 
         typeof obj === 'object' && 
         prop in obj;
}

export function isNonNullable<T>(value: T): value is NonNullable<T> {
  return value !== null && value !== undefined;
}

export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && !isNaN(value);
}

export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

export function isArray<T = unknown>(value: unknown): value is T[] {
  return Array.isArray(value);
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && 
         typeof value === 'object' && 
         !Array.isArray(value);
}

export function isDate(value: unknown): value is Date {
  return value instanceof Date && !isNaN(value.getTime());
}

export function isUUID(value: unknown): value is string {
  if (!isString(value)) return false;
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidPattern.test(value);
}

export function isEmail(value: unknown): value is string {
  if (!isString(value)) return false;
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailPattern.test(value);
}

export function isURL(value: unknown): value is string {
  if (!isString(value)) return false;
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
}

// ===========================
// Array Type Guards
// ===========================

export function isArrayOf<T>(
  value: unknown,
  guard: (item: unknown) => item is T
): value is T[] {
  if (!Array.isArray(value)) return false;
  return value.every(guard);
}

export function isStringArray(value: unknown): value is string[] {
  return isArrayOf(value, isString);
}

export function isNumberArray(value: unknown): value is number[] {
  return isArrayOf(value, isNumber);
}

// ===========================
// Shape Validation Guards
// ===========================

export function hasShape<T extends Record<string, unknown>>(
  obj: unknown,
  shape: { [K in keyof T]: (value: unknown) => boolean }
): obj is T {
  if (!isObject(obj)) return false;
  
  for (const [key, validator] of Object.entries(shape)) {
    if (!(key in obj) || !validator(obj[key])) {
      return false;
    }
  }
  
  return true;
}

// ===========================
// Optional Property Guards
// ===========================

export function hasOptionalProperty<T extends string, V>(
  obj: unknown,
  prop: T,
  guard?: (value: unknown) => value is V
): obj is Record<T, V | undefined> {
  if (!isObject(obj)) return false;
  if (!(prop in obj)) return true; // Optional property can be missing
  if (guard && obj[prop] !== undefined) {
    return guard(obj[prop]);
  }
  return true;
}

// ===========================
// Enum Guards
// ===========================

export function isEnum<T extends string>(
  value: unknown,
  enumValues: readonly T[]
): value is T {
  return isString(value) && enumValues.includes(value as T);
}

// ===========================
// Import type definitions
// ===========================

import type { 
  BusinessProfile,
  ChatMessage
} from '../validation/zod-schemas';
