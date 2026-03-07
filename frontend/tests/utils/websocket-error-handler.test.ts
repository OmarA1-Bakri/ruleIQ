import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  WebSocketErrorType,
  categorizeError,
  getUserMessage,
  getRecoverySuggestion,
  calculateRetryDelay,
  MessageQueue,
  createRecoveryStrategy,
  logError,
} from '@/lib/utils/websocket-error-handler';
import type { WebSocketError } from '@/lib/utils/websocket-error-handler';

// Mock use-toast
vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
}));

describe('categorizeError', () => {
  describe('CloseEvent handling', () => {
    function makeCloseEvent(code: number, reason = ''): CloseEvent {
      return { code, reason } as CloseEvent;
    }

    it('categorizes code 1000 as CONNECTION_FAILED (normal close)', () => {
      const result = categorizeError(makeCloseEvent(1000));
      expect(result.type).toBe(WebSocketErrorType.CONNECTION_FAILED);
      expect(result.recoverable).toBe(false);
    });

    it('categorizes code 1001 as CONNECTION_FAILED (going away)', () => {
      const result = categorizeError(makeCloseEvent(1001));
      expect(result.type).toBe(WebSocketErrorType.CONNECTION_FAILED);
      expect(result.recoverable).toBe(true);
      expect(result.retryAfter).toBe(5000);
    });

    it('categorizes code 1002 as INVALID_MESSAGE (protocol error)', () => {
      const result = categorizeError(makeCloseEvent(1002));
      expect(result.type).toBe(WebSocketErrorType.INVALID_MESSAGE);
      expect(result.recoverable).toBe(false);
    });

    it('categorizes code 1003 as INVALID_MESSAGE', () => {
      const result = categorizeError(makeCloseEvent(1003));
      expect(result.type).toBe(WebSocketErrorType.INVALID_MESSAGE);
    });

    it('categorizes code 1006 as NETWORK_ERROR (abnormal close)', () => {
      const result = categorizeError(makeCloseEvent(1006));
      expect(result.type).toBe(WebSocketErrorType.NETWORK_ERROR);
      expect(result.recoverable).toBe(true);
      expect(result.retryAfter).toBe(2000);
    });

    it('categorizes code 1008 as SERVER_ERROR (policy violation)', () => {
      const result = categorizeError(makeCloseEvent(1008));
      expect(result.type).toBe(WebSocketErrorType.SERVER_ERROR);
      expect(result.recoverable).toBe(false);
    });

    it('categorizes code 1009 as INVALID_MESSAGE (too large)', () => {
      const result = categorizeError(makeCloseEvent(1009));
      expect(result.type).toBe(WebSocketErrorType.INVALID_MESSAGE);
      expect(result.recoverable).toBe(false);
    });

    it('categorizes code 1011 as SERVER_ERROR', () => {
      const result = categorizeError(makeCloseEvent(1011));
      expect(result.type).toBe(WebSocketErrorType.SERVER_ERROR);
      expect(result.recoverable).toBe(true);
      expect(result.retryAfter).toBe(10000);
    });

    it('categorizes code 4000 as AUTHENTICATION_FAILED', () => {
      const result = categorizeError(makeCloseEvent(4000, 'Token expired'));
      expect(result.type).toBe(WebSocketErrorType.AUTHENTICATION_FAILED);
      expect(result.recoverable).toBe(false);
      expect(result.message).toBe('Token expired');
    });

    it('categorizes code 4429 as RATE_LIMITED', () => {
      const result = categorizeError(makeCloseEvent(4429, 'Slow down'));
      expect(result.type).toBe(WebSocketErrorType.RATE_LIMITED);
      expect(result.recoverable).toBe(true);
      expect(result.retryAfter).toBe(60000);
    });

    it('categorizes unknown close code as UNKNOWN', () => {
      const result = categorizeError(makeCloseEvent(9999));
      expect(result.type).toBe(WebSocketErrorType.UNKNOWN);
      expect(result.recoverable).toBe(true);
    });
  });

  describe('Error object handling', () => {
    it('categorizes network errors', () => {
      const result = categorizeError(new Error('Failed to fetch'));
      expect(result.type).toBe(WebSocketErrorType.NETWORK_ERROR);
      expect(result.recoverable).toBe(true);
    });

    it('categorizes NetworkError pattern', () => {
      const result = categorizeError(new Error('NetworkError when attempting connection'));
      expect(result.type).toBe(WebSocketErrorType.NETWORK_ERROR);
    });

    it('categorizes 401 Unauthorized', () => {
      const result = categorizeError(new Error('401 Unauthorized'));
      expect(result.type).toBe(WebSocketErrorType.AUTHENTICATION_FAILED);
      expect(result.recoverable).toBe(false);
    });

    it('categorizes rate limit by error message', () => {
      const result = categorizeError(new Error('429 rate limit exceeded'));
      expect(result.type).toBe(WebSocketErrorType.RATE_LIMITED);
      expect(result.retryAfter).toBe(60000);
    });

    it('categorizes server errors by status code in message', () => {
      const result = categorizeError(new Error('500 Internal Server Error'));
      expect(result.type).toBe(WebSocketErrorType.SERVER_ERROR);
      expect(result.retryAfter).toBe(10000);
    });

    it('categorizes 503 as server error', () => {
      const result = categorizeError(new Error('503 Service Unavailable'));
      expect(result.type).toBe(WebSocketErrorType.SERVER_ERROR);
    });

    it('categorizes timeout errors', () => {
      const result = categorizeError(new Error('Connection timeout'));
      expect(result.type).toBe(WebSocketErrorType.TIMEOUT);
      expect(result.retryAfter).toBe(3000);
    });

    it('categorizes unknown errors as UNKNOWN', () => {
      const result = categorizeError(new Error('Something unexpected happened'));
      expect(result.type).toBe(WebSocketErrorType.UNKNOWN);
      expect(result.recoverable).toBe(true);
    });
  });
});

