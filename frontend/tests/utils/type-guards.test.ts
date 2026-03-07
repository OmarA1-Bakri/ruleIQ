import { describe, it, expect } from 'vitest';
import {
  isAssessmentData,
  isAIAnalysisResponse,
  isApiResponse,
  isSuccessResponse,
  isErrorResponse,
  hasProperty,
  isNonNullable,
  isString,
  isNumber,
  isBoolean,
  isArray,
  isObject,
  isDate,
  isUUID,
  isEmail,
  isURL,
  isArrayOf,
  isStringArray,
  isNumberArray,
  hasShape,
  hasOptionalProperty,
  isEnum,
} from '@/lib/utils/type-guards';

describe('Assessment guards', () => {
  it('isAssessmentData detects assessment objects', () => {
    expect(isAssessmentData({ responses: {}, completion_status: 'done' })).toBe(true);
    expect(isAssessmentData({ answers: [], progress_percentage: 50 })).toBe(true);
    expect(isAssessmentData({ something: 'else' })).toBe(false);
    expect(isAssessmentData(null)).toBe(false);
    expect(isAssessmentData('string')).toBe(false);
  });
});

describe('AI response guards', () => {
  it('isAIAnalysisResponse detects AI analysis', () => {
    expect(isAIAnalysisResponse({ analysis: 'result' })).toBe(true);
    expect(isAIAnalysisResponse({ results: [], confidence: 0.9 })).toBe(true);
    expect(isAIAnalysisResponse({ something: 'else' })).toBe(false);
    expect(isAIAnalysisResponse(null)).toBe(false);
    expect(isAIAnalysisResponse('string')).toBe(false);
  });
});

describe('API response guards', () => {
  it('isApiResponse detects API response objects', () => {
    expect(isApiResponse({ success: true, data: {} })).toBe(true);
    expect(isApiResponse({ success: false, error: 'msg' })).toBe(true);
    expect(isApiResponse({ other: true })).toBe(false);
    expect(isApiResponse(null)).toBe(false);
  });

  it('isSuccessResponse identifies successful responses', () => {
    expect(isSuccessResponse({ success: true, data: { id: 1 } })).toBe(true);
    expect(isSuccessResponse({ success: true })).toBe(false); // No data
    expect(isSuccessResponse({ success: false, error: 'err' })).toBe(false);
  });

  it('isErrorResponse identifies error responses', () => {
    expect(isErrorResponse({ success: false, error: 'Something went wrong' })).toBe(true);
    expect(isErrorResponse({ success: false })).toBe(false); // No error field
    expect(isErrorResponse({ success: true, data: {} })).toBe(false);
  });
});

