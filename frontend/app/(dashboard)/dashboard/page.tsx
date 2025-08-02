'use client';

import { Shield, AlertTriangle, Brain, FileCheck, RefreshCw, AlertCircle } from 'lucide-react';
import * as React from 'react';

import { AIInsightsWidget } from '@/components/dashboard/ai-insights-widget';
import {
  ComplianceTrendChart,
  FrameworkBreakdownChart,
  ActivityHeatmap,
  RiskMatrix,
  TaskProgressChart,
} from '@/components/dashboard/charts';
import { ComplianceScoreWidget } from '@/components/dashboard/compliance-score-widget';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { DataTable } from '@/components/dashboard/data-table';
import { EnhancedStatsCard } from '@/components/dashboard/enhanced-stats-card';
import { EnhancedMetricCard } from '@/components/dashboard/enhanced-metric-card';
import { PendingTasksWidget } from '@/components/dashboard/pending-tasks-widget';
import { QuickActionsWidget } from '@/components/dashboard/quick-actions';
import { AppSidebar } from '@/components/navigation/app-sidebar';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useDashboard } from '@/lib/tanstack-query/hooks';
import { safeGetFromStorage } from '@/lib/utils/type-safety';

// Mock data generation functions
function generateMockTrendData() {
  const data = [];
  const today = new Date();
  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    data.push({
      date: date.toISOString(),
      score: Math.floor(Math.random() * 20) + 75 + (30 - i) * 0.5,
      target: 90,
    });
  }
  return data;
}

function generateMockFrameworkData() {
  return [
    { framework: 'ISO 27001', score: 92 },
    { framework: 'GDPR', score: 88 },
    { framework: 'Cyber Essentials', score: 95 },
    { framework: 'PCI DSS', score: 78 },
    { framework: 'SOC 2', score: 85 },
  ];
}

function generateMockTaskData() {
  return [
    { category: 'Policies', completed: 18, total: 20 },
    { category: 'Assessments', completed: 12, total: 15 },
    { category: 'Evidence', completed: 45, total: 50 },
    { category: 'Training', completed: 8, total: 10 },
    { category: 'Reviews', completed: 5, total: 8 },
  ];
}

function generateMockRiskData() {
  return [
    { id: '1', name: 'Data Breach', impact: 'high', likelihood: 'medium', category: 'Security' },
    {
      id: '2',
      name: 'Compliance Violation',
      impact: 'high',
      likelihood: 'low',
      category: 'Compliance',
    },
    {
      id: '3',
      name: 'System Downtime',
      impact: 'medium',
      likelihood: 'medium',
      category: 'Operational',
    },
    { id: '4', name: 'Third-party Risk', impact: 'medium', likelihood: 'high', category: 'Vendor' },
    { id: '5', name: 'Insider Threat', impact: 'high', likelihood: 'low', category: 'Security' },
    {
      id: '6',
      name: 'Regulatory Change',
      impact: 'medium',
      likelihood: 'medium',
      category: 'Compliance',
    },
  ];
}

function generateMockActivityData() {
  const data = [];
  const activities = ['Policy Update', 'Assessment', 'Evidence Upload', 'Review', 'Training'];
  for (let week = 0; week < 12; week++) {
    for (let day = 0; day < 7; day++) {
      data.push({
        week: `W${week + 1}`,
        day,
        value: Math.floor(Math.random() * 10),
        activity: activities[Math.floor(Math.random() * activities.length)],
      });
    }
  }
  return data;
}

