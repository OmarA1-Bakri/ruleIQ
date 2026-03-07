import { describe, it, expect, vi } from 'vitest';
import { z, ZodError } from 'zod';
import {
  ValidationError,
  validateApiResponse,
  safeValidateApiResponse,
  formatValidationError,
  validateRequest,
  validateBatch,
} from '@/lib/api/validation';

// Mock the apiClient to prevent actual HTTP requests
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// Mock ApiResponseSchema since it's imported from validation/zod-schemas
vi.mock('@/lib/validation/zod-schemas', () => ({
  ApiResponseSchema: (dataSchema: any) =>
    z.object({
      success: z.boolean(),
      data: dataSchema.optional(),
      error: z.string().optional(),
      message: z.string().optional(),
    }),
}));

// ── ValidationError ──────────────────────────────────────

describe('ValidationError', () => {
  it('creates error with correct properties', () => {
    const zodError = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['name'],
        message: 'Expected string, received number',
      },
    ]);

    const error = new ValidationError('Validation failed', zodError, { name: 42 });

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe('ValidationError');
    expect(error.message).toBe('Validation failed');
    expect(error.errors).toBe(zodError);
    expect(error.data).toEqual({ name: 42 });
  });

  it('toJSON returns structured data', () => {
    const zodError = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['email'],
        message: 'Expected string, received number',
      },
    ]);

    const error = new ValidationError('Validation failed', zodError, { email: 123 });
    const json = error.toJSON();

    expect(json.name).toBe('ValidationError');
    expect(json.message).toBe('Validation failed');
    expect(json.errors).toHaveLength(1);
    expect(json.data).toEqual({ email: 123 });
  });

  it('allows undefined data', () => {
    const zodError = new ZodError([]);
    const error = new ValidationError('Empty', zodError);

    expect(error.data).toBeUndefined();
  });
});

// ── validateApiResponse ──────────────────────────────────

describe('validateApiResponse', () => {
  const UserSchema = z.object({
    id: z.string(),
    name: z.string(),
    email: z.string().email(),
  });

  it('returns validated data for valid input', () => {
    const data = { id: '1', name: 'John', email: 'john@example.com' };
    const result = validateApiResponse(data, UserSchema);

    expect(result).toEqual(data);
  });

  it('strips extra fields (by default with Zod strict mode off)', () => {
    const data = { id: '1', name: 'John', email: 'john@example.com', extra: 'field' };
    const result = validateApiResponse(data, UserSchema);

    expect(result.id).toBe('1');
    expect(result.name).toBe('John');
  });

  it('throws ValidationError for invalid data', () => {
    const data = { id: 123, name: '', email: 'not-an-email' };

    expect(() => validateApiResponse(data, UserSchema)).toThrow(ValidationError);
  });

  it('thrown error contains formatted message', () => {
    const data = { id: 123 };

    try {
      validateApiResponse(data, UserSchema);
      expect.fail('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ValidationError);
      expect((error as ValidationError).message).toContain('Validation failed');
    }
  });

  it('thrown error contains original data', () => {
    const data = { wrong: 'shape' };

    try {
      validateApiResponse(data, UserSchema);
      expect.fail('Should have thrown');
    } catch (error) {
      expect((error as ValidationError).data).toEqual(data);
    }
  });
});

// ── safeValidateApiResponse ──────────────────────────────

describe('safeValidateApiResponse', () => {
  const NumberSchema = z.number().min(0).max(100);

  it('returns success for valid data', () => {
    const result = safeValidateApiResponse(42, NumberSchema);

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toBe(42);
    }
  });

  it('returns failure for invalid data', () => {
    const result = safeValidateApiResponse(-1, NumberSchema);

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBeInstanceOf(ValidationError);
    }
  });

  it('returns failure for wrong type', () => {
    const result = safeValidateApiResponse('not a number', NumberSchema);

    expect(result.success).toBe(false);
  });

  it('handles edge case values', () => {
    expect(safeValidateApiResponse(0, NumberSchema).success).toBe(true);
    expect(safeValidateApiResponse(100, NumberSchema).success).toBe(true);
    expect(safeValidateApiResponse(101, NumberSchema).success).toBe(false);
  });
});