describe('Utility type guards', () => {
  describe('hasProperty', () => {
    it('checks for property existence', () => {
      expect(hasProperty({ name: 'test' }, 'name')).toBe(true);
      expect(hasProperty({ name: 'test' }, 'age')).toBe(false);
      expect(hasProperty(null, 'key')).toBe(false);
    });
  });

  describe('isNonNullable', () => {
    it('returns true for defined values', () => {
      expect(isNonNullable('hello')).toBe(true);
      expect(isNonNullable(0)).toBe(true);
      expect(isNonNullable(false)).toBe(true);
      expect(isNonNullable([])).toBe(true);
    });

    it('returns false for null and undefined', () => {
      expect(isNonNullable(null)).toBe(false);
      expect(isNonNullable(undefined)).toBe(false);
    });
  });

  describe('primitive type guards', () => {
    it('isString', () => {
      expect(isString('hello')).toBe(true);
      expect(isString(42)).toBe(false);
    });

    it('isNumber', () => {
      expect(isNumber(42)).toBe(true);
      expect(isNumber(0)).toBe(true);
      expect(isNumber(NaN)).toBe(false);
      expect(isNumber('42')).toBe(false);
    });

    it('isBoolean', () => {
      expect(isBoolean(true)).toBe(true);
      expect(isBoolean(1)).toBe(false);
    });

    it('isArray', () => {
      expect(isArray([1, 2])).toBe(true);
      expect(isArray({})).toBe(false);
    });

    it('isObject', () => {
      expect(isObject({ key: 'val' })).toBe(true);
      expect(isObject(null)).toBe(false);
      expect(isObject([1])).toBe(false);
    });
  });

  describe('isDate', () => {
    it('returns true for valid Date', () => {
      expect(isDate(new Date())).toBe(true);
    });

    it('returns false for invalid Date', () => {
      expect(isDate(new Date('invalid'))).toBe(false);
    });

    it('returns false for non-Date', () => {
      expect(isDate('2025-01-01')).toBe(false);
      expect(isDate(Date.now())).toBe(false);
    });
  });

  describe('isUUID', () => {
    it('returns true for valid UUIDs', () => {
      expect(isUUID('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
      expect(isUUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')).toBe(true);
    });

    it('returns false for invalid UUIDs', () => {
      expect(isUUID('not-a-uuid')).toBe(false);
      expect(isUUID('550e8400-e29b-41d4-a716')).toBe(false);
      expect(isUUID(123)).toBe(false);
    });
  });

  describe('isEmail', () => {
    it('validates email addresses', () => {
      expect(isEmail('user@example.com')).toBe(true);
      expect(isEmail('test@domain.co.uk')).toBe(true);
      expect(isEmail('invalid')).toBe(false);
      expect(isEmail('@domain.com')).toBe(false);
      expect(isEmail(42)).toBe(false);
    });
  });

  describe('isURL', () => {
    it('validates URLs', () => {
      expect(isURL('https://example.com')).toBe(true);
      expect(isURL('http://localhost:3000/path')).toBe(true);
      expect(isURL('not a url')).toBe(false);
      expect(isURL(42)).toBe(false);
    });
  });
});

describe('Array type guards', () => {
  describe('isArrayOf', () => {
    it('validates typed arrays', () => {
      expect(isArrayOf(['a', 'b'], isString)).toBe(true);
      expect(isArrayOf([1, 'a'], isString)).toBe(false);
      expect(isArrayOf('string', isString)).toBe(false);
    });

    it('handles empty arrays', () => {
      expect(isArrayOf([], isString)).toBe(true);
    });
  });

  describe('isStringArray', () => {
    it('validates string arrays', () => {
      expect(isStringArray(['a', 'b', 'c'])).toBe(true);
      expect(isStringArray([1, 2, 3])).toBe(false);
      expect(isStringArray(['a', 1])).toBe(false);
      expect(isStringArray([])).toBe(true);
    });
  });

  describe('isNumberArray', () => {
    it('validates number arrays', () => {
      expect(isNumberArray([1, 2, 3])).toBe(true);
      expect(isNumberArray(['a', 'b'])).toBe(false);
      expect(isNumberArray([1, NaN])).toBe(false);
      expect(isNumberArray([])).toBe(true);
    });
  });
});

describe('Shape validation', () => {
  describe('hasShape', () => {
    it('validates object shape', () => {
      const shape = {
        name: (v: unknown) => typeof v === 'string',
        age: (v: unknown) => typeof v === 'number',
      };

      expect(hasShape({ name: 'John', age: 30 }, shape)).toBe(true);
      expect(hasShape({ name: 'John' }, shape)).toBe(false); // Missing age
      expect(hasShape({ name: 123, age: 30 }, shape)).toBe(false); // Wrong type
      expect(hasShape(null, shape)).toBe(false);
    });
  });

  describe('hasOptionalProperty', () => {
    it('allows missing optional property', () => {
      expect(hasOptionalProperty({}, 'name')).toBe(true);
    });

    it('validates existing optional property', () => {
      expect(hasOptionalProperty({ name: 'test' }, 'name', isString)).toBe(true);
      expect(hasOptionalProperty({ name: 42 }, 'name', isString)).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(hasOptionalProperty('string', 'prop')).toBe(false);
    });
  });
});

describe('Enum guard', () => {
  it('validates enum values', () => {
    const statuses = ['active', 'inactive', 'pending'] as const;

    expect(isEnum('active', statuses)).toBe(true);
    expect(isEnum('inactive', statuses)).toBe(true);
    expect(isEnum('unknown', statuses)).toBe(false);
    expect(isEnum(42, statuses)).toBe(false);
  });
});
