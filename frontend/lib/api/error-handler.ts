/**
 * Advanced Error Handling for ruleIQ
 *
 * Provides sophisticated error classification, retry logic with exponential backoff,
 * and user-friendly error messages for different error scenarios.
 */

import { type AxiosError } from 'axios';

// Error type classification
export enum ErrorType {
  NETWORK = 'NETWORK',
  VALIDATION = 'VALIDATION',
  AUTHENTICATION = 'AUTHENTICATION',
  PERMISSION = 'PERMISSION',
  NOT_FOUND = 'NOT_FOUND',
  TIMEOUT = 'TIMEOUT',
  SERVER = 'SERVER',
  RATE_LIMIT = 'RATE_LIMIT',
  UNKNOWN = 'UNKNOWN',
}

// Error severity levels
export enum ErrorSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

// Enhanced API Error class
export class EnhancedApiError extends Error {
  constructor(
    public type: ErrorType,
    public status: number,
    public detail: string,
    public severity: ErrorSeverity,
    public retryable: boolean,
    public userMessage: string,
    public technicalDetails?: any,
    public originalError?: AxiosError,
  ) {
    super(detail);
    this.name = 'EnhancedApiError';
  }
}

// Error classification based on status code and error details
export function classifyError(error: AxiosError): {
  type: ErrorType;
  severity: ErrorSeverity;
  retryable: boolean;
  userMessage: string;
} {
  const status = error.response?.status;
  const message = error.message?.toLowerCase() || '';

  // Network errors
  if (!error.response) {
    if (message.includes('network') || error.code === 'ECONNABORTED') {
      return {
        type: ErrorType.NETWORK,
        severity: ErrorSeverity.HIGH,
        retryable: true,
        userMessage:
          'Network connection issue. Please check your internet connection and try again.',
      };
    }
    if (message.includes('timeout')) {
      return {
        type: ErrorType.TIMEOUT,
        severity: ErrorSeverity.MEDIUM,
        retryable: true,
        userMessage: 'The request took too long. Please try again.',
      };
    }
  }

  // Status code based classification
  switch (status) {
    case 400:
      return {
        type: ErrorType.VALIDATION,
        severity: ErrorSeverity.LOW,
        retryable: false,
        userMessage: 'Invalid data provided. Please check your input and try again.',
      };

    case 401:
      return {
        type: ErrorType.PERMISSION,
        severity: ErrorSeverity.HIGH,
        retryable: false,
        userMessage: 'Your session has expired. Please log in again.',
      };

    case 403:
      return {
        type: ErrorType.PERMISSION,
        severity: ErrorSeverity.MEDIUM,
        retryable: false,
        userMessage: "You don't have permission to perform this action.",
      };

    case 404:
      return {
        type: ErrorType.NOT_FOUND,
        severity: ErrorSeverity.LOW,
        retryable: false,
        userMessage: 'The requested resource was not found.',
      };

    case 429:
      return {
        type: ErrorType.RATE_LIMIT,
        severity: ErrorSeverity.MEDIUM,
        retryable: true,
        userMessage: 'Too many requests. Please wait a moment and try again.',
      };

    case 500:
    case 502:
    case 503:
    case 504:
      return {
        type: ErrorType.SERVER,
        severity: ErrorSeverity.CRITICAL,
        retryable: true,
        userMessage: 'Server error occurred. Our team has been notified. Please try again later.',
      };

    default:
      return {
        type: ErrorType.UNKNOWN,
        severity: ErrorSeverity.MEDIUM,
        retryable: status ? status >= 500 : false,
        userMessage: 'An unexpected error occurred. Please try again.',
      };
  }
}

// Retry configuration based on error type
export interface RetryConfig {
  maxAttempts: number;
  baseDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
}

export function getRetryConfig(errorType: ErrorType): RetryConfig {
  switch (errorType) {
    case ErrorType.NETWORK:
      return {
        maxAttempts: 5,
        baseDelay: 1000,
        maxDelay: 30000,
        backoffMultiplier: 2,
      };

    case ErrorType.TIMEOUT:
      return {
        maxAttempts: 3,
        baseDelay: 2000,
        maxDelay: 10000,
        backoffMultiplier: 1.5,
      };

    case ErrorType.RATE_LIMIT:
      return {
        maxAttempts: 3,
        baseDelay: 5000,
        maxDelay: 60000,
        backoffMultiplier: 3,
      };

    case ErrorType.SERVER:
      return {
        maxAttempts: 3,
        baseDelay: 3000,
        maxDelay: 15000,
        backoffMultiplier: 2,
      };

    default:
      return {
        maxAttempts: 1,
        baseDelay: 1000,
        maxDelay: 1000,
        backoffMultiplier: 1,
      };
  }
}

// Calculate delay with exponential backoff and jitter
export function calculateRetryDelay(attemptNumber: number, config: RetryConfig): number {
  const exponentialDelay = Math.min(
    config.baseDelay * Math.pow(config.backoffMultiplier, attemptNumber - 1),
    config.maxDelay,
  );

  // Add jitter (±20%) to prevent thundering herd
  const jitter = exponentialDelay * 0.2 * (Math.random() - 0.5);

  return Math.round(exponentialDelay + jitter);
}

