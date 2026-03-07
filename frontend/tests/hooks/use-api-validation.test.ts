import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { z } from 'zod';

// Mock the validation module to avoid side effects (API client imports)
vi.mock('@/lib/api/validation', () => {
  const { z: zod } = require('zod');

  class ValidationError extends Error {
    constructor(
      message: string,
      public readonly errors: any,
      public readonly data?: unknown,
    ) {
      super(message);
      this.name = 'ValidationError';
    }
  }

  function validateApiResponse<T>(data: unknown, schema: any): T {
    try {
      return schema.parse(data);
    } catch (error: any) {
      throw new ValidationError(error.message, error, data);
    }
  }

  function safeValidateApiResponse<T>(
    data: unknown,
    schema: any,
  ): { success: true; data: T } | { success: false; error: ValidationError } {
    try {
      const validated = validateApiResponse<T>(data, schema);
      return { success: true, data: validated };
    } catch (error: any) {
      if (error instanceof ValidationError) {
        return { success: false, error };
      }
      return { success: false, error: new ValidationError(error.message, error) };
    }
  }

  return {
    ValidationError,
    validateApiResponse,
    safeValidateApiResponse,
    logValidationWarning: vi.fn(),
    reportValidationError: vi.fn(),
  };
});

// Mock @tanstack/react-query (used by useValidatedQuery/useValidatedMutation)
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(() => ({ data: undefined, isLoading: false, error: null })),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isLoading: false })),
}));

import {
  useFormValidation,
  useBatchValidation,
  useValidatedCache,
  useRealtimeValidation,
} from '@/lib/hooks/use-api-validation';

// ============================================================================
// useFormValidation
// ============================================================================

describe('useFormValidation', () => {
  const schema = z.object({
    name: z.string().min(2, 'Name must be at least 2 characters'),
    email: z.string().email('Invalid email'),
    age: z.number().min(18, 'Must be 18 or older'),
  });

  it('initializes with empty errors and not validating', () => {
    const { result } = renderHook(() => useFormValidation(schema));
    expect(result.current.errors).toEqual({});
    expect(result.current.isValidating).toBe(false);
  });

  it('returns isValid true for valid data', async () => {
    const { result } = renderHook(() => useFormValidation(schema));

    let validation: any;
    await act(async () => {
      validation = await result.current.validate({
        name: 'Alice',
        email: 'alice@example.com',
        age: 25,
      });
    });

    expect(validation.isValid).toBe(true);
    expect(validation.data).toEqual({ name: 'Alice', email: 'alice@example.com', age: 25 });
  });

  it('returns isValid false and field errors for invalid data', async () => {
    const { result } = renderHook(() => useFormValidation(schema));

    let validation: any;
    await act(async () => {
      validation = await result.current.validate({
        name: 'A',
        email: 'not-an-email',
        age: 16,
      });
    });

    expect(validation.isValid).toBe(false);
    expect(validation.errors).toBeDefined();
    expect(Object.keys(validation.errors).length).toBeGreaterThan(0);
  });

  it('clearErrors resets errors to empty object', async () => {
    const { result } = renderHook(() => useFormValidation(schema));

    // First create some errors
    await act(async () => {
      await result.current.validate({ name: 'A', email: 'bad', age: 10 });
    });

    act(() => {
      result.current.clearErrors();
    });

    expect(result.current.errors).toEqual({});
  });

  it('clearFieldError removes only the specified field error', async () => {
    const { result } = renderHook(() => useFormValidation(schema));

    // Create errors
    await act(async () => {
      await result.current.validate({ name: 'A', email: 'bad', age: 10 });
    });

    act(() => {
      result.current.clearFieldError('email');
    });

    expect(result.current.errors['email']).toBeUndefined();
  });
});

// ============================================================================
// useBatchValidation
// ============================================================================

