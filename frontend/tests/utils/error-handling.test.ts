import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createAppError, withRetry } from '@/lib/utils/error-handling';
import type { AppError } from '@/lib/utils/error-handling';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

describe('createAppError', () => {
  it('classifies fetch TypeError as network error', () => {
    const error = new TypeError('Failed to fetch');
    const result = createAppError(error);

    expect(result.type).toBe('network');
    expect(result.retryable).toBe(true);
    expect(result.message).toContain('Network connection failed');
    expect(result.originalError).toBe(error);
  });

  it('classifies 401 status as authorization error', () => {
    const error = Object.assign(new Error('Unauthorized'), {
      response: { status: 401 },
    });

    const result = createAppError(error);

    expect(result.type).toBe('authorization');
    expect(result.retryable).toBe(false);
    expect(result.statusCode).toBe(401);
  });

  it('classifies 403 status as authorization error', () => {
    const error = Object.assign(new Error('Forbidden'), {
      response: { status: 403 },
    });

    const result = createAppError(error);

    expect(result.type).toBe('authorization');
    expect(result.statusCode).toBe(403);
  });

  it('classifies 429 status as rate_limit error', () => {
    const error = Object.assign(new Error('Too Many Requests'), {
      response: {
        status: 429,
        headers: { 'retry-after': '30' },
      },
    });

    const result = createAppError(error);

    expect(result.type).toBe('rate_limit');
    expect(result.retryable).toBe(true);
    expect(result.message).toContain('30');
    expect(result.details).toEqual({ retryAfter: '30' });
  });

  it('classifies 400-499 status (non-auth, non-rate-limit) as validation error', () => {
    const error = Object.assign(new Error('Bad Request'), {
      response: { status: 400, data: { message: 'Invalid email format' } },
    });

    const result = createAppError(error);

    expect(result.type).toBe('validation');
    expect(result.retryable).toBe(false);
    expect(result.statusCode).toBe(400);
    expect(result.message).toBe('Invalid email format');
  });

  it('classifies 500+ status as server error', () => {
    const error = Object.assign(new Error('Internal Server Error'), {
      response: { status: 500 },
    });

    const result = createAppError(error);

    expect(result.type).toBe('server');
    expect(result.retryable).toBe(true);
    expect(result.statusCode).toBe(500);
  });

  it('classifies 503 status as server error', () => {
    const error = Object.assign(new Error('Service Unavailable'), {
      response: { status: 503 },
    });

    const result = createAppError(error);

    expect(result.type).toBe('server');
    expect(result.retryable).toBe(true);
  });

  it('classifies unknown Error as unknown type', () => {
    const error = new Error('Something went wrong');
    const result = createAppError(error);

    expect(result.type).toBe('unknown');
    expect(result.retryable).toBe(false);
    expect(result.originalError).toBe(error);
  });

  it('adds context to unknown error message', () => {
    const result = createAppError(new Error('oops'), 'Dashboard');

    expect(result.message).toBe('An error occurred in Dashboard');
  });

  it('handles non-Error values', () => {
    const result = createAppError('string error');

    expect(result.type).toBe('unknown');
    expect(result.message).toBe('An unexpected error occurred');
    expect(result.originalError).toBeInstanceOf(Error);
    expect(result.originalError?.message).toBe('string error');
  });

  it('handles null/undefined values', () => {
    const result = createAppError(null);

    expect(result.type).toBe('unknown');
    expect(result.originalError).toBeInstanceOf(Error);
  });

  it('handles number values', () => {
    const result = createAppError(42);

    expect(result.type).toBe('unknown');
    expect(result.originalError?.message).toBe('42');
  });
});

describe('withRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns result on first successful attempt', async () => {
    const operation = vi.fn().mockResolvedValue('success');

    const resultPromise = withRetry(operation);
    const result = await resultPromise;

    expect(result).toBe('success');
    expect(operation).toHaveBeenCalledTimes(1);
  });

  it('retries on retryable failure and succeeds', async () => {
    const fetchError = new TypeError('Failed to fetch');
    const operation = vi
      .fn()
      .mockRejectedValueOnce(fetchError)
      .mockResolvedValueOnce('recovered');

    const resultPromise = withRetry(operation, { initialDelay: 100 });

    // Fast-forward past the delay
    await vi.advanceTimersByTimeAsync(200);

    const result = await resultPromise;
    expect(result).toBe('recovered');
    expect(operation).toHaveBeenCalledTimes(2);
  });

  it('throws after max attempts exceeded', async () => {
    const fetchError = new TypeError('Failed to fetch');
    const operation = vi.fn().mockRejectedValue(fetchError);

    const resultPromise = withRetry(operation, {
      maxAttempts: 2,
      initialDelay: 50,
    });

    // Attach rejection handler immediately to prevent unhandled rejection
    let caughtError: any;
    const handled = resultPromise.catch((err) => {
      caughtError = err;
    });

    // Advance timers for retries
    await vi.advanceTimersByTimeAsync(200);
    await handled;

    expect(caughtError).toMatchObject({
      type: 'network',
      retryable: true,
    });

    expect(operation).toHaveBeenCalledTimes(2);
  });

  it('does not retry non-retryable errors', async () => {
    const error = Object.assign(new Error('Unauthorized'), {
      response: { status: 401 },
    });
    const operation = vi.fn().mockRejectedValue(error);

    const resultPromise = withRetry(operation, { maxAttempts: 3 });

    await expect(resultPromise).rejects.toMatchObject({
      type: 'authorization',
      retryable: false,
    });

    expect(operation).toHaveBeenCalledTimes(1);
  });

  it('respects custom retry condition', async () => {
    const error = new Error('custom error');
    const operation = vi.fn().mockRejectedValue(error);

    const resultPromise = withRetry(operation, {
      maxAttempts: 3,
      initialDelay: 50,
      retryCondition: () => false, // Never retry
    });

    await expect(resultPromise).rejects.toBeDefined();
    expect(operation).toHaveBeenCalledTimes(1);
  });

  it('uses default options when none provided', async () => {
    const operation = vi.fn().mockResolvedValue('ok');

    const result = await withRetry(operation);
    expect(result).toBe('ok');
  });
});
