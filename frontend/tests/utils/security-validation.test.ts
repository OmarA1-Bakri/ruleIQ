import { describe, it, expect } from 'vitest';
import {
  sanitizeInput,
  sanitizeObject,
  INPUT_LIMITS,
  RATE_LIMITS,
  authSchemas,
  businessProfileSchema,
  assessmentSchemas,
} from '@/lib/security/validation';

// ============================================================================
// INPUT_LIMITS constants
// ============================================================================

describe('INPUT_LIMITS', () => {
  it('SHORT_TEXT is 255', () => {
    expect(INPUT_LIMITS.SHORT_TEXT).toBe(255);
  });

  it('MEDIUM_TEXT is 1000', () => {
    expect(INPUT_LIMITS.MEDIUM_TEXT).toBe(1000);
  });

  it('LONG_TEXT is 5000', () => {
    expect(INPUT_LIMITS.LONG_TEXT).toBe(5000);
  });

  it('EMAIL is 320 (RFC 5321)', () => {
    expect(INPUT_LIMITS.EMAIL).toBe(320);
  });

  it('PASSWORD is 128', () => {
    expect(INPUT_LIMITS.PASSWORD).toBe(128);
  });

  it('URL is 2048', () => {
    expect(INPUT_LIMITS.URL).toBe(2048);
  });

  it('FILE_NAME is 255', () => {
    expect(INPUT_LIMITS.FILE_NAME).toBe(255);
  });

  it('MAX_FILE_SIZE is 10MB (10 * 1024 * 1024)', () => {
    expect(INPUT_LIMITS.MAX_FILE_SIZE).toBe(10 * 1024 * 1024);
  });

  it('MAX_FILES_PER_UPLOAD is 10', () => {
    expect(INPUT_LIMITS.MAX_FILES_PER_UPLOAD).toBe(10);
  });

  it('limits are in ascending order: SHORT < MEDIUM < LONG', () => {
    expect(INPUT_LIMITS.SHORT_TEXT).toBeLessThan(INPUT_LIMITS.MEDIUM_TEXT);
    expect(INPUT_LIMITS.MEDIUM_TEXT).toBeLessThan(INPUT_LIMITS.LONG_TEXT);
  });

  it('all values are positive numbers', () => {
    Object.values(INPUT_LIMITS).forEach((v) => {
      expect(typeof v).toBe('number');
      expect(v).toBeGreaterThan(0);
    });
  });
});

// ============================================================================
// RATE_LIMITS constants
// ============================================================================

describe('RATE_LIMITS', () => {
  it('LOGIN_ATTEMPTS is 5', () => {
    expect(RATE_LIMITS.LOGIN_ATTEMPTS).toBe(5);
  });

  it('PASSWORD_RESET is 3', () => {
    expect(RATE_LIMITS.PASSWORD_RESET).toBe(3);
  });

  it('API_REQUESTS_PER_MINUTE is 60', () => {
    expect(RATE_LIMITS.API_REQUESTS_PER_MINUTE).toBe(60);
  });

  it('FILE_UPLOADS_PER_HOUR is 20', () => {
    expect(RATE_LIMITS.FILE_UPLOADS_PER_HOUR).toBe(20);
  });

  it('LOGIN_ATTEMPTS < PASSWORD_RESET? No — login > reset by design', () => {
    // login is 5, reset is 3 — login is more permissive
    expect(RATE_LIMITS.LOGIN_ATTEMPTS).toBeGreaterThan(RATE_LIMITS.PASSWORD_RESET);
  });

  it('all values are positive integers', () => {
    Object.values(RATE_LIMITS).forEach((v) => {
      expect(typeof v).toBe('number');
      expect(v).toBeGreaterThan(0);
      expect(Number.isInteger(v)).toBe(true);
    });
  });
});

// ============================================================================
// sanitizeInput
// ============================================================================

