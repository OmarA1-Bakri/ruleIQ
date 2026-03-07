import { describe, it, expect } from 'vitest';
import {
  validateField,
  ValidationPatterns,
  CommonValidationRules,
  type ValidationRule,
} from '@/lib/form-validation';

describe('validateField', () => {
  describe('required validation', () => {
    const rules: ValidationRule = { required: true };

    it('returns invalid when value is empty string', () => {
      const result = validateField('', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('This field is required');
    });

    it('returns invalid when value is whitespace only', () => {
      const result = validateField('   ', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('This field is required');
    });

    it('returns invalid when value is null', () => {
      const result = validateField(null, rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('This field is required');
    });

    it('returns invalid when value is undefined', () => {
      const result = validateField(undefined, rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('This field is required');
    });

    it('returns valid when value is a non-empty string', () => {
      const result = validateField('hello', rules);
      expect(result.isValid).toBe(true);
    });
  });

  describe('optional field validation', () => {
    const rules: ValidationRule = { required: false, minLength: 5 };

    it('returns valid for empty string when not required', () => {
      const result = validateField('', rules);
      expect(result.isValid).toBe(true);
    });

    it('returns valid for null when not required', () => {
      const result = validateField(null, rules);
      expect(result.isValid).toBe(true);
    });
  });

  describe('minLength validation', () => {
    const rules: ValidationRule = { minLength: 5 };

    it('returns invalid when string is too short', () => {
      const result = validateField('abc', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be at least 5 characters long');
    });

    it('returns valid when string meets minimum length', () => {
      const result = validateField('abcde', rules);
      expect(result.isValid).toBe(true);
    });

    it('returns valid when string exceeds minimum length', () => {
      const result = validateField('abcdefgh', rules);
      expect(result.isValid).toBe(true);
    });
  });

  describe('maxLength validation', () => {
    const rules: ValidationRule = { maxLength: 10 };

    it('returns invalid when string exceeds max length', () => {
      const result = validateField('this is too long for max', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be no more than 10 characters long');
    });

    it('returns valid when string is within max length', () => {
      const result = validateField('short', rules);
      expect(result.isValid).toBe(true);
    });

    it('returns valid when string is exactly max length', () => {
      const result = validateField('1234567890', rules);
      expect(result.isValid).toBe(true);
    });
  });

  describe('pattern validation', () => {
    const rules: ValidationRule = { pattern: /^\d+$/ };

    it('returns invalid when value does not match pattern', () => {
      const result = validateField('abc', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Invalid format');
    });

    it('returns valid when value matches pattern', () => {
      const result = validateField('12345', rules);
      expect(result.isValid).toBe(true);
    });
  });

  describe('custom validation', () => {
    const rules: ValidationRule = {
      custom: (value: unknown) => {
        if (typeof value === 'string' && value.includes('bad')) {
          return 'Value must not contain "bad"';
        }
        return null;
      },
    };

    it('returns invalid when custom validation fails', () => {
      const result = validateField('this is bad', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Value must not contain "bad"');
    });

    it('returns valid when custom validation passes', () => {
      const result = validateField('this is good', rules);
      expect(result.isValid).toBe(true);
      expect(result.success).toBe('Valid input');
    });
  });

  describe('combined rules', () => {
    const rules: ValidationRule = {
      required: true,
      minLength: 3,
      maxLength: 10,
      pattern: /^[a-z]+$/,
    };

    it('checks required first', () => {
      const result = validateField('', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('This field is required');
    });

    it('checks minLength after required', () => {
      const result = validateField('ab', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be at least 3 characters long');
    });

    it('checks maxLength', () => {
      const result = validateField('abcdefghijk', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be no more than 10 characters long');
    });

    it('checks pattern', () => {
      const result = validateField('ABC', rules);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Invalid format');
    });

    it('returns valid when all rules pass', () => {
      const result = validateField('abcdef', rules);
      expect(result.isValid).toBe(true);
      expect(result.success).toBe('Valid input');
    });
  });
});

describe('ValidationPatterns', () => {
  describe('email', () => {
    it('matches valid email', () => {
      expect(ValidationPatterns.email.test('user@example.com')).toBe(true);
    });

    it('rejects email without @', () => {
      expect(ValidationPatterns.email.test('userexample.com')).toBe(false);
    });

    it('rejects email without domain', () => {
      expect(ValidationPatterns.email.test('user@')).toBe(false);
    });

    it('rejects empty string', () => {
      expect(ValidationPatterns.email.test('')).toBe(false);
    });
  });

  describe('url', () => {
    it('matches http url', () => {
      expect(ValidationPatterns.url.test('http://example.com')).toBe(true);
    });

    it('matches https url', () => {
      expect(ValidationPatterns.url.test('https://example.com')).toBe(true);
    });

    it('rejects plain text', () => {
      expect(ValidationPatterns.url.test('example.com')).toBe(false);
    });
  });

  describe('strongPassword', () => {
    it('matches strong password', () => {
      expect(ValidationPatterns.strongPassword.test('Passw0rd!')).toBe(true);
    });

    it('rejects all lowercase', () => {
      expect(ValidationPatterns.strongPassword.test('password1!')).toBe(false);
    });

    it('rejects without number', () => {
      expect(ValidationPatterns.strongPassword.test('Password!')).toBe(false);
    });

    it('rejects without special character', () => {
      expect(ValidationPatterns.strongPassword.test('Password1')).toBe(false);
    });
  });

  describe('alphanumeric', () => {
    it('matches alphanumeric string', () => {
      expect(ValidationPatterns.alphanumeric.test('abc123')).toBe(true);
    });

    it('rejects string with special characters', () => {
      expect(ValidationPatterns.alphanumeric.test('abc-123')).toBe(false);
    });
  });

  describe('numbersOnly', () => {
    it('matches numeric string', () => {
      expect(ValidationPatterns.numbersOnly.test('12345')).toBe(true);
    });

    it('rejects string with letters', () => {
      expect(ValidationPatterns.numbersOnly.test('123abc')).toBe(false);
    });
  });
});

describe('CommonValidationRules', () => {
  describe('email rule', () => {
    it('rejects empty email', () => {
      const result = validateField('', CommonValidationRules.email as unknown as ValidationRule);
      expect(result.isValid).toBe(false);
    });

    it('accepts valid email format', () => {
      const result = validateField('user@example.com', CommonValidationRules.email as unknown as ValidationRule);
      expect(result.isValid).toBe(true);
    });
  });

  describe('password rule', () => {
    it('rejects empty password', () => {
      const result = validateField('', CommonValidationRules.password as unknown as ValidationRule);
      expect(result.isValid).toBe(false);
    });

    it('rejects short password', () => {
      const result = validateField('Ab1!', CommonValidationRules.password as unknown as ValidationRule);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be at least 8 characters long');
    });

    it('rejects weak long password', () => {
      const result = validateField('simplepassword', CommonValidationRules.password as unknown as ValidationRule);
      expect(result.isValid).toBe(false);
    });

    it('accepts strong password', () => {
      const result = validateField('StrongP@ss1', CommonValidationRules.password as unknown as ValidationRule);
      expect(result.isValid).toBe(true);
    });
  });

  describe('companyName rule', () => {
    it('rejects empty company name', () => {
      const result = validateField('', CommonValidationRules.companyName as ValidationRule);
      expect(result.isValid).toBe(false);
    });

    it('rejects single character company name', () => {
      const result = validateField('A', CommonValidationRules.companyName as ValidationRule);
      expect(result.isValid).toBe(false);
      expect(result.error).toBe('Must be at least 2 characters long');
    });

    it('accepts valid company name', () => {
      const result = validateField('RuleIQ Ltd', CommonValidationRules.companyName as ValidationRule);
      expect(result.isValid).toBe(true);
    });
  });
});
