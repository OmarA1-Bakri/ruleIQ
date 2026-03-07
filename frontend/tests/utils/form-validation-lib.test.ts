import { describe, it, expect } from 'vitest';
import {
  validateField,
  ValidationPatterns,
  CommonValidationRules,
} from '@/lib/form-validation';

// ============================================================================
// validateField — required
// ============================================================================

describe('validateField — required', () => {
  it('returns isValid=false when required and value is empty string', () => {
    const result = validateField('', { required: true });
    expect(result.isValid).toBe(false);
    expect(result.error).toBe('This field is required');
  });

  it('returns isValid=false when required and value is null', () => {
    const result = validateField(null, { required: true });
    expect(result.isValid).toBe(false);
  });

  it('returns isValid=false when required and value is undefined', () => {
    const result = validateField(undefined, { required: true });
    expect(result.isValid).toBe(false);
  });

  it('returns isValid=false when required and value is whitespace-only', () => {
    const result = validateField('   ', { required: true });
    expect(result.isValid).toBe(false);
  });

  it('returns isValid=true when required and value is provided', () => {
    const result = validateField('hello', { required: true });
    expect(result.isValid).toBe(true);
  });

  it('returns isValid=true when not required and value is empty', () => {
    const result = validateField('', { required: false });
    expect(result.isValid).toBe(true);
  });

  it('returns isValid=true when no rules provided and value is empty', () => {
    const result = validateField('', {});
    expect(result.isValid).toBe(true);
  });
});

// ============================================================================
// validateField — minLength
// ============================================================================

describe('validateField — minLength', () => {
  it('returns error when string is shorter than minLength', () => {
    const result = validateField('hi', { minLength: 5 });
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('5');
  });

  it('returns isValid=true when string exactly meets minLength', () => {
    const result = validateField('hello', { minLength: 5 });
    expect(result.isValid).toBe(true);
  });

  it('returns isValid=true when string exceeds minLength', () => {
    const result = validateField('hello world', { minLength: 5 });
    expect(result.isValid).toBe(true);
  });

  it('skips minLength check for empty non-required field', () => {
    const result = validateField('', { minLength: 5 });
    expect(result.isValid).toBe(true);
  });
});

// ============================================================================
// validateField — maxLength
// ============================================================================

describe('validateField — maxLength', () => {
  it('returns error when string exceeds maxLength', () => {
    const result = validateField('toolongvalue', { maxLength: 5 });
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('5');
  });

  it('returns isValid=true when string exactly meets maxLength', () => {
    const result = validateField('hello', { maxLength: 5 });
    expect(result.isValid).toBe(true);
  });

  it('returns isValid=true when string is shorter than maxLength', () => {
    const result = validateField('hi', { maxLength: 5 });
    expect(result.isValid).toBe(true);
  });
});

// ============================================================================
// validateField — pattern
// ============================================================================

describe('validateField — pattern', () => {
  it('returns error when string does not match pattern', () => {
    const result = validateField('abc', { pattern: /^\d+$/ });
    expect(result.isValid).toBe(false);
    expect(result.error).toBe('Invalid format');
  });

  it('returns isValid=true when string matches pattern', () => {
    const result = validateField('12345', { pattern: /^\d+$/ });
    expect(result.isValid).toBe(true);
  });
});

// ============================================================================
// validateField — custom validation
// ============================================================================

describe('validateField — custom validation', () => {
  it('returns error from custom validator', () => {
    const result = validateField('bad', {
      custom: (v) => (v === 'bad' ? 'Value cannot be "bad"' : null),
    });
    expect(result.isValid).toBe(false);
    expect(result.error).toBe('Value cannot be "bad"');
  });

  it('returns isValid=true when custom validator returns null', () => {
    const result = validateField('good', {
      custom: () => null,
    });
    expect(result.isValid).toBe(true);
  });
});

// ============================================================================
// validateField — success result
// ============================================================================

describe('validateField — success result', () => {
  it('returns success message when validation passes', () => {
    const result = validateField('hello', { required: true });
    expect(result.success).toBe('Valid input');
  });

  it('returns no error on success', () => {
    const result = validateField('hello', { required: true });
    expect(result.error).toBeUndefined();
  });
});

// ============================================================================
// ValidationPatterns
// ============================================================================

describe('ValidationPatterns.email', () => {
  it('accepts valid email', () => {
    expect(ValidationPatterns.email.test('user@example.com')).toBe(true);
  });

  it('rejects email without @', () => {
    expect(ValidationPatterns.email.test('notanemail')).toBe(false);
  });

  it('rejects email without domain', () => {
    expect(ValidationPatterns.email.test('user@')).toBe(false);
  });
});

