import { describe, it, expect, vi } from 'vitest';
import {
  ErrorType,
  ErrorSeverity,
  EnhancedApiError,
  classifyError,
  getRetryConfig,
  calculateRetryDelay,
  getContextualErrorMessage,
  logError,
} from '@/lib/api/error-handler';

// Helper to create mock AxiosError-like objects
function mockAxiosError(overrides: Record<string, any> = {}): any {
  return {
    message: overrides.message || 'Request failed',
    response: overrides.response,
    code: overrides.code,
    config: overrides.config || { url: '/api/test', method: 'GET' },
    isAxiosError: true,
    ...overrides,
  };
}

// ── EnhancedApiError ─────────────────────────────────────

describe('EnhancedApiError', () => {
  it('creates error with all properties', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK,
      0,
      'Network failure',
      ErrorSeverity.HIGH,
      true,
      'Check your connection',
    );

    expect(error.type).toBe(ErrorType.NETWORK);
    expect(error.status).toBe(0);
    expect(error.detail).toBe('Network failure');
    expect(error.severity).toBe(ErrorSeverity.HIGH);
    expect(error.retryable).toBe(true);
    expect(error.userMessage).toBe('Check your connection');
    expect(error.name).toBe('EnhancedApiError');
    expect(error).toBeInstanceOf(Error);
  });

  it('accepts optional technicalDetails and originalError', () => {
    const origError = mockAxiosError();
    const error = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'Server error occurred',
      { url: '/api/test', method: 'POST' },
      origError,
    );

    expect(error.technicalDetails).toEqual({ url: '/api/test', method: 'POST' });
    expect(error.originalError).toBe(origError);
  });
});

// ── classifyError ────────────────────────────────────────

