'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import React from 'react';

import { cn } from '@/lib/utils';
import { NumberTicker } from '@/components/magicui/number-ticker';
import { MagicCard } from '@/components/magicui/magic-card';

interface EnhancedMetricCardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    trend: 'up' | 'down' | 'neutral';
  };
  suffix?: string;
  prefix?: string;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
  gradient?: boolean;
}

export function EnhancedMetricCard({
  title,
  value,
  change,
  suffix,
  prefix,
  description,
  icon,
  className,
  gradient = true,
}: EnhancedMetricCardProps) {
  const getTrendIcon = () => {
    if (!change) return null;

    switch (change.trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4" />;
      case 'down':
        return <TrendingDown className="h-4 w-4" />;
      default:
        return <Minus className="h-4 w-4" />;
    }
  };

  const getTrendColor = () => {
    if (!change) return '';

    switch (change.trend) {
      case 'up':
        return 'text-emerald-600';
      case 'down':
        return 'text-red-600';
      default:
        return 'text-neutral-600';
    }
  };

  return (
    <MagicCard
      className={cn(
        'cursor-pointer flex-col items-start justify-start p-6 shadow-2xl',
        gradient && 'bg-gradient-to-br from-white to-teal-50/30',
        className
      )}
      gradientColor="#2C7A7B"
    >
      <div className="w-full space-y-4">
        {/* Header with icon and title */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-100 text-teal-600">
                {icon}
              </div>
            )}
            <p className="text-sm font-medium text-neutral-600">{title}</p>
          </div>
          {change && (
            <div className={cn('flex items-center gap-1 text-sm font-medium', getTrendColor())}>
              {getTrendIcon()}
              <span>{change.value}%</span>
            </div>
          )}
        </div>

        {/* Main value */}
        <div className="space-y-1">
          <div className="flex items-baseline gap-1">
            <h3 className="text-3xl font-bold text-neutral-900">
              {prefix}
              {typeof value === 'number' ? (
                <NumberTicker 
                  value={value} 
                  className="text-3xl font-bold text-neutral-900" 
                />
              ) : (
                value
              )}
              {suffix}
            </h3>
          </div>
          
          {description && (
            <p className="text-sm text-neutral-500">{description}</p>
          )}
        </div>
      </div>
    </MagicCard>
  );
}
