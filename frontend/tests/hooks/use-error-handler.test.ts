import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}));

// Mock the error-handler module — provide real classes but mock getContextualErrorMessage
vi.mock('@/lib/api/error-handler', () => {
  const ErrorType = {
    NETWORK: 'NETWORK',
    VALIDATION: 'VALIDATION',
    AUTHENTICATION: 'AUTHENTICATION',
    PERMISSION: 'PERMISSION',
    NOT_FOUND: 'NOT_FOUND',
    TIMEOUT: 'TIMEOUT',
    SERVER: 'SERVER',
    RATE_LIMIT: 'RATE_LIMIT',
    UNKNOWN: 'UNKNOWN',
  };

  const ErrorSeverity = {
    LOW: 'LOW',
    MEDIUM: 'MEDIUM',
    HIGH: 'HIGH',
    CRITICAL: 'CRITICAL',
  };

  class EnhancedApiError extends Error {
    constructor(
      public type: string,
      public status: number,
      public detail: string,
      public severity: string,
      public retryable: boolean,
      public userMessage: string,
      public technicalDetails?: any,
      public originalError?: any,
    ) {
      super(detail);
      this.name = 'EnhancedApiError';
    }
  }

  return {
    ErrorType,
    ErrorSeverity,
    EnhancedApiError,
    getContextualErrorMessage: vi.fn((error: any, _context?: string) => error.userMessage || error.message),
  };
});

// Mock the API client — provide a real APIError class
vi.mock('@/lib/api/client', () => {
  class APIError extends Error {
    constructor(
      message: string,
      public status: number,
      public response?: any,
    ) {
      super(message);
      this.name = 'APIError';
    }
  }

  return {
    APIError,
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
    },
  };
});

import { useErrorHandler, useAsyncError, useFormError } from '@/lib/hooks/use-error-handler';
import { toast } from 'sonner';
import { EnhancedApiError, ErrorType, ErrorSeverity } from '@/lib/api/error-handler';
import { APIError } from '@/lib/api/client';

describe('useErrorHandler', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with null error and not retrying', () => {
    const { result } = renderHook(() => useErrorHandler());
    expect(result.current.error).toBeNull();
    expect(result.current.isRetrying).toBe(false);
  });

  it('handles an APIError and shows toast.error', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.handleError(new APIError('Not found', 404));
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.message).toBe('Not found');
    expect(toast.error).toHaveBeenCalledWith('Not found', expect.any(Object));
  });

  it('handles an EnhancedApiError with CRITICAL severity as toast.error', () => {
    const { result } = renderHook(() => useErrorHandler());

    const enhancedError = new EnhancedApiError(
      ErrorType.SERVER,
      500,
      'Server error',
      ErrorSeverity.CRITICAL,
      true,
      'A critical server error occurred',
    );

    act(() => {
      result.current.handleError(enhancedError);
    });

    expect(result.current.error).not.toBeNull();
    expect(toast.error).toHaveBeenCalled();
  });

  it('handles an EnhancedApiError with MEDIUM severity as toast.warning', () => {
    const { result } = renderHook(() => useErrorHandler());

    const enhancedError = new EnhancedApiError(
      ErrorType.TIMEOUT,
      408,
      'Timeout',
      ErrorSeverity.MEDIUM,
      true,
      'Request timed out',
    );

    act(() => {
      result.current.handleError(enhancedError);
    });

    expect(toast.warning).toHaveBeenCalled();
  });

  it('handles an EnhancedApiError with LOW severity as toast.info', () => {
    const { result } = renderHook(() => useErrorHandler());

    const enhancedError = new EnhancedApiError(
      ErrorType.NOT_FOUND,
      404,
      'Not found',
      ErrorSeverity.LOW,
      false,
      'Resource not found',
    );

    act(() => {
      result.current.handleError(enhancedError);
    });

    expect(toast.info).toHaveBeenCalled();
  });

  it('handles a generic Error object', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.handleError(new Error('Something went wrong'));
    });

    expect(result.current.error).not.toBeNull();
    expect(toast.error).toHaveBeenCalledWith('Something went wrong', expect.any(Object));
  });

  it('handles a plain string-like error', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.handleError({ message: 'Custom error message' });
    });

    expect(result.current.error).not.toBeNull();
    expect(toast.error).toHaveBeenCalled();
  });

  it('handles non-object error (falls back to generic message)', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.handleError('string error');
    });

    expect(result.current.error).not.toBeNull();
    expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred', expect.any(Object));
  });

  it('does not show toast when showToast is false', () => {
    const { result } = renderHook(() =>
      useErrorHandler({ showToast: false }),
    );

    act(() => {
      result.current.handleError(new Error('Silent error'));
    });

    expect(result.current.error).not.toBeNull();
    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.warning).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
  });

  it('calls custom onError callback', () => {
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useErrorHandler({ onError, showToast: false }),
    );

    const error = new APIError('test', 500);

    act(() => {
      result.current.handleError(error);
    });

    expect(onError).toHaveBeenCalledWith(error);
  });

  it('clears error via clearError', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.handleError(new Error('test'));
    });

    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it('retry calls onRetry and clears error on success', async () => {
    const onRetry = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useErrorHandler({ onRetry }),
    );

    act(() => {
      result.current.handleError(new Error('test'));
    });

    await act(async () => {
      await result.current.retry();
    });

    expect(onRetry).toHaveBeenCalled();
    expect(result.current.error).toBeNull();
    expect(toast.success).toHaveBeenCalledWith('Operation completed successfully');
  });

  it('retry does nothing when no onRetry provided', async () => {
    const { result } = renderHook(() => useErrorHandler());

    await act(async () => {
      await result.current.retry();
    });

    // Should not throw or change state
    expect(result.current.isRetrying).toBe(false);
  });
});

