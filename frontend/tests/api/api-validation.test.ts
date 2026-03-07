import { describe, it, expect, vi, beforeEach } from 'vitest';
import { z, ZodError } from 'zod';
import {
  ValidationError,
  validateApiResponse,
  safeValidateApiResponse,
  formatValidationError,
  validateRequest,
  validateBatch,
  ValidatedAPIClient,
  createValidationMiddleware,
  logValidationWarning,
  reportValidationError,
} from '@/lib/api/validation';

describe('ValidationError', () => {
  it('creates instance with message, errors, and data', () => {
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

    expect(error.message).toBe('Validation failed');
    expect(error.name).toBe('ValidationError');
    expect(error.errors).toBe(zodError);
    expect(error.data).toEqual({ name: 42 });
    expect(error).toBeInstanceOf(Error);
  });

  it('toJSON serializes correctly', () => {
    const zodError = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['email'],
        message: 'Expected string',
      },
    ]);

    const error = new ValidationError('Test error', zodError, { email: 123 });
    const json = error.toJSON();

    expect(json.name).toBe('ValidationError');
    expect(json.message).toBe('Test error');
    expect(json.errors).toEqual(zodError.errors);
    expect(json.data).toEqual({ email: 123 });
  });
});

describe('validateApiResponse', () => {
  const schema = z.object({
    id: z.number(),
    name: z.string(),
  });

  it('returns parsed data for valid input', () => {
    const result = validateApiResponse({ id: 1, name: 'Test' }, schema);
    expect(result).toEqual({ id: 1, name: 'Test' });
  });

  it('strips extra fields with strict-less schemas', () => {
    const result = validateApiResponse({ id: 1, name: 'Test', extra: 'field' }, schema);
    expect(result).toEqual({ id: 1, name: 'Test' });
  });

  it('throws ValidationError for invalid input', () => {
    expect(() => validateApiResponse({ id: 'not-a-number', name: 'Test' }, schema)).toThrow(
      ValidationError,
    );
  });

  it('throws ValidationError with formatted message', () => {
    try {
      validateApiResponse({ id: 'bad' }, schema);
    } catch (error) {
      expect(error).toBeInstanceOf(ValidationError);
      expect((error as ValidationError).message).toContain('Validation failed');
    }
  });

  it('re-throws non-ZodError errors', () => {
    const badSchema = {
      parse: () => {
        throw new Error('Not a ZodError');
      },
    } as any;

    expect(() => validateApiResponse({}, badSchema)).toThrow('Not a ZodError');
  });
});

describe('safeValidateApiResponse', () => {
  const schema = z.object({
    value: z.string(),
  });

  it('returns success result for valid data', () => {
    const result = safeValidateApiResponse({ value: 'hello' }, schema);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ value: 'hello' });
    }
  });

  it('returns failure result for invalid data', () => {
    const result = safeValidateApiResponse({ value: 42 }, schema);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBeInstanceOf(ValidationError);
    }
  });

  it('handles non-ValidationError exceptions', () => {
    const badSchema = {
      parse: () => {
        throw new TypeError('unexpected');
      },
    } as any;

    const result = safeValidateApiResponse({}, badSchema);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBeInstanceOf(ValidationError);
      expect(result.error.message).toBe('Unknown validation error');
    }
  });
});

describe('formatValidationError', () => {
  it('formats single error without path', () => {
    const zodError = new ZodError([
      {
        code: 'custom',
        message: 'Invalid value',
        path: [],
      },
    ]);

    expect(formatValidationError(zodError)).toBe('Validation failed: Invalid value');
  });

  it('formats single error with path', () => {
    const zodError = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'number',
        path: ['user', 'email'],
        message: 'Expected string',
      },
    ]);

    expect(formatValidationError(zodError)).toBe('Validation failed: user.email: Expected string');
  });

  it('formats multiple errors', () => {
    const zodError = new ZodError([
      {
        code: 'invalid_type',
        expected: 'string',
        received: 'undefined',
        path: ['name'],
        message: 'Required',
      },
      {
        code: 'invalid_type',
        expected: 'number',
        received: 'string',
        path: ['age'],
        message: 'Expected number',
      },
    ]);

    const result = formatValidationError(zodError);
    expect(result).toContain('name: Required');
    expect(result).toContain('age: Expected number');
  });
});