describe('getUserMessage', () => {
  it('returns connection error message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.CONNECTION_FAILED } as WebSocketError),
    ).toContain('Unable to connect');
  });

  it('returns authentication message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.AUTHENTICATION_FAILED } as WebSocketError),
    ).toContain('Authentication failed');
  });

  it('returns rate limit message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.RATE_LIMITED } as WebSocketError),
    ).toContain('Too many requests');
  });

  it('returns server error message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.SERVER_ERROR } as WebSocketError),
    ).toContain('Server error');
  });

  it('returns network error message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.NETWORK_ERROR } as WebSocketError),
    ).toContain('Network connection lost');
  });

  it('returns invalid message error', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.INVALID_MESSAGE } as WebSocketError),
    ).toContain('Invalid message');
  });

  it('returns timeout message', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.TIMEOUT } as WebSocketError),
    ).toContain('timeout');
  });

  it('returns original message for unknown type', () => {
    expect(
      getUserMessage({ type: WebSocketErrorType.UNKNOWN, message: 'Custom error' } as WebSocketError),
    ).toBe('Custom error');
  });
});

describe('getRecoverySuggestion', () => {
  it('suggests checking internet for connection errors', () => {
    expect(
      getRecoverySuggestion({ type: WebSocketErrorType.CONNECTION_FAILED } as WebSocketError),
    ).toContain('internet connection');
  });

  it('suggests signing in for auth errors', () => {
    expect(
      getRecoverySuggestion({ type: WebSocketErrorType.AUTHENTICATION_FAILED } as WebSocketError),
    ).toContain('sign in');
  });

  it('suggests waiting for rate limit with time', () => {
    const result = getRecoverySuggestion({
      type: WebSocketErrorType.RATE_LIMITED,
      retryAfter: 60000,
    } as WebSocketError);
    expect(result).toContain('60 seconds');
  });

  it('suggests trying later for server errors', () => {
    expect(
      getRecoverySuggestion({ type: WebSocketErrorType.SERVER_ERROR } as WebSocketError),
    ).toContain('try again later');
  });

  it('suggests auto-retry for recoverable unknown errors', () => {
    expect(
      getRecoverySuggestion({
        type: WebSocketErrorType.UNKNOWN,
        recoverable: true,
      } as WebSocketError),
    ).toContain('retry automatically');
  });

  it('suggests refresh for non-recoverable unknown errors', () => {
    expect(
      getRecoverySuggestion({
        type: WebSocketErrorType.UNKNOWN,
        recoverable: false,
      } as WebSocketError),
    ).toContain('refresh');
  });
});

