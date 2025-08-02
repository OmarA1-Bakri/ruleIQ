import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import React from 'react';

import { cn } from '@/lib/utils';
import { NumberTicker } from '@/components/magicui/number-ticker';

interface MetricWidgetProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    trend: 'up' | 'down' | 'neutral';
  };
  suffix?: string;
  prefix?: string;
  description?: string;
  className?: string;
}

export function MetricWidget({
  title,
  value,
  change,
  suffix,
  prefix,
  description,
  className,
}: MetricWidgetProps) {
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
        return 'text-teal-600';
      case 'down':
        return 'text-red-600';
      default:
        return 'text-neutral-600';
    }
  };

  return (
    <div className={cn('space-y-3', className)}>
      <div className="space-y-1">
        <p className="text-sm font-medium text-neutral-600">{title}</p>
        <div className="flex items-baseline gap-2">
          <h3 className="text-3xl font-bold text-neutral-900">
            {prefix}
            {typeof value === 'number' ? (
              <NumberTicker value={value} className="text-3xl font-bold text-neutral-900" />
            ) : (
              value
            )}
            {suffix}
          </h3>
          {change && (
            <div className={cn('flex items-center gap-1 text-sm font-medium', getTrendColor())}>
              {getTrendIcon()}
              <span>{change.value}%</span>
            </div>
          )}
        </div>
      </div>
      {description && <p className="text-sm text-neutral-500">{description}</p>}
    </div>
  );
}
