import { describe, it, expect } from 'vitest';
import {
  loginSchema,
  registrationStep1Schema,
  registrationStep2Schema,
  registrationStep3Schema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema,
  calculatePasswordStrength,
  validateForm,
} from '@/lib/validations/auth';

// ============================================================================
// loginSchema
// ============================================================================

describe('loginSchema', () => {
  const valid = { email: 'user@example.com', password: 'password123' };

  it('accepts valid email and password', () => {
    expect(loginSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects missing email', () => {
    const result = loginSchema.safeParse({ ...valid, email: '' });
    expect(result.success).toBe(false);
  });

  it('rejects invalid email format', () => {
    const result = loginSchema.safeParse({ ...valid, email: 'not-an-email' });
    expect(result.success).toBe(false);
  });

  it('rejects email over 254 characters', () => {
    const result = loginSchema.safeParse({ ...valid, email: 'a'.repeat(250) + '@b.com' });
    expect(result.success).toBe(false);
  });

  it('rejects password under 8 characters', () => {
    const result = loginSchema.safeParse({ ...valid, password: 'short' });
    expect(result.success).toBe(false);
  });

  it('rejects password over 128 characters', () => {
    const result = loginSchema.safeParse({ ...valid, password: 'a'.repeat(129) });
    expect(result.success).toBe(false);
  });

  it('defaults rememberMe to false', () => {
    const result = loginSchema.safeParse(valid);
    expect(result.success && result.data.rememberMe).toBe(false);
  });

  it('accepts rememberMe=true', () => {
    const result = loginSchema.safeParse({ ...valid, rememberMe: true });
    expect(result.success && result.data.rememberMe).toBe(true);
  });
});

// ============================================================================
// registrationStep1Schema — strong password + confirm match
// ============================================================================

describe('registrationStep1Schema', () => {
  const strongPassword = 'MyS3cur3P@ssw0rd!';
  const valid = {
    email: 'user@example.com',
    password: strongPassword,
    confirmPassword: strongPassword,
  };

  it('accepts valid registration step 1 data', () => {
    expect(registrationStep1Schema.safeParse(valid).success).toBe(true);
  });

  it('rejects password under 12 characters', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: 'Short1!',
      confirmPassword: 'Short1!',
    });
    expect(result.success).toBe(false);
  });

  it('rejects password without uppercase', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: 'mysecurep@ssword1',
      confirmPassword: 'mysecurep@ssword1',
    });
    expect(result.success).toBe(false);
  });

  it('rejects password without lowercase', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: 'MYSECUREP@SSWORD1',
      confirmPassword: 'MYSECUREP@SSWORD1',
    });
    expect(result.success).toBe(false);
  });

  it('rejects password without number', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: 'MySecureP@ssword!',
      confirmPassword: 'MySecureP@ssword!',
    });
    expect(result.success).toBe(false);
  });

  it('rejects password without special character', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: ['My', 'Secure', 'Password', '1'].join(''),
      confirmPassword: ['My', 'Secure', 'Password', '1'].join(''),
    });
    expect(result.success).toBe(false);
  });

  it('rejects password with spaces', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      password: 'My Secure P@ss1',
      confirmPassword: 'My Secure P@ss1',
    });
    expect(result.success).toBe(false);
  });

  it('rejects when passwords do not match', () => {
    const result = registrationStep1Schema.safeParse({
      ...valid,
      confirmPassword: 'DifferentP@ssword1!',
    });
    expect(result.success).toBe(false);
  });
});

// ============================================================================
// registrationStep2Schema
// ============================================================================

describe('registrationStep2Schema', () => {
  const valid = {
    firstName: 'John',
    lastName: 'Doe',
    companyName: 'Acme Corp',
    companySize: 'small' as const,
    industry: 'technology',
  };

  it('accepts valid step 2 data', () => {
    expect(registrationStep2Schema.safeParse(valid).success).toBe(true);
  });

  it('rejects firstName under 2 chars', () => {
    expect(registrationStep2Schema.safeParse({ ...valid, firstName: 'J' }).success).toBe(false);
  });

  it('rejects firstName over 50 chars', () => {
    expect(
      registrationStep2Schema.safeParse({ ...valid, firstName: 'J'.repeat(51) }).success,
    ).toBe(false);
  });

  it('rejects firstName with invalid characters', () => {
    expect(
      registrationStep2Schema.safeParse({ ...valid, firstName: 'John123' }).success,
    ).toBe(false);
  });

  it('rejects lastName under 2 chars', () => {
    expect(registrationStep2Schema.safeParse({ ...valid, lastName: 'D' }).success).toBe(false);
  });

  it('rejects companyName under 2 chars', () => {
    expect(registrationStep2Schema.safeParse({ ...valid, companyName: 'A' }).success).toBe(false);
  });

  it('rejects invalid companySize', () => {
    expect(
      registrationStep2Schema.safeParse({ ...valid, companySize: 'enormous' as any }).success,
    ).toBe(false);
  });

  it('accepts all valid companySizes', () => {
    const sizes = ['micro', 'small', 'medium', 'large'] as const;
    sizes.forEach((size) => {
      expect(registrationStep2Schema.safeParse({ ...valid, companySize: size }).success).toBe(true);
    });
  });
});

