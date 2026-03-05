'use client';

import { CreditCard, Download, AlertCircle, CheckCircle, Calendar, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { paymentService } from '@/lib/api/payment.service';
import { PRICING_PLANS, formatPrice } from '@/lib/stripe/client';

import type { Subscription, PaymentMethod, Invoice } from '@/lib/api/payment.service';

export default function BillingPage() {
  const [loading, setLoading] = useState(true);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [upcomingInvoice, setUpcomingInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBillingData();
  }, []);

  const fetchBillingData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all billing data in parallel
      const [sub, methods, inv, upcoming] = await Promise.all([
        paymentService.getCurrentSubscription(),
        paymentService.getPaymentMethods(),
        paymentService.getInvoices({ limit: 10 }),
        paymentService.getUpcomingInvoice(),
      ]);

      setSubscription(sub);
      setPaymentMethods(methods);
      setInvoices(inv);
      setUpcomingInvoice(upcoming);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing information');
    } finally {
      setLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    try {
      const response = await paymentService.createPortalSession(window.location.href);
      window.location.href = response.url;
    } catch (_error) {
    }
  };

  const handleCancelSubscription = async () => {
    if (
      !confirm(
        'Are you sure you want to cancel your subscription? You will still have access until the end of your billing period.',
      )
    ) {
      return;
    }

    try {
      await paymentService.cancelSubscription(true);
      await fetchBillingData();
    } catch (_error) {
    }
  };

  const handleReactivateSubscription = async () => {
    try {
      await paymentService.reactivateSubscription();
      await fetchBillingData();
    } catch (_error) {
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="border-success/40 bg-success/20 text-success">Active</Badge>;
      case 'trialing':
        return <Badge className="border-blue-500/40 bg-blue-500/20 text-blue-700">Trial</Badge>;
      case 'past_due':
        return (
          <Badge className="border-amber-500/40 bg-amber-500/20 text-amber-700">Past Due</Badge>
        );
      case 'canceled':
        return <Badge className="border-gray-500/40 bg-gray-500/20 text-gray-700">Canceled</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="flex-1 space-y-8 p-8">
        <div>
          <h1 className="text-3xl font-bold text-navy">Billing & Subscription</h1>
          <p className="text-muted-foreground">Manage your subscription and billing information</p>
        </div>
        <div className="grid gap-6">
          <Skeleton className="h-48" />
          <Skeleton className="h-64" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const plan = subscription ? PRICING_PLANS[subscription.plan_id] : null;

  return (
    <div className="flex-1 space-y-8 p-8">
      <div>
        <h1 className="text-3xl font-bold text-navy">Billing & Subscription</h1>
        <p className="text-muted-foreground">Manage your subscription and billing information</p>
      </div>

      {/* Current Subscription */}
      <Card>
        <CardHeader>
          <CardTitle>Current Subscription</CardTitle>
          <CardDescription>Your active plan and billing details</CardDescription>
        </CardHeader>
        <CardContent>
          {subscription ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold">{plan?.name} Plan</h3>
                  <p className="text-muted-foreground">{formatPrice(plan?.price || 0)}/month</p>
                </div>
                {getStatusBadge(subscription.status)}
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Current Period</p>
                  <p className="font-medium">
                    {new Date(subscription.current_period_start).toLocaleDateString()} -{' '}
                    {new Date(subscription.current_period_end).toLocaleDateString()}
                  </p>
                </div>
                {subscription.trial_end && (
                  <div>
                    <p className="text-muted-foreground">Trial Ends</p>
                    <p className="font-medium">
                      {new Date(subscription.trial_end).toLocaleDateString()}
                    </p>
                  </div>
                )}
              </div>

              {subscription.cancel_at_period_end && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    Your subscription will end on{' '}
                    {new Date(subscription.current_period_end).toLocaleDateString()}
                  </AlertDescription>
                </Alert>
              )}

              <div className="flex gap-3">
                <Button
                  onClick={handleManageSubscription}
                  className="bg-gold text-navy hover:bg-gold-dark"
                >
                  <CreditCard className="mr-2 h-4 w-4" />
                  Manage Subscription
                </Button>
                {subscription.status === 'active' && !subscription.cancel_at_period_end && (
                  <Button variant="outline" onClick={handleCancelSubscription}>
                    Cancel Subscription
                  </Button>
                )}
                {subscription.cancel_at_period_end && (
                  <Button variant="outline" onClick={handleReactivateSubscription}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Reactivate
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="py-8 text-center">
              <p className="mb-4 text-muted-foreground">No active subscription</p>
              <Button asChild className="bg-gold text-navy hover:bg-gold-dark">
                <a href="/pricing">View Plans</a>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Payment Methods */}
      <Card>
        <CardHeader>
          <CardTitle>Payment Methods</CardTitle>
          <CardDescription>Manage your payment methods</CardDescription>
        </CardHeader>
        <CardContent>
          {paymentMethods.length > 0 ? (
            <div className="space-y-3">
              {paymentMethods.map((method) => (
                <div
                  key={method.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <CreditCard className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">
                        {method.brand} •••• {method.last4}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Expires {method.exp_month}/{method.exp_year}
                      </p>
                    </div>
                  </div>
                  {method.is_default && <Badge variant="secondary">Default</Badge>}
                </div>
              ))}
            </div>
          ) : (
            <p className="py-4 text-center text-muted-foreground">No payment methods on file</p>
          )}
          <Button className="mt-4" variant="outline" onClick={handleManageSubscription}>
            Manage Payment Methods
          </Button>
        </CardContent>
      </Card>

      {/* Billing History */}
      <Card>
        <CardHeader>
          <CardTitle>Billing History</CardTitle>
          <CardDescription>Your past invoices and receipts</CardDescription>
        </CardHeader>
        <CardContent>
          {upcomingInvoice && (
            <Alert className="mb-4">
              <Calendar className="h-4 w-4" />
              <AlertDescription>
                Next invoice: {formatPrice(upcomingInvoice.amount_due / 100)} due on{' '}
                {upcomingInvoice.due_date
                  ? new Date(upcomingInvoice.due_date).toLocaleDateString()
                  : 'next billing date'}
              </AlertDescription>
            </Alert>
          )}

          {invoices.length > 0 ? (
            <div className="space-y-2">
              {invoices.map((invoice) => (
                <div
                  key={invoice.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <p className="font-medium">Invoice #{invoice.number || invoice.id.slice(-8)}</p>
                    <p className="text-sm text-muted-foreground">
                      {new Date(invoice.created).toLocaleDateString()} •{' '}
                      {formatPrice(invoice.amount_paid / 100)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {invoice.status === 'paid' && <CheckCircle className="h-4 w-4 text-success" />}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => paymentService.downloadInvoice(invoice.id)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-4 text-center text-muted-foreground">No invoices yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