export default function Dashboard() {
  // Use TanStack Query hook
  const {
    data: dashboardData,
    isLoading,
    error,
    refetch,
  } = useDashboard({
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
    staleTime: 10 * 60 * 1000, // Consider data stale after 10 minutes
  });

  // Get compliance profile from localStorage (set during AI-guided signup)
  const [complianceProfile, setComplianceProfile] = React.useState<{
    priorities?: string[];
    maturityLevel?: string;
  } | null>(null);
  const [onboardingData, setOnboardingData] = React.useState<{
    fullName?: string;
    timeline?: string;
  } | null>(null);

  React.useEffect(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      const profile = safeGetFromStorage('ruleiq_compliance_profile');
      const onboarding = safeGetFromStorage('ruleiq_onboarding_data');
      if (profile) setComplianceProfile(profile);
      if (onboarding) setOnboardingData(onboarding);
    }
  }, []);

  // Default chart data for when API doesn't provide historical data
  const complianceData = dashboardData?.compliance_trends
    ?.slice(-7)
    .map((t: { score: number }) => t.score) || [85, 87, 89, 92, 88, 95, 98];
  const alertsData = [12, 8, 15, 6, 9, 4, 3];
  const insightsData = [3, 5, 2, 8, 6, 9, 7];
  const tasksData = [120, 135, 128, 142, 138, 145, 142];

  return (
    <div className="flex flex-1">
      <AppSidebar />
      <div className="flex-1 overflow-auto bg-gradient-to-br from-neutral-50 to-white">
        <div className="bg-white border-b border-neutral-200 shadow-sm">
          <DashboardHeader />
        </div>
        <div className="space-y-8 p-6">
          {/* Page Header with Refresh */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="gradient-text text-3xl font-bold">
                Welcome back
                {onboardingData?.fullName ? `, ${onboardingData.fullName.split(' ')[0]}` : ''}
              </h1>
              <p className="text-muted-foreground">
                {complianceProfile?.priorities && complianceProfile.priorities.length > 0
                  ? `Focusing on: ${complianceProfile.priorities[0]}`
                  : "Here's what's happening with your compliance today"}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading}
              className="border-glass-border hover:border-glass-border-hover hover:bg-glass-white"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {/* Error State */}
          {error && (
            <Alert variant="destructive" className="rounded-xl border-red-200 bg-red-50 shadow-sm">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {error instanceof Error ? error.message : 'Failed to load dashboard data'}
              </AlertDescription>
            </Alert>
          )}

          {/* Dashboard Stats */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {isLoading ? (
              // Loading skeletons
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[180px]" />)
            ) : (
              <>
                <EnhancedMetricCard
                  title="Compliance Score"
                  value={dashboardData?.compliance_score || 92}
                  suffix="%"
                  description="Overall compliance health"
                  icon={<Shield className="h-5 w-5" />}
                  change={{ value: 8, trend: 'up' }}
                  gradient={true}
                />
                <EnhancedMetricCard
                  title="Active Alerts"
                  value={dashboardData?.active_alerts || 3}
                  description="Requires immediate attention"
                  icon={<AlertTriangle className="h-5 w-5" />}
                  change={{ value: 23, trend: 'down' }}
                  gradient={true}
                />
                <EnhancedMetricCard
                  title="AI Insights"
                  value={dashboardData?.ai_insights_count || 12}
                  description="New recommendations this week"
                  icon={<Brain className="h-5 w-5" />}
                  change={{ value: 15, trend: 'up' }}
                  gradient={true}
                />
                <EnhancedMetricCard
                  title="Tasks Completed"
                  value={`${dashboardData?.tasks_completed || 24}/${dashboardData?.total_tasks || 30}`}
                  description="This month's progress"
                  icon={<FileCheck className="h-5 w-5" />}
                  change={{ value: 12, trend: 'up' }}
                  gradient={true}
                />
              </>
            )}
          </div>

          {/* Dashboard Widgets */}
          <div className="grid gap-8 lg:grid-cols-3">
            {/* AI Insights Widget */}
            {isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <AIInsightsWidget
                insights={dashboardData?.insights || []}
                complianceProfile={complianceProfile || { priorities: [], maturityLevel: '' }}
                onboardingData={onboardingData || { fullName: '', timeline: '' }}
              />
            )}

            {/* Compliance Score Widget */}
            {isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <ComplianceScoreWidget
                data={{
                  overall_score: dashboardData?.compliance_score || 0,
                  trend: 'up',
                  last_updated: new Date().toISOString(),
                  frameworks: dashboardData?.framework_scores || [],
                }}
              />
            )}

            {/* Pending Tasks Widget */}
            {isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <PendingTasksWidget tasks={dashboardData?.pending_tasks || []} />
            )}
          </div>

          {/* Quick Actions Widget - Full Width */}
          <div className="w-full">
            {isLoading ? <Skeleton className="h-[200px]" /> : <QuickActionsWidget />}
          </div>

          {/* Charts Section */}
          <div className="grid gap-8 lg:grid-cols-2">
            {/* Compliance Trend Chart */}
            {isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <ComplianceTrendChart
                data={dashboardData?.compliance_trends || generateMockTrendData()}
              />
            )}

            {/* Framework Breakdown Chart */}
            {isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <FrameworkBreakdownChart
                data={
                  dashboardData?.framework_scores
                    ? Object.entries(dashboardData.framework_scores).map(([framework, score]) => ({
                        framework,
                        score: score as number,
                      }))
                    : generateMockFrameworkData()
                }
              />
            )}
          </div>

          {/* Second Row of Charts */}
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Task Progress Chart */}
            {isLoading ? (
              <Skeleton className="h-[300px]" />
            ) : (
              <TaskProgressChart data={dashboardData?.task_progress || generateMockTaskData()} />
            )}

            {/* Risk Matrix */}
            {isLoading ? (
              <Skeleton className="h-[300px]" />
            ) : (
              <RiskMatrix risks={dashboardData?.risks || generateMockRiskData()} />
            )}

            {/* Activity Heatmap */}
            {isLoading ? (
              <Skeleton className="h-[300px]" />
            ) : (
              <ActivityHeatmap data={dashboardData?.activity_data || generateMockActivityData()} />
            )}
          </div>

          {/* Recent Activity Table */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Your latest compliance activities and updates</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-[300px]" />
              ) : (
                <DataTable assessments={dashboardData?.recent_activity || []} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