describe('ValidationPatterns.phone', () => {
  it('accepts basic UK-style phone', () => {
    expect(ValidationPatterns.phone.test('+44 7911 123456')).toBe(true);
  });

  it('accepts digits-only phone', () => {
    expect(ValidationPatterns.phone.test('07911123456')).toBe(true);
  });
});

describe('ValidationPatterns.url', () => {
  it('accepts https URL', () => {
    expect(ValidationPatterns.url.test('https://example.com')).toBe(true);
  });

  it('accepts http URL', () => {
    expect(ValidationPatterns.url.test('http://example.com')).toBe(true);
  });

  it('rejects plain string', () => {
    expect(ValidationPatterns.url.test('not-a-url')).toBe(false);
  });
});

describe('ValidationPatterns.strongPassword', () => {
  it('accepts password with all character types', () => {
    expect(ValidationPatterns.strongPassword.test('Passw0rd!')).toBe(true);
  });

  it('rejects lowercase-only password', () => {
    expect(ValidationPatterns.strongPassword.test('password')).toBe(false);
  });
});

describe('ValidationPatterns.alphanumeric', () => {
  it('accepts alphanumeric string', () => {
    expect(ValidationPatterns.alphanumeric.test('abc123')).toBe(true);
  });

  it('rejects string with special characters', () => {
    expect(ValidationPatterns.alphanumeric.test('abc!123')).toBe(false);
  });

  it('rejects string with spaces', () => {
    expect(ValidationPatterns.alphanumeric.test('abc 123')).toBe(false);
  });
});

describe('ValidationPatterns.numbersOnly', () => {
  it('accepts digits-only string', () => {
    expect(ValidationPatterns.numbersOnly.test('12345')).toBe(true);
  });

  it('rejects string with letters', () => {
    expect(ValidationPatterns.numbersOnly.test('123a5')).toBe(false);
  });
});

// ============================================================================
// CommonValidationRules
// ============================================================================

describe('CommonValidationRules.email', () => {
  it('has required=true', () => {
    expect(CommonValidationRules.email.required).toBe(true);
  });

  it('has email pattern', () => {
    expect(CommonValidationRules.email.pattern).toBe(ValidationPatterns.email);
  });

  it('custom returns error for invalid email', () => {
    const error = (CommonValidationRules.email.custom as Function)('not-an-email');
    expect(error).toContain('valid email');
  });

  it('custom returns null for valid email', () => {
    const error = (CommonValidationRules.email.custom as Function)('user@example.com');
    expect(error).toBeNull();
  });
});

describe('CommonValidationRules.password', () => {
  it('has required=true', () => {
    expect(CommonValidationRules.password.required).toBe(true);
  });

  it('has minLength=8', () => {
    expect(CommonValidationRules.password.minLength).toBe(8);
  });

  it('custom returns error for weak password (no uppercase)', () => {
    const error = (CommonValidationRules.password.custom as Function)('password1!');
    expect(error).toContain('uppercase');
  });

  it('custom returns null for strong password', () => {
    const error = (CommonValidationRules.password.custom as Function)('Passw0rd!');
    expect(error).toBeNull();
  });

  it('custom returns null for short password (minLength handled separately)', () => {
    // custom only runs its check when length >= 8
    const error = (CommonValidationRules.password.custom as Function)('short');
    expect(error).toBeNull();
  });
});

describe('CommonValidationRules.companyName', () => {
  it('has required=true', () => {
    expect(CommonValidationRules.companyName.required).toBe(true);
  });

  it('has minLength=2', () => {
    expect(CommonValidationRules.companyName.minLength).toBe(2);
  });

  it('has maxLength=100', () => {
    expect(CommonValidationRules.companyName.maxLength).toBe(100);
  });
});

describe('CommonValidationRules.phone', () => {
  it('has phone pattern', () => {
    expect(CommonValidationRules.phone.pattern).toBe(ValidationPatterns.phone);
  });

  it('custom returns error for invalid phone', () => {
    const error = (CommonValidationRules.phone.custom as Function)('abc');
    expect(error).toContain('phone');
  });

  it('custom returns null for valid phone', () => {
    const error = (CommonValidationRules.phone.custom as Function)('+44 7911 123456');
    expect(error).toBeNull();
  });

  it('custom returns null for empty value (not required)', () => {
    const error = (CommonValidationRules.phone.custom as Function)('');
    expect(error).toBeNull();
  });
});
