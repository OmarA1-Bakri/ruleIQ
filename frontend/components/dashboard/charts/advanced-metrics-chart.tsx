'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { neuralPurple, silver } from '@/lib/theme/neural-purple-colors';

interface AdvancedMetricsChartProps {
  data: Array<{
    metric: string;
    value: number;
    target?: number;
    unit?: string;
  }>;
  title?: string;
  description?: string;
  className?: string;
}

export function AdvancedMetricsChart({
  data,
  title = 'Advanced Metrics',
  description = 'Key performance indicators and metrics',
  className,
}: AdvancedMetricsChartProps) {
  const formatValue = (value: number, unit?: string) => {
    if (unit === '%') return `${value}%`;
    if (unit === '$') return `$${value.toLocaleString()}`;
    return value.toLocaleString();
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="metric"
              tick={{ fontSize: 12 }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(value: number, name: string, props: any) => [
                formatValue(value, props?.payload?.unit),
                name,
              ]}
              labelStyle={{ color: '#8b5cf6' }}
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #c0c0c0',
                borderRadius: '4px',
              }}
            />
            <Legend />
            <Bar dataKey="value" fill={neuralPurple.primary} name="Current Value" radius={[4, 4, 0, 0]} />
            {data.some((item) => item.target) && (
              <Bar dataKey="target" fill={silver.DEFAULT} name="Target" radius={[4, 4, 0, 0]} />
            )}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
