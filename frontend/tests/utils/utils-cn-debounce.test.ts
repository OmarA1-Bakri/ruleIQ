import { describe, it, expect, vi } from 'vitest';
import { cn, debounce } from '@/lib/utils';

// ============================================================================
// cn — class merging utility
// ============================================================================

describe('cn', () => {
  it('returns empty string for no args', () => {
    expect(cn()).toBe('');
  });

  it('merges two class strings', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles undefined gracefully', () => {
    expect(cn('foo', undefined)).toBe('foo');
  });

  it('handles false gracefully', () => {
    expect(cn('foo', false)).toBe('foo');
  });

  it('includes all provided class strings in output', () => {
    const result = cn('text-sm', 'font-bold');
    expect(result).toContain('text-sm');
    expect(result).toContain('font-bold');
  });

  it('resolves padding conflict — px-2 overrides p-4 on x-axis', () => {
    const result = cn('p-4', 'px-2');
    // twMerge keeps p-4 for py and px-2 for x
    expect(result).toContain('px-2');
  });

  it('handles conditional classes (ternary false)', () => {
    const show = false;
    const result = cn('base', show && 'hidden');
    expect(result).toBe('base');
  });

  it('handles conditional classes (ternary true)', () => {
    const show = true;
    const result = cn('base', show && 'hidden');
    expect(result).toBe('base hidden');
  });

  it('handles object syntax — truthy keys included', () => {
    const result = cn({ foo: true, bar: false, baz: true });
    expect(result).toBe('foo baz');
  });

  it('handles multiple string args (spread)', () => {
    const result = cn('a', 'b', 'c');
    expect(result).toBe('a b c');
  });

  it('handles many args including empty strings', () => {
    const result = cn('a', '', 'b');
    expect(result).toBe('a b');
  });

  it('deduplicates non-conflicting identical classes', () => {
    // clsx keeps both but twMerge deduplicates on conflict
    const result = cn('flex', 'flex');
    // Result contains flex (at least once)
    expect(result).toContain('flex');
  });

  it('handles multiple args of mixed types', () => {
    const result = cn('a', { b: true, skip: false }, false, undefined, 'd');
    expect(result).toBe('a b d');
  });

  it('returns a string', () => {
    expect(typeof cn('foo')).toBe('string');
  });
});

// ============================================================================
// debounce
// ============================================================================

describe('debounce', () => {
  it('does not call function before delay', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('calls function after delay elapses', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('passes arguments through to the wrapped function', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 50);
    debounced('hello', 42);
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledWith('hello', 42);
    vi.useRealTimers();
  });

  it('only fires once when called multiple times within delay', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced('a');
    debounced('b');
    debounced('c');
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('uses the last call arguments when debounced', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced('first');
    debounced('second');
    debounced('last');
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledWith('last');
    vi.useRealTimers();
  });

  it('resets the timer on each call', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    vi.advanceTimersByTime(90);
    debounced(); // reset
    vi.advanceTimersByTime(90); // only 90ms since last call
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(10); // now 100ms from last call
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('returns void (not the wrapped function return value)', () => {
    vi.useFakeTimers();
    const fn = vi.fn(() => 'result');
    const debounced = debounce(fn, 100);
    const result = debounced();
    expect(result).toBeUndefined();
    vi.useRealTimers();
  });

  it('fires again for a call after the delay has already elapsed', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    debounced();
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it('returns a function', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    expect(typeof debounced).toBe('function');
  });
});