describe('calculateRetryDelay', () => {
  it('calculates exponential backoff', () => {
    // With jitter=false for predictable results
    expect(calculateRetryDelay(1, 1000, 30000, false)).toBe(1000);
    expect(calculateRetryDelay(2, 1000, 30000, false)).toBe(2000);
    expect(calculateRetryDelay(3, 1000, 30000, false)).toBe(4000);
    expect(calculateRetryDelay(4, 1000, 30000, false)).toBe(8000);
  });

  it('caps at max delay', () => {
    const delay = calculateRetryDelay(10, 1000, 5000, false);
    expect(delay).toBe(5000);
  });

  it('adds jitter when enabled', () => {
    const baseDelay = calculateRetryDelay(1, 1000, 30000, false);
    const jitteredDelay = calculateRetryDelay(1, 1000, 30000, true);

    // Jittered delay should be >= base delay (jitter only adds, never subtracts)
    expect(jitteredDelay).toBeGreaterThanOrEqual(baseDelay);
    // And at most 10% more
    expect(jitteredDelay).toBeLessThanOrEqual(baseDelay * 1.1);
  });

  it('uses default values', () => {
    const delay = calculateRetryDelay(1);
    // Default base: 1000, attempt 1, so should be around 1000 + jitter
    expect(delay).toBeGreaterThanOrEqual(1000);
    expect(delay).toBeLessThanOrEqual(1100);
  });
});

describe('MessageQueue', () => {
  let queue: MessageQueue;

  beforeEach(() => {
    queue = new MessageQueue(3);
  });

  it('enqueues and dequeues messages in FIFO order', () => {
    queue.enqueue('first');
    queue.enqueue('second');
    queue.enqueue('third');

    expect(queue.dequeue()).toBe('first');
    expect(queue.dequeue()).toBe('second');
    expect(queue.dequeue()).toBe('third');
  });

  it('returns undefined when dequeuing empty queue', () => {
    expect(queue.dequeue()).toBeUndefined();
  });

  it('peeks at the front without removing', () => {
    queue.enqueue('front');
    queue.enqueue('back');

    expect(queue.peek()).toBe('front');
    expect(queue.size()).toBe(2); // Not removed
  });

  it('returns undefined when peeking empty queue', () => {
    expect(queue.peek()).toBeUndefined();
  });

  it('reports correct size', () => {
    expect(queue.size()).toBe(0);
    queue.enqueue('a');
    expect(queue.size()).toBe(1);
    queue.enqueue('b');
    expect(queue.size()).toBe(2);
    queue.dequeue();
    expect(queue.size()).toBe(1);
  });

  it('evicts oldest when max size exceeded', () => {
    queue.enqueue('a');
    queue.enqueue('b');
    queue.enqueue('c');
    queue.enqueue('d'); // Should evict 'a'

    expect(queue.size()).toBe(3);
    expect(queue.dequeue()).toBe('b'); // 'a' was evicted
  });

  it('clears all messages', () => {
    queue.enqueue('x');
    queue.enqueue('y');
    queue.clear();

    expect(queue.size()).toBe(0);
    expect(queue.dequeue()).toBeUndefined();
  });

  it('getAll returns a copy of the queue', () => {
    queue.enqueue(1);
    queue.enqueue(2);

    const all = queue.getAll();
    expect(all).toEqual([1, 2]);

    // Modifying the returned array should not affect the queue
    all.push(3);
    expect(queue.size()).toBe(2);
  });

  it('always returns true from enqueue', () => {
    expect(queue.enqueue('msg')).toBe(true);
    expect(queue.enqueue('msg2')).toBe(true);
  });

  it('uses default max size of 100', () => {
    const defaultQueue = new MessageQueue();
    for (let i = 0; i < 105; i++) {
      defaultQueue.enqueue(i);
    }
    expect(defaultQueue.size()).toBe(100);
    // First 5 should have been evicted
    expect(defaultQueue.dequeue()).toBe(5);
  });
});

