import { describe, it, expect } from 'vitest';
import {
  isAppError,
  isValidationError,
  isApiError,
  safeJsonParse,
  safeJsonParseWithValidation,
  safeGetFromStorage,
  safeSetToStorage,
  assertNonNull,
  assertIsString,
  assertIsNumber,
  assertIsArray,
  safeAccess,
  safeAccessNested,
  toAppError,
  toValidationError,
  toApiError,
  isString,
  isNumber,
  isBoolean,
  isObject,
  isArray,
  isNonEmptyString,
  isValidEmail,
  isValidUrl,
  success,
  failure,
  isSuccess,
  isFailure,
} from '@/lib/utils/type-safety';

// ── Type Guards ──────────────────────────────────────────

describe('isAppError', () => {
  it('returns true for objects with message string', () => {
    expect(isAppError({ message: 'error' })).toBe(true);
    expect(isAppError({ message: 'error', code: 'E001' })).toBe(true);
  });

  it('returns false for non-error objects', () => {
    expect(isAppError(null)).toBe(false);
    expect(isAppError(undefined)).toBe(false);
    expect(isAppError('string')).toBe(false);
    expect(isAppError(42)).toBe(false);
    expect(isAppError({})).toBe(false);
    expect(isAppError({ message: 42 })).toBe(false);
  });
});

describe('isValidationError', () => {
  it('returns true for error with field property', () => {
    expect(isValidationError({ message: 'bad', field: 'email' })).toBe(true);
  });

  it('returns false when no field', () => {
    expect(isValidationError({ message: 'bad' })).toBe(false);
  });
});

describe('isApiError', () => {
  it('returns true for error with status property', () => {
    expect(isApiError({ message: 'bad', status: 404 })).toBe(true);
  });

  it('returns false when no status', () => {
    expect(isApiError({ message: 'bad' })).toBe(false);
  });
});

// ── safeJsonParse ────────────────────────────────────────

describe('safeJsonParse', () => {
  it('parses valid JSON', () => {
    expect(safeJsonParse('{"key":"value"}')).toEqual({ key: 'value' });
    expect(safeJsonParse('[1,2,3]')).toEqual([1, 2, 3]);
    expect(safeJsonParse('"hello"')).toBe('hello');
    expect(safeJsonParse('42')).toBe(42);
  });

  it('returns null for invalid JSON', () => {
    expect(safeJsonParse('{')).toBeNull();
    expect(safeJsonParse('undefined')).toBeNull();
    expect(safeJsonParse('')).toBeNull();
  });

  it('returns fallback for invalid JSON when provided', () => {
    expect(safeJsonParse('{', { default: true })).toEqual({ default: true });
    expect(safeJsonParse('bad', [])).toEqual([]);
  });
});

// ── safeJsonParseWithValidation ──────────────────────────

describe('safeJsonParseWithValidation', () => {
  const isStringArray = (v: unknown): v is string[] =>
    Array.isArray(v) && v.every((item) => typeof item === 'string');

  it('returns parsed value when validation passes', () => {
    expect(safeJsonParseWithValidation('["a","b"]', isStringArray)).toEqual(['a', 'b']);
  });

  it('returns null when validation fails', () => {
    expect(safeJsonParseWithValidation('[1,2,3]', isStringArray)).toBeNull();
  });

  it('returns fallback when validation fails', () => {
    expect(safeJsonParseWithValidation('[1,2]', isStringArray, ['default'])).toEqual(['default']);
  });

  it('returns null for invalid JSON', () => {
    expect(safeJsonParseWithValidation('{bad}', isStringArray)).toBeNull();
  });

  it('returns fallback for invalid JSON', () => {
    expect(safeJsonParseWithValidation('{bad}', isStringArray, ['fallback'])).toEqual(['fallback']);
  });
});

// ── safeGetFromStorage / safeSetToStorage ─────────────────

describe('safeGetFromStorage', () => {
  it('returns parsed value from localStorage', () => {
    localStorage.setItem('test-key', JSON.stringify({ data: 42 }));
    expect(safeGetFromStorage('test-key')).toEqual({ data: 42 });
    localStorage.removeItem('test-key');
  });

  it('returns null for missing key', () => {
    expect(safeGetFromStorage('nonexistent-key')).toBeNull();
  });

  it('returns null for invalid JSON in storage', () => {
    localStorage.setItem('bad-json', '{not valid}');
    expect(safeGetFromStorage('bad-json')).toBeNull();
    localStorage.removeItem('bad-json');
  });

  it('applies validator function', () => {
    localStorage.setItem('validated', JSON.stringify({ name: 'test' }));
    const validator = (v: unknown): v is { name: string } =>
      typeof v === 'object' && v !== null && 'name' in v;

    expect(safeGetFromStorage('validated', validator)).toEqual({ name: 'test' });

    // Validator that fails
    const failValidator = (v: unknown): v is number => typeof v === 'number';
    expect(safeGetFromStorage('validated', failValidator)).toBeNull();

    localStorage.removeItem('validated');
  });
});

