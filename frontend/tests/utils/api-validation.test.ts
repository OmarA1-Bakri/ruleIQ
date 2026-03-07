import { describe, it, expect } from 'vitest';
import { z } from 'zod';
import {
  ValidationError,
  validateApiResponse,
  safeValidateApiResponse,
  formatValidationError,
  validateBatch,
  createValidationMiddleware,
  validateRequest,
} from '@/lib/api/validation';

// Simple schemas for testing
const UserSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email(),
});

const StringSchema = z.string();
const NumberSchema = z.number();

// ============================================================================
// ValidationError
// ============================================================================

describe('ValidationError', () => {
  function makeZodError(): z.ZodError {
    const result = UserSchema.safeParse({ id: 'not-a-number' });
    if (!result.success) return result.error;
    throw new Error('Expected safeParse to fail');
  }

  it('is an instance of Error', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('Validation failed', zodErr);
    expect(err).toBeInstanceOf(Error);
  });

  it('has name "ValidationError"', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('msg', zodErr);
    expect(err.name).toBe('ValidationError');
  });

  it('stores message', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('Custom message', zodErr);
    expect(err.message).toBe('Custom message');
  });

  it('stores errors (ZodError reference)', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('msg', zodErr);
    expect(err.errors).toBe(zodErr);
  });

  it('stores optional data', () => {
    const zodErr = makeZodError();
    const data = { id: 'bad', name: 'test' };
    const err = new ValidationError('msg', zodErr, data);
    expect(err.data).toEqual(data);
  });

  it('data is undefined when not provided', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('msg', zodErr);
    expect(err.data).toBeUndefined();
  });

  it('toJSON returns object with name, message, errors, data', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('msg', zodErr, { raw: true });
    const json = err.toJSON();
    expect(json).toHaveProperty('name', 'ValidationError');
    expect(json).toHaveProperty('message', 'msg');
    expect(json).toHaveProperty('errors');
    expect(json).toHaveProperty('data');
  });

  it('toJSON errors is an array of ZodIssues', () => {
    const zodErr = makeZodError();
    const err = new ValidationError('msg', zodErr);
    const json = err.toJSON();
    expect(Array.isArray(json.errors)).toBe(true);
    expect(json.errors.length).toBeGreaterThan(0);
  });

  it('can be thrown and caught', () => {
    const zodErr = makeZodError();
    expect(() => {
      throw new ValidationError('fail', zodErr);
    }).toThrow(ValidationError);
  });
});

// ============================================================================
// formatValidationError
// ============================================================================

describe('formatValidationError', () => {
  it('returns a string starting with "Validation failed:"', () => {
    const result = UserSchema.safeParse({});
    if (!result.success) {
      const msg = formatValidationError(result.error);
      expect(msg).toMatch(/^Validation failed:/);
    }
  });

  it('includes field paths in the message', () => {
    const result = UserSchema.safeParse({ id: 'bad', name: 123, email: 'not-email' });
    if (!result.success) {
      const msg = formatValidationError(result.error);
      expect(msg).toContain('id');
    }
  });

  it('handles top-level (no path) errors', () => {
    const result = StringSchema.safeParse(42);
    if (!result.success) {
      const msg = formatValidationError(result.error);
      expect(typeof msg).toBe('string');
      expect(msg.length).toBeGreaterThan(0);
    }
  });
});

// ============================================================================
// validateApiResponse
// ============================================================================

describe('validateApiResponse', () => {
  it('returns parsed data when valid', () => {
    const data = { id: 1, name: 'Alice', email: 'alice@example.com' };
    const result = validateApiResponse(data, UserSchema);
    expect(result).toEqual(data);
  });

  it('throws ValidationError when invalid', () => {
    expect(() => {
      validateApiResponse({ id: 'bad' }, UserSchema);
    }).toThrow(ValidationError);
  });

  it('thrown ValidationError contains ZodError', () => {
    try {
      validateApiResponse({ id: 'bad' }, UserSchema);
    } catch (err) {
      expect(err).toBeInstanceOf(ValidationError);
      expect((err as ValidationError).errors).toBeInstanceOf(z.ZodError);
    }
  });

  it('works with primitive schemas', () => {
    expect(validateApiResponse('hello', StringSchema)).toBe('hello');
    expect(validateApiResponse(42, NumberSchema)).toBe(42);
  });

  it('throws for wrong primitive type', () => {
    expect(() => validateApiResponse(42, StringSchema)).toThrow(ValidationError);
  });
});

