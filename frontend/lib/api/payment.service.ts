import { apiClient } from './client';

import type { PricingPlan } from '@/lib/stripe/client';

export interface PaymentMethod {
  id: string;
  brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
  is_default: boolean;
}

export interface Subscription {
  id: string;
  status:
    | 'active'
    | 'canceled'
    | 'incomplete'
    | 'incomplete_expired'
    | 'past_due'
    | 'trialing'
    | 'unpaid';
  plan_id: PricingPlan;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  trial_end?: string;
  stripe_subscription_id: string;
  stripe_customer_id: string;
}

export interface Invoice {
  id: string;
  number: string;
  amount_paid: number;
  amount_due: number;
  currency: string;
  status: 'draft' | 'open' | 'paid' | 'void' | 'uncollectible';
  created: string;
  due_date?: string;
  pdf_url?: string;
}

export interface CreateCheckoutSessionResponse {
  session_id: string;
  url: string;
}

export interface CreatePortalSessionResponse {
  url: string;
}

class PaymentService {
  /**
   * Create a Stripe checkout session for subscription
   */
  async createCheckoutSession(data: {
    plan_id: PricingPlan;
    success_url: string;
    cancel_url: string;
    trial_days?: number;
  }): Promise<CreateCheckoutSessionResponse> {
    const response = await apiClient.post<CreateCheckoutSessionResponse>(
      '/payments/create-checkout-session',
      data,
    );
    return response;
  }

  /**
   * Create a Stripe customer portal session
   */
  async createPortalSession(return_url: string): Promise<CreatePortalSessionResponse> {
    const response = await apiClient.post<CreatePortalSessionResponse>(
      '/payments/create-portal-session',
      { return_url },
    );
    return response;
  }

  /**
   * Get current subscription
   */
  async getCurrentSubscription(): Promise<Subscription | null> {
    try {
      const response = await apiClient.get<{ subscription: Subscription }>(
        '/payments/subscription',
      );
      return response.subscription;
    } catch (_error) {
      return null;
    }
  }

  /**
   * Cancel subscription
   */
  async cancelSubscription(at_period_end: boolean = true): Promise<Subscription> {
    const response = await apiClient.post<Subscription>('/payments/subscription/cancel', {
      at_period_end,
    });
    return response;
  }

  /**
   * Reactivate subscription
   */
  async reactivateSubscription(): Promise<Subscription> {
    const response = await apiClient.post<Subscription>('/payments/subscription/reactivate');
    return response;
  }

  /**
   * Get payment methods
   */
  async getPaymentMethods(): Promise<PaymentMethod[]> {
    const response = await apiClient.get<{ payment_methods: PaymentMethod[] }>(
      '/payments/payment-methods',
    );
    return response.payment_methods;
  }

  /**
   * Add payment method
   */
  async addPaymentMethod(payment_method_id: string): Promise<PaymentMethod> {
    const response = await apiClient.post<PaymentMethod>('/payments/payment-methods', {
      payment_method_id,
    });
    return response;
  }

  /**
   * Remove payment method
   */
  async removePaymentMethod(payment_method_id: string): Promise<void> {
    await apiClient.delete(`/payments/payment-methods/${payment_method_id}`);
  }

  /**
   * Set default payment method
   */
  async setDefaultPaymentMethod(payment_method_id: string): Promise<PaymentMethod> {
    const response = await apiClient.post<PaymentMethod>(
      `/payments/payment-methods/${payment_method_id}/default`,
    );
    return response;
  }

  /**
   * Get invoices
   */
  async getInvoices(params?: { limit?: number; starting_after?: string }): Promise<Invoice[]> {
    const response = await apiClient.get<{ invoices: Invoice[] }>('/payments/invoices', params ? { params } : {});
    return response.invoices;
  }

  /**
   * Download invoice
   */
  async downloadInvoice(invoice_id: string): Promise<void> {
    await apiClient.download(
      `/payments/invoices/${invoice_id}/download`,
      `invoice-${invoice_id}.pdf`,
    );
  }

  /**
   * Get upcoming invoice
   */
  async getUpcomingInvoice(): Promise<Invoice | null> {
    try {
      const response = await apiClient.get<{ invoice: Invoice }>('/payments/invoices/upcoming');
      return response.invoice;
    } catch (_error) {
      return null;
    }
  }

  /**
   * Apply coupon code
   */
  async applyCoupon(coupon_code: string): Promise<{
    success: boolean;
    discount?: {
      percent_off?: number;
      amount_off?: number;
      duration: 'forever' | 'once' | 'repeating';
      duration_in_months?: number;
    };
  }> {
    const response = await apiClient.post<any>('/payments/coupons/apply', { coupon_code });
    return response;
  }

  /**
   * Check subscription limits
   */
  async checkSubscriptionLimits(): Promise<{
    plan_id: PricingPlan;
    limits: {
      business_profiles: {
        current: number;
        max: number;
      };
      frameworks: {
        current: number;
        max: number;
      };
      users: {
        current: number;
        max: number;
      };
    };
    can_upgrade: boolean;
  }> {
    const response = await apiClient.get<any>('/payments/subscription/limits');
    return response;
  }
}

export const paymentService = new PaymentService();
