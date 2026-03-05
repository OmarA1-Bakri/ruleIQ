/**
 * Type safety utilities for runtime type checking and safe operations
 */

// Error types
export interface AppError {
  message: string;
  code?: string;
  details?: unknown;
}

export interface ValidationError extends AppError {
  field?: string;
  value?: unknown;
}

export interface ApiError extends AppError {
  status?: number;
  endpoint?: string;
}

// Type guards
export function isAppError(error: unknown): error is AppError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as AppError).message === 'string'
  );
}

export function isValidationError(error: unknown): error is ValidationError {
  return isAppError(error) && 'field' in error;
}

export function isApiError(error: unknown): error is ApiError {
  return isAppError(error) && 'status' in error;
}

// Safe JSON parsing
export function safeJsonParse<T>(json: string): T | null;
export function safeJsonParse<T>(json: string, fallback: T): T;
export function safeJsonParse<T>(json: string, fallback?: T): T | null {
  try {
    const parsed = JSON.parse(json);
    return parsed as T;
  } catch (_error) {
    return fallback ?? null;
  }
}

// Safe JSON parsing with validation
export function safeJsonParseWithValidation<T>(
  json: string,
  validator: (value: unknown) => value is T,
): T | null;
export function safeJsonParseWithValidation<T>(
  json: string,
  validator: (value: unknown) => value is T,
  fallback: T,
): T;
export function safeJsonParseWithValidation<T>(
  json: string,
  validator: (value: unknown) => value is T,
  fallback?: T,
): T | null {
  try {
    const parsed = JSON.parse(json);
    if (validator(parsed)) {
      return parsed;
    }
    return fallback ?? null;
  } catch (_error) {
    return fallback ?? null;
  }
}

// Safe localStorage operations
export function safeGetFromStorage<T>(
  key: string,
  validator?: (value: unknown) => value is T,
): T | null {
  try {
    const item = localStorage.getItem(key);
    if (!item) return null;

    const parsed = JSON.parse(item);
    if (validator && !validator(parsed)) {
      return null;
    }

    return parsed as T;
  } catch (_error) {
    return null;
  }
}

export function safeSetToStorage<T>(key: string, value: T): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (_error) {
    return false;
  }
}

// Type assertion helpers
export function assertNonNull<T>(
  value: T | null | undefined,
  message?: string,
): asserts value is T {
  if (value === null || value === undefined) {
    throw new Error(message ?? 'Value is null or undefined');
  }
}

export function assertIsString(value: unknown): asserts value is string {
  if (typeof value !== 'string') {
    throw new Error(`Expected string but got ${typeof value}`);
  }
}

export function assertIsNumber(value: unknown): asserts value is number {
  if (typeof value !== 'number' || isNaN(value)) {
    throw new Error(`Expected number but got ${typeof value}`);
  }
}

export function assertIsArray<T>(
  value: unknown,
  itemValidator?: (item: unknown) => item is T,
): asserts value is T[] {
  if (!Array.isArray(value)) {
    throw new Error(`Expected array but got ${typeof value}`);
  }

  if (itemValidator) {
    for (let i = 0; i < value.length; i++) {
      if (!itemValidator(value[i])) {
        throw new Error(`Invalid array item at index ${i}`);
      }
    }
  }
}

// Safe property access
export function safeAccess<T, K extends keyof T>(
  obj: T | null | undefined,
  key: K,
): T[K] | undefined {
  return obj?.[key];
}

export function safeAccessNested<T>(obj: unknown, path: string[]): T | undefined {
  let current = obj;
  for (const key of path) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current as T;
}

// Error conversion utilities
export function toAppError(error: unknown): AppError {
  if (isAppError(error)) {
    return error;
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      code: error.name,
      details: error.stack,
    };
  }

  if (typeof error === 'string') {
    return {
      message: error,
    };
  }

  return {
    message: 'An unknown error occurred',
    details: error,
  };
}

export function toValidationError(
  error: unknown,
  field?: string,
  value?: unknown,
): ValidationError {
  const appError = toAppError(error);
  return {
    ...appError,
    field,
    value,
  };
}

export function toApiError(error: unknown, status?: number, endpoint?: string): ApiError {
  const appError = toAppError(error);
  return {
    ...appError,
    status,
    endpoint,
  };
}

// Common type validators
export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && !isNaN(value);
}

export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

export function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0;
}

export function isValidEmail(value: unknown): value is string {
  if (!isString(value)) return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(value);
}

export function isValidUrl(value: unknown): value is string {
  if (!isString(value)) return false;
  try {
    new URL(value);
    return true;
  } catch (_error) {
    return false;
  }
}

// Result type for operations that can fail
export type Result<T, E = AppError> = { success: true; data: T } | { success: false; error: E };

export function success<T>(data: T): Result<T> {
  return { success: true, data };
}

export function failure<E = AppError>(error: E): Result<never, E> {
  return { success: false, error };
}

export function isSuccess<T, E>(result: Result<T, E>): result is { success: true; data: T } {
  return result.success;
}

export function isFailure<T, E>(result: Result<T, E>): result is { success: false; error: E } {
  return !result.success;
}
