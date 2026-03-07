import { describe, it, expect, vi } from 'vitest';
import {
  ErrorType,
  ErrorSeverity,
  EnhancedApiError,
  classifyError,
  getRetryConfig,
  calculateRetryDelay,
  handleApiError,
  getContextualErrorMessage,
  logError,
} from '@/lib/api/error-handler';

// Helper to create a mock AxiosError
function createMockAxiosError(
  status?: number,
  message = 'Request failed',
  code?: string,
  responseData?: any,
): any {
  return {
    message,
    code,
    response: status
      ? {
          status,
          data: responseData || {},
          statusText: `Status ${status}`,
        }
      : undefined,
    config: {
      url: '/api/v1/test',
      method: 'GET',
      data: null,
    },
    isAxiosError: true,
  };
}

describe('EnhancedApiError', () => {
  it('creates an error with correct properties', () => {
    const error = new EnhancedApiError(
      ErrorType.VALIDATION,
      400,
      'Invalid input',
      ErrorSeverity.LOW,
      false,
      'Please check your input',
    );

    expect(error.name).toBe('EnhancedApiError');
    expect(error.type).toBe(ErrorType.VALIDATION);
    expect(error.status).toBe(400);
    expect(error.detail).toBe('Invalid input');
    expect(error.severity).toBe(ErrorSeverity.LOW);
    expect(error.retryable).toBe(false);
    expect(error.userMessage).toBe('Please check your input');
    expect(error.message).toBe('Invalid input');
  });

  it('is an instance of Error', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'Something went wrong',
    );

    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(EnhancedApiError);
  });
});

describe('classifyError', () => {
  describe('network errors', () => {
    it('classifies network errors (no response)', () => {
      const error = createMockAxiosError(undefined, 'Network Error', 'ECONNABORTED');
      const result = classifyError(error);

      expect(result.type).toBe(ErrorType.NETWORK);
      expect(result.severity).toBe(ErrorSeverity.HIGH);
      expect(result.retryable).toBe(true);
    });

    it('classifies timeout errors', () => {
      const error = createMockAxiosError(undefined, 'timeout of 5000ms exceeded');
      const result = classifyError(error);

      expect(result.type).toBe(ErrorType.TIMEOUT);
      expect(result.severity).toBe(ErrorSeverity.MEDIUM);
      expect(result.retryable).toBe(true);
    });
  });

  describe('HTTP status code classification', () => {
    it('classifies 400 as VALIDATION', () => {
      const result = classifyError(createMockAxiosError(400));
      expect(result.type).toBe(ErrorType.VALIDATION);
      expect(result.severity).toBe(ErrorSeverity.LOW);
      expect(result.retryable).toBe(false);
    });

    it('classifies 401 as PERMISSION', () => {
      const result = classifyError(createMockAxiosError(401));
      expect(result.type).toBe(ErrorType.PERMISSION);
      expect(result.severity).toBe(ErrorSeverity.HIGH);
      expect(result.retryable).toBe(false);
    });

    it('classifies 403 as PERMISSION', () => {
      const result = classifyError(createMockAxiosError(403));
      expect(result.type).toBe(ErrorType.PERMISSION);
      expect(result.severity).toBe(ErrorSeverity.MEDIUM);
      expect(result.retryable).toBe(false);
    });

    it('classifies 404 as NOT_FOUND', () => {
      const result = classifyError(createMockAxiosError(404));
      expect(result.type).toBe(ErrorType.NOT_FOUND);
      expect(result.severity).toBe(ErrorSeverity.LOW);
      expect(result.retryable).toBe(false);
    });

    it('classifies 429 as RATE_LIMIT', () => {
      const result = classifyError(createMockAxiosError(429));
      expect(result.type).toBe(ErrorType.RATE_LIMIT);
      expect(result.severity).toBe(ErrorSeverity.MEDIUM);
      expect(result.retryable).toBe(true);
    });

    it('classifies 500 as SERVER', () => {
      const result = classifyError(createMockAxiosError(500));
      expect(result.type).toBe(ErrorType.SERVER);
      expect(result.severity).toBe(ErrorSeverity.CRITICAL);
      expect(result.retryable).toBe(true);
    });

    it('classifies 502 as SERVER', () => {
      const result = classifyError(createMockAxiosError(502));
      expect(result.type).toBe(ErrorType.SERVER);
      expect(result.retryable).toBe(true);
    });

    it('classifies 503 as SERVER', () => {
      const result = classifyError(createMockAxiosError(503));
      expect(result.type).toBe(ErrorType.SERVER);
    });

    it('classifies 504 as SERVER', () => {
      const result = classifyError(createMockAxiosError(504));
      expect(result.type).toBe(ErrorType.SERVER);
    });

    it('classifies unknown status codes as UNKNOWN', () => {
      const result = classifyError(createMockAxiosError(418));
      expect(result.type).toBe(ErrorType.UNKNOWN);
      expect(result.severity).toBe(ErrorSeverity.MEDIUM);
    });

    it('marks unknown 5xx errors as retryable', () => {
      const result = classifyError(createMockAxiosError(599));
      expect(result.retryable).toBe(true);
    });

    it('marks unknown 4xx errors as not retryable', () => {
      const result = classifyError(createMockAxiosError(418));
      expect(result.retryable).toBe(false);
    });
  });
});

