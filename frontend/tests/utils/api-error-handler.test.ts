import { describe, it, expect } from 'vitest';
import {
  ErrorType,
  ErrorSeverity,
  EnhancedApiError,
  classifyError,
  getRetryConfig,
  calculateRetryDelay,
  getContextualErrorMessage,
  logError,
  errorHandler,
} from '@/lib/api/error-handler';
import type { AxiosError } from 'axios';

// Helper to build a minimal AxiosError-shaped object
function makeAxiosError(overrides: {
  status?: number;
  message?: string;
  code?: string;
  hasResponse?: boolean;
}): AxiosError {
  const { status, message = '', code, hasResponse = true } = overrides;
  return {
    message,
    code,
    response: hasResponse && status !== undefined ? { status, data: {} } : undefined,
    config: {},
    isAxiosError: true,
    toJSON: () => ({}),
    name: 'AxiosError',
  } as unknown as AxiosError;
}

// ============================================================================
// EnhancedApiError
// ============================================================================

describe('EnhancedApiError', () => {
  it('is an instance of Error', () => {
    const err = new EnhancedApiError(
      ErrorType.NETWORK,
      0,
      'Network error',
      ErrorSeverity.HIGH,
      true,
      'Please check your connection',
    );
    expect(err).toBeInstanceOf(Error);
  });

  it('has name "EnhancedApiError"', () => {
    const err = new EnhancedApiError(ErrorType.SERVER, 500, 'detail', ErrorSeverity.CRITICAL, true, 'msg');
    expect(err.name).toBe('EnhancedApiError');
  });

  it('stores type, status, detail, severity, retryable, userMessage', () => {
    const err = new EnhancedApiError(
      ErrorType.VALIDATION,
      400,
      'Bad input',
      ErrorSeverity.LOW,
      false,
      'Invalid data provided',
    );
    expect(err.type).toBe(ErrorType.VALIDATION);
    expect(err.status).toBe(400);
    expect(err.detail).toBe('Bad input');
    expect(err.severity).toBe(ErrorSeverity.LOW);
    expect(err.retryable).toBe(false);
    expect(err.userMessage).toBe('Invalid data provided');
  });

  it('message equals detail', () => {
    const err = new EnhancedApiError(ErrorType.TIMEOUT, 408, 'Timed out', ErrorSeverity.MEDIUM, true, 'Too slow');
    expect(err.message).toBe('Timed out');
  });

  it('stores optional technicalDetails', () => {
    const details = { url: '/api/test', method: 'GET' };
    const err = new EnhancedApiError(ErrorType.SERVER, 500, 'd', ErrorSeverity.CRITICAL, true, 'u', details);
    expect(err.technicalDetails).toEqual(details);
  });

  it('technicalDetails defaults to undefined when not provided', () => {
    const err = new EnhancedApiError(ErrorType.UNKNOWN, 0, 'd', ErrorSeverity.MEDIUM, false, 'u');
    expect(err.technicalDetails).toBeUndefined();
  });

  it('can be thrown and caught', () => {
    expect(() => {
      throw new EnhancedApiError(ErrorType.PERMISSION, 403, 'Forbidden', ErrorSeverity.HIGH, false, 'No permission');
    }).toThrow(EnhancedApiError);
  });
});

// ============================================================================
// ErrorType enum
// ============================================================================

describe('ErrorType enum', () => {
  it('has NETWORK value', () => expect(ErrorType.NETWORK).toBe('NETWORK'));
  it('has VALIDATION value', () => expect(ErrorType.VALIDATION).toBe('VALIDATION'));
  it('has AUTHENTICATION value', () => expect(ErrorType.AUTHENTICATION).toBe('AUTHENTICATION'));
  it('has PERMISSION value', () => expect(ErrorType.PERMISSION).toBe('PERMISSION'));
  it('has NOT_FOUND value', () => expect(ErrorType.NOT_FOUND).toBe('NOT_FOUND'));
  it('has TIMEOUT value', () => expect(ErrorType.TIMEOUT).toBe('TIMEOUT'));
  it('has SERVER value', () => expect(ErrorType.SERVER).toBe('SERVER'));
  it('has RATE_LIMIT value', () => expect(ErrorType.RATE_LIMIT).toBe('RATE_LIMIT'));
  it('has UNKNOWN value', () => expect(ErrorType.UNKNOWN).toBe('UNKNOWN'));
});

