import { describe, it, expect } from 'vitest';
import { animationPresets } from '@/lib/animations/index';

// ============================================================================
// animationPresets.easing
// ============================================================================

describe('animationPresets.easing', () => {
  it('easeOut is an array of 4 numbers', () => {
    expect(Array.isArray(animationPresets.easing.easeOut)).toBe(true);
    expect(animationPresets.easing.easeOut.length).toBe(4);
    animationPresets.easing.easeOut.forEach((v) => expect(typeof v).toBe('number'));
  });

  it('easeIn is an array of 4 numbers', () => {
    expect(Array.isArray(animationPresets.easing.easeIn)).toBe(true);
    expect(animationPresets.easing.easeIn.length).toBe(4);
  });

  it('easeInOut is an array of 4 numbers', () => {
    expect(Array.isArray(animationPresets.easing.easeInOut)).toBe(true);
    expect(animationPresets.easing.easeInOut.length).toBe(4);
  });

  it('spring is an object with type, stiffness, damping', () => {
    expect(animationPresets.easing.spring).toHaveProperty('type', 'spring');
    expect(animationPresets.easing.spring).toHaveProperty('stiffness', 300);
    expect(animationPresets.easing.spring).toHaveProperty('damping', 30);
  });

  it('easeOut starts with 0.16', () => {
    expect(animationPresets.easing.easeOut[0]).toBe(0.16);
  });

  it('easeIn starts with 0.4', () => {
    expect(animationPresets.easing.easeIn[0]).toBe(0.4);
  });

  it('easeInOut starts with 0.4', () => {
    expect(animationPresets.easing.easeInOut[0]).toBe(0.4);
  });
});

// ============================================================================
// animationPresets.duration
// ============================================================================

describe('animationPresets.duration', () => {
  it('fast = 0.2', () => {
    expect(animationPresets.duration.fast).toBe(0.2);
  });

  it('normal = 0.3', () => {
    expect(animationPresets.duration.normal).toBe(0.3);
  });

  it('slow = 0.5', () => {
    expect(animationPresets.duration.slow).toBe(0.5);
  });

  it('fast < normal < slow', () => {
    expect(animationPresets.duration.fast).toBeLessThan(animationPresets.duration.normal);
    expect(animationPresets.duration.normal).toBeLessThan(animationPresets.duration.slow);
  });

  it('all durations are positive numbers', () => {
    Object.values(animationPresets.duration).forEach((v) => {
      expect(typeof v).toBe('number');
      expect(v).toBeGreaterThan(0);
    });
  });
});

// ============================================================================
// animationPresets.stagger
// ============================================================================

describe('animationPresets.stagger', () => {
  it('fast = 0.05', () => {
    expect(animationPresets.stagger.fast).toBe(0.05);
  });

  it('normal = 0.1', () => {
    expect(animationPresets.stagger.normal).toBe(0.1);
  });

  it('slow = 0.15', () => {
    expect(animationPresets.stagger.slow).toBe(0.15);
  });

  it('fast < normal < slow', () => {
    expect(animationPresets.stagger.fast).toBeLessThan(animationPresets.stagger.normal);
    expect(animationPresets.stagger.normal).toBeLessThan(animationPresets.stagger.slow);
  });

  it('all stagger values are positive numbers', () => {
    Object.values(animationPresets.stagger).forEach((v) => {
      expect(typeof v).toBe('number');
      expect(v).toBeGreaterThan(0);
    });
  });
});

// ============================================================================
// animationPresets structure
// ============================================================================

describe('animationPresets structure', () => {
  it('has easing, duration, stagger top-level keys', () => {
    expect(animationPresets).toHaveProperty('easing');
    expect(animationPresets).toHaveProperty('duration');
    expect(animationPresets).toHaveProperty('stagger');
  });

  it('easing has 4 keys: easeOut, easeIn, easeInOut, spring', () => {
    const keys = Object.keys(animationPresets.easing);
    expect(keys).toContain('easeOut');
    expect(keys).toContain('easeIn');
    expect(keys).toContain('easeInOut');
    expect(keys).toContain('spring');
    expect(keys.length).toBe(4);
  });

  it('duration has 3 keys: fast, normal, slow', () => {
    const keys = Object.keys(animationPresets.duration);
    expect(keys).toContain('fast');
    expect(keys).toContain('normal');
    expect(keys).toContain('slow');
    expect(keys.length).toBe(3);
  });

  it('stagger has 3 keys: fast, normal, slow', () => {
    const keys = Object.keys(animationPresets.stagger);
    expect(keys).toContain('fast');
    expect(keys).toContain('normal');
    expect(keys).toContain('slow');
    expect(keys.length).toBe(3);
  });
});