describe('useBatchValidation', () => {
  const itemSchema = z.object({
    id: z.number(),
    label: z.string().min(1),
  });

  it('initializes with empty results and not validating', () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));
    expect(result.current.results).toEqual({ valid: [], invalid: [] });
    expect(result.current.isValidating).toBe(false);
  });

  it('separates valid and invalid items', async () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));

    let batchResult: any;
    await act(async () => {
      batchResult = await result.current.validateBatch([
        { id: 1, label: 'Valid item' },
        { id: 2, label: '' },           // invalid: label too short
        { id: 3, label: 'Another' },
        { label: 'Missing id' },         // invalid: id missing
      ]);
    });

    expect(batchResult.valid).toHaveLength(2);
    expect(batchResult.invalid).toHaveLength(2);
  });

  it('all valid when all items pass schema', async () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));

    let batchResult: any;
    await act(async () => {
      batchResult = await result.current.validateBatch([
        { id: 1, label: 'First' },
        { id: 2, label: 'Second' },
        { id: 3, label: 'Third' },
      ]);
    });

    expect(batchResult.valid).toHaveLength(3);
    expect(batchResult.invalid).toHaveLength(0);
  });

  it('all invalid when no items pass schema', async () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));

    let batchResult: any;
    await act(async () => {
      batchResult = await result.current.validateBatch([
        { id: 'not-a-number', label: 'Bad' },
        {},
      ]);
    });

    expect(batchResult.valid).toHaveLength(0);
    expect(batchResult.invalid).toHaveLength(2);
  });

  it('includes correct index in invalid results', async () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));

    let batchResult: any;
    await act(async () => {
      batchResult = await result.current.validateBatch([
        { id: 1, label: 'Valid' },
        { id: 'bad', label: 'Invalid' },
        { id: 3, label: 'Valid' },
      ]);
    });

    expect(batchResult.invalid[0].index).toBe(1);
  });

  it('handles empty batch', async () => {
    const { result } = renderHook(() => useBatchValidation(itemSchema));

    let batchResult: any;
    await act(async () => {
      batchResult = await result.current.validateBatch([]);
    });

    expect(batchResult.valid).toHaveLength(0);
    expect(batchResult.invalid).toHaveLength(0);
  });
});

// ============================================================================
// useValidatedCache
// ============================================================================

describe('useValidatedCache', () => {
  const schema = z.object({
    id: z.number(),
    name: z.string(),
  });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('initializes with null data', () => {
    const { result } = renderHook(() => useValidatedCache('test-key', schema));
    expect(result.current.data).toBeNull();
    expect(result.current.isExpired).toBe(true);
  });

  it('returns false from set when data fails validation', () => {
    const { result } = renderHook(() => useValidatedCache('test-key', schema));

    let setResult: boolean;
    act(() => {
      setResult = result.current.set({ id: 'not-a-number', name: 'test' });
    });

    expect(setResult!).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it('returns true from set when data passes validation', () => {
    const { result } = renderHook(() => useValidatedCache('test-key', schema));

    let setResult: boolean;
    act(() => {
      setResult = result.current.set({ id: 1, name: 'Alice' });
    });

    expect(setResult!).toBe(true);
    expect(result.current.data).toEqual({ id: 1, name: 'Alice' });
  });

  it('get returns data when not expired', () => {
    const { result } = renderHook(() =>
      useValidatedCache('test-key', schema, 60000),
    );

    act(() => {
      result.current.set({ id: 42, name: 'Bob' });
    });

    let gotten: any;
    act(() => {
      gotten = result.current.get();
    });

    expect(gotten).toEqual({ id: 42, name: 'Bob' });
  });

  it('get returns null after TTL expires', () => {
    const { result } = renderHook(() =>
      useValidatedCache('test-key', schema, 1000),
    );

    act(() => {
      result.current.set({ id: 1, name: 'Alice' });
    });

    // Advance time past TTL
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    let gotten: any;
    act(() => {
      gotten = result.current.get();
    });

    expect(gotten).toBeNull();
  });

  it('clear resets data to null', () => {
    const { result } = renderHook(() => useValidatedCache('test-key', schema));

    act(() => {
      result.current.set({ id: 1, name: 'Alice' });
    });

    act(() => {
      result.current.clear();
    });

    expect(result.current.data).toBeNull();
  });
});

// ============================================================================
// useRealtimeValidation
// ============================================================================

describe('useRealtimeValidation', () => {
  const schema = z.object({
    username: z.string().min(3, 'Username must be at least 3 chars'),
    email: z.string().email('Invalid email'),
  });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('initializes with empty data, errors, touched, and isValid=false', () => {
    const { result } = renderHook(() => useRealtimeValidation(schema));
    expect(result.current.data).toEqual({});
    expect(result.current.errors).toEqual({});
    expect(result.current.touched).toEqual({});
    expect(result.current.isValid).toBe(false);
  });

  it('reset clears all state', () => {
    const { result } = renderHook(() => useRealtimeValidation(schema));

    act(() => {
      result.current.updateField('username', 'alice' as any);
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.data).toEqual({});
    expect(result.current.touched).toEqual({});
  });

  it('updateField marks field as touched', () => {
    const { result } = renderHook(() => useRealtimeValidation(schema));

    act(() => {
      result.current.updateField('username', 'alice' as any);
    });

    expect(result.current.touched['username']).toBe(true);
  });

  it('updateField updates data with new value', () => {
    const { result } = renderHook(() => useRealtimeValidation(schema));

    act(() => {
      result.current.updateField('username', 'bob' as any);
    });

    expect((result.current.data as any)['username']).toBe('bob');
  });
});
