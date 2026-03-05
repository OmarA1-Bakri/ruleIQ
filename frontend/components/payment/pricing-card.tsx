'use client';

import { Check } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { PRICING_PLANS, type PricingPlan, formatPrice, isPlanPopular } from '@/lib/stripe/client';

interface PricingCardProps {
  planId: PricingPlan;
  onSelectPlan?: (planId: PricingPlan) => void;
  disabled?: boolean;
  currentPlan?: PricingPlan;
}

export function PricingCard({
  planId,
  onSelectPlan,
  disabled = false,
  currentPlan,
}: PricingCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const plan = PRICING_PLANS[planId];

  if (!plan) {
    return null;
  }

  const isCurrentPlan = currentPlan === planId;
  const isPopular = isPlanPopular(planId);

  const handleSelectPlan = async () => {
    if (disabled || isCurrentPlan) return;

    setIsLoading(true);

    try {
      if (onSelectPlan) {
        onSelectPlan(planId);
      } else {
        // Default behavior - redirect to checkout
        router.push(`/checkout?plan=${planId}`);
      }
    } catch (_error) {
    } finally {
      setIsLoading(false);
    }
  };

  const getButtonText = () => {
    if (isCurrentPlan) return 'Current Plan';
    if (planId === 'enterprise') return 'Contact Sales';
    return 'Start Free Trial';
  };

  return (
    <Card
      className={`relative transition-all duration-300 hover:shadow-lg ${
        isPopular ? 'scale-105 border-gold shadow-md' : 'border-border hover:border-gold/50'
      } ${isCurrentPlan ? 'bg-muted/50' : ''}`}
    >
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge className="bg-gold px-3 py-1 text-navy">Most Popular</Badge>
        </div>
      )}

      <CardHeader className="pb-2 text-center">
        <CardTitle className="text-2xl font-bold text-navy">{plan.name}</CardTitle>
        <div className="mt-4">
          <span className="text-4xl font-bold text-gold">{formatPrice(plan.price)}</span>
          <span className="text-lg text-muted-foreground">/{plan.interval}</span>
        </div>
        <CardDescription className="mt-2">
          {planId === 'starter' && 'Perfect for small businesses getting started with compliance'}
          {planId === 'professional' && 'Advanced features for growing businesses'}
          {planId === 'enterprise' && 'Complete solution for large organizations'}
        </CardDescription>
      </CardHeader>

      <CardContent className="pt-4">
        <div className="space-y-3">
          {plan.features.map((feature, index) => (
            <div key={index} className="flex items-start gap-3">
              <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-gold" />
              <span className="text-sm text-muted-foreground">{feature}</span>
            </div>
          ))}
        </div>
      </CardContent>

      <CardFooter className="pt-4">
        <Button
          className={`w-full ${
            isCurrentPlan
              ? 'bg-muted text-muted-foreground'
              : 'bg-gold text-navy hover:bg-gold-dark'
          }`}
          size="lg"
          onClick={handleSelectPlan}
          disabled={disabled || isLoading || isCurrentPlan}
        >
          {isLoading ? 'Loading...' : getButtonText()}
        </Button>

        {!isCurrentPlan && (
          <p className="mt-2 w-full text-center text-xs text-muted-foreground">
            30-day free trial • Cancel anytime
          </p>
        )}
      </CardFooter>
    </Card>
  );
}

// Pricing section component
interface PricingSectionProps {
  onSelectPlan?: (planId: PricingPlan) => void;
  currentPlan?: PricingPlan;
  showHeader?: boolean;
}

export function PricingSection({
  onSelectPlan,
  currentPlan,
  showHeader = true,
}: PricingSectionProps) {
  return (
    <div className="px-4 py-16">
      {showHeader && (
        <div className="mb-12 text-center">
          <h2 className="mb-4 text-3xl font-bold text-navy">Choose Your Plan</h2>
          <p className="mx-auto max-w-2xl text-xl text-muted-foreground">
            Start with a 30-day free trial. No credit card required.
          </p>
        </div>
      )}

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 md:grid-cols-3">
        <PricingCard
          planId="starter"
          {...(onSelectPlan && { onSelectPlan })}
          {...(currentPlan && { currentPlan })}
        />
        <PricingCard
          planId="professional"
          {...(onSelectPlan && { onSelectPlan })}
          {...(currentPlan && { currentPlan })}
        />
        <PricingCard
          planId="enterprise"
          {...(onSelectPlan && { onSelectPlan })}
          {...(currentPlan && { currentPlan })}
        />
      </div>

      <div className="mt-12 text-center">
        <div className="inline-flex items-center gap-8 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-gold" />
            <span>30-day free trial</span>
          </div>
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-gold" />
            <span>Cancel anytime</span>
          </div>
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-gold" />
            <span>No setup fees</span>
          </div>
        </div>
      </div>
    </div>
  );
}