// ============================================================================
// ErrorSeverity enum
// ============================================================================

describe('ErrorSeverity enum', () => {
  it('has LOW value', () => expect(ErrorSeverity.LOW).toBe('LOW'));
  it('has MEDIUM value', () => expect(ErrorSeverity.MEDIUM).toBe('MEDIUM'));
  it('has HIGH value', () => expect(ErrorSeverity.HIGH).toBe('HIGH'));
  it('has CRITICAL value', () => expect(ErrorSeverity.CRITICAL).toBe('CRITICAL'));
});

// ============================================================================
// classifyError
// ============================================================================

describe('classifyError', () => {
  it('classifies network error (no response, network message)', () => {
    const err = makeAxiosError({ hasResponse: false, message: 'network error' });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.NETWORK);
    expect(result.retryable).toBe(true);
    expect(result.severity).toBe(ErrorSeverity.HIGH);
  });

  it('classifies network error via ECONNABORTED code', () => {
    const err = makeAxiosError({ hasResponse: false, code: 'ECONNABORTED' });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.NETWORK);
    expect(result.retryable).toBe(true);
  });

  it('classifies timeout error (no response, timeout message)', () => {
    const err = makeAxiosError({ hasResponse: false, message: 'timeout exceeded' });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.TIMEOUT);
    expect(result.retryable).toBe(true);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
  });

  it('classifies 400 as VALIDATION, not retryable', () => {
    const err = makeAxiosError({ status: 400 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.VALIDATION);
    expect(result.retryable).toBe(false);
    expect(result.severity).toBe(ErrorSeverity.LOW);
  });

  it('classifies 401 as PERMISSION, not retryable', () => {
    const err = makeAxiosError({ status: 401 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.PERMISSION);
    expect(result.retryable).toBe(false);
    expect(result.severity).toBe(ErrorSeverity.HIGH);
  });

  it('classifies 403 as PERMISSION, not retryable', () => {
    const err = makeAxiosError({ status: 403 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.PERMISSION);
    expect(result.retryable).toBe(false);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
  });

  it('classifies 404 as NOT_FOUND, not retryable', () => {
    const err = makeAxiosError({ status: 404 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.NOT_FOUND);
    expect(result.retryable).toBe(false);
    expect(result.severity).toBe(ErrorSeverity.LOW);
  });

  it('classifies 429 as RATE_LIMIT, retryable', () => {
    const err = makeAxiosError({ status: 429 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.RATE_LIMIT);
    expect(result.retryable).toBe(true);
    expect(result.severity).toBe(ErrorSeverity.MEDIUM);
  });

  it('classifies 500 as SERVER, retryable', () => {
    const err = makeAxiosError({ status: 500 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.SERVER);
    expect(result.retryable).toBe(true);
    expect(result.severity).toBe(ErrorSeverity.CRITICAL);
  });

  it('classifies 502 as SERVER, retryable', () => {
    const err = makeAxiosError({ status: 502 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.SERVER);
    expect(result.retryable).toBe(true);
  });

  it('classifies 503 as SERVER, retryable', () => {
    const err = makeAxiosError({ status: 503 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.SERVER);
    expect(result.retryable).toBe(true);
  });

  it('classifies 504 as SERVER, retryable', () => {
    const err = makeAxiosError({ status: 504 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.SERVER);
    expect(result.retryable).toBe(true);
  });

  it('classifies unknown status as UNKNOWN', () => {
    const err = makeAxiosError({ status: 418 });
    const result = classifyError(err);
    expect(result.type).toBe(ErrorType.UNKNOWN);
  });

  it('unknown status >=500 is retryable', () => {
    const err = makeAxiosError({ status: 599 });
    const result = classifyError(err);
    expect(result.retryable).toBe(true);
  });

  it('unknown status <500 is not retryable', () => {
    const err = makeAxiosError({ status: 418 });
    const result = classifyError(err);
    expect(result.retryable).toBe(false);
  });

  it('returns a userMessage string for all classified errors', () => {
    [400, 401, 403, 404, 429, 500].forEach((status) => {
      const err = makeAxiosError({ status });
      const result = classifyError(err);
      expect(typeof result.userMessage).toBe('string');
      expect(result.userMessage.length).toBeGreaterThan(0);
    });
  });
});

// ============================================================================
// getRetryConfig
// ============================================================================

describe('getRetryConfig', () => {
  it('NETWORK: 5 max attempts, 1000 base delay, multiplier 2', () => {
    const config = getRetryConfig(ErrorType.NETWORK);
    expect(config.maxAttempts).toBe(5);
    expect(config.baseDelay).toBe(1000);
    expect(config.maxDelay).toBe(30000);
    expect(config.backoffMultiplier).toBe(2);
  });

  it('TIMEOUT: 3 max attempts, 2000 base delay, multiplier 1.5', () => {
    const config = getRetryConfig(ErrorType.TIMEOUT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(2000);
    expect(config.maxDelay).toBe(10000);
    expect(config.backoffMultiplier).toBe(1.5);
  });

  it('RATE_LIMIT: 3 max attempts, 5000 base delay, multiplier 3', () => {
    const config = getRetryConfig(ErrorType.RATE_LIMIT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(5000);
    expect(config.maxDelay).toBe(60000);
    expect(config.backoffMultiplier).toBe(3);
  });

  it('SERVER: 3 max attempts, 3000 base delay, multiplier 2', () => {
    const config = getRetryConfig(ErrorType.SERVER);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(3000);
    expect(config.maxDelay).toBe(15000);
    expect(config.backoffMultiplier).toBe(2);
  });

  it('non-retryable types: 1 max attempt', () => {
    [ErrorType.VALIDATION, ErrorType.PERMISSION, ErrorType.NOT_FOUND, ErrorType.UNKNOWN].forEach(
      (type) => {
        const config = getRetryConfig(type);
        expect(config.maxAttempts).toBe(1);
      },
    );
  });

  it('returns an object with required keys', () => {
    const config = getRetryConfig(ErrorType.SERVER);
    expect(config).toHaveProperty('maxAttempts');
    expect(config).toHaveProperty('baseDelay');
    expect(config).toHaveProperty('maxDelay');
    expect(config).toHaveProperty('backoffMultiplier');
  });
});

// ============================================================================
// calculateRetryDelay
// ============================================================================

describe('calculateRetryDelay', () => {
  const config = {
    maxAttempts: 5,
    baseDelay: 1000,
    maxDelay: 30000,
    backoffMultiplier: 2,
  };

  it('returns a number', () => {
    expect(typeof calculateRetryDelay(1, config)).toBe('number');
  });

  it('attempt 1 returns a value close to baseDelay (±20% jitter)', () => {
    const delay = calculateRetryDelay(1, config);
    // baseDelay * 2^0 = 1000, ±20% = 800-1200
    expect(delay).toBeGreaterThanOrEqual(800);
    expect(delay).toBeLessThanOrEqual(1200);
  });

  it('attempt 2 doubles the base delay (≈2000, ±20%)', () => {
    const delay = calculateRetryDelay(2, config);
    expect(delay).toBeGreaterThanOrEqual(1600);
    expect(delay).toBeLessThanOrEqual(2400);
  });

  it('never exceeds maxDelay (with jitter allowance)', () => {
    const delay = calculateRetryDelay(100, config);
    expect(delay).toBeLessThanOrEqual(config.maxDelay * 1.2);
  });

  it('returns a rounded integer', () => {
    const delay = calculateRetryDelay(1, config);
    expect(delay).toBe(Math.round(delay));
  });
});

// ============================================================================
// getContextualErrorMessage
// ============================================================================

describe('getContextualErrorMessage', () => {
  function makeEnhancedError(type: ErrorType, userMessage: string): EnhancedApiError {
    return new EnhancedApiError(type, 400, 'detail', ErrorSeverity.LOW, false, userMessage);
  }

  it('returns context-specific message for login + VALIDATION', () => {
    const err = makeEnhancedError(ErrorType.VALIDATION, 'generic message');
    const msg = getContextualErrorMessage(err, 'login');
    expect(msg).toContain('password');
  });

  it('returns context-specific message for upload + TIMEOUT', () => {
    const err = makeEnhancedError(ErrorType.TIMEOUT, 'generic message');
    const msg = getContextualErrorMessage(err, 'upload');
    expect(msg.length).toBeGreaterThan(0);
    expect(msg).not.toBe('generic message');
  });

  it('returns context-specific message for save + NETWORK', () => {
    const err = makeEnhancedError(ErrorType.NETWORK, 'generic message');
    const msg = getContextualErrorMessage(err, 'save');
    expect(msg.length).toBeGreaterThan(0);
  });

  it('falls back to userMessage when no context provided', () => {
    const err = makeEnhancedError(ErrorType.SERVER, 'Server is down');
    const msg = getContextualErrorMessage(err);
    expect(msg).toBe('Server is down');
  });

  it('falls back to userMessage for unknown context', () => {
    const err = makeEnhancedError(ErrorType.SERVER, 'Server is down');
    const msg = getContextualErrorMessage(err, 'unknown-context');
    expect(msg).toBe('Server is down');
  });

  it('returns a non-empty string in all cases', () => {
    const types = Object.values(ErrorType);
    const contexts = ['login', 'upload', 'save', undefined];
    types.forEach((type) => {
      contexts.forEach((ctx) => {
        const err = makeEnhancedError(type, 'fallback');
        const msg = getContextualErrorMessage(err, ctx);
        expect(typeof msg).toBe('string');
        expect(msg.length).toBeGreaterThan(0);
      });
    });
  });
});

// ============================================================================
// logError
// ============================================================================

describe('logError', () => {
  it('does not throw when called with valid error', () => {
    const err = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'detail',
      ErrorSeverity.CRITICAL,
      true,
      'Server error',
    );
    expect(() => logError(err)).not.toThrow();
  });

  it('does not throw when called with null/undefined error', () => {
    expect(() => logError(null as any)).not.toThrow();
  });

  it('accepts optional additionalContext without throwing', () => {
    const err = new EnhancedApiError(
      ErrorType.VALIDATION,
      400,
      'detail',
      ErrorSeverity.LOW,
      false,
      'Invalid',
    );
    expect(() => logError(err, { component: 'LoginForm' })).not.toThrow();
  });
});

// ============================================================================
// errorHandler object
// ============================================================================

describe('errorHandler', () => {
  it('has classify, handle, retry, getRetryConfig, getContextualMessage, log', () => {
    expect(typeof errorHandler.classify).toBe('function');
    expect(typeof errorHandler.handle).toBe('function');
    expect(typeof errorHandler.retry).toBe('function');
    expect(typeof errorHandler.getRetryConfig).toBe('function');
    expect(typeof errorHandler.getContextualMessage).toBe('function');
    expect(typeof errorHandler.log).toBe('function');
  });

  it('errorHandler.getRetryConfig delegates correctly', () => {
    const config = errorHandler.getRetryConfig(ErrorType.NETWORK);
    expect(config.maxAttempts).toBe(5);
  });
});
