import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ComplianceScoreWidget } from '@/components/dashboard/widgets/compliance-score-widget'
import { PendingTasksWidget } from '@/components/dashboard/widgets/pending-tasks-widget'
import { AIInsightsWidget } from '@/components/dashboard/widgets/ai-insights-widget'
import { RecentActivityWidget } from '@/components/dashboard/widgets/recent-activity-widget'

// Mock the chart components
vi.mock('@/components/ui/chart', () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
  ChartTooltip: () => <div data-testid="chart-tooltip" />,
  ChartTooltipContent: () => <div data-testid="chart-tooltip-content" />,
}))

// Mock icons
vi.mock('lucide-react', () => ({
  TrendingUp: () => <div data-testid="trending-up-icon" />,
  TrendingDown: () => <div data-testid="trending-down-icon" />,
  AlertTriangle: () => <div data-testid="alert-icon" />,
  CheckCircle: () => <div data-testid="check-icon" />,
  Clock: () => <div data-testid="clock-icon" />,
  FileText: () => <div data-testid="file-icon" />,
  Target: () => <div data-testid="target-icon" />,
}))

describe('Dashboard Widgets', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('ComplianceScoreWidget', () => {
    const mockProps = {
      score: 85,
      trend: 'up' as const,
      previousScore: 78,
      frameworks: [
        { name: 'GDPR', score: 90, status: 'compliant' },
        { name: 'ISO 27001', score: 80, status: 'partially_compliant' },
      ],
    }

    it('should render compliance score correctly', () => {
      render(<ComplianceScoreWidget {...mockProps} />)
      
      expect(screen.getByText('85%')).toBeInTheDocument()
      expect(screen.getByText('Compliance Score')).toBeInTheDocument()
    })

    it('should show trend indicator', () => {
      render(<ComplianceScoreWidget {...mockProps} />)
      
      expect(screen.getByTestId('trending-up-icon')).toBeInTheDocument()
      expect(screen.getByText('+7 from last month')).toBeInTheDocument()
    })

    it('should display framework breakdown', () => {
      render(<ComplianceScoreWidget {...mockProps} />)
      
      expect(screen.getByText('GDPR')).toBeInTheDocument()
      expect(screen.getByText('90%')).toBeInTheDocument()
      expect(screen.getByText('ISO 27001')).toBeInTheDocument()
      expect(screen.getByText('80%')).toBeInTheDocument()
    })

    it('should handle low scores with warning styling', () => {
      const lowScoreProps = { ...mockProps, score: 45, trend: 'down' as const }
      render(<ComplianceScoreWidget {...lowScoreProps} />)
      
      expect(screen.getByTestId('trending-down-icon')).toBeInTheDocument()
      expect(screen.getByText('45%')).toHaveClass('text-red-600')
    })

    it('should handle click to view details', () => {
      const onViewDetails = vi.fn()
      render(<ComplianceScoreWidget {...mockProps} onViewDetails={onViewDetails} />)
      
      const viewButton = screen.getByRole('button', { name: /view details/i })
      fireEvent.click(viewButton)
      
      expect(onViewDetails).toHaveBeenCalled()
    })
  })

  describe('PendingTasksWidget', () => {
    const mockTasks = [
      {
        id: 'task-1',
        title: 'Complete GDPR assessment',
        priority: 'high' as const,
        dueDate: new Date('2025-01-15'),
        framework: 'GDPR',
        type: 'assessment',
      },
      {
        id: 'task-2',
        title: 'Upload security policies',
        priority: 'medium' as const,
        dueDate: new Date('2025-01-20'),
        framework: 'ISO 27001',
        type: 'evidence',
      },
    ]

    it('should render pending tasks list', () => {
      render(<PendingTasksWidget tasks={mockTasks} />)
      
      expect(screen.getByText('Pending Tasks')).toBeInTheDocument()
      expect(screen.getByText('Complete GDPR assessment')).toBeInTheDocument()
      expect(screen.getByText('Upload security policies')).toBeInTheDocument()
    })

    it('should show task priorities', () => {
      render(<PendingTasksWidget tasks={mockTasks} />)
      
      expect(screen.getByText('High')).toBeInTheDocument()
      expect(screen.getByText('Medium')).toBeInTheDocument()
    })

    it('should display due dates', () => {
      render(<PendingTasksWidget tasks={mockTasks} />)
      
      expect(screen.getByText(/Jan 15/)).toBeInTheDocument()
      expect(screen.getByText(/Jan 20/)).toBeInTheDocument()
    })

    it('should handle empty tasks list', () => {
      render(<PendingTasksWidget tasks={[]} />)
      
      expect(screen.getByText('No pending tasks')).toBeInTheDocument()
      expect(screen.getByText('Great job! All tasks are complete.')).toBeInTheDocument()
    })

    it('should handle task click', () => {
      const onTaskClick = vi.fn()
      render(<PendingTasksWidget tasks={mockTasks} onTaskClick={onTaskClick} />)
      
      fireEvent.click(screen.getByText('Complete GDPR assessment'))
      
      expect(onTaskClick).toHaveBeenCalledWith('task-1')
    })

    it('should show overdue tasks with warning', () => {
      const overdueTasks = [
        {
          ...mockTasks[0],
          dueDate: new Date('2025-01-01'), // Past date
        },
      ]
      
      render(<PendingTasksWidget tasks={overdueTasks} />)
      
      expect(screen.getByText(/overdue/i)).toBeInTheDocument()
    })
  })

  describe('AIInsightsWidget', () => {
    const mockInsights = [
      {
        id: 'insight-1',
        type: 'recommendation' as const,
        title: 'Improve data retention policies',
        description: 'Consider implementing automated data deletion',
        confidence: 0.85,
        framework: 'GDPR',
        priority: 'high' as const,
      },
      {
        id: 'insight-2',
        type: 'risk' as const,
        title: 'Potential compliance gap',
        description: 'Missing employee training records',
        confidence: 0.92,
        framework: 'ISO 27001',
        priority: 'medium' as const,
      },
    ]

    it('should render AI insights', () => {
      render(<AIInsightsWidget insights={mockInsights} />)
      
      expect(screen.getByText('AI Insights')).toBeInTheDocument()
      expect(screen.getByText('Improve data retention policies')).toBeInTheDocument()
      expect(screen.getByText('Potential compliance gap')).toBeInTheDocument()
    })

    it('should show confidence scores', () => {
      render(<AIInsightsWidget insights={mockInsights} />)
      
      expect(screen.getByText('85%')).toBeInTheDocument()
      expect(screen.getByText('92%')).toBeInTheDocument()
    })

    it('should display insight types', () => {
      render(<AIInsightsWidget insights={mockInsights} />)
      
      expect(screen.getByText('Recommendation')).toBeInTheDocument()
      expect(screen.getByText('Risk')).toBeInTheDocument()
    })

    it('should handle insight click for details', () => {
      const onInsightClick = vi.fn()
      render(<AIInsightsWidget insights={mockInsights} onInsightClick={onInsightClick} />)
      
      fireEvent.click(screen.getByText('Improve data retention policies'))
      
      expect(onInsightClick).toHaveBeenCalledWith('insight-1')
    })

    it('should handle loading state', () => {
      render(<AIInsightsWidget insights={[]} isLoading={true} />)
      
      expect(screen.getByText(/analyzing/i)).toBeInTheDocument()
    })

    it('should handle refresh insights', () => {
      const onRefresh = vi.fn()
      render(<AIInsightsWidget insights={mockInsights} onRefresh={onRefresh} />)
      
      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      fireEvent.click(refreshButton)
      
      expect(onRefresh).toHaveBeenCalled()
    })
  })

  describe('RecentActivityWidget', () => {
    const mockActivities = [
      {
        id: 'activity-1',
        type: 'assessment_completed' as const,
        title: 'GDPR Assessment Completed',
        description: 'Achieved 90% compliance score',
        timestamp: new Date('2025-01-08T10:00:00Z'),
        user: 'John Smith',
        metadata: { score: 90 },
      },
      {
        id: 'activity-2',
        type: 'evidence_uploaded' as const,
        title: 'Security Policy Updated',
        description: 'Data protection policy v2.1 uploaded',
        timestamp: new Date('2025-01-07T15:30:00Z'),
        user: 'Jane Doe',
        metadata: { filename: 'data-protection-policy-v2.1.pdf' },
      },
    ]

    it('should render recent activities', () => {
      render(<RecentActivityWidget activities={mockActivities} />)
      
      expect(screen.getByText('Recent Activity')).toBeInTheDocument()
      expect(screen.getByText('GDPR Assessment Completed')).toBeInTheDocument()
      expect(screen.getByText('Security Policy Updated')).toBeInTheDocument()
    })

    it('should show activity timestamps', () => {
      render(<RecentActivityWidget activities={mockActivities} />)
      
      expect(screen.getByText(/10:00/)).toBeInTheDocument()
      expect(screen.getByText(/15:30/)).toBeInTheDocument()
    })

    it('should display user information', () => {
      render(<RecentActivityWidget activities={mockActivities} />)
      
      expect(screen.getByText('John Smith')).toBeInTheDocument()
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })

    it('should handle empty activity list', () => {
      render(<RecentActivityWidget activities={[]} />)
      
      expect(screen.getByText('No recent activity')).toBeInTheDocument()
    })

    it('should show activity type icons', () => {
      render(<RecentActivityWidget activities={mockActivities} />)
      
      expect(screen.getByTestId('check-icon')).toBeInTheDocument()
      expect(screen.getByTestId('file-icon')).toBeInTheDocument()
    })

    it('should handle view all activities', () => {
      const onViewAll = vi.fn()
      render(<RecentActivityWidget activities={mockActivities} onViewAll={onViewAll} />)
      
      const viewAllButton = screen.getByRole('button', { name: /view all/i })
      fireEvent.click(viewAllButton)
      
      expect(onViewAll).toHaveBeenCalled()
    })

    it('should format relative timestamps', () => {
      const recentActivity = [
        {
          ...mockActivities[0],
          timestamp: new Date(Date.now() - 5 * 60 * 1000), // 5 minutes ago
        },
      ]
      
      render(<RecentActivityWidget activities={recentActivity} />)
      
      expect(screen.getByText(/5 minutes ago/i)).toBeInTheDocument()
    })
  })

  describe('Widget Accessibility', () => {
    it('should have proper ARIA labels', () => {
      const mockProps = {
        score: 85,
        trend: 'up' as const,
        previousScore: 78,
        frameworks: [],
      }
      
      render(<ComplianceScoreWidget {...mockProps} />)
      
      expect(screen.getByRole('region')).toHaveAttribute('aria-label', 'Compliance Score Widget')
    })

    it('should support keyboard navigation', () => {
      const mockTasks = [
        {
          id: 'task-1',
          title: 'Test task',
          priority: 'high' as const,
          dueDate: new Date(),
          framework: 'GDPR',
          type: 'assessment',
        },
      ]
      
      render(<PendingTasksWidget tasks={mockTasks} />)
      
      const taskButton = screen.getByRole('button')
      expect(taskButton).toHaveAttribute('tabIndex', '0')
    })
  })
})