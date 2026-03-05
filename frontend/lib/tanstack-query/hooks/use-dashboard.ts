import { useQuery } from '@tanstack/react-query';

import { dashboardService } from '@/lib/api/dashboard.service';

import { createQueryKey, type BaseQueryOptions } from './base';

// Define types locally until they're exported from the service
interface UserDashboard {
  stats: any;
  activities: any[];
  tasks: any[];
  insights: any[];
  frameworkProgress: any[];
  // Additional properties from the actual response
  recent_activity?: any[];
  pending_tasks?: any[];
  ai_insights?: any[];
  framework_progress?: any[];
  upcoming_deadlines?: any[];
  compliance_trends?: any[];
  compliance_score?: number;
  framework_scores?: any;
  active_alerts?: number;
  ai_insights_count?: number;
  tasks_completed?: number;
  total_tasks?: number;
  risks?: any[];
  task_progress?: any[];
  activity_data?: any[];
}

// Query keys
const DASHBOARD_KEY = 'dashboard';

export const dashboardKeys = {
  all: [DASHBOARD_KEY] as const,
  main: () => createQueryKey(DASHBOARD_KEY, 'main'),
  widget: (widgetType: string) => createQueryKey(DASHBOARD_KEY, 'widget', { widgetType }),
  insights: () => createQueryKey(DASHBOARD_KEY, 'insights'),
  tasks: () => createQueryKey(DASHBOARD_KEY, 'tasks'),
  score: () => createQueryKey(DASHBOARD_KEY, 'score'),
};

// Hook to fetch main dashboard data
export function useDashboard(options?: BaseQueryOptions<UserDashboard>) {
  return useQuery({
    queryKey: dashboardKeys.main(),
    queryFn: async () => {
      const response = await dashboardService.getUserDashboard();
      // Map the actual response to the UserDashboard interface
      return {
        stats: response.stats,
        activities: response.recent_activity || [],
        tasks: response.pending_tasks || [],
        insights: response.ai_insights || [],
        frameworkProgress: response.framework_progress || [],
        // Include all other properties from the response
        recent_activity: response.recent_activity,
        pending_tasks: response.pending_tasks,
        ai_insights: response.ai_insights,
        framework_progress: response.framework_progress,
        upcoming_deadlines: response.upcoming_deadlines,
        compliance_trends: response.compliance_trends,
        // Extract additional properties from stats if needed
        compliance_score: response.stats?.compliance_score,
        active_alerts: response.stats?.risk_items,
        ai_insights_count: response.ai_insights?.length || 0,
        tasks_completed: response.stats?.assessments_completed,
        total_tasks: response.stats?.tasks_pending,
      } as UserDashboard;
    },
    ...options,
  });
}

// Hook to fetch specific widget data - COMMENTED OUT: getWidgetData doesn't exist
// export function useDashboardWidget(
//   widgetType: 'insights' | 'tasks' | 'score' | 'activity',
//   options?: BaseQueryOptions<WidgetData>,
// ) {
//   return useQuery({
//     queryKey: dashboardKeys.widget(widgetType),
//     queryFn: () => dashboardService.getWidgetData(widgetType),
//     ...options,
//   });
// }

// Hook to fetch AI insights
export function useAIInsights(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: dashboardKeys.insights(),
    queryFn: async () => {
      const dashboard = await dashboardService.getUserDashboard();
      return dashboard.ai_insights || [];
    },
    ...options,
  });
}

// Hook to fetch pending tasks
export function usePendingTasks(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: dashboardKeys.tasks(),
    queryFn: async () => {
      const dashboard = await dashboardService.getUserDashboard();
      return dashboard.pending_tasks || [];
    },
    ...options,
  });
}

// Hook to fetch compliance score from dashboard
export function useDashboardComplianceScore(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: dashboardKeys.score(),
    queryFn: async () => {
      const dashboard = await dashboardService.getUserDashboard();
      return {
        overall_score: dashboard.stats?.compliance_score || 0,
        frameworks: dashboard.framework_progress?.reduce((acc: any, fp: any) => {
          acc[fp.framework_name] = fp.compliance_percentage;
          return acc;
        }, {}) || {},
      };
    },
    ...options,
  });
}