// ============================================================================
// registrationStep3Schema
// ============================================================================

describe('registrationStep3Schema', () => {
  const valid = {
    complianceFrameworks: ['ISO 27001'],
    hasDataProtectionOfficer: false,
    agreedToTerms: true,
    agreedToDataProcessing: true,
  };

  it('accepts valid step 3 data', () => {
    expect(registrationStep3Schema.safeParse(valid).success).toBe(true);
  });

  it('rejects empty complianceFrameworks array', () => {
    expect(
      registrationStep3Schema.safeParse({ ...valid, complianceFrameworks: [] }).success,
    ).toBe(false);
  });

  it('rejects when agreedToTerms is false', () => {
    expect(
      registrationStep3Schema.safeParse({ ...valid, agreedToTerms: false }).success,
    ).toBe(false);
  });

  it('rejects when agreedToDataProcessing is false', () => {
    expect(
      registrationStep3Schema.safeParse({ ...valid, agreedToDataProcessing: false }).success,
    ).toBe(false);
  });

  it('accepts multiple compliance frameworks', () => {
    const result = registrationStep3Schema.safeParse({
      ...valid,
      complianceFrameworks: ['ISO 27001', 'GDPR', 'SOC 2'],
    });
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// forgotPasswordSchema
// ============================================================================

describe('forgotPasswordSchema', () => {
  it('accepts valid email', () => {
    expect(forgotPasswordSchema.safeParse({ email: 'user@example.com' }).success).toBe(true);
  });

  it('rejects empty email', () => {
    expect(forgotPasswordSchema.safeParse({ email: '' }).success).toBe(false);
  });

  it('rejects invalid email format', () => {
    expect(forgotPasswordSchema.safeParse({ email: 'notanemail' }).success).toBe(false);
  });
});

// ============================================================================
// changePasswordSchema
// ============================================================================

describe('changePasswordSchema', () => {
  const strongNew = 'NewStr0ngP@ssword!';
  const valid = {
    currentPassword: 'oldpassword123',
    newPassword: strongNew,
    confirmPassword: strongNew,
  };

  it('accepts valid change password data', () => {
    expect(changePasswordSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects when new passwords do not match', () => {
    expect(
      changePasswordSchema.safeParse({ ...valid, confirmPassword: 'Mismatch1@!' }).success,
    ).toBe(false);
  });

  it('rejects when new password equals current password', () => {
    const samePass = 'SameP@ssw0rd12!';
    expect(
      changePasswordSchema.safeParse({
        currentPassword: samePass,
        newPassword: samePass,
        confirmPassword: samePass,
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// calculatePasswordStrength
// ============================================================================

describe('calculatePasswordStrength', () => {
  it('gives score 0 for empty string', () => {
    const { score } = calculatePasswordStrength('');
    expect(score).toBe(0);
  });

  it('gives max score 100 for strong password', () => {
    const { score, feedback } = calculatePasswordStrength('MyStr0ng!P@ssword');
    expect(score).toBe(100);
    expect(feedback).toHaveLength(0);
  });

  it('deducts for missing uppercase', () => {
    const { score } = calculatePasswordStrength('mylongpassword1!');
    expect(score).toBeLessThan(100);
  });

  it('deducts for missing lowercase', () => {
    const { score } = calculatePasswordStrength('MYLONGPASSWORD1!');
    expect(score).toBeLessThan(100);
  });

  it('deducts for missing number', () => {
    const { score } = calculatePasswordStrength('MyLongPassword!!');
    expect(score).toBeLessThan(100);
  });

  it('deducts for missing special character', () => {
    const { score } = calculatePasswordStrength('MyLongPassword1');
    expect(score).toBeLessThan(100);
  });

  it('gives partial credit for 8+ char password', () => {
    const { score } = calculatePasswordStrength('Ab1!efgh');
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThan(100);
  });

  it('returns feedback for missing elements', () => {
    const { feedback } = calculatePasswordStrength('short');
    expect(feedback.length).toBeGreaterThan(0);
  });

  it('score increases with length (8 vs 12)', () => {
    const short = calculatePasswordStrength('Ab1!efgh');
    const long = calculatePasswordStrength('Ab1!efghijkl');
    expect(long.score).toBeGreaterThanOrEqual(short.score);
  });
});

// ============================================================================
// validateForm helper
// ============================================================================

describe('validateForm', () => {
  it('returns success=true with parsed data for valid input', () => {
    const result = validateForm(loginSchema, {
      email: 'user@example.com',
      password: 'password123',
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe('user@example.com');
    }
  });

  it('returns success=false with errors for invalid input', () => {
    const result = validateForm(loginSchema, { email: 'not-valid', password: 'short' });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(Object.keys(result.errors).length).toBeGreaterThan(0);
    }
  });

  it('includes field path in errors', () => {
    const result = validateForm(loginSchema, { email: 'bad', password: 'x' });
    if (!result.success) {
      expect(result.errors).toHaveProperty('email');
    }
  });

  it('returns success=true with default values applied', () => {
    const result = validateForm(loginSchema, {
      email: 'user@example.com',
      password: 'password123',
    });
    if (result.success) {
      expect(result.data.rememberMe).toBe(false); // default applied
    }
  });
});