describe('classifyError', () => {
  it('classifies network error (no response, network message)', () => {
    const error = mockAxiosError({
      message: 'Network Error',
      response: undefined,
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.NETWORK);
    expect(result.severity).toBe(ErrorSeverity.HIGH);
    expect(result.retryable).toBe(true);
  });

  it('classifies network error by ECONNABORTED code', () => {
    const error = mockAxiosError({
      message: 'something',
      response: undefined,
      code: 'ECONNABORTED',
    });

    const result = classifyError(error);
    expect(result.type).toBe(ErrorType.NETWORK);
  });

  it('classifies timeout error', () => {
    const error = mockAxiosError({
      message: 'timeout of 5000ms exceeded',
      response: undefined,
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.TIMEOUT);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
    expect(result.retryable).toBe(true);
  });

  it('classifies 400 as validation error', () => {
    const error = mockAxiosError({
      response: { status: 400, data: { detail: 'Invalid input' } },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.VALIDATION);
    expect(result.severity).toBe(ErrorSeverity.LOW);
    expect(result.retryable).toBe(false);
  });

  it('classifies 401 as permission error', () => {
    const error = mockAxiosError({
      response: { status: 401 },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.PERMISSION);
    expect(result.severity).toBe(ErrorSeverity.HIGH);
    expect(result.retryable).toBe(false);
  });

  it('classifies 403 as permission error', () => {
    const error = mockAxiosError({
      response: { status: 403 },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.PERMISSION);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
  });

  it('classifies 404 as not found', () => {
    const error = mockAxiosError({
      response: { status: 404 },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.NOT_FOUND);
    expect(result.severity).toBe(ErrorSeverity.LOW);
    expect(result.retryable).toBe(false);
  });

  it('classifies 429 as rate limit', () => {
    const error = mockAxiosError({
      response: { status: 429 },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.RATE_LIMIT);
    expect(result.retryable).toBe(true);
  });

  it('classifies 500 as server error', () => {
    const error = mockAxiosError({
      response: { status: 500 },
    });

    const result = classifyError(error);

    expect(result.type).toBe(ErrorType.SERVER);
    expect(result.severity).toBe(ErrorSeverity.CRITICAL);
    expect(result.retryable).toBe(true);
  });

  it('classifies 502 as server error', () => {
    const result = classifyError(mockAxiosError({ response: { status: 502 } }));
    expect(result.type).toBe(ErrorType.SERVER);
  });

  it('classifies 503 as server error', () => {
    const result = classifyError(mockAxiosError({ response: { status: 503 } }));
    expect(result.type).toBe(ErrorType.SERVER);
  });

  it('classifies 504 as server error', () => {
    const result = classifyError(mockAxiosError({ response: { status: 504 } }));
    expect(result.type).toBe(ErrorType.SERVER);
  });

  it('classifies unknown status as UNKNOWN', () => {
    const result = classifyError(mockAxiosError({ response: { status: 418 } }));

    expect(result.type).toBe(ErrorType.UNKNOWN);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
    expect(result.retryable).toBe(false);
  });

  it('classifies unknown 5xx as retryable UNKNOWN', () => {
    const result = classifyError(mockAxiosError({ response: { status: 599 } }));

    expect(result.type).toBe(ErrorType.UNKNOWN);
    expect(result.retryable).toBe(true);
  });
});

// ── getRetryConfig ───────────────────────────────────────

describe('getRetryConfig', () => {
  it('returns NETWORK config with 5 attempts', () => {
    const config = getRetryConfig(ErrorType.NETWORK);
    expect(config.maxAttempts).toBe(5);
    expect(config.baseDelay).toBe(1000);
    expect(config.maxDelay).toBe(30000);
    expect(config.backoffMultiplier).toBe(2);
  });

  it('returns TIMEOUT config with 3 attempts', () => {
    const config = getRetryConfig(ErrorType.TIMEOUT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(2000);
    expect(config.backoffMultiplier).toBe(1.5);
  });

  it('returns RATE_LIMIT config with higher base delay', () => {
    const config = getRetryConfig(ErrorType.RATE_LIMIT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(5000);
    expect(config.backoffMultiplier).toBe(3);
  });

  it('returns SERVER config', () => {
    const config = getRetryConfig(ErrorType.SERVER);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(3000);
  });

  it('returns default config for non-retryable errors', () => {
    const config = getRetryConfig(ErrorType.VALIDATION);
    expect(config.maxAttempts).toBe(1);
    expect(config.baseDelay).toBe(1000);
    expect(config.backoffMultiplier).toBe(1);
  });

  it('returns default config for UNKNOWN', () => {
    const config = getRetryConfig(ErrorType.UNKNOWN);
    expect(config.maxAttempts).toBe(1);
  });
});

// ── calculateRetryDelay ──────────────────────────────────

describe('calculateRetryDelay', () => {
  it('returns approximately baseDelay for first attempt', () => {
    const config = { maxAttempts: 3, baseDelay: 1000, maxDelay: 30000, backoffMultiplier: 2 };
    const delay = calculateRetryDelay(1, config);

    // baseDelay=1000 * 2^0 = 1000, jitter ±20% = 800-1200
    expect(delay).toBeGreaterThanOrEqual(800);
    expect(delay).toBeLessThanOrEqual(1200);
  });

  it('increases delay with each attempt', () => {
    const config = { maxAttempts: 5, baseDelay: 1000, maxDelay: 100000, backoffMultiplier: 2 };

    // Run multiple times and check the average trend
    const delays: number[] = [];
    for (let attempt = 1; attempt <= 4; attempt++) {
      // Average of many runs to reduce jitter effect
      let sum = 0;
      for (let i = 0; i < 100; i++) {
        sum += calculateRetryDelay(attempt, config);
      }
      delays.push(sum / 100);
    }

    // Each average should be roughly double the previous
    expect(delays[1]).toBeGreaterThan(delays[0]);
    expect(delays[2]).toBeGreaterThan(delays[1]);
    expect(delays[3]).toBeGreaterThan(delays[2]);
  });

  it('caps at maxDelay', () => {
    const config = { maxAttempts: 10, baseDelay: 1000, maxDelay: 5000, backoffMultiplier: 10 };

    const delay = calculateRetryDelay(5, config);
    // maxDelay=5000 + jitter ±20% = 4000-6000
    expect(delay).toBeLessThanOrEqual(6000);
  });

  it('includes jitter for thundering herd prevention', () => {
    const config = { maxAttempts: 3, baseDelay: 1000, maxDelay: 30000, backoffMultiplier: 2 };

    const delays = new Set<number>();
    for (let i = 0; i < 20; i++) {
      delays.add(calculateRetryDelay(1, config));
    }

    // With jitter, we should get multiple unique values
    expect(delays.size).toBeGreaterThan(1);
  });
});

// ── getContextualErrorMessage ────────────────────────────

describe('getContextualErrorMessage', () => {
  it('returns login-specific validation message', () => {
    const error = new EnhancedApiError(
      ErrorType.VALIDATION, 400, 'Bad request', ErrorSeverity.LOW,
      false, 'Generic validation message',
    );

    const message = getContextualErrorMessage(error, 'login');
    expect(message).toContain('Invalid email or password');
  });

  it('returns login-specific network message', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK, 0, 'Network error', ErrorSeverity.HIGH,
      true, 'Generic network message',
    );

    const message = getContextualErrorMessage(error, 'login');
    expect(message).toContain('internet connection');
  });

  it('returns upload-specific timeout message', () => {
    const error = new EnhancedApiError(
      ErrorType.TIMEOUT, 0, 'Timeout', ErrorSeverity.MEDIUM,
      true, 'Generic timeout',
    );

    const message = getContextualErrorMessage(error, 'upload');
    expect(message).toContain('smaller file');
  });

  it('returns save-specific validation message', () => {
    const error = new EnhancedApiError(
      ErrorType.VALIDATION, 400, 'Validation error', ErrorSeverity.LOW,
      false, 'Generic validation',
    );

    const message = getContextualErrorMessage(error, 'save');
    expect(message).toContain('fields contain invalid data');
  });

  it('falls back to userMessage for unknown context', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK, 0, 'Network error', ErrorSeverity.HIGH,
      true, 'User-friendly fallback',
    );

    const message = getContextualErrorMessage(error, 'unknown-context');
    expect(message).toBe('User-friendly fallback');
  });

  it('falls back to userMessage when no context provided', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER, 500, 'Server error', ErrorSeverity.CRITICAL,
      true, 'Default server message',
    );

    const message = getContextualErrorMessage(error);
    expect(message).toBe('Default server message');
  });
});

// ── logError ─────────────────────────────────────────────

describe('logError', () => {
  it('does not throw when given a valid error', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER, 500, 'Server error', ErrorSeverity.CRITICAL,
      true, 'Server error occurred',
    );

    expect(() => logError(error)).not.toThrow();
  });

  it('handles null/undefined error gracefully', () => {
    expect(() => logError(null as any)).not.toThrow();
    expect(() => logError(undefined as any)).not.toThrow();
  });

  it('accepts additional context', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK, 0, 'Network', ErrorSeverity.HIGH,
      true, 'Connection issue',
    );

    expect(() => logError(error, { component: 'Dashboard' })).not.toThrow();
  });
});

// ── ErrorType and ErrorSeverity enums ────────────────────

describe('ErrorType enum', () => {
  it('has all expected values', () => {
    expect(ErrorType.NETWORK).toBe('NETWORK');
    expect(ErrorType.VALIDATION).toBe('VALIDATION');
    expect(ErrorType.AUTHENTICATION).toBe('AUTHENTICATION');
    expect(ErrorType.PERMISSION).toBe('PERMISSION');
    expect(ErrorType.NOT_FOUND).toBe('NOT_FOUND');
    expect(ErrorType.TIMEOUT).toBe('TIMEOUT');
    expect(ErrorType.SERVER).toBe('SERVER');
    expect(ErrorType.RATE_LIMIT).toBe('RATE_LIMIT');
    expect(ErrorType.UNKNOWN).toBe('UNKNOWN');
  });
});

describe('ErrorSeverity enum', () => {
  it('has all expected values', () => {
    expect(ErrorSeverity.LOW).toBe('LOW');
    expect(ErrorSeverity.MEDIUM).toBe('MEDIUM');
    expect(ErrorSeverity.HIGH).toBe('HIGH');
    expect(ErrorSeverity.CRITICAL).toBe('CRITICAL');
  });
});
