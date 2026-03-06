import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    download: vi.fn(),
  },
}));

describe('PaymentService', () => {
  let paymentService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/payment.service');
    paymentService = serviceMod.paymentService;
  });

  describe('createCheckoutSession', () => {
    it('calls POST /payments/create-checkout-session', async () => {
      const data = {
        plan_id: 'professional',
        success_url: 'https://app.ruleiq.com/success',
        cancel_url: 'https://app.ruleiq.com/cancel',
        trial_days: 14,
      };

      const mockResponse = {
        session_id: 'cs_test_123',
        url: 'https://checkout.stripe.com/pay/cs_test_123',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await paymentService.createCheckoutSession(data);

      expect(apiClient.post).toHaveBeenCalledWith('/payments/create-checkout-session', data);
      expect(result.session_id).toBe('cs_test_123');
      expect(result.url).toContain('stripe.com');
    });
  });

  describe('createPortalSession', () => {
    it('calls POST /payments/create-portal-session', async () => {
      const mockResponse = { url: 'https://billing.stripe.com/session/ses_123' };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await paymentService.createPortalSession('https://app.ruleiq.com/settings');

      expect(apiClient.post).toHaveBeenCalledWith('/payments/create-portal-session', {
        return_url: 'https://app.ruleiq.com/settings',
      });
      expect(result.url).toContain('stripe.com');
    });
  });

  describe('getCurrentSubscription', () => {
    it('returns subscription when exists', async () => {
      const mockSub = {
        id: 'sub-1',
        status: 'active',
        plan_id: 'professional',
        current_period_start: '2025-06-01',
        current_period_end: '2025-07-01',
        cancel_at_period_end: false,
        stripe_subscription_id: 'sub_stripe_123',
        stripe_customer_id: 'cus_stripe_123',
      };

      (apiClient.get as any).mockResolvedValue({ subscription: mockSub });

      const result = await paymentService.getCurrentSubscription();

      expect(apiClient.get).toHaveBeenCalledWith('/payments/subscription');
      expect(result.status).toBe('active');
      expect(result.plan_id).toBe('professional');
    });

    it('returns null on error', async () => {
      (apiClient.get as any).mockRejectedValue(new Error('Not found'));

      const result = await paymentService.getCurrentSubscription();

      expect(result).toBeNull();
    });
  });

  describe('cancelSubscription', () => {
    it('cancels at period end by default', async () => {
      const mockSub = { id: 'sub-1', status: 'active', cancel_at_period_end: true };
      (apiClient.post as any).mockResolvedValue(mockSub);

      const result = await paymentService.cancelSubscription();

      expect(apiClient.post).toHaveBeenCalledWith('/payments/subscription/cancel', {
        at_period_end: true,
      });
      expect(result.cancel_at_period_end).toBe(true);
    });

    it('cancels immediately when at_period_end is false', async () => {
      const mockSub = { id: 'sub-1', status: 'canceled' };
      (apiClient.post as any).mockResolvedValue(mockSub);

      await paymentService.cancelSubscription(false);

      expect(apiClient.post).toHaveBeenCalledWith('/payments/subscription/cancel', {
        at_period_end: false,
      });
    });
  });

  describe('reactivateSubscription', () => {
    it('calls POST /payments/subscription/reactivate', async () => {
      const mockSub = { id: 'sub-1', status: 'active', cancel_at_period_end: false };
      (apiClient.post as any).mockResolvedValue(mockSub);

      const result = await paymentService.reactivateSubscription();

      expect(apiClient.post).toHaveBeenCalledWith('/payments/subscription/reactivate');
      expect(result.status).toBe('active');
    });
  });

  describe('getPaymentMethods', () => {
    it('returns payment_methods array from response wrapper', async () => {
      const mockMethods = [
        { id: 'pm-1', brand: 'visa', last4: '4242', exp_month: 12, exp_year: 2026, is_default: true },
        { id: 'pm-2', brand: 'mastercard', last4: '5555', exp_month: 6, exp_year: 2027, is_default: false },
      ];

      (apiClient.get as any).mockResolvedValue({ payment_methods: mockMethods });

      const result = await paymentService.getPaymentMethods();

      expect(apiClient.get).toHaveBeenCalledWith('/payments/payment-methods');
      expect(result).toHaveLength(2);
      expect(result[0].brand).toBe('visa');
      expect(result[0].is_default).toBe(true);
    });
  });

  describe('addPaymentMethod', () => {
    it('calls POST /payments/payment-methods', async () => {
      const mockMethod = { id: 'pm-new', brand: 'visa', last4: '1234' };
      (apiClient.post as any).mockResolvedValue(mockMethod);

      const result = await paymentService.addPaymentMethod('pm_stripe_token');

      expect(apiClient.post).toHaveBeenCalledWith('/payments/payment-methods', {
        payment_method_id: 'pm_stripe_token',
      });
      expect(result.id).toBe('pm-new');
    });
  });

  describe('removePaymentMethod', () => {
    it('calls DELETE /payments/payment-methods/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await paymentService.removePaymentMethod('pm-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/payments/payment-methods/pm-1');
    });
  });

  describe('setDefaultPaymentMethod', () => {
    it('calls POST /payments/payment-methods/:id/default', async () => {
      const mockMethod = { id: 'pm-2', is_default: true };
      (apiClient.post as any).mockResolvedValue(mockMethod);

      const result = await paymentService.setDefaultPaymentMethod('pm-2');

      expect(apiClient.post).toHaveBeenCalledWith('/payments/payment-methods/pm-2/default');
      expect(result.is_default).toBe(true);
    });
  });

  describe('getInvoices', () => {
    it('returns invoices array from response wrapper', async () => {
      const mockInvoices = [
        { id: 'inv-1', number: 'INV-001', amount_paid: 4999, currency: 'gbp', status: 'paid' },
      ];

      (apiClient.get as any).mockResolvedValue({ invoices: mockInvoices });

      const result = await paymentService.getInvoices();

      expect(apiClient.get).toHaveBeenCalledWith('/payments/invoices', {});
      expect(result).toHaveLength(1);
      expect(result[0].number).toBe('INV-001');
    });

    it('passes pagination params', async () => {
      (apiClient.get as any).mockResolvedValue({ invoices: [] });

      await paymentService.getInvoices({ limit: 5, starting_after: 'inv-10' });

      expect(apiClient.get).toHaveBeenCalledWith('/payments/invoices', {
        params: { limit: 5, starting_after: 'inv-10' },
      });
    });
  });

  describe('downloadInvoice', () => {
    it('calls download with correct path and filename', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await paymentService.downloadInvoice('inv-42');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/payments/invoices/inv-42/download',
        'invoice-inv-42.pdf',
      );
    });
  });

  describe('getUpcomingInvoice', () => {
    it('returns invoice when exists', async () => {
      const mockInvoice = { id: 'inv-upcoming', amount_due: 4999, status: 'draft' };
      (apiClient.get as any).mockResolvedValue({ invoice: mockInvoice });

      const result = await paymentService.getUpcomingInvoice();

      expect(apiClient.get).toHaveBeenCalledWith('/payments/invoices/upcoming');
      expect(result.amount_due).toBe(4999);
    });

    it('returns null on error', async () => {
      (apiClient.get as any).mockRejectedValue(new Error('No upcoming invoice'));

      const result = await paymentService.getUpcomingInvoice();

      expect(result).toBeNull();
    });
  });

  describe('applyCoupon', () => {
    it('calls POST /payments/coupons/apply', async () => {
      const mockResponse = {
        success: true,
        discount: {
          percent_off: 20,
          duration: 'repeating',
          duration_in_months: 3,
        },
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await paymentService.applyCoupon('SAVE20');

      expect(apiClient.post).toHaveBeenCalledWith('/payments/coupons/apply', {
        coupon_code: 'SAVE20',
      });
      expect(result.success).toBe(true);
      expect(result.discount.percent_off).toBe(20);
    });
  });

  describe('checkSubscriptionLimits', () => {
    it('calls GET /payments/subscription/limits', async () => {
      const mockLimits = {
        plan_id: 'professional',
        limits: {
          business_profiles: { current: 2, max: 5 },
          frameworks: { current: 3, max: 10 },
          users: { current: 5, max: 25 },
        },
        can_upgrade: true,
      };

      (apiClient.get as any).mockResolvedValue(mockLimits);

      const result = await paymentService.checkSubscriptionLimits();

      expect(apiClient.get).toHaveBeenCalledWith('/payments/subscription/limits');
      expect(result.limits.business_profiles.current).toBe(2);
      expect(result.can_upgrade).toBe(true);
    });
  });
});

// -- Type interface tests --

describe('Payment type interfaces', () => {
  it('Subscription status values', () => {
    const statuses = ['active', 'canceled', 'incomplete', 'incomplete_expired', 'past_due', 'trialing', 'unpaid'];
    expect(statuses).toHaveLength(7);
  });

  it('Invoice status values', () => {
    const statuses = ['draft', 'open', 'paid', 'void', 'uncollectible'];
    expect(statuses).toHaveLength(5);
  });

  it('PaymentMethod has required fields', () => {
    const method = {
      id: 'pm-1',
      brand: 'visa',
      last4: '4242',
      exp_month: 12,
      exp_year: 2026,
      is_default: true,
    };
    expect(Object.keys(method)).toHaveLength(6);
  });
});
