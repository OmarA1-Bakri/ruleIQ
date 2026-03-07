import { describe, it, expect } from 'vitest';
import {
  cn,
  getComplianceScoreStyle,
  getComplianceScoreColor,
  getButtonClassName,
  getStatusColor,
  buttonVariants,
  cardStyles,
  formStyles,
  statusStyles,
  complianceScoreStyles,
  animationClasses,
  shadowClasses,
  a11yStyles,
  responsiveStyles,
  ruleIQStyles,
} from '@/lib/ui-utils';

// ============================================================================
// cn() utility
// ============================================================================

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('combines multiple class strings', () => {
    const result = cn('text-sm', 'font-bold');
    expect(result).toContain('text-sm');
    expect(result).toContain('font-bold');
  });

  it('handles conditional classes with objects', () => {
    const result = cn({ 'text-red-500': true, 'text-blue-500': false });
    expect(result).toContain('text-red-500');
    expect(result).not.toContain('text-blue-500');
  });

  it('handles undefined/null values', () => {
    expect(cn('foo', undefined, null as any, 'bar')).toBe('foo bar');
  });

  it('returns empty string for no inputs', () => {
    expect(cn()).toBe('');
  });
});

// ============================================================================
// getComplianceScoreStyle
// ============================================================================

describe('getComplianceScoreStyle', () => {
  it('returns critical style for score <= 40', () => {
    expect(getComplianceScoreStyle(0)).toBe(complianceScoreStyles.critical);
    expect(getComplianceScoreStyle(40)).toBe(complianceScoreStyles.critical);
  });

  it('returns warning style for score 41-70', () => {
    expect(getComplianceScoreStyle(41)).toBe(complianceScoreStyles.warning);
    expect(getComplianceScoreStyle(70)).toBe(complianceScoreStyles.warning);
  });

  it('returns good style for score 71-90', () => {
    expect(getComplianceScoreStyle(71)).toBe(complianceScoreStyles.good);
    expect(getComplianceScoreStyle(90)).toBe(complianceScoreStyles.good);
  });

  it('returns excellent style for score > 90', () => {
    expect(getComplianceScoreStyle(91)).toBe(complianceScoreStyles.excellent);
    expect(getComplianceScoreStyle(100)).toBe(complianceScoreStyles.excellent);
  });
});

// ============================================================================
// getComplianceScoreColor
// ============================================================================

describe('getComplianceScoreColor', () => {
  it('returns red for score <= 40', () => {
    expect(getComplianceScoreColor(0)).toContain('red');
    expect(getComplianceScoreColor(40)).toContain('red');
  });

  it('returns amber for score 41-70', () => {
    expect(getComplianceScoreColor(41)).toContain('amber');
    expect(getComplianceScoreColor(70)).toContain('amber');
  });

  it('returns green for score 71-90', () => {
    expect(getComplianceScoreColor(71)).toContain('green');
    expect(getComplianceScoreColor(90)).toContain('green');
  });

  it('returns green-700 for score > 90', () => {
    expect(getComplianceScoreColor(91)).toBe('text-green-700');
    expect(getComplianceScoreColor(100)).toBe('text-green-700');
  });
});

// ============================================================================
// getButtonClassName
// ============================================================================

describe('getButtonClassName', () => {
  it('returns a string containing base classes', () => {
    const cls = getButtonClassName('primary', 'default');
    expect(cls).toContain('inline-flex');
    expect(cls).toContain('items-center');
  });

  it('includes variant classes for primary', () => {
    const cls = getButtonClassName('primary', 'default');
    expect(cls).toContain('bg-purple-600');
  });

  it('includes variant classes for destructive', () => {
    const cls = getButtonClassName('destructive', 'default');
    expect(cls).toContain('bg-error');
  });

  it('includes size classes for sm', () => {
    const cls = getButtonClassName('primary', 'sm');
    expect(cls).toContain('h-8');
  });

  it('includes size classes for lg', () => {
    const cls = getButtonClassName('primary', 'lg');
    expect(cls).toContain('h-12');
  });

  it('merges custom className', () => {
    const cls = getButtonClassName('primary', 'default', 'my-custom');
    expect(cls).toContain('my-custom');
  });

  it('works without className argument', () => {
    expect(() => getButtonClassName()).not.toThrow();
  });
});

// ============================================================================
// getStatusColor
// ============================================================================