describe('validateRequest', () => {
  const schema = z.object({
    email: z.string().email(),
    password: z.string().min(8),
  });

  it('returns validated data for valid input', () => {
    const data = { email: 'test@example.com', password: 'password123' };
    expect(validateRequest(data, schema)).toEqual(data);
  });

  it('throws ValidationError with "Invalid request data" prefix', () => {
    try {
      validateRequest({ email: 'bad', password: '123' }, schema);
    } catch (error) {
      expect(error).toBeInstanceOf(ValidationError);
      expect((error as ValidationError).message).toContain('Invalid request data');
    }
  });

  it('re-throws non-ZodError errors', () => {
    const badSchema = {
      parse: () => {
        throw new RangeError('out of range');
      },
    } as any;

    expect(() => validateRequest({}, badSchema)).toThrow('out of range');
  });
});

describe('validateBatch', () => {
  const schema = z.object({
    id: z.number(),
    name: z.string(),
  });

  it('separates valid and invalid items', () => {
    const items = [
      { id: 1, name: 'Alice' },
      { id: 'bad', name: 'Bob' },
      { id: 3, name: 'Charlie' },
      { id: 4 }, // missing name
    ];

    const result = validateBatch(items, schema);

    expect(result.valid.length).toBe(2);
    expect(result.valid[0]).toEqual({ id: 1, name: 'Alice' });
    expect(result.valid[1]).toEqual({ id: 3, name: 'Charlie' });

    expect(result.invalid.length).toBe(2);
    expect(result.invalid[0].index).toBe(1);
    expect(result.invalid[1].index).toBe(3);
    expect(result.invalid[0].error).toBeInstanceOf(ValidationError);
  });

  it('returns all valid for correct items', () => {
    const items = [
      { id: 1, name: 'A' },
      { id: 2, name: 'B' },
    ];

    const result = validateBatch(items, schema);
    expect(result.valid.length).toBe(2);
    expect(result.invalid.length).toBe(0);
  });

  it('returns all invalid for bad items', () => {
    const items = [{ bad: true }, { also: 'bad' }];

    const result = validateBatch(items, schema);
    expect(result.valid.length).toBe(0);
    expect(result.invalid.length).toBe(2);
  });

  it('handles empty array', () => {
    const result = validateBatch([], schema);
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([]);
  });
});

describe('createValidationMiddleware', () => {
  it('creates a middleware function that validates data', async () => {
    const schema = z.object({ status: z.string() });
    const middleware = createValidationMiddleware(schema);

    const result = await middleware({ status: 'ok' });
    expect(result).toEqual({ status: 'ok' });
  });

  it('middleware rejects invalid data', async () => {
    const schema = z.object({ status: z.string() });
    const middleware = createValidationMiddleware(schema);

    await expect(middleware({ status: 123 })).rejects.toThrow(ValidationError);
  });
});

describe('logValidationWarning', () => {
  it('logs warning in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const zodError = new ZodError([]);
    const error = new ValidationError('test warning', zodError);
    logValidationWarning('TestContext', error);

    expect(warnSpy).toHaveBeenCalledWith(
      '[Validation Warning] TestContext:',
      expect.objectContaining({ message: 'test warning' }),
    );

    warnSpy.mockRestore();
    process.env.NODE_ENV = originalEnv;
  });

  it('does not log in non-development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const zodError = new ZodError([]);
    const error = new ValidationError('test', zodError);
    logValidationWarning('Context', error);

    expect(warnSpy).not.toHaveBeenCalled();

    warnSpy.mockRestore();
    process.env.NODE_ENV = originalEnv;
  });
});

describe('reportValidationError', () => {
  it('logs error in production mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const zodError = new ZodError([
      { code: 'custom', message: 'bad', path: [] },
    ]);
    const error = new ValidationError('prod error', zodError);
    reportValidationError('ProdContext', error);

    expect(errorSpy).toHaveBeenCalledWith(
      '[Validation Error] ProdContext:',
      expect.objectContaining({ message: 'prod error', errorCount: 1 }),
    );

    errorSpy.mockRestore();
    process.env.NODE_ENV = originalEnv;
  });

  it('does not log in non-production mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const zodError = new ZodError([]);
    const error = new ValidationError('dev error', zodError);
    reportValidationError('DevContext', error);

    expect(errorSpy).not.toHaveBeenCalled();

    errorSpy.mockRestore();
    process.env.NODE_ENV = originalEnv;
  });
});