describe('createRecoveryStrategy', () => {
  it('creates strategy with defaults', () => {
    const strategy = createRecoveryStrategy();

    expect(typeof strategy.shouldRetry).toBe('function');
    expect(typeof strategy.getDelay).toBe('function');
    expect(typeof strategy.onRetry).toBe('function');
    expect(typeof strategy.onGiveUp).toBe('function');
  });

  it('default shouldRetry returns true for recoverable errors under max attempts', () => {
    const strategy = createRecoveryStrategy();

    const recoverableError: WebSocketError = {
      type: WebSocketErrorType.NETWORK_ERROR,
      message: 'Network lost',
      recoverable: true,
    };

    expect(strategy.shouldRetry(recoverableError, 1)).toBe(true);
    expect(strategy.shouldRetry(recoverableError, 4)).toBe(true);
    expect(strategy.shouldRetry(recoverableError, 5)).toBe(false); // >= 5
  });

  it('default shouldRetry returns false for non-recoverable errors', () => {
    const strategy = createRecoveryStrategy();

    const nonRecoverableError: WebSocketError = {
      type: WebSocketErrorType.AUTHENTICATION_FAILED,
      message: 'Auth failed',
      recoverable: false,
    };

    expect(strategy.shouldRetry(nonRecoverableError, 1)).toBe(false);
  });

  it('accepts custom shouldRetry', () => {
    const strategy = createRecoveryStrategy({
      shouldRetry: (_error, attempt) => attempt < 2,
    });

    const error: WebSocketError = {
      type: WebSocketErrorType.NETWORK_ERROR,
      message: 'Error',
      recoverable: true,
    };

    expect(strategy.shouldRetry(error, 1)).toBe(true);
    expect(strategy.shouldRetry(error, 2)).toBe(false);
  });

  it('default getDelay uses error retryAfter as base', () => {
    const strategy = createRecoveryStrategy();

    const error: WebSocketError = {
      type: WebSocketErrorType.NETWORK_ERROR,
      message: 'Error',
      recoverable: true,
      retryAfter: 2000,
    };

    const delay = strategy.getDelay(error, 1);
    // Base delay = 2000, attempt 1, so around 2000 + jitter
    expect(delay).toBeGreaterThanOrEqual(2000);
  });

  it('default onRetry logs to console', () => {
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const strategy = createRecoveryStrategy();

    const error: WebSocketError = {
      type: WebSocketErrorType.NETWORK_ERROR,
      message: 'Error',
      recoverable: true,
    };

    strategy.onRetry(error, 3);
    expect(consoleSpy).toHaveBeenCalledWith('Retrying connection (attempt 3)...');

    consoleSpy.mockRestore();
  });
});

describe('logError', () => {
  it('logs recoverable errors with console.warn', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const error: WebSocketError = {
      type: WebSocketErrorType.NETWORK_ERROR,
      message: 'Network lost',
      recoverable: true,
      retryAfter: 2000,
    };

    logError(error);

    expect(warnSpy).toHaveBeenCalledWith(
      'WebSocket Error:',
      expect.objectContaining({
        type: WebSocketErrorType.NETWORK_ERROR,
        message: 'Network lost',
        recoverable: true,
      }),
    );

    warnSpy.mockRestore();
  });

  it('logs non-recoverable errors with console.error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const error: WebSocketError = {
      type: WebSocketErrorType.AUTHENTICATION_FAILED,
      message: 'Auth failed',
      recoverable: false,
    };

    logError(error);

    expect(errorSpy).toHaveBeenCalledWith(
      'WebSocket Error:',
      expect.objectContaining({
        type: WebSocketErrorType.AUTHENTICATION_FAILED,
        recoverable: false,
      }),
    );

    errorSpy.mockRestore();
  });

  it('includes context in log data', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const error: WebSocketError = {
      type: WebSocketErrorType.TIMEOUT,
      message: 'Timeout',
      recoverable: true,
    };

    logError(error, { connectionId: 'conn-123' });

    expect(warnSpy).toHaveBeenCalledWith(
      'WebSocket Error:',
      expect.objectContaining({
        connectionId: 'conn-123',
      }),
    );

    warnSpy.mockRestore();
  });
});