describe('safeSetToStorage', () => {
  it('stores value and returns true', () => {
    const result = safeSetToStorage('test-set', { value: 123 });
    expect(result).toBe(true);
    expect(JSON.parse(localStorage.getItem('test-set')!)).toEqual({ value: 123 });
    localStorage.removeItem('test-set');
  });

  it('stores string values', () => {
    expect(safeSetToStorage('str-key', 'hello')).toBe(true);
    expect(JSON.parse(localStorage.getItem('str-key')!)).toBe('hello');
    localStorage.removeItem('str-key');
  });
});

// ── Assertion helpers ────────────────────────────────────

describe('assertNonNull', () => {
  it('does not throw for non-null values', () => {
    expect(() => assertNonNull('hello')).not.toThrow();
    expect(() => assertNonNull(0)).not.toThrow();
    expect(() => assertNonNull(false)).not.toThrow();
    expect(() => assertNonNull('')).not.toThrow();
  });

  it('throws for null', () => {
    expect(() => assertNonNull(null)).toThrow('Value is null or undefined');
  });

  it('throws for undefined', () => {
    expect(() => assertNonNull(undefined)).toThrow('Value is null or undefined');
  });

  it('uses custom message', () => {
    expect(() => assertNonNull(null, 'Custom error')).toThrow('Custom error');
  });
});

describe('assertIsString', () => {
  it('does not throw for strings', () => {
    expect(() => assertIsString('hello')).not.toThrow();
    expect(() => assertIsString('')).not.toThrow();
  });

  it('throws for non-strings', () => {
    expect(() => assertIsString(42)).toThrow('Expected string');
    expect(() => assertIsString(null)).toThrow();
    expect(() => assertIsString(undefined)).toThrow();
  });
});

describe('assertIsNumber', () => {
  it('does not throw for numbers', () => {
    expect(() => assertIsNumber(42)).not.toThrow();
    expect(() => assertIsNumber(0)).not.toThrow();
    expect(() => assertIsNumber(-1.5)).not.toThrow();
  });

  it('throws for NaN', () => {
    expect(() => assertIsNumber(NaN)).toThrow('Expected number');
  });

  it('throws for non-numbers', () => {
    expect(() => assertIsNumber('42')).toThrow();
    expect(() => assertIsNumber(null)).toThrow();
  });
});

describe('assertIsArray', () => {
  it('does not throw for arrays', () => {
    expect(() => assertIsArray([])).not.toThrow();
    expect(() => assertIsArray([1, 2, 3])).not.toThrow();
  });

  it('throws for non-arrays', () => {
    expect(() => assertIsArray('hello')).toThrow('Expected array');
    expect(() => assertIsArray({})).toThrow('Expected array');
    expect(() => assertIsArray(null)).toThrow();
  });

  it('validates array items with validator', () => {
    const isNum = (v: unknown): v is number => typeof v === 'number';

    expect(() => assertIsArray([1, 2, 3], isNum)).not.toThrow();
    expect(() => assertIsArray([1, 'two', 3], isNum)).toThrow('Invalid array item at index 1');
  });
});

// ── Safe property access ─────────────────────────────────

describe('safeAccess', () => {
  it('returns property value', () => {
    const obj = { name: 'test', value: 42 };
    expect(safeAccess(obj, 'name')).toBe('test');
    expect(safeAccess(obj, 'value')).toBe(42);
  });

  it('returns undefined for null/undefined objects', () => {
    expect(safeAccess(null, 'name' as any)).toBeUndefined();
    expect(safeAccess(undefined, 'name' as any)).toBeUndefined();
  });
});

describe('safeAccessNested', () => {
  it('accesses nested properties', () => {
    const obj = { a: { b: { c: 'deep' } } };
    expect(safeAccessNested(obj, ['a', 'b', 'c'])).toBe('deep');
  });

  it('returns undefined for missing paths', () => {
    const obj = { a: { b: 42 } };
    expect(safeAccessNested(obj, ['a', 'x', 'y'])).toBeUndefined();
  });

  it('handles null in chain', () => {
    expect(safeAccessNested(null, ['a'])).toBeUndefined();
    expect(safeAccessNested({ a: null }, ['a', 'b'])).toBeUndefined();
  });

  it('handles empty path', () => {
    const obj = { a: 1 };
    expect(safeAccessNested(obj, [])).toEqual(obj);
  });
});

// ── Error conversion utilities ───────────────────────────

describe('toAppError', () => {
  it('returns AppError as-is', () => {
    const error = { message: 'already an error', code: 'E001' };
    expect(toAppError(error)).toEqual(error);
  });

  it('converts Error instance', () => {
    const error = new TypeError('type problem');
    const result = toAppError(error);
    expect(result.message).toBe('type problem');
    // Error instances have { message: string } so isAppError() returns true,
    // meaning they are returned as-is (without adding code from error.name).
    // The code field is only set when !isAppError(error) && error instanceof Error.
    // Since TypeError has 'message' in it, isAppError returns true first.
  });

  it('converts string to AppError', () => {
    const result = toAppError('something broke');
    expect(result.message).toBe('something broke');
  });

  it('handles unknown values', () => {
    const result = toAppError(42);
    expect(result.message).toBe('An unknown error occurred');
    expect(result.details).toBe(42);
  });

  it('handles null', () => {
    const result = toAppError(null);
    expect(result.message).toBe('An unknown error occurred');
  });
});

