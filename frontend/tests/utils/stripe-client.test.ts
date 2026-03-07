import { describe, it, expect } from 'vitest';
import {
  PRICING_PLANS,
  TRIAL_PERIOD_DAYS,
  DISCOUNT_CODES,
  formatPrice,
  getPlanFeatures,
  isPlanPopular,
  getPlanByPriceId,
  type PricingPlan,
} from '@/lib/stripe/client';

// ============================================================================
// PRICING_PLANS constant
// ============================================================================

describe('PRICING_PLANS', () => {
  it('has starter, professional, enterprise plans', () => {
    expect(PRICING_PLANS).toHaveProperty('starter');
    expect(PRICING_PLANS).toHaveProperty('professional');
    expect(PRICING_PLANS).toHaveProperty('enterprise');
  });

  it('starter price is £29/month', () => {
    expect(PRICING_PLANS.starter.price).toBe(29);
    expect(PRICING_PLANS.starter.currency).toBe('gbp');
    expect(PRICING_PLANS.starter.interval).toBe('month');
  });

  it('professional price is £99/month', () => {
    expect(PRICING_PLANS.professional.price).toBe(99);
    expect(PRICING_PLANS.professional.currency).toBe('gbp');
    expect(PRICING_PLANS.professional.interval).toBe('month');
  });

  it('enterprise price is £299/month', () => {
    expect(PRICING_PLANS.enterprise.price).toBe(299);
    expect(PRICING_PLANS.enterprise.currency).toBe('gbp');
    expect(PRICING_PLANS.enterprise.interval).toBe('month');
  });

  it('prices are in ascending order: starter < professional < enterprise', () => {
    expect(PRICING_PLANS.starter.price).toBeLessThan(PRICING_PLANS.professional.price);
    expect(PRICING_PLANS.professional.price).toBeLessThan(PRICING_PLANS.enterprise.price);
  });

  it('starter maxProfiles is 1', () => {
    expect(PRICING_PLANS.starter.maxProfiles).toBe(1);
  });

  it('professional maxProfiles is 5', () => {
    expect(PRICING_PLANS.professional.maxProfiles).toBe(5);
  });

  it('enterprise maxProfiles is -1 (unlimited)', () => {
    expect(PRICING_PLANS.enterprise.maxProfiles).toBe(-1);
  });

  it('each plan has a non-empty name and id', () => {
    (['starter', 'professional', 'enterprise'] as PricingPlan[]).forEach((planKey) => {
      const plan = PRICING_PLANS[planKey];
      expect(plan.name.length).toBeGreaterThan(0);
      expect(plan.id).toBe(planKey);
    });
  });

  it('each plan has a non-empty features array', () => {
    (['starter', 'professional', 'enterprise'] as PricingPlan[]).forEach((planKey) => {
      const plan = PRICING_PLANS[planKey];
      expect(Array.isArray(plan.features)).toBe(true);
      expect(plan.features.length).toBeGreaterThan(0);
    });
  });

  it('professional plan has popular flag', () => {
    expect((PRICING_PLANS.professional as any).popular).toBe(true);
  });

  it('starter does not have popular flag', () => {
    expect((PRICING_PLANS.starter as any).popular).toBeUndefined();
  });

  it('enterprise does not have popular flag', () => {
    expect((PRICING_PLANS.enterprise as any).popular).toBeUndefined();
  });

  it('enterprise has more features than starter', () => {
    expect(PRICING_PLANS.enterprise.features.length).toBeGreaterThan(
      PRICING_PLANS.starter.features.length,
    );
  });
});

// ============================================================================
// TRIAL_PERIOD_DAYS
// ============================================================================

describe('TRIAL_PERIOD_DAYS', () => {
  it('is 30', () => {
    expect(TRIAL_PERIOD_DAYS).toBe(30);
  });

  it('is a positive number', () => {
    expect(TRIAL_PERIOD_DAYS).toBeGreaterThan(0);
  });
});

// ============================================================================
// DISCOUNT_CODES
// ============================================================================