describe('useAsyncError', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with not loading and no error', () => {
    const { result } = renderHook(() => useAsyncError());
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('executes async function successfully', async () => {
    const { result } = renderHook(() => useAsyncError());

    let returnValue: string | null = null;

    await act(async () => {
      returnValue = await result.current.execute(async () => 'success');
    });

    expect(returnValue).toBe('success');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('returns null and sets error on failure', async () => {
    const { result } = renderHook(() => useAsyncError());

    let returnValue: string | null = 'not null';

    await act(async () => {
      returnValue = await result.current.execute(async () => {
        throw new Error('Failed!');
      });
    });

    expect(returnValue).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('clears previous error before executing', async () => {
    const { result } = renderHook(() => useAsyncError());

    // Trigger an error first
    await act(async () => {
      await result.current.execute(async () => {
        throw new Error('First error');
      });
    });

    expect(result.current.error).not.toBeNull();

    // Execute successfully
    await act(async () => {
      await result.current.execute(async () => 'ok');
    });

    expect(result.current.error).toBeNull();
  });
});

describe('useFormError', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with empty field errors', () => {
    const { result } = renderHook(() => useFormError());
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.error).toBeNull();
  });

  it('extracts field errors from response data', () => {
    const { result } = renderHook(() => useFormError('form'));

    const errorWithResponse = {
      message: 'Validation failed',
      response: {
        data: {
          errors: {
            email: ['Email is required'],
            password: ['Password too short', 'Must contain number'],
          },
        },
      },
    };

    act(() => {
      result.current.handleFormError(errorWithResponse);
    });

    expect(result.current.fieldErrors.email).toBe('Email is required');
    // Takes the first message from array
    expect(result.current.fieldErrors.password).toBe('Password too short');
  });

  it('clears a specific field error', () => {
    const { result } = renderHook(() => useFormError());

    const errorWithResponse = {
      message: 'Validation failed',
      response: {
        data: {
          errors: {
            email: ['Required'],
            name: 'Name is required',
          },
        },
      },
    };

    act(() => {
      result.current.handleFormError(errorWithResponse);
    });

    expect(result.current.fieldErrors.email).toBe('Required');
    expect(result.current.fieldErrors.name).toBe('Name is required');

    act(() => {
      result.current.clearFieldError('email');
    });

    expect(result.current.fieldErrors.email).toBeUndefined();
    expect(result.current.fieldErrors.name).toBe('Name is required');
  });

  it('clears all errors', () => {
    const { result } = renderHook(() => useFormError());

    const errorWithResponse = {
      message: 'Validation failed',
      response: {
        data: {
          errors: {
            email: ['Required'],
          },
        },
      },
    };

    act(() => {
      result.current.handleFormError(errorWithResponse);
    });

    expect(result.current.fieldErrors.email).toBe('Required');

    act(() => {
      result.current.clearAllErrors();
    });

    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.error).toBeNull();
  });

  it('shows toast for errors without response data', () => {
    const { result } = renderHook(() => useFormError());

    act(() => {
      result.current.handleFormError(new Error('Generic form error'));
    });

    // showToast is false for form error, but it manually calls toast.error for generic errors
    expect(toast.error).toHaveBeenCalled();
  });
});
