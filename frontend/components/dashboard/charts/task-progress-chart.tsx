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
import { Progress } from '@/components/ui/progress';
import { silver, semantic, neutral } from '@/lib/theme/neural-purple-colors';

interface TaskProgressChartProps {
  data: Array<{
    category: string;
    completed: number;
    pending: number;
    overdue: number;
  }>;
  title?: string;
  description?: string;
  className?: string;
}

export function TaskProgressChart({
  data,
  title = 'Task Progress',
  description = 'Task completion status by category',
  className,
}: TaskProgressChartProps) {
  const COLORS = {
    completed: semantic.success,
    pending: semantic.warning,
    overdue: semantic.error,
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const total = payload.reduce((sum: number, entry: any) => sum + entry.value, 0);
      return (
        <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
          <p className="mb-2 text-sm font-semibold text-gray-900">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {entry.name}: <span className="font-semibold">{entry.value}</span>
            </p>
          ))}
          <p className="mt-2 border-t pt-2 text-sm font-semibold text-gray-900">Total: {total}</p>
        </div>
      );
    }
    return null;
  };

  // Calculate overall progress
  const totalCompleted = data.reduce((sum, item) => sum + item.completed, 0);
  const totalPending = data.reduce((sum, item) => sum + item.pending, 0);
  const totalOverdue = data.reduce((sum, item) => sum + item.overdue, 0);
  const totalTasks = totalCompleted + totalPending + totalOverdue;
  const completionRate = totalTasks > 0 ? Math.round((totalCompleted / totalTasks) * 100) : 0;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Overall Completion</span>
            <span className="font-semibold">{completionRate}%</span>
          </div>
          <Progress value={completionRate} className="h-2" />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{totalCompleted} completed</span>
            <span>{totalPending} pending</span>
            <span className="text-red-600">{totalOverdue} overdue</span>
          </div>
        </div>

        {/* Stacked Bar Chart */}
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="category"
              tick={{ fontSize: 12, fill: neutral.gray[600] }}
              axisLine={{ stroke: silver.light }}
            />
            <YAxis tick={{ fontSize: 12, fill: neutral.gray[600] }} axisLine={{ stroke: silver.light }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12 }} iconType="square" />
            <Bar dataKey="completed" stackId="a" fill={COLORS.completed} />
            <Bar dataKey="pending" stackId="a" fill={COLORS.pending} />
            <Bar dataKey="overdue" stackId="a" fill={COLORS.overdue} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
