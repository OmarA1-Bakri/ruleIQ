import { describe, it, expect } from 'vitest';
import { spacing, semanticSpacing, grid, isOnGrid } from '@/lib/styles/spacing';

// ============================================================================
// spacing scale
// ============================================================================

describe('spacing scale', () => {
  it('has 0 = "0"', () => {
    expect(spacing['0']).toBe('0');
  });

  it('has px = "1px"', () => {
    expect(spacing.px).toBe('1px');
  });

  it('has "2" = "0.5rem" (8px base unit)', () => {
    expect(spacing['2']).toBe('0.5rem');
  });

  it('has "4" = "1rem" (16px)', () => {
    expect(spacing['4']).toBe('1rem');
  });

  it('has "8" = "2rem" (32px)', () => {
    expect(spacing['8']).toBe('2rem');
  });

  it('has "16" = "4rem" (64px)', () => {
    expect(spacing['16']).toBe('4rem');
  });

  it('has "32" = "8rem" (128px)', () => {
    expect(spacing['32']).toBe('8rem');
  });

  it('has "0.5" = "0.125rem" (2px)', () => {
    expect(spacing['0.5']).toBe('0.125rem');
  });

  it('has "1" = "0.25rem" (4px)', () => {
    expect(spacing['1']).toBe('0.25rem');
  });

  it('all rem values are strings ending in rem or px', () => {
    Object.values(spacing).forEach((value) => {
      const isRemOrPxOrZero = value === '0' || value.endsWith('rem') || value.endsWith('px');
      expect(isRemOrPxOrZero).toBe(true);
    });
  });
});

// ============================================================================
// semanticSpacing
// ============================================================================

describe('semanticSpacing', () => {
  it('has button-sm = spacing["3"] (12px)', () => {
    expect(semanticSpacing['button-sm']).toBe(spacing['3']);
    expect(semanticSpacing['button-sm']).toBe('0.75rem');
  });

  it('has button-md = spacing["4"] (16px)', () => {
    expect(semanticSpacing['button-md']).toBe(spacing['4']);
    expect(semanticSpacing['button-md']).toBe('1rem');
  });

  it('has button-lg = spacing["6"] (24px)', () => {
    expect(semanticSpacing['button-lg']).toBe(spacing['6']);
    expect(semanticSpacing['button-lg']).toBe('1.5rem');
  });

  it('has card-padding = spacing["6"] (24px)', () => {
    expect(semanticSpacing['card-padding']).toBe(spacing['6']);
  });

  it('has card-gap = spacing["4"] (16px)', () => {
    expect(semanticSpacing['card-gap']).toBe(spacing['4']);
  });

  it('has section-gap = spacing["8"] (32px)', () => {
    expect(semanticSpacing['section-gap']).toBe(spacing['8']);
    expect(semanticSpacing['section-gap']).toBe('2rem');
  });

  it('has container-padding = spacing["6"] (24px)', () => {
    expect(semanticSpacing['container-padding']).toBe(spacing['6']);
  });

  it('has form-gap = spacing["4"] (16px)', () => {
    expect(semanticSpacing['form-gap']).toBe(spacing['4']);
  });

  it('has input-padding-x = spacing["3"] (12px)', () => {
    expect(semanticSpacing['input-padding-x']).toBe(spacing['3']);
  });

  it('has input-padding-y = spacing["2"] (8px)', () => {
    expect(semanticSpacing['input-padding-y']).toBe(spacing['2']);
    expect(semanticSpacing['input-padding-y']).toBe('0.5rem');
  });

  it('all values are strings', () => {
    Object.values(semanticSpacing).forEach((value) => {
      expect(typeof value).toBe('string');
    });
  });
});

// ============================================================================
// grid() function
// ============================================================================

describe('grid()', () => {
  it('returns "0rem" for multiplier 0', () => {
    expect(grid(0)).toBe('0rem');
  });

  it('returns "0.5rem" for multiplier 1 (8px base = 0.5rem)', () => {
    expect(grid(1)).toBe('0.5rem');
  });

  it('returns "1rem" for multiplier 2 (16px)', () => {
    expect(grid(2)).toBe('1rem');
  });

  it('returns "2rem" for multiplier 4 (32px)', () => {
    expect(grid(4)).toBe('2rem');
  });

  it('returns "4rem" for multiplier 8 (64px)', () => {
    expect(grid(8)).toBe('4rem');
  });

  it('returns a string ending in "rem"', () => {
    expect(grid(3)).toMatch(/rem$/);
  });

  it('scales linearly', () => {
    const result1 = parseFloat(grid(1));
    const result2 = parseFloat(grid(2));
    expect(result2).toBe(result1 * 2);
  });
});

// ============================================================================
// isOnGrid() function
// ============================================================================

describe('isOnGrid()', () => {
  it('returns true for "0.5rem" (8px)', () => {
    expect(isOnGrid('0.5rem')).toBe(true);
  });

  it('returns true for "1rem" (16px)', () => {
    expect(isOnGrid('1rem')).toBe(true);
  });

  it('returns true for "2rem" (32px)', () => {
    expect(isOnGrid('2rem')).toBe(true);
  });

  it('returns true for "3rem" (48px)', () => {
    expect(isOnGrid('3rem')).toBe(true);
  });

  it('returns false for "0.3rem" (4.8px, not on 8px grid)', () => {
    expect(isOnGrid('0.3rem')).toBe(false);
  });

  it('returns false for "0.25rem" (4px, not on 8px grid)', () => {
    expect(isOnGrid('0.25rem')).toBe(false);
  });

  it('returns false for px values (no rem suffix)', () => {
    expect(isOnGrid('8px')).toBe(false);
  });

  it('returns false for "0" (no rem suffix)', () => {
    expect(isOnGrid('0')).toBe(false);
  });

  it('returns true for "4rem" (64px)', () => {
    expect(isOnGrid('4rem')).toBe(true);
  });
});
