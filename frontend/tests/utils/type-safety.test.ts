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

describe('Type guards', () => {
  describe('isAppError', () => {
    it('returns true for valid AppError', () => {
      expect(isAppError({ message: 'test error' })).toBe(true);
    });

    it('returns false for null', () => {
      expect(isAppError(null)).toBe(false);
    });

    it('returns false for string', () => {
      expect(isAppError('error')).toBe(false);
    });

    it('returns false for object without message', () => {
      expect(isAppError({ code: 'ERR' })).toBe(false);
    });

    it('returns false for object with non-string message', () => {
      expect(isAppError({ message: 123 })).toBe(false);
    });
  });

  describe('isValidationError', () => {
    it('returns true for valid ValidationError', () => {
      expect(isValidationError({ message: 'test', field: 'email' })).toBe(true);
    });

    it('returns false for plain AppError without field', () => {
      expect(isValidationError({ message: 'test' })).toBe(false);
    });
  });

  describe('isApiError', () => {
    it('returns true for valid ApiError', () => {
      expect(isApiError({ message: 'test', status: 404 })).toBe(true);
    });

    it('returns false for plain AppError without status', () => {
      expect(isApiError({ message: 'test' })).toBe(false);
    });
  });
});

describe('safeJsonParse', () => {
  it('parses valid JSON', () => {
    expect(safeJsonParse('{"key":"value"}')).toEqual({ key: 'value' });
  });

  it('returns null for invalid JSON without fallback', () => {
    expect(safeJsonParse('not json')).toBeNull();
  });

  it('returns fallback for invalid JSON', () => {
    expect(safeJsonParse('not json', { default: true })).toEqual({ default: true });
  });

  it('parses JSON arrays', () => {
    expect(safeJsonParse('[1,2,3]')).toEqual([1, 2, 3]);
  });

  it('parses JSON primitives', () => {
    expect(safeJsonParse('"hello"')).toBe('hello');
    expect(safeJsonParse('42')).toBe(42);
    expect(safeJsonParse('true')).toBe(true);
    expect(safeJsonParse('null')).toBeNull();
  });
});

describe('safeJsonParseWithValidation', () => {
  const isStringArray = (value: unknown): value is string[] => {
    return Array.isArray(value) && value.every((v) => typeof v === 'string');
  };

  it('returns parsed data when valid', () => {
    expect(safeJsonParseWithValidation('["a","b"]', isStringArray)).toEqual(['a', 'b']);
  });

  it('returns null when parsed data fails validation', () => {
    expect(safeJsonParseWithValidation('[1,2,3]', isStringArray)).toBeNull();
  });

  it('returns fallback when validation fails', () => {
    expect(safeJsonParseWithValidation('[1,2]', isStringArray, ['default'])).toEqual(['default']);
  });

  it('returns null for invalid JSON', () => {
    expect(safeJsonParseWithValidation('bad json', isStringArray)).toBeNull();
  });
});

describe('safeGetFromStorage / safeSetToStorage', () => {
  it('gets item from storage', () => {
    localStorage.setItem('test-key', JSON.stringify({ data: true }));
    expect(safeGetFromStorage('test-key')).toEqual({ data: true });
  });

  it('returns null for missing key', () => {
    expect(safeGetFromStorage('nonexistent')).toBeNull();
  });

  it('returns null when validator fails', () => {
    localStorage.setItem('test-key2', JSON.stringify(42));
    const validator = (v: unknown): v is string => typeof v === 'string';
    expect(safeGetFromStorage('test-key2', validator)).toBeNull();
  });

  it('sets item to storage and returns true', () => {
    expect(safeSetToStorage('set-test', { value: 123 })).toBe(true);
    expect(JSON.parse(localStorage.getItem('set-test')!)).toEqual({ value: 123 });
  });
});

describe('Assert functions', () => {
  describe('assertNonNull', () => {
    it('does not throw for non-null value', () => {
      expect(() => assertNonNull('value')).not.toThrow();
      expect(() => assertNonNull(0)).not.toThrow();
      expect(() => assertNonNull(false)).not.toThrow();
    });

    it('throws for null', () => {
      expect(() => assertNonNull(null)).toThrow();
    });

    it('throws for undefined', () => {
      expect(() => assertNonNull(undefined)).toThrow();
    });

    it('uses custom message', () => {
      expect(() => assertNonNull(null, 'Custom error')).toThrow('Custom error');
    });
  });

  describe('assertIsString', () => {
    it('does not throw for string', () => {
      expect(() => assertIsString('hello')).not.toThrow();
    });

    it('throws for non-string', () => {
      expect(() => assertIsString(42)).toThrow('Expected string but got number');
    });
  });

  describe('assertIsNumber', () => {
    it('does not throw for number', () => {
      expect(() => assertIsNumber(42)).not.toThrow();
    });

    it('throws for NaN', () => {
      expect(() => assertIsNumber(NaN)).toThrow();
    });

    it('throws for string', () => {
      expect(() => assertIsNumber('42')).toThrow();
    });
  });

  describe('assertIsArray', () => {
    it('does not throw for array', () => {
      expect(() => assertIsArray([1, 2, 3])).not.toThrow();
    });

    it('throws for non-array', () => {
      expect(() => assertIsArray('not array')).toThrow('Expected array');
    });

    it('validates items with validator', () => {
      const isNum = (v: unknown): v is number => typeof v === 'number';
      expect(() => assertIsArray([1, 2, 3], isNum)).not.toThrow();
      expect(() => assertIsArray([1, 'a', 3], isNum)).toThrow('Invalid array item at index 1');
    });
  });
});