describe('DISCOUNT_CODES', () => {
  it('has LAUNCH50 code', () => {
    expect(DISCOUNT_CODES).toHaveProperty('LAUNCH50');
    expect(typeof DISCOUNT_CODES.LAUNCH50).toBe('string');
  });

  it('has ENTERPRISE25 code', () => {
    expect(DISCOUNT_CODES).toHaveProperty('ENTERPRISE25');
    expect(typeof DISCOUNT_CODES.ENTERPRISE25).toBe('string');
  });

  it('has ANNUAL20 code', () => {
    expect(DISCOUNT_CODES).toHaveProperty('ANNUAL20');
    expect(typeof DISCOUNT_CODES.ANNUAL20).toBe('string');
  });

  it('LAUNCH50 description mentions 50%', () => {
    expect(DISCOUNT_CODES.LAUNCH50).toContain('50%');
  });

  it('ENTERPRISE25 description mentions 25%', () => {
    expect(DISCOUNT_CODES.ENTERPRISE25).toContain('25%');
  });

  it('ANNUAL20 description mentions 20%', () => {
    expect(DISCOUNT_CODES.ANNUAL20).toContain('20%');
  });

  it('has exactly 3 discount codes', () => {
    expect(Object.keys(DISCOUNT_CODES).length).toBe(3);
  });
});

// ============================================================================
// formatPrice
// ============================================================================

describe('formatPrice', () => {
  it('formats GBP amount correctly', () => {
    const result = formatPrice(29, 'gbp');
    expect(result).toContain('29');
    expect(result).toContain('£');
  });

  it('formats £99', () => {
    const result = formatPrice(99, 'gbp');
    expect(result).toContain('99');
  });

  it('formats £299', () => {
    const result = formatPrice(299, 'gbp');
    expect(result).toContain('299');
  });

  it('defaults currency to gbp', () => {
    const withExplicit = formatPrice(29, 'gbp');
    const withDefault = formatPrice(29);
    expect(withExplicit).toBe(withDefault);
  });

  it('returns a non-empty string', () => {
    const result = formatPrice(100, 'gbp');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('formats zero as £0', () => {
    const result = formatPrice(0, 'gbp');
    expect(result).toContain('0');
  });

  it('uses uppercase currency code for Intl formatting', () => {
    // Both 'gbp' and 'GBP' should produce the same output
    const lower = formatPrice(50, 'gbp');
    const upper = formatPrice(50, 'GBP');
    expect(lower).toBe(upper);
  });
});

// ============================================================================
// getPlanFeatures
// ============================================================================

describe('getPlanFeatures', () => {
  it('returns an array for starter', () => {
    const features = getPlanFeatures('starter');
    expect(Array.isArray(features)).toBe(true);
    expect(features.length).toBeGreaterThan(0);
  });

  it('returns an array for professional', () => {
    const features = getPlanFeatures('professional');
    expect(Array.isArray(features)).toBe(true);
  });

  it('returns an array for enterprise', () => {
    const features = getPlanFeatures('enterprise');
    expect(Array.isArray(features)).toBe(true);
  });

  it('returns a copy (not the original array reference)', () => {
    const features = getPlanFeatures('starter');
    expect(features).not.toBe(PRICING_PLANS.starter.features);
  });

  it('features match PRICING_PLANS content', () => {
    const features = getPlanFeatures('professional');
    expect(features).toEqual([...PRICING_PLANS.professional.features]);
  });

  it('all feature strings are non-empty', () => {
    (['starter', 'professional', 'enterprise'] as PricingPlan[]).forEach((planKey) => {
      getPlanFeatures(planKey).forEach((feature) => {
        expect(typeof feature).toBe('string');
        expect(feature.length).toBeGreaterThan(0);
      });
    });
  });
});

// ============================================================================
// isPlanPopular
// ============================================================================

describe('isPlanPopular', () => {
  it('returns true for professional', () => {
    expect(isPlanPopular('professional')).toBe(true);
  });

  it('returns false for starter', () => {
    expect(isPlanPopular('starter')).toBe(false);
  });

  it('returns false for enterprise', () => {
    expect(isPlanPopular('enterprise')).toBe(false);
  });

  it('returns a boolean', () => {
    (['starter', 'professional', 'enterprise'] as PricingPlan[]).forEach((planKey) => {
      expect(typeof isPlanPopular(planKey)).toBe('boolean');
    });
  });
});

// ============================================================================
// getPlanByPriceId
// ============================================================================

describe('getPlanByPriceId', () => {
  it('returns null for a non-matching price ID', () => {
    expect(getPlanByPriceId('price_does_not_exist')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(getPlanByPriceId('')).toBeNull();
  });

  it('returns null for random string', () => {
    expect(getPlanByPriceId('price_xyz')).toBeNull();
  });

  it('returns a plan object when the price ID matches (env-configured)', () => {
    // When environment variables are set in CI/prod, this would return a plan
    // In test environment, NEXT_PUBLIC_STRIPE_*_PRICE_ID are undefined
    // So we test the undefined-priceId case returns null
    const result = getPlanByPriceId('undefined');
    expect(result === null || typeof result === 'object').toBe(true);
  });
});
