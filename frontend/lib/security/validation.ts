import DOMPurify from 'isomorphic-dompurify';
import { z } from 'zod';

/**
 * Security-focused validation schemas using Zod
 */

// Base string validators with XSS protection (without transforms for SSR compatibility)
const safeString = (maxLength = 255) =>
  z.string().max(maxLength, `Text must be no more than ${maxLength} characters`);

const safeText = (maxLength = 1000) =>
  z.string().max(maxLength, `Text must be no more than ${maxLength} characters`);

// Email validation with security checks (simplified for SSR compatibility)
const secureEmail = z
  .string()
  .email('Please enter a valid email address')
  .max(320, 'Email address is too long') // RFC 5321 limit
  .toLowerCase()
  .refine((email) => {
    // Prevent email injection attacks
    const dangerousChars = /[<>"\n\r\t]/;
    return !dangerousChars.test(email);
  }, 'Invalid characters in email address');

// Password validation with security requirements
const securePassword = z
  .string()
  .min(12, 'Password must be at least 12 characters long')
  .max(128, 'Password is too long')
  .refine((password) => {
    // Check for required character types
    const hasLower = /[a-z]/.test(password);
    const hasUpper = /[A-Z]/.test(password);
    const hasNumber = /\d/.test(password);
    const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);

    return hasLower && hasUpper && hasNumber && hasSpecial;
  }, 'Password must contain uppercase, lowercase, number, and special character')
  .refine((password) => {
    // Prevent common weak patterns
    const weakPatterns = [
      /(.)\1{2,}/, // Repeated characters
      /123456|654321|qwerty|password|admin/i, // Common patterns
    ];
    return !weakPatterns.some((pattern) => pattern.test(password));
  }, 'Password contains weak patterns');

// URL validation with security checks
const secureUrl = z
  .string()
  .url('Please enter a valid URL')
  .refine((url) => {
    try {
      const parsed = new URL(url);
      // Only allow safe protocols
      return ['http:', 'https:'].includes(parsed.protocol);
    } catch (_error) {
      return false;
    }
  }, 'Only HTTP and HTTPS URLs are allowed')
  .transform((url) => DOMPurify.sanitize(url));

// File upload validation
const secureFile = z
  .instanceof(File)
  .refine((file) => file.size <= 10 * 1024 * 1024, 'File size must be less than 10MB')
  .refine((file) => {
    const allowedTypes = [
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'application/pdf',
      'text/plain',
      'text/csv',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ];
    return allowedTypes.includes(file.type);
  }, 'File type not allowed')
  .refine((file) => {
    // Prevent dangerous file names
    const dangerousPattern = /[<>:"/\\|?*\x00-\x1f]/;
    return !dangerousPattern.test(file.name);
  }, 'File name contains invalid characters');

// Common form schemas
export const authSchemas = {
  login: z.object({
    email: secureEmail,
    password: z.string().min(1, 'Password is required').max(128),
    rememberMe: z.boolean().default(false),
  }),

  register: z
    .object({
      email: secureEmail,
      password: securePassword,
      confirmPassword: z.string(),
      firstName: safeString(50).min(1, 'First name is required'),
      lastName: safeString(50).min(1, 'Last name is required'),
      companyName: safeString(100).min(1, 'Company name is required'),
      acceptTerms: z.literal(true, {
        errorMap: () => ({ message: 'You must accept the terms and conditions' }),
      }),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: 'Passwords do not match',
      path: ['confirmPassword'],
    }),

  forgotPassword: z.object({
    email: secureEmail,
  }),

  resetPassword: z
    .object({
      token: z.string().min(1, 'Reset token is required'),
      password: securePassword,
      confirmPassword: z.string(),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: 'Passwords do not match',
      path: ['confirmPassword'],
    }),
};

export const businessProfileSchema = z.object({
  companyName: safeString(100).min(1, 'Company name is required'),
  industry: safeString(50).min(1, 'Industry is required'),
  companySize: z.enum(['1-10', '11-50', '51-200', '201-1000', '1000+'], {
    errorMap: () => ({ message: 'Please select a valid company size' }),
  }),
  website: secureUrl.optional().or(z.literal('')),
  description: safeText(500).optional(),
  handlesPersonalData: z.boolean(),
  hasDataProcessingAgreements: z.boolean(),
  region: z.enum(['uk', 'eu', 'us', 'other'], {
    errorMap: () => ({ message: 'Please select a valid region' }),
  }),
});

export const assessmentSchemas = {
  create: z.object({
    title: safeString(100).min(1, 'Assessment title is required'),
    description: safeText(500).optional(),
    framework: z.enum(['gdpr', 'iso27001', 'soc2', 'custom'], {
      errorMap: () => ({ message: 'Please select a valid framework' }),
    }),
    dueDate: z.string().datetime().optional(),
  }),

  question: z.object({
    questionId: z.string().uuid('Invalid question ID'),
    answer: z.enum(['yes', 'no', 'partial', 'not_applicable']),
    notes: safeText(1000).optional(),
    evidence: z.array(secureFile).max(5, 'Maximum 5 files allowed').optional(),
  }),
};

export const evidenceSchema = z.object({
  title: safeString(100).min(1, 'Evidence title is required'),
  description: safeText(500).optional(),
  files: z
    .array(secureFile)
    .min(1, 'At least one file is required')
    .max(10, 'Maximum 10 files allowed'),
  tags: z.array(safeString(30)).max(10, 'Maximum 10 tags allowed').optional(),
  category: z.enum(['policy', 'procedure', 'record', 'certificate', 'training', 'other'], {
    errorMap: () => ({ message: 'Please select a valid category' }),
  }),
});

// XSS Protection utilities
export function sanitizeInput(input: string, options?: { allowHTML?: boolean }): string {
  if (options?.allowHTML) {
    // Allow safe HTML tags only
    return DOMPurify.sanitize(input, {
      ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'u', 'br', 'p'],
      ALLOWED_ATTR: [],
    });
  }

  // Strip all HTML
  return DOMPurify.sanitize(input, { ALLOWED_TAGS: [] });
}

export function sanitizeObject<T extends Record<string, any>>(obj: T): T {
  const sanitized = {} as T;

  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === 'string') {
      sanitized[key as keyof T] = sanitizeInput(value) as T[keyof T];
    } else if (Array.isArray(value)) {
      sanitized[key as keyof T] = value.map((item) =>
        typeof item === 'string' ? sanitizeInput(item) : item,
      ) as T[keyof T];
    } else {
      sanitized[key as keyof T] = value;
    }
  }

  return sanitized;
}

// Input length limits to prevent DoS attacks
export const INPUT_LIMITS = {
  SHORT_TEXT: 255,
  MEDIUM_TEXT: 1000,
  LONG_TEXT: 5000,
  EMAIL: 320,
  PASSWORD: 128,
  URL: 2048,
  FILE_NAME: 255,
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  MAX_FILES_PER_UPLOAD: 10,
} as const;

// Rate limiting configuration
export const RATE_LIMITS = {
  LOGIN_ATTEMPTS: 5,
  PASSWORD_RESET: 3,
  API_REQUESTS_PER_MINUTE: 60,
  FILE_UPLOADS_PER_HOUR: 20,
} as const;
