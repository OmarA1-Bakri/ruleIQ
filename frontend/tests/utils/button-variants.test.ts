import { describe, it, expect } from 'vitest';
import {
  ruleIQButtonConfig,
  getButtonStyles,
  type ButtonVariant,
  type ButtonSize,
} from '@/lib/button-variants';

describe('ruleIQButtonConfig', () => {
  it('defines all expected color variants', () => {
    const variants: ButtonVariant[] = [
      'primary',
      'secondary',
      'ghost',
      'accent',
      'success',
      'warning',
      'error',
    ];
    variants.forEach((v) => {
      expect(ruleIQButtonConfig.colors[v]).toBeDefined();
    });
  });

  it('defines all expected size variants', () => {
    const sizes: ButtonSize[] = ['small', 'medium', 'large'];
    sizes.forEach((s) => {
      expect(ruleIQButtonConfig.sizes[s]).toBeDefined();
    });
  });

  it('primary variant has background and text colors', () => {
    expect(ruleIQButtonConfig.colors.primary.background).toBeTruthy();
    expect(ruleIQButtonConfig.colors.primary.text).toBeTruthy();
  });

  it('secondary variant has border and hover config', () => {
    expect(ruleIQButtonConfig.colors.secondary.border).toBeTruthy();
    expect(ruleIQButtonConfig.colors.secondary.hover).toBeDefined();
  });

  it('small size has correct height', () => {
    expect(ruleIQButtonConfig.sizes.small.height).toBe('2rem');
  });

  it('medium size has correct height', () => {
    expect(ruleIQButtonConfig.sizes.medium.height).toBe('2.5rem');
  });

  it('large size has correct height', () => {
    expect(ruleIQButtonConfig.sizes.large.height).toBe('3rem');
  });

  it('defines transitions', () => {
    expect(ruleIQButtonConfig.transitions.default).toBeTruthy();
    expect(ruleIQButtonConfig.transitions.colors).toBeTruthy();
  });

  it('defines focus config', () => {
    expect(ruleIQButtonConfig.focus.ring).toBeTruthy();
    expect(ruleIQButtonConfig.focus.ringOffset).toBeTruthy();
    expect(ruleIQButtonConfig.focus.outline).toBe('none');
  });
});

describe('getButtonStyles', () => {
  it('returns color config for given variant', () => {
    const styles = getButtonStyles('primary', 'medium');
    expect(styles.color).toBeDefined();
    expect(styles.color).toEqual(ruleIQButtonConfig.colors.primary);
  });

  it('returns size config for given size', () => {
    const styles = getButtonStyles('primary', 'large');
    expect(styles.size).toBeDefined();
    expect(styles.size).toEqual(ruleIQButtonConfig.sizes.large);
  });

  it('returns transition string', () => {
    const styles = getButtonStyles('primary', 'small');
    expect(styles.transition).toBe(ruleIQButtonConfig.transitions.colors);
  });

  it('returns focus config', () => {
    const styles = getButtonStyles('primary', 'small');
    expect(styles.focus).toEqual(ruleIQButtonConfig.focus);
  });

  it('returns correct config for secondary small', () => {
    const styles = getButtonStyles('secondary', 'small');
    expect(styles.color).toEqual(ruleIQButtonConfig.colors.secondary);
    expect(styles.size).toEqual(ruleIQButtonConfig.sizes.small);
  });

  it('returns correct config for success large', () => {
    const styles = getButtonStyles('success', 'large');
    expect(styles.color).toEqual(ruleIQButtonConfig.colors.success);
    expect(styles.size).toEqual(ruleIQButtonConfig.sizes.large);
  });

  it('all variant+size combinations return valid styles', () => {
    const variants: ButtonVariant[] = ['primary', 'secondary', 'ghost', 'accent', 'success', 'warning', 'error'];
    const sizes: ButtonSize[] = ['small', 'medium', 'large'];

    variants.forEach((variant) => {
      sizes.forEach((size) => {
        const styles = getButtonStyles(variant, size);
        expect(styles.color).toBeDefined();
        expect(styles.size).toBeDefined();
        expect(styles.transition).toBeTruthy();
        expect(styles.focus).toBeDefined();
      });
    });
  });
});