describe('sanitizeInput', () => {
  it('returns plain text unchanged', () => {
    expect(sanitizeInput('Hello world')).toBe('Hello world');
  });

  it('strips script tags from input (default mode)', () => {
    const result = sanitizeInput('<script>alert("xss")</script>Hello');
    expect(result).not.toContain('<script>');
    expect(result).toContain('Hello');
  });

  it('strips all HTML tags in default mode', () => {
    const result = sanitizeInput('<b>bold</b> text');
    expect(result).not.toContain('<b>');
    expect(result).toContain('bold');
    expect(result).toContain('text');
  });

  it('strips img tags with onerror (XSS vector)', () => {
    const result = sanitizeInput('<img src="x" onerror="alert(1)">');
    expect(result).not.toContain('<img');
    expect(result).not.toContain('onerror');
  });

  it('returns empty string for empty input', () => {
    expect(sanitizeInput('')).toBe('');
  });

  it('preserves text content with special chars (non-HTML)', () => {
    expect(sanitizeInput('Hello & World')).toContain('World');
  });

  it('allowHTML=true permits safe tags (b, i, em, strong)', () => {
    const result = sanitizeInput('<b>bold</b> and <em>italic</em>', { allowHTML: true });
    expect(result).toContain('<b>');
    expect(result).toContain('<em>');
    expect(result).toContain('bold');
    expect(result).toContain('italic');
  });

  it('allowHTML=true still strips script tags', () => {
    const result = sanitizeInput('<script>evil()</script><b>ok</b>', { allowHTML: true });
    expect(result).not.toContain('<script>');
    expect(result).toContain('<b>');
  });

  it('allowHTML=true strips attributes (even on safe tags)', () => {
    const result = sanitizeInput('<b onclick="evil()">text</b>', { allowHTML: true });
    expect(result).not.toContain('onclick');
  });

  it('returns a string for all inputs', () => {
    expect(typeof sanitizeInput('anything')).toBe('string');
    expect(typeof sanitizeInput('')).toBe('string');
    expect(typeof sanitizeInput('<script>')).toBe('string');
  });
});

// ============================================================================
// sanitizeObject
// ============================================================================

describe('sanitizeObject', () => {
  it('sanitizes string values in an object', () => {
    const result = sanitizeObject({ name: '<script>evil</script>Alice' });
    expect(result.name).not.toContain('<script>');
    expect(result.name).toContain('Alice');
  });

  it('preserves non-string values unchanged', () => {
    const result = sanitizeObject({ count: 42, active: true, data: null } as any);
    expect(result.count).toBe(42);
    expect(result.active).toBe(true);
    expect(result.data).toBeNull();
  });

  it('sanitizes strings inside arrays', () => {
    const result = sanitizeObject({ tags: ['<b>tag1</b>', 'clean'] });
    expect(result.tags[0]).not.toContain('<b>');
    expect(result.tags[1]).toBe('clean');
  });

  it('preserves non-string array elements', () => {
    const result = sanitizeObject({ ids: [1, 2, 3] });
    expect(result.ids).toEqual([1, 2, 3]);
  });

  it('handles empty object', () => {
    const result = sanitizeObject({});
    expect(result).toEqual({});
  });

  it('handles object with multiple fields', () => {
    const result = sanitizeObject({
      title: '<img onerror="x">Good Title',
      count: 5,
      notes: 'Clean notes',
    });
    expect(result.title).not.toContain('<img');
    expect(result.count).toBe(5);
    expect(result.notes).toBe('Clean notes');
  });

  it('returns an object of the same shape', () => {
    const input = { a: 'hello', b: 123 };
    const result = sanitizeObject(input);
    expect(Object.keys(result)).toEqual(['a', 'b']);
  });
});

// ============================================================================
// authSchemas.login
// ============================================================================

describe('authSchemas.login', () => {
  const validLogin = {
    email: 'user@example.com',
    password: 'Password123',
    rememberMe: false,
  };

  it('accepts valid login data', () => {
    expect(authSchemas.login.safeParse(validLogin).success).toBe(true);
  });

  it('rejects invalid email format', () => {
    expect(authSchemas.login.safeParse({ ...validLogin, email: 'bad' }).success).toBe(false);
  });

  it('rejects email with dangerous characters', () => {
    // secureEmail rejects <> chars
    const result = authSchemas.login.safeParse({ ...validLogin, email: 'user<>@example.com' });
    expect(result.success).toBe(false);
  });

  it('rejects empty password', () => {
    expect(authSchemas.login.safeParse({ ...validLogin, password: '' }).success).toBe(false);
  });

  it('defaults rememberMe to false when omitted', () => {
    const result = authSchemas.login.safeParse({ email: 'user@example.com', password: 'pass123' });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.rememberMe).toBe(false);
    }
  });

  it('lowercases the email', () => {
    const result = authSchemas.login.safeParse({ ...validLogin, email: 'User@EXAMPLE.COM' });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe('user@example.com');
    }
  });
});

