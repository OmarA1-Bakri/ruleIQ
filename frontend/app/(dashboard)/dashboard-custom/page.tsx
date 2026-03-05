'use client';

import { RefreshCw, Info } from 'lucide-react';
import { useState, useEffect } from 'react';
// @ts-ignore - react-grid-layout doesn't have proper types
import { type Layouts } from 'react-grid-layout';

import { CustomizableDashboard } from '@/components/dashboard/customizable-dashboard';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { AppSidebar } from '@/components/navigation/app-sidebar';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useDashboard } from '@/lib/tanstack-query/hooks';

// Mock data generator
function generateMockData() {
  return {
    compliance_score: 92,
    framework_scores: {
      'ISO 27001': 92,
      GDPR: 88,
      'Cyber Essentials': 95,
      'PCI DSS': 78,
      'SOC 2': 85,
    },
    insights: [
      {
        id: '1',
        type: 'recommendation',
        title: 'Update Access Control Policy',
        description:
          "Your access control policy hasn't been reviewed in 6 months. Consider updating it to reflect recent organizational changes.",
        priority: 'high',
        framework: 'ISO 27001',
      },
      {
        id: '2',
        type: 'achievement',
        title: 'GDPR Compliance Improved',
        description: 'Great job! Your GDPR compliance score has increased by 5% this month.',
        priority: 'medium',
        framework: 'GDPR',
      },
      {
        id: '3',
        type: 'alert',
        title: 'Encryption Certificate Expiring',
        description:
          'SSL certificate for api.company.com expires in 14 days. Renew to maintain security compliance.',
        priority: 'critical',
        framework: 'Cyber Essentials',
      },
    ],
    pending_tasks: [
      {
        id: '1',
        title: 'Complete annual risk assessment',
        framework: 'ISO 27001',
        dueDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        priority: 'high',
        assignee: 'John Doe',
      },
      {
        id: '2',
        title: 'Review data retention policies',
        framework: 'GDPR',
        dueDate: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
        priority: 'medium',
        assignee: 'Jane Smith',
      },
      {
        id: '3',
        title: 'Update incident response plan',
        framework: 'SOC 2',
        dueDate: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
        priority: 'critical',
        assignee: 'Security Team',
      },
    ],
    compliance_trends: Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString(),
      score: Math.floor(Math.random() * 20) + 75 + i * 0.5,
      target: 90,
    })),
    framework_breakdown: [
      { framework: 'ISO 27001', score: 92 },
      { framework: 'GDPR', score: 88 },
      { framework: 'Cyber Essentials', score: 95 },
      { framework: 'PCI DSS', score: 78 },
      { framework: 'SOC 2', score: 85 },
    ],
    activity_data: Array.from({ length: 84 }, (_, i) => ({
      week: `W${Math.floor(i / 7) + 1}`,
      day: i % 7,
      value: Math.floor(Math.random() * 10),
      activity: ['Policy Update', 'Assessment', 'Evidence Upload'][Math.floor(Math.random() * 3)],
    })),
    risks: [
      { id: '1', name: 'Data Breach', impact: 'high', likelihood: 'medium', category: 'Security' },
      {
        id: '2',
        name: 'Compliance Gap',
        impact: 'medium',
        likelihood: 'low',
        category: 'Compliance',
      },
      {
        id: '3',
        name: 'System Failure',
        impact: 'high',
        likelihood: 'low',
        category: 'Operational',
      },
      {
        id: '4',
        name: 'Vendor Risk',
        impact: 'medium',
        likelihood: 'medium',
        category: 'Third Party',
      },
    ],
    task_progress: [
      { category: 'Policies', completed: 18, total: 20 },
      { category: 'Assessments', completed: 12, total: 15 },
      { category: 'Evidence', completed: 45, total: 50 },
      { category: 'Training', completed: 8, total: 10 },
      { category: 'Reviews', completed: 5, total: 8 },
    ],
  };
}

export default function CustomDashboardPage() {
  const [dashboardData, setDashboardData] = useState(generateMockData());
  const {
    data: apiData,
    isLoading,
    error,
    refetch,
  } = useDashboard({
    refetchInterval: 5 * 60 * 1000,
    staleTime: 10 * 60 * 1000,
  });

  // Use API data if available, otherwise use mock data
  useEffect(() => {
    if (apiData) {
      // Merge API data with mock data structure
      setDashboardData({
        ...generateMockData(),
        compliance_score: (apiData as any).compliance_score || 0,
        framework_scores: (apiData as any).framework_scores || {},
        insights: (apiData as any).insights || [],
        pending_tasks: (apiData as any).pending_tasks || [],
        compliance_trends: (apiData as any).compliance_trends || generateMockData().compliance_trends,
      });
    }
  }, [apiData]);

  const handleLayoutChange = (_layouts: Layouts) => {
    // Save to localStorage or backend
  };

  const handleRefresh = () => {
    setDashboardData(generateMockData());
    refetch();
  };

  return (
    <div className="flex flex-1">
      <AppSidebar />
      <div className="flex-1 overflow-auto">
        <DashboardHeader />
        <div className="space-y-6 p-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-navy">Customizable Dashboard</h1>
              <p className="text-muted-foreground">
                Drag, drop, and resize widgets to create your perfect dashboard
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {/* Info Alert */}
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              <strong>Tip:</strong> Enable "Edit Mode" to customize your dashboard. You can drag
              widgets to rearrange, resize them by dragging corners, add new widgets, or remove ones
              you don't need.
            </AlertDescription>
          </Alert>

          {/* Error State */}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>
                {error instanceof Error ? error.message : 'Failed to load dashboard data'}
              </AlertDescription>
            </Alert>
          )}

          {/* Dashboard */}
          {isLoading ? (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <Skeleton className="h-[300px]" />
                <Skeleton className="h-[300px]" />
                <Skeleton className="h-[300px]" />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Skeleton className="h-[300px]" />
                <Skeleton className="h-[300px]" />
              </div>
            </div>
          ) : (
            <CustomizableDashboard data={dashboardData} onLayoutChange={handleLayoutChange} />
          )}
        </div>
      </div>
    </div>
  );
}
