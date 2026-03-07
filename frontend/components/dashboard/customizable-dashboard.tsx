'use client';

import { Settings2, Plus, GripVertical, X, Save, RotateCcw } from 'lucide-react';
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Responsive, WidthProvider, type Layout } from 'react-grid-layout';
import { toast } from 'sonner';
import { layoutsService, getCurrentUserId } from '@/lib/api/layouts.service';
import { debounce } from '@/lib/utils';
import { useLayoutStore } from '@/lib/stores/layout.store';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';

import { AIInsightsWidget } from './ai-insights-widget';
import {
  ComplianceTrendChart,
  FrameworkBreakdownChart,
  ActivityHeatmap,
  RiskMatrix,
  TaskProgressChart,
} from './charts';
import { ComplianceScoreWidget } from './compliance-score-widget';
import { PendingTasksWidget } from './pending-tasks-widget';

// Import CSS for react-grid-layout
import 'react-grid-layout/css/styles.css';
// import 'react-resizable/css/styles.css'; // TODO: Install react-resizable

const ResponsiveGridLayout = WidthProvider(Responsive);

// Widget types
export type WidgetType =
  | 'ai-insights'
  | 'compliance-score'
  | 'pending-tasks'
  | 'compliance-trend'
  | 'framework-breakdown'
  | 'activity-heatmap'
  | 'risk-matrix'
  | 'task-progress'
  | 'custom';

// Widget configuration
interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  description?: string;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
}

// Available widgets catalog
const widgetCatalog: Record<WidgetType, Omit<WidgetConfig, 'id'>> = {
  'ai-insights': {
    type: 'ai-insights',
    title: 'AI Insights',
    description: 'Latest AI-powered recommendations',
    minW: 2,
    minH: 3,
  },
  'compliance-score': {
    type: 'compliance-score',
    title: 'Compliance Score',
    description: 'Overall compliance metrics',
    minW: 2,
    minH: 3,
  },
  'pending-tasks': {
    type: 'pending-tasks',
    title: 'Pending Tasks',
    description: 'Tasks requiring attention',
    minW: 2,
    minH: 3,
  },
  'compliance-trend': {
    type: 'compliance-trend',
    title: 'Compliance Trend',
    description: 'Historical compliance scores',
    minW: 3,
    minH: 2,
  },
  'framework-breakdown': {
    type: 'framework-breakdown',
    title: 'Framework Breakdown',
    description: 'Compliance by framework',
    minW: 3,
    minH: 2,
  },
  'activity-heatmap': {
    type: 'activity-heatmap',
    title: 'Activity Heatmap',
    description: 'Team activity patterns',
    minW: 2,
    minH: 2,
  },
  'risk-matrix': {
    type: 'risk-matrix',
    title: 'Risk Matrix',
    description: 'Current risk assessment',
    minW: 2,
    minH: 2,
  },
  'task-progress': {
    type: 'task-progress',
    title: 'Task Progress',
    description: 'Task completion status',
    minW: 2,
    minH: 2,
  },
  custom: {
    type: 'custom',
    title: 'Custom Widget',
    description: 'Create your own widget',
    minW: 2,
    minH: 2,
  },
};

// Default layouts for different breakpoints
const defaultLayouts = {
  lg: [
    { i: 'compliance-score', x: 0, y: 0, w: 4, h: 3 },
    { i: 'ai-insights', x: 4, y: 0, w: 4, h: 3 },
    { i: 'pending-tasks', x: 8, y: 0, w: 4, h: 3 },
    { i: 'compliance-trend', x: 0, y: 3, w: 6, h: 3 },
    { i: 'framework-breakdown', x: 6, y: 3, w: 6, h: 3 },
  ],
  md: [
    { i: 'compliance-score', x: 0, y: 0, w: 6, h: 3 },
    { i: 'ai-insights', x: 6, y: 0, w: 6, h: 3 },
    { i: 'pending-tasks', x: 0, y: 3, w: 12, h: 3 },
    { i: 'compliance-trend', x: 0, y: 6, w: 12, h: 3 },
    { i: 'framework-breakdown', x: 0, y: 9, w: 12, h: 3 },
  ],
  sm: [
    { i: 'compliance-score', x: 0, y: 0, w: 6, h: 3 },
    { i: 'ai-insights', x: 0, y: 3, w: 6, h: 3 },
    { i: 'pending-tasks', x: 0, y: 6, w: 6, h: 3 },
    { i: 'compliance-trend', x: 0, y: 9, w: 6, h: 3 },
    { i: 'framework-breakdown', x: 0, y: 12, w: 6, h: 3 },
  ],
};