// ============================================================================
// safeValidateApiResponse
// ============================================================================

describe('safeValidateApiResponse', () => {
  it('returns { success: true, data } for valid input', () => {
    const data = { id: 1, name: 'Alice', email: 'alice@example.com' };
    const result = safeValidateApiResponse(data, UserSchema);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual(data);
    }
  });

  it('returns { success: false, error } for invalid input', () => {
    const result = safeValidateApiResponse({ id: 'bad' }, UserSchema);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBeInstanceOf(ValidationError);
    }
  });

  it('does not throw for invalid input', () => {
    expect(() => {
      safeValidateApiResponse({ id: 'bad' }, UserSchema);
    }).not.toThrow();
  });

  it('error contains the invalid data reference', () => {
    const badData = { id: 'not-a-number' };
    const result = safeValidateApiResponse(badData, UserSchema);
    if (!result.success) {
      expect(result.error.data).toEqual(badData);
    }
  });

  it('works with string schema', () => {
    const result = safeValidateApiResponse('hello', StringSchema);
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// validateBatch
// ============================================================================

describe('validateBatch', () => {
  const items = [
    { id: 1, name: 'Alice', email: 'alice@example.com' },
    { id: 'bad', name: 'Bob' },
    { id: 2, name: 'Carol', email: 'carol@example.com' },
  ];

  it('separates valid and invalid items', () => {
    const result = validateBatch(items, UserSchema);
    expect(result.valid.length).toBe(2);
    expect(result.invalid.length).toBe(1);
  });

  it('returns correct indices for invalid items', () => {
    const result = validateBatch(items, UserSchema);
    expect(result.invalid[0]!.index).toBe(1);
  });

  it('invalid items contain ValidationError', () => {
    const result = validateBatch(items, UserSchema);
    expect(result.invalid[0]!.error).toBeInstanceOf(ValidationError);
  });

  it('returns empty valid/invalid arrays for empty input', () => {
    const result = validateBatch([], UserSchema);
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(0);
  });

  it('all valid when all items pass', () => {
    const validItems = [
      { id: 1, name: 'Alice', email: 'a@a.com' },
      { id: 2, name: 'Bob', email: 'b@b.com' },
    ];
    const result = validateBatch(validItems, UserSchema);
    expect(result.valid.length).toBe(2);
    expect(result.invalid.length).toBe(0);
  });

  it('all invalid when all items fail', () => {
    const badItems = [{ id: 'x' }, { id: 'y' }];
    const result = validateBatch(badItems, UserSchema);
    expect(result.valid.length).toBe(0);
    expect(result.invalid.length).toBe(2);
  });
});

// ============================================================================
// createValidationMiddleware
// ============================================================================

describe('createValidationMiddleware', () => {
  it('returns a function', () => {
    const middleware = createValidationMiddleware(UserSchema);
    expect(typeof middleware).toBe('function');
  });

  it('validates and returns data when valid', async () => {
    const middleware = createValidationMiddleware(UserSchema);
    const data = { id: 1, name: 'Alice', email: 'alice@example.com' };
    const result = await middleware(data);
    expect(result).toEqual(data);
  });

  it('throws ValidationError when data is invalid', async () => {
    const middleware = createValidationMiddleware(UserSchema);
    await expect(middleware({ id: 'bad' })).rejects.toBeInstanceOf(ValidationError);
  });
});

// ============================================================================
// validateRequest
// ============================================================================

describe('validateRequest', () => {
  it('returns validated data for valid input', () => {
    const data = { id: 1, name: 'Alice', email: 'alice@example.com' };
    const result = validateRequest(data, UserSchema);
    expect(result).toEqual(data);
  });

  it('throws ValidationError for invalid input', () => {
    expect(() => {
      validateRequest({ id: 'bad' }, UserSchema);
    }).toThrow(ValidationError);
  });

  it('error message starts with "Invalid request data:"', () => {
    try {
      validateRequest({ id: 'bad' }, UserSchema);
    } catch (err) {
      expect((err as ValidationError).message).toMatch(/^Invalid request data:/);
    }
  });
});