// ── formatValidationError ────────────────────────────────

describe('formatValidationError', () => {
  it('formats single error with path', () => {
    const error = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['name'],
        message: 'Expected string, received number',
      },
    ]);

    const result = formatValidationError(error);
    expect(result).toContain('name');
    expect(result).toContain('Expected string');
  });

  it('formats multiple errors', () => {
    const error = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['name'],
        message: 'Expected string',
      },
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'undefined',
        path: ['email'],
        message: 'Required',
      },
    ]);

    const result = formatValidationError(error);
    expect(result).toContain('name');
    expect(result).toContain('email');
    expect(result).toContain('Validation failed');
  });

  it('formats error without path', () => {
    const error = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: [],
        message: 'Expected string',
      },
    ]);

    const result = formatValidationError(error);
    expect(result).toContain('Expected string');
  });

  it('formats nested path', () => {
    const error = new ZodError([
      {
        code: 'invalid_type',
        expected: 'number',
        received: 'string',
        path: ['address', 'zip'],
        message: 'Expected number',
      },
    ]);

    const result = formatValidationError(error);
    expect(result).toContain('address.zip');
  });
});

// ── validateRequest ──────────────────────────────────────

describe('validateRequest', () => {
  const RequestSchema = z.object({
    title: z.string().min(1),
    priority: z.enum(['low', 'medium', 'high']),
  });

  it('returns validated data for valid request', () => {
    const data = { title: 'Task 1', priority: 'high' };
    const result = validateRequest(data, RequestSchema);

    expect(result).toEqual(data);
  });

  it('throws ValidationError for invalid request', () => {
    const data = { title: '', priority: 'extreme' };

    expect(() => validateRequest(data, RequestSchema)).toThrow(ValidationError);
  });

  it('thrown error message includes "Invalid request data"', () => {
    try {
      validateRequest({}, RequestSchema);
      expect.fail('Should have thrown');
    } catch (error) {
      expect((error as ValidationError).message).toContain('Invalid request data');
    }
  });
});

// ── validateBatch ────────────────────────────────────────

describe('validateBatch', () => {
  const ItemSchema = z.object({
    id: z.string(),
    value: z.number(),
  });

  it('separates valid and invalid items', () => {
    const items = [
      { id: '1', value: 10 },
      { id: '2', value: 'not a number' },
      { id: '3', value: 30 },
      { value: 40 },
    ];

    const result = validateBatch(items, ItemSchema);

    expect(result.valid).toHaveLength(2);
    expect(result.valid[0].id).toBe('1');
    expect(result.valid[1].id).toBe('3');

    expect(result.invalid).toHaveLength(2);
    expect(result.invalid[0].index).toBe(1);
    expect(result.invalid[1].index).toBe(3);
  });

  it('returns all valid when all items pass', () => {
    const items = [
      { id: '1', value: 10 },
      { id: '2', value: 20 },
    ];

    const result = validateBatch(items, ItemSchema);

    expect(result.valid).toHaveLength(2);
    expect(result.invalid).toHaveLength(0);
  });

  it('returns all invalid when all items fail', () => {
    const items = [
      { id: 123, value: 'bad' },
      { wrong: 'shape' },
    ];

    const result = validateBatch(items, ItemSchema);

    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(2);
  });

  it('handles empty array', () => {
    const result = validateBatch([], ItemSchema);

    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([]);
  });

  it('invalid items contain ValidationError', () => {
    const items = [{ broken: true }];
    const result = validateBatch(items, ItemSchema);

    expect(result.invalid[0].error).toBeInstanceOf(ValidationError);
    expect(result.invalid[0].index).toBe(0);
  });
});
