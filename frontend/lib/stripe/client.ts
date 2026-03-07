import { loadStripe, type Stripe } from '@stripe/stripe-js';

// Ensure you have your Stripe publishable key in environment variables
const stripePublishableKey = process.env['NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY'];

if (!stripePublishableKey) {
  // intentionally empty - Stripe key not configured, will use null client
}

// Singleton pattern for Stripe instance
let stripePromise: Promise<Stripe | null>;

export const getStripe = () => {
  if (!stripePromise) {
    stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : Promise.resolve(null);
  }
  return stripePromise;
};

// Pricing plans for ruleIQ
export const PRICING_PLANS = {
  starter: {
    id: 'starter',
    name: 'Starter',
    price: 29,
    currency: 'gbp',
    interval: 'month' as const,
    stripePriceId: process.env['NEXT_PUBLIC_STRIPE_STARTER_PRICE_ID'],
    features: [
      '1 Business Profile',
      'Basic Compliance Assessment',
      'Framework Recommendations',
      'Standard Support',
      'Basic Reporting',
    ],
    maxProfiles: 1,
  },
  professional: {
    id: 'professional',
    name: 'Professional',
    price: 99,
    currency: 'gbp',
    interval: 'month' as const,
    stripePriceId: process.env['NEXT_PUBLIC_STRIPE_PROFESSIONAL_PRICE_ID'],
    popular: true,
    features: [
      '5 Business Profiles',
      'Advanced Compliance Assessment',
      'AI-Powered Recommendations',
      'Evidence Management',
      'Policy Generation',
      'Priority Support',
      'Advanced Reporting & Analytics',
    ],
    maxProfiles: 5,
  },
  enterprise: {
    id: 'enterprise',
    name: 'Enterprise',
    price: 299,
    currency: 'gbp',
    interval: 'month' as const,
    stripePriceId: process.env['NEXT_PUBLIC_STRIPE_ENTERPRISE_PRICE_ID'],
    features: [
      'Unlimited Business Profiles',
      'Full Compliance Suite',
      'Custom Framework Support',
      'Advanced Evidence Automation',
      'Custom Policy Templates',
      'Integration Management',
      'Dedicated Account Manager',
      'Custom Reporting',
      'SLA Guarantee',
    ],
    maxProfiles: -1, // Unlimited
  },
} as const;

export type PricingPlan = keyof typeof PRICING_PLANS;
export type PricingPlanDetails = (typeof PRICING_PLANS)[PricingPlan];

// Payment intent creation
export interface CreatePaymentIntentRequest {
  planId: PricingPlan;
  customerEmail: string;
  customerId?: string;
  businessProfileId?: string;
}

export interface CreateCheckoutSessionRequest {
  planId: PricingPlan;
  customerEmail: string;
  customerId?: string;
  businessProfileId?: string;
  successUrl: string;
  cancelUrl: string;
  trialDays?: number;
}

// Subscription management
export interface SubscriptionStatus {
  id: string;
  status:
    | 'active'
    | 'canceled'
    | 'incomplete'
    | 'incomplete_expired'
    | 'past_due'
    | 'trialing'
    | 'unpaid';
  planId: PricingPlan;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  trialEnd?: string;
}

// Customer portal session
export interface CreatePortalSessionRequest {
  customerId: string;
  returnUrl: string;
}

// Webhook event types
export type StripeWebhookEvent =
  | 'checkout.session.completed'
  | 'customer.subscription.created'
  | 'customer.subscription.updated'
  | 'customer.subscription.deleted'
  | 'invoice.payment_succeeded'
  | 'invoice.payment_failed';

// Utility functions
export const formatPrice = (amount: number, currency: string = 'gbp'): string => {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: currency.toUpperCase(),
    minimumFractionDigits: 0,
  }).format(amount);
};

export const getPlanFeatures = (planId: PricingPlan): string[] => {
  return [...(PRICING_PLANS[planId]?.features || [])];
};

export const isPlanPopular = (planId: PricingPlan): boolean => {
  return (PRICING_PLANS[planId] as any)?.popular === true;
};

export const getPlanByPriceId = (stripePriceId: string): PricingPlanDetails | null => {
  const plan = Object.values(PRICING_PLANS).find((plan) => plan.stripePriceId === stripePriceId);
  return plan || null;
};

// Trial period configuration (30 days)
export const TRIAL_PERIOD_DAYS = 30;

// Discount codes (can be managed in Stripe dashboard)
export const DISCOUNT_CODES = {
  LAUNCH50: 'Launch discount - 50% off first 3 months',
  ENTERPRISE25: 'Enterprise discount - 25% off',
  ANNUAL20: 'Annual billing - 20% off',
} as const;

export default getStripe;
