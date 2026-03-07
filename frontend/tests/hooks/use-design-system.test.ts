import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDesignSystem } from '@/hooks/use-design-system';

describe('useDesignSystem', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('defaults to teal design system', () => {
    const { result } = renderHook(() => useDesignSystem());
    expect(result.current.designSystem).toBe('teal');
  });

  it('defaults isNewTheme to true', () => {
    const { result } = renderHook(() => useDesignSystem());
    expect(result.current.isNewTheme).toBe(true);
  });

  it('loads saved preference from localStorage', () => {
    localStorage.setItem('design-system', 'legacy');
    const { result } = renderHook(() => useDesignSystem());
    expect(result.current.designSystem).toBe('legacy');
    expect(result.current.isNewTheme).toBe(false);
  });

  it('loads teal preference from localStorage', () => {
    localStorage.setItem('design-system', 'teal');
    const { result } = renderHook(() => useDesignSystem());
    expect(result.current.designSystem).toBe('teal');
    expect(result.current.isNewTheme).toBe(true);
  });

  it('ignores invalid localStorage values', () => {
    localStorage.setItem('design-system', 'invalid-value');
    const { result } = renderHook(() => useDesignSystem());
    // Falls back to default teal
    expect(result.current.designSystem).toBe('teal');
  });

  it('toggleDesignSystem switches from teal to legacy', () => {
    const { result } = renderHook(() => useDesignSystem());
    act(() => {
      result.current.toggleDesignSystem();
    });
    expect(result.current.designSystem).toBe('legacy');
    expect(result.current.isNewTheme).toBe(false);
  });

  it('toggleDesignSystem switches from legacy to teal', () => {
    localStorage.setItem('design-system', 'legacy');
    const { result } = renderHook(() => useDesignSystem());

    act(() => {
      result.current.toggleDesignSystem();
    });
    expect(result.current.designSystem).toBe('teal');
    expect(result.current.isNewTheme).toBe(true);
  });

  it('saves preference to localStorage after toggle', () => {
    const { result } = renderHook(() => useDesignSystem());

    act(() => {
      result.current.toggleDesignSystem();
    });

    expect(localStorage.getItem('design-system')).toBe('legacy');
  });

  it('persists teal preference to localStorage on mount', () => {
    renderHook(() => useDesignSystem());
    expect(localStorage.getItem('design-system')).toBe('teal');
  });

  it('exposes toggleDesignSystem as a function', () => {
    const { result } = renderHook(() => useDesignSystem());
    expect(typeof result.current.toggleDesignSystem).toBe('function');
  });
});