// ============================================================================
// authSchemas.forgotPassword
// ============================================================================

describe('authSchemas.forgotPassword', () => {
  it('accepts valid email', () => {
    expect(authSchemas.forgotPassword.safeParse({ email: 'user@example.com' }).success).toBe(true);
  });

  it('rejects empty email', () => {
    expect(authSchemas.forgotPassword.safeParse({ email: '' }).success).toBe(false);
  });

  it('rejects invalid email', () => {
    expect(authSchemas.forgotPassword.safeParse({ email: 'not-email' }).success).toBe(false);
  });
});

// ============================================================================
// businessProfileSchema (security/validation.ts version)
// ============================================================================

describe('businessProfileSchema (security)', () => {
  const validProfile = {
    companyName: 'ACME Corp',
    industry: 'Technology',
    companySize: '11-50' as const,
    handlesPersonalData: false,
    hasDataProcessingAgreements: false,
    region: 'uk' as const,
  };

  it('accepts valid profile', () => {
    expect(businessProfileSchema.safeParse(validProfile).success).toBe(true);
  });

  it('rejects empty company name', () => {
    expect(businessProfileSchema.safeParse({ ...validProfile, companyName: '' }).success).toBe(false);
  });

  it('rejects company name over 100 chars', () => {
    expect(
      businessProfileSchema.safeParse({ ...validProfile, companyName: 'A'.repeat(101) }).success,
    ).toBe(false);
  });

  it('accepts all valid company sizes', () => {
    const sizes = ['1-10', '11-50', '51-200', '201-1000', '1000+'] as const;
    sizes.forEach((size) => {
      expect(
        businessProfileSchema.safeParse({ ...validProfile, companySize: size }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid company size', () => {
    expect(
      businessProfileSchema.safeParse({ ...validProfile, companySize: 'huge' as any }).success,
    ).toBe(false);
  });

  it('accepts all valid regions', () => {
    const regions = ['uk', 'eu', 'us', 'other'] as const;
    regions.forEach((region) => {
      expect(businessProfileSchema.safeParse({ ...validProfile, region }).success).toBe(true);
    });
  });

  it('rejects invalid region', () => {
    expect(
      businessProfileSchema.safeParse({ ...validProfile, region: 'mars' as any }).success,
    ).toBe(false);
  });

  it('accepts optional description', () => {
    expect(
      businessProfileSchema.safeParse({ ...validProfile, description: 'We do stuff' }).success,
    ).toBe(true);
  });
});

// ============================================================================
// assessmentSchemas.create
// ============================================================================

describe('assessmentSchemas.create', () => {
  const validCreate = {
    title: 'Q1 GDPR Assessment',
    framework: 'gdpr' as const,
  };

  it('accepts valid assessment creation data', () => {
    expect(assessmentSchemas.create.safeParse(validCreate).success).toBe(true);
  });

  it('rejects empty title', () => {
    expect(assessmentSchemas.create.safeParse({ ...validCreate, title: '' }).success).toBe(false);
  });

  it('rejects title over 100 chars', () => {
    expect(
      assessmentSchemas.create.safeParse({ ...validCreate, title: 'A'.repeat(101) }).success,
    ).toBe(false);
  });

  it('accepts all valid frameworks', () => {
    const frameworks = ['gdpr', 'iso27001', 'soc2', 'custom'] as const;
    frameworks.forEach((framework) => {
      expect(assessmentSchemas.create.safeParse({ ...validCreate, framework }).success).toBe(true);
    });
  });

  it('rejects invalid framework', () => {
    expect(
      assessmentSchemas.create.safeParse({ ...validCreate, framework: 'pci-dss' as any }).success,
    ).toBe(false);
  });

  it('accepts optional description', () => {
    expect(
      assessmentSchemas.create.safeParse({ ...validCreate, description: 'Annual review' }).success,
    ).toBe(true);
  });
});