describe('Safe access', () => {
  describe('safeAccess', () => {
    it('accesses existing property', () => {
      expect(safeAccess({ name: 'test' }, 'name')).toBe('test');
    });

    it('returns undefined for null object', () => {
      expect(safeAccess(null, 'name' as never)).toBeUndefined();
    });

    it('returns undefined for undefined object', () => {
      expect(safeAccess(undefined, 'name' as never)).toBeUndefined();
    });
  });

  describe('safeAccessNested', () => {
    it('accesses deeply nested property', () => {
      const obj = { a: { b: { c: 42 } } };
      expect(safeAccessNested(obj, ['a', 'b', 'c'])).toBe(42);
    });

    it('returns undefined for missing path', () => {
      const obj = { a: { b: 1 } };
      expect(safeAccessNested(obj, ['a', 'c', 'd'])).toBeUndefined();
    });

    it('returns undefined for null in path', () => {
      expect(safeAccessNested(null, ['a'])).toBeUndefined();
    });

    it('returns the object for empty path', () => {
      const obj = { key: 'value' };
      expect(safeAccessNested(obj, [])).toEqual(obj);
    });
  });
});

describe('Error conversion', () => {
  describe('toAppError', () => {
    it('returns AppError as-is', () => {
      const error = { message: 'test', code: 'ERR' };
      expect(toAppError(error)).toEqual(error);
    });

    it('converts Error instance', () => {
      const error = new Error('test error');
      const result = toAppError(error);
      expect(result.message).toBe('test error');
      // Error objects already match isAppError (have .message), so returned as-is
      // The code property is not set on a plain Error instance
    });

    it('converts string to AppError', () => {
      const result = toAppError('string error');
      expect(result.message).toBe('string error');
    });

    it('handles unknown types', () => {
      const result = toAppError(42);
      expect(result.message).toBe('An unknown error occurred');
      expect(result.details).toBe(42);
    });
  });

  describe('toValidationError', () => {
    it('converts error with field and value', () => {
      const result = toValidationError('bad value', 'email', 'invalid@');
      expect(result.message).toBe('bad value');
      expect(result.field).toBe('email');
      expect(result.value).toBe('invalid@');
    });
  });

  describe('toApiError', () => {
    it('converts error with status and endpoint', () => {
      const result = toApiError('Not found', 404, '/api/v1/users');
      expect(result.message).toBe('Not found');
      expect(result.status).toBe(404);
      expect(result.endpoint).toBe('/api/v1/users');
    });
  });
});

describe('Type validators', () => {
  it('isString', () => {
    expect(isString('hello')).toBe(true);
    expect(isString(42)).toBe(false);
    expect(isString(null)).toBe(false);
  });

  it('isNumber', () => {
    expect(isNumber(42)).toBe(true);
    expect(isNumber(NaN)).toBe(false);
    expect(isNumber('42')).toBe(false);
  });

  it('isBoolean', () => {
    expect(isBoolean(true)).toBe(true);
    expect(isBoolean(false)).toBe(true);
    expect(isBoolean(0)).toBe(false);
  });

  it('isObject', () => {
    expect(isObject({})).toBe(true);
    expect(isObject({ key: 'value' })).toBe(true);
    expect(isObject(null)).toBe(false);
    expect(isObject([])).toBe(false);
    expect(isObject('string')).toBe(false);
  });

  it('isArray', () => {
    expect(isArray([])).toBe(true);
    expect(isArray([1, 2])).toBe(true);
    expect(isArray({})).toBe(false);
    expect(isArray('arr')).toBe(false);
  });

  it('isNonEmptyString', () => {
    expect(isNonEmptyString('hello')).toBe(true);
    expect(isNonEmptyString('')).toBe(false);
    expect(isNonEmptyString('   ')).toBe(false);
    expect(isNonEmptyString(42)).toBe(false);
  });

  it('isValidEmail', () => {
    expect(isValidEmail('user@example.com')).toBe(true);
    expect(isValidEmail('invalid')).toBe(false);
    expect(isValidEmail('')).toBe(false);
    expect(isValidEmail(42)).toBe(false);
  });

  it('isValidUrl', () => {
    expect(isValidUrl('https://example.com')).toBe(true);
    expect(isValidUrl('http://localhost:3000')).toBe(true);
    expect(isValidUrl('not a url')).toBe(false);
    expect(isValidUrl(42)).toBe(false);
  });
});

describe('Result type', () => {
  it('success creates success result', () => {
    const result = success(42);
    expect(result.success).toBe(true);
    expect((result as any).data).toBe(42);
  });

  it('failure creates failure result', () => {
    const error = { message: 'error' };
    const result = failure(error);
    expect(result.success).toBe(false);
    expect((result as any).error).toEqual(error);
  });

  it('isSuccess correctly identifies success', () => {
    expect(isSuccess(success('data'))).toBe(true);
    expect(isSuccess(failure({ message: 'err' }))).toBe(false);
  });

  it('isFailure correctly identifies failure', () => {
    expect(isFailure(failure({ message: 'err' }))).toBe(true);
    expect(isFailure(success('data'))).toBe(false);
  });
});