interface CustomizableDashboardProps {
  data?: any;
  onLayoutChange?: (layouts: any) => void;
}

export function CustomizableDashboard({ data, onLayoutChange }: CustomizableDashboardProps) {
  const [layouts, setLayouts] = useState(defaultLayouts);
  const [widgets, setWidgets] = useState<WidgetConfig[]>([
    { id: 'compliance-score', ...widgetCatalog['compliance-score'] },
    { id: 'ai-insights', ...widgetCatalog['ai-insights'] },
    { id: 'pending-tasks', ...widgetCatalog['pending-tasks'] },
    { id: 'compliance-trend', ...widgetCatalog['compliance-trend'] },
    { id: 'framework-breakdown', ...widgetCatalog['framework-breakdown'] },
  ]);
  const [isEditMode, setIsEditMode] = useState(false);
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [selectedWidgetType, setSelectedWidgetType] = useState<WidgetType>('ai-insights');

  // Get undo/redo functions from store (Comment 3 & 10 requirements)
  const { undo, redo, history: _history, historyIndex: _historyIndex } = useLayoutStore();

  // Keyboard shortcuts (Comment 10 requirement)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const ctrlOrCmd = isMac ? e.metaKey : e.ctrlKey;

      if (ctrlOrCmd && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (undo()) {
          toast.success('Action undone');
        }
      } else if (ctrlOrCmd && ((e.key === 'z' && e.shiftKey) || e.key === 'y')) {
        e.preventDefault();
        if (redo()) {
          toast.success('Action redone');
        }
      } else if (e.key === 'Escape' && isEditMode) {
        setIsEditMode(false);
        toast.info('Edit mode disabled');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, isEditMode]);

  // Debounced save function (Comment 2 requirement)
  const saveLayoutDebounced = useRef(
    debounce(async (layouts: any, widgets: WidgetConfig[]) => {
      try {
        const userId = getCurrentUserId();
        if (!userId) {
          console.warn('No user ID available, skipping layout save');
          return;
        }
        
        const layoutData = {
          id: `layout-${userId}`,
          userId,
          widgets: widgets.map(w => ({
            id: w.id,
            type: w.type,
            gridX: layouts.lg?.find((l: Layout) => l.i === w.id)?.x || 0,
            gridY: layouts.lg?.find((l: Layout) => l.i === w.id)?.y || 0,
            width: layouts.lg?.find((l: Layout) => l.i === w.id)?.w || 2,
            height: layouts.lg?.find((l: Layout) => l.i === w.id)?.h || 2,
            settings: {},
          })),
          ruleOrder: [],
          settings: {
            breakpoints: layouts,
            isEditMode,
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };

        await layoutsService.saveLayout(userId, layoutData as any);
      } catch (error) {
        console.error('Failed to save layout:', error);
        toast.error('Failed to save layout changes');
      }
    }, 400) // 400ms debounce as specified in Comment 2
  ).current;

  // Handle layout changes
  const handleLayoutChange = useCallback(
    (_layout: Layout[], allLayouts: any) => {
      setLayouts(allLayouts);
      if (onLayoutChange) {
        onLayoutChange(allLayouts);
      }

      // Trigger debounced save to API (Comment 2 requirement)
      saveLayoutDebounced(allLayouts, widgets);
    },
    [onLayoutChange, widgets, saveLayoutDebounced],
  );

  // Add new widget
  const addWidget = () => {
    const widgetConfig = widgetCatalog[selectedWidgetType];
    const newWidget: WidgetConfig = {
      id: `${selectedWidgetType}-${Date.now()}`,
      ...widgetConfig,
    };

    // Add widget to list
    setWidgets([...widgets, newWidget]);

    // Add to layouts
    const newLayouts = { ...layouts };
    Object.keys(newLayouts).forEach((breakpoint) => {
      const layout = newLayouts[breakpoint as keyof typeof newLayouts];
      const y = layout.length > 0 ? Math.max(...layout.map((item) => item.y + item.h)) : 0;
      layout.push({
        i: newWidget.id,
        x: 0,
        y,
        w: widgetConfig.minW || 2,
        h: widgetConfig.minH || 2,
      });
    });
    setLayouts(newLayouts);
    setShowAddWidget(false);
    toast.success(`Added ${widgetConfig.title} widget`);
  };

  // Remove widget
  const removeWidget = (widgetId: string) => {
    setWidgets(widgets.filter((w) => w.id !== widgetId));
    const newLayouts = { ...layouts };
    Object.keys(newLayouts).forEach((breakpoint) => {
      newLayouts[breakpoint as keyof typeof newLayouts] = newLayouts[
        breakpoint as keyof typeof newLayouts
      ].filter((item) => item.i !== widgetId);
    });
    setLayouts(newLayouts);
    toast.success('Widget removed');
  };

  // Save layout
  const saveLayout = () => {
    // In a real app, this would save to backend/localStorage
    localStorage.setItem('dashboard-layout', JSON.stringify({ layouts, widgets }));
    toast.success('Dashboard layout saved');
  };

  // Reset to default
  const resetLayout = () => {
    setLayouts(defaultLayouts);
    setWidgets([
      { id: 'compliance-score', ...widgetCatalog['compliance-score'] },
      { id: 'ai-insights', ...widgetCatalog['ai-insights'] },
      { id: 'pending-tasks', ...widgetCatalog['pending-tasks'] },
      { id: 'compliance-trend', ...widgetCatalog['compliance-trend'] },
      { id: 'framework-breakdown', ...widgetCatalog['framework-breakdown'] },
    ]);
    localStorage.removeItem('dashboard-layout');
    toast.success('Dashboard reset to default');
  };

  // Render widget content
  const renderWidget = (widget: WidgetConfig) => {
    switch (widget.type) {
      case 'ai-insights':
        return <AIInsightsWidget insights={data?.insights || []} />;
      case 'compliance-score':
        return (
          <ComplianceScoreWidget
            data={{
              overall_score: data?.compliance_score || 0,
              frameworks: data?.framework_scores || [],
            }}
          />
        );
      case 'pending-tasks':
        return <PendingTasksWidget tasks={data?.pending_tasks || []} />;
      case 'compliance-trend':
        return <ComplianceTrendChart data={data?.compliance_trends || []} />;
      case 'framework-breakdown':
        return <FrameworkBreakdownChart data={data?.framework_breakdown || []} />;
      case 'activity-heatmap':
        return <ActivityHeatmap data={data?.activity_data || []} />;
      case 'risk-matrix':
        return <RiskMatrix risks={data?.risks || []} />;
      case 'task-progress':
        return <TaskProgressChart data={data?.task_progress || []} />;
      case 'custom':
        return (
          <Card className="h-full">
            <CardContent className="flex h-full items-center justify-center">
              <p className="text-muted-foreground">Custom widget content</p>
            </CardContent>
          </Card>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center space-x-2">
            <Switch id="edit-mode" checked={isEditMode} onCheckedChange={setIsEditMode} />
            <Label htmlFor="edit-mode">Edit Mode</Label>
          </div>
          {isEditMode && (
            <>
              <Dialog open={showAddWidget} onOpenChange={setShowAddWidget}>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Widget
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Widget</DialogTitle>
                    <DialogDescription>
                      Select a widget type to add to your dashboard
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>Widget Type</Label>
                      <Select
                        value={selectedWidgetType}
                        onValueChange={(v) => setSelectedWidgetType(v as WidgetType)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(widgetCatalog).map(([key, config]) => (
                            <SelectItem key={key} value={key}>
                              <div>
                                <div className="font-medium">{config.title}</div>
                                <div className="text-xs text-muted-foreground">
                                  {config.description}
                                </div>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowAddWidget(false)}>
                      Cancel
                    </Button>
                    <Button onClick={addWidget}>Add Widget</Button>
                  </div>
                </DialogContent>
              </Dialog>
              <Button size="sm" variant="outline" onClick={saveLayout}>
                <Save className="mr-2 h-4 w-4" />
                Save Layout
              </Button>
              <Button size="sm" variant="outline" onClick={resetLayout}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset
              </Button>
            </>
          )}
        </div>
        <Button size="sm" variant="ghost">
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Grid Layout */}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        onLayoutChange={handleLayoutChange}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 12, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={100}
        isDraggable={isEditMode}
        isResizable={isEditMode}
        containerPadding={[0, 0]}
        margin={[16, 16]}
      >
        {widgets.map((widget) => (
          <div key={widget.id} className="group relative">
            {isEditMode && (
              <>
                <div className="absolute left-2 top-2 z-10 opacity-0 transition-opacity group-hover:opacity-100">
                  <div className="cursor-move rounded bg-white/90 p-1">
                    <GripVertical className="h-4 w-4 text-gray-600" />
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute right-2 top-2 z-10 h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={() => removeWidget(widget.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </>
            )}
            <div className="h-full overflow-hidden">{renderWidget(widget)}</div>
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}