describe('toValidationError', () => {
  it('creates ValidationError with field and value', () => {
    const result = toValidationError('Invalid email', 'email', 'bad@');
    expect(result.message).toBe('Invalid email');
    expect(result.field).toBe('email');
    expect(result.value).toBe('bad@');
  });
});

describe('toApiError', () => {
  it('creates ApiError with status and endpoint', () => {
    const result = toApiError('Not found', 404, '/api/users');
    expect(result.message).toBe('Not found');
    expect(result.status).toBe(404);
    expect(result.endpoint).toBe('/api/users');
  });
});

// ── Common type validators ───────────────────────────────

describe('isString', () => {
  it('identifies strings', () => {
    expect(isString('hello')).toBe(true);
    expect(isString('')).toBe(true);
    expect(isString(42)).toBe(false);
    expect(isString(null)).toBe(false);
  });
});

describe('isNumber', () => {
  it('identifies numbers', () => {
    expect(isNumber(42)).toBe(true);
    expect(isNumber(0)).toBe(true);
    expect(isNumber(-1.5)).toBe(true);
    expect(isNumber(NaN)).toBe(false);
    expect(isNumber('42')).toBe(false);
  });
});

describe('isBoolean', () => {
  it('identifies booleans', () => {
    expect(isBoolean(true)).toBe(true);
    expect(isBoolean(false)).toBe(true);
    expect(isBoolean(0)).toBe(false);
    expect(isBoolean('true')).toBe(false);
  });
});

describe('isObject', () => {
  it('identifies plain objects', () => {
    expect(isObject({})).toBe(true);
    expect(isObject({ key: 'value' })).toBe(true);
    expect(isObject(null)).toBe(false);
    expect(isObject([])).toBe(false);
    expect(isObject('string')).toBe(false);
  });
});

describe('isArray', () => {
  it('identifies arrays', () => {
    expect(isArray([])).toBe(true);
    expect(isArray([1, 2])).toBe(true);
    expect(isArray({})).toBe(false);
    expect(isArray('string')).toBe(false);
  });
});

describe('isNonEmptyString', () => {
  it('returns true for non-empty strings', () => {
    expect(isNonEmptyString('hello')).toBe(true);
    expect(isNonEmptyString('a')).toBe(true);
  });

  it('returns false for empty or whitespace strings', () => {
    expect(isNonEmptyString('')).toBe(false);
    expect(isNonEmptyString('   ')).toBe(false);
    expect(isNonEmptyString('\t\n')).toBe(false);
  });

  it('returns false for non-strings', () => {
    expect(isNonEmptyString(42)).toBe(false);
    expect(isNonEmptyString(null)).toBe(false);
  });
});

describe('isValidEmail', () => {
  it('validates correct emails', () => {
    expect(isValidEmail('test@example.com')).toBe(true);
    expect(isValidEmail('user.name@domain.co.uk')).toBe(true);
    expect(isValidEmail('user+tag@domain.com')).toBe(true);
  });

  it('rejects invalid emails', () => {
    expect(isValidEmail('notanemail')).toBe(false);
    expect(isValidEmail('@domain.com')).toBe(false);
    expect(isValidEmail('user@')).toBe(false);
    expect(isValidEmail('')).toBe(false);
    expect(isValidEmail(42)).toBe(false);
  });
});

describe('isValidUrl', () => {
  it('validates correct URLs', () => {
    expect(isValidUrl('https://example.com')).toBe(true);
    expect(isValidUrl('http://localhost:3000')).toBe(true);
    expect(isValidUrl('ftp://files.example.com/data.txt')).toBe(true);
  });

  it('rejects invalid URLs', () => {
    expect(isValidUrl('not a url')).toBe(false);
    expect(isValidUrl('')).toBe(false);
    expect(isValidUrl(42)).toBe(false);
  });
});

// ── Result type ──────────────────────────────────────────

describe('Result type utilities', () => {
  describe('success', () => {
    it('creates a success result', () => {
      const result = success(42);
      expect(result.success).toBe(true);
      expect((result as any).data).toBe(42);
    });
  });

  describe('failure', () => {
    it('creates a failure result', () => {
      const result = failure({ message: 'Error' });
      expect(result.success).toBe(false);
      expect((result as any).error).toEqual({ message: 'Error' });
    });
  });

  describe('isSuccess', () => {
    it('identifies success results', () => {
      expect(isSuccess(success('data'))).toBe(true);
      expect(isSuccess(failure({ message: 'err' }))).toBe(false);
    });
  });

  describe('isFailure', () => {
    it('identifies failure results', () => {
      expect(isFailure(failure({ message: 'err' }))).toBe(true);
      expect(isFailure(success('data'))).toBe(false);
    });
  });
});