describe('getRetryConfig', () => {
  it('returns high retry count for NETWORK errors', () => {
    const config = getRetryConfig(ErrorType.NETWORK);
    expect(config.maxAttempts).toBe(5);
    expect(config.baseDelay).toBe(1000);
    expect(config.backoffMultiplier).toBe(2);
  });

  it('returns moderate retry count for TIMEOUT errors', () => {
    const config = getRetryConfig(ErrorType.TIMEOUT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(2000);
  });

  it('returns longer delays for RATE_LIMIT errors', () => {
    const config = getRetryConfig(ErrorType.RATE_LIMIT);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(5000);
    expect(config.backoffMultiplier).toBe(3);
  });

  it('returns moderate config for SERVER errors', () => {
    const config = getRetryConfig(ErrorType.SERVER);
    expect(config.maxAttempts).toBe(3);
    expect(config.baseDelay).toBe(3000);
  });

  it('returns single attempt for non-retryable errors', () => {
    const config = getRetryConfig(ErrorType.VALIDATION);
    expect(config.maxAttempts).toBe(1);
  });

  it('returns single attempt for UNKNOWN errors', () => {
    const config = getRetryConfig(ErrorType.UNKNOWN);
    expect(config.maxAttempts).toBe(1);
  });
});

describe('calculateRetryDelay', () => {
  it('returns base delay for first attempt', () => {
    const config = { maxAttempts: 3, baseDelay: 1000, maxDelay: 10000, backoffMultiplier: 2 };
    const delay = calculateRetryDelay(1, config);
    // With jitter (+-20%), should be between 800 and 1200
    expect(delay).toBeGreaterThanOrEqual(800);
    expect(delay).toBeLessThanOrEqual(1200);
  });

  it('increases delay exponentially', () => {
    const config = { maxAttempts: 5, baseDelay: 1000, maxDelay: 100000, backoffMultiplier: 2 };
    const delay1 = calculateRetryDelay(1, config);
    const delay2 = calculateRetryDelay(2, config);
    const delay3 = calculateRetryDelay(3, config);

    // delay2 should be roughly double delay1, delay3 roughly double delay2
    // Account for jitter - just verify the trend
    expect(delay2).toBeGreaterThan(delay1 * 0.7);
    expect(delay3).toBeGreaterThan(delay2 * 0.7);
  });

  it('caps at maxDelay', () => {
    const config = { maxAttempts: 10, baseDelay: 1000, maxDelay: 5000, backoffMultiplier: 10 };
    const delay = calculateRetryDelay(5, config);
    // With jitter, should still be bounded around maxDelay
    expect(delay).toBeLessThanOrEqual(6000); // maxDelay + 20% jitter
  });
});

describe('handleApiError', () => {
  it('converts AxiosError to EnhancedApiError', () => {
    const axiosError = createMockAxiosError(400, 'Bad Request', undefined, {
      detail: 'Invalid email',
    });

    const result = handleApiError(axiosError);

    expect(result).toBeInstanceOf(EnhancedApiError);
    expect(result.status).toBe(400);
    expect(result.detail).toBe('Invalid email');
    expect(result.type).toBe(ErrorType.VALIDATION);
  });

  it('uses message fallback when no detail in response', () => {
    const axiosError = createMockAxiosError(500, 'Internal Server Error');
    const result = handleApiError(axiosError);

    expect(result.detail).toBe('Internal Server Error');
  });

  it('includes technical details', () => {
    const axiosError = createMockAxiosError(404);
    const result = handleApiError(axiosError);

    expect(result.technicalDetails).toBeDefined();
    expect(result.technicalDetails.url).toBe('/api/v1/test');
    expect(result.technicalDetails.method).toBe('GET');
  });

  it('preserves original error', () => {
    const axiosError = createMockAxiosError(500);
    const result = handleApiError(axiosError);

    expect(result.originalError).toBe(axiosError);
  });
});

describe('getContextualErrorMessage', () => {
  it('returns login-specific message for validation error in login context', () => {
    const error = new EnhancedApiError(
      ErrorType.VALIDATION,
      400,
      'Bad request',
      ErrorSeverity.LOW,
      false,
      'Generic validation message',
    );

    const message = getContextualErrorMessage(error, 'login');
    expect(message).toBe('Invalid email or password. Please try again.');
  });

  it('returns upload-specific message for timeout in upload context', () => {
    const error = new EnhancedApiError(
      ErrorType.TIMEOUT,
      0,
      'Timeout',
      ErrorSeverity.MEDIUM,
      true,
      'Generic timeout message',
    );

    const message = getContextualErrorMessage(error, 'upload');
    expect(message).toBe('Upload is taking too long. Please try with a smaller file.');
  });

  it('returns save-specific message for network error in save context', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK,
      0,
      'Network error',
      ErrorSeverity.HIGH,
      true,
      'Generic network message',
    );

    const message = getContextualErrorMessage(error, 'save');
    expect(message).toBe('Unable to save due to connection issues. Your data is safe.');
  });

  it('falls back to userMessage when no context provided', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'Something went wrong on our end',
    );

    const message = getContextualErrorMessage(error);
    expect(message).toBe('Something went wrong on our end');
  });

  it('falls back to userMessage for unknown context', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'Default user message',
    );

    const message = getContextualErrorMessage(error, 'unknownContext');
    expect(message).toBe('Default user message');
  });
});

describe('logError', () => {
  it('does not throw when called with a valid error', () => {
    const error = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'User message',
    );

    expect(() => logError(error)).not.toThrow();
  });

  it('handles null error gracefully', () => {
    expect(() => logError(null as any)).not.toThrow();
  });

  it('handles undefined error gracefully', () => {
    expect(() => logError(undefined as any)).not.toThrow();
  });

  it('accepts additional context', () => {
    const error = new EnhancedApiError(
      ErrorType.NETWORK,
      0,
      'Network error',
      ErrorSeverity.HIGH,
      true,
      'Connection failed',
    );

    expect(() => logError(error, { page: 'dashboard', action: 'fetch' })).not.toThrow();
  });
});