// Enhanced error handler
export function handleApiError(error: AxiosError): EnhancedApiError {
  const classification = classifyError(error);
  const status = error.response?.status || 0;
  const detail = (error.response?.data as any)?.detail || error.message || 'Unknown error';

  return new EnhancedApiError(
    classification.type,
    status,
    detail,
    classification.severity,
    classification.retryable,
    classification.userMessage,
    {
      url: error.config?.url,
      method: error.config?.method,
      data: error.config?.data,
      timestamp: new Date().toISOString(),
    },
    error,
  );
}

// Retry with exponential backoff
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  errorType: ErrorType,
  onRetry?: (attempt: number, delay: number) => void,
): Promise<T> {
  const config = getRetryConfig(errorType);
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      if (attempt === config.maxAttempts) {
        break;
      }

      const delay = calculateRetryDelay(attempt, config);

      if (onRetry) {
        onRetry(attempt, delay);
      }

      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

// Error recovery strategies
export interface RecoveryStrategy {
  shouldRecover: (error: EnhancedApiError) => boolean;
  recover: () => Promise<void>;
}

export const recoveryStrategies: RecoveryStrategy[] = [
  {
    // Auto-refresh token on 401
    shouldRecover: (error) => error.type === ErrorType.PERMISSION && error.status === 401,
    recover: async () => {
      // This will be handled by the auth interceptor
      window.location.href = '/auth/login';
    },
  },
  {
    // Clear cache on certain server errors
    shouldRecover: (error) => error.type === ErrorType.SERVER && error.status === 500,
    recover: async () => {
      // Clear any cached data that might be corrupted
      if (typeof window !== 'undefined') {
        sessionStorage.clear();
      }
    },
  },
];

// User-friendly error messages based on context
export function getContextualErrorMessage(error: EnhancedApiError, context?: string): string {
  const contextMessages: Record<string, Record<ErrorType, string>> = {
    login: {
      [ErrorType.VALIDATION]: 'Invalid email or password. Please try again.',
      [ErrorType.NETWORK]: 'Unable to connect. Please check your internet connection.',
      [ErrorType.SERVER]: 'Login service is temporarily unavailable. Please try again later.',
      [ErrorType.TIMEOUT]: 'Login is taking longer than expected. Please try again.',
      [ErrorType.AUTHENTICATION]: 'Authentication failed. Please check your credentials.',
      [ErrorType.PERMISSION]: 'Access denied. Please check your credentials.',
      [ErrorType.NOT_FOUND]: 'Login endpoint not found. Please contact support.',
      [ErrorType.RATE_LIMIT]: 'Too many login attempts. Please wait and try again.',
      [ErrorType.UNKNOWN]: 'An unexpected error occurred during login.',
    },
    upload: {
      [ErrorType.VALIDATION]: 'Invalid file format or size. Please check the requirements.',
      [ErrorType.NETWORK]: 'Upload failed due to connection issues. Please try again.',
      [ErrorType.TIMEOUT]: 'Upload is taking too long. Please try with a smaller file.',
      [ErrorType.SERVER]: 'Upload service is temporarily unavailable.',
      [ErrorType.AUTHENTICATION]: 'Authentication required. Please log in and try again.',
      [ErrorType.PERMISSION]: 'You do not have permission to upload files.',
      [ErrorType.NOT_FOUND]: 'Upload endpoint not found. Please contact support.',
      [ErrorType.RATE_LIMIT]: 'Upload rate limit exceeded. Please wait and try again.',
      [ErrorType.UNKNOWN]: 'An unexpected error occurred during upload.',
    },
    save: {
      [ErrorType.VALIDATION]: 'Some fields contain invalid data. Please review and correct.',
      [ErrorType.NETWORK]: 'Unable to save due to connection issues. Your data is safe.',
      [ErrorType.SERVER]: 'Save failed. Please try again or contact support if the issue persists.',
      [ErrorType.AUTHENTICATION]: 'Session expired. Please log in and try again.',
      [ErrorType.PERMISSION]: 'You do not have permission to save this data.',
      [ErrorType.NOT_FOUND]: 'Save endpoint not found. Please contact support.',
      [ErrorType.TIMEOUT]: 'Save operation timed out. Please try again.',
      [ErrorType.RATE_LIMIT]: 'Save rate limit exceeded. Please wait and try again.',
      [ErrorType.UNKNOWN]: 'An unexpected error occurred while saving.',
    },
  };

  if (context && contextMessages[context]?.[error.type]) {
    return contextMessages[context][error.type];
  }

  return error.userMessage;
}

// Error logging for monitoring
export function logError(error: EnhancedApiError, additionalContext?: any): void {
  // Handle cases where error might be undefined or empty
  if (!error) {
    return;
  }

  const _errorLog = {
    timestamp: new Date().toISOString(),
    type: error.type || 'UNKNOWN',
    severity: error.severity || 'ERROR',
    status: error.status || 'N/A',
    message: error.detail || error.message || 'Unknown error occurred',
    url: error.technicalDetails?.url || 'N/A',
    method: error.technicalDetails?.method || 'N/A',
    context: additionalContext,
    stack: error.stack,
  };

  // In production, send to error monitoring service
  if (process.env.NODE_ENV === 'production') {
    // TODO: Send to Sentry or similar service
  } else {
    // intentionally empty - development logging handled elsewhere
  }
}

// Export utility for use in components
export const errorHandler = {
  classify: classifyError,
  handle: handleApiError,
  retry: retryWithBackoff,
  getRetryConfig,
  getContextualMessage: getContextualErrorMessage,
  log: logError,
};