describe('getStatusColor', () => {
  it('returns green for completed', () => {
    expect(getStatusColor('completed')).toContain('green');
  });

  it('returns blue for in-progress', () => {
    expect(getStatusColor('in-progress')).toContain('blue');
  });

  it('returns amber for pending', () => {
    expect(getStatusColor('pending')).toContain('amber');
  });

  it('returns red for overdue', () => {
    expect(getStatusColor('overdue')).toContain('red');
  });

  it('returns purple for active', () => {
    expect(getStatusColor('active')).toContain('purple');
  });

  it('returns gray for inactive', () => {
    expect(getStatusColor('inactive')).toContain('gray');
  });

  it('returns gray for unknown status', () => {
    expect(getStatusColor('unknown-status')).toBe('text-gray-600');
  });

  it('is case-insensitive', () => {
    expect(getStatusColor('COMPLETED')).toContain('green');
    expect(getStatusColor('Pending')).toContain('amber');
  });
});

// ============================================================================
// buttonVariants structure
// ============================================================================

describe('buttonVariants', () => {
  it('has a base string', () => {
    expect(typeof buttonVariants.base).toBe('string');
    expect(buttonVariants.base.length).toBeGreaterThan(0);
  });

  it('has all required variant keys', () => {
    const expectedVariants = ['primary', 'secondary', 'accent', 'outline', 'ghost', 'destructive', 'success', 'link'];
    expectedVariants.forEach((v) => {
      expect(buttonVariants.variants).toHaveProperty(v);
    });
  });

  it('has all required size keys', () => {
    const expectedSizes = ['sm', 'default', 'lg', 'xl', 'icon'];
    expectedSizes.forEach((s) => {
      expect(buttonVariants.sizes).toHaveProperty(s);
    });
  });
});

// ============================================================================
// cardStyles structure
// ============================================================================

describe('cardStyles', () => {
  it('has base class string', () => {
    expect(typeof cardStyles.base).toBe('string');
  });

  it('has header, content, footer, trust properties', () => {
    expect(cardStyles).toHaveProperty('header');
    expect(cardStyles).toHaveProperty('content');
    expect(cardStyles).toHaveProperty('footer');
    expect(cardStyles).toHaveProperty('trust');
  });
});

// ============================================================================
// statusStyles structure
// ============================================================================

describe('statusStyles', () => {
  it('has base class', () => {
    expect(typeof statusStyles.base).toBe('string');
  });

  it('has compliant and non-compliant variants', () => {
    expect(statusStyles.variants).toHaveProperty('compliant');
    expect(statusStyles.variants).toHaveProperty('non-compliant');
  });

  it('has pending, approved, rejected variants', () => {
    expect(statusStyles.variants).toHaveProperty('pending');
    expect(statusStyles.variants).toHaveProperty('approved');
    expect(statusStyles.variants).toHaveProperty('rejected');
  });
});

// ============================================================================
// animationClasses structure
// ============================================================================

describe('animationClasses', () => {
  it('has fadeIn class', () => {
    expect(animationClasses.fadeIn).toContain('animate');
  });

  it('has spin and pulse classes', () => {
    expect(animationClasses.spin).toContain('spin');
    expect(animationClasses.pulse).toContain('pulse');
  });

  it('has shimmer class', () => {
    expect(animationClasses.shimmer).toContain('shimmer');
  });
});

// ============================================================================
// a11yStyles
// ============================================================================

describe('a11yStyles', () => {
  it('has sr-only class', () => {
    expect(a11yStyles.srOnly).toBe('sr-only');
  });

  it('has not-sr-only class', () => {
    expect(a11yStyles.notSrOnly).toBe('not-sr-only');
  });
});

// ============================================================================
// responsiveStyles
// ============================================================================

describe('responsiveStyles', () => {
  it('has mobileOnly style', () => {
    expect(responsiveStyles.mobileOnly).toContain('block');
    expect(responsiveStyles.mobileOnly).toContain('md:hidden');
  });

  it('has tabletUp style', () => {
    expect(responsiveStyles.tabletUp).toContain('md:block');
  });
});

// ============================================================================
// ruleIQStyles (consolidated export)
// ============================================================================

describe('ruleIQStyles', () => {
  it('exports button, card, form, status namespaces', () => {
    expect(ruleIQStyles).toHaveProperty('button');
    expect(ruleIQStyles).toHaveProperty('card');
    expect(ruleIQStyles).toHaveProperty('form');
    expect(ruleIQStyles).toHaveProperty('status');
  });

  it('exports compliance, widget, nav, table namespaces', () => {
    expect(ruleIQStyles).toHaveProperty('compliance');
    expect(ruleIQStyles).toHaveProperty('widget');
    expect(ruleIQStyles).toHaveProperty('nav');
    expect(ruleIQStyles).toHaveProperty('table');
  });

  it('exports a11y, responsive, print namespaces', () => {
    expect(ruleIQStyles).toHaveProperty('a11y');
    expect(ruleIQStyles).toHaveProperty('responsive');
    expect(ruleIQStyles).toHaveProperty('print');
  });
});
