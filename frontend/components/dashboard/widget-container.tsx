'use client';

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
  type DragOverEvent,
  type UniqueIdentifier,
  MeasuringStrategy,
  type Announcements,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  restrictToWindowEdges,
} from '@dnd-kit/modifiers';
import { GripVertical, X, Settings, Maximize2, Minimize2 } from 'lucide-react';
import React, { useCallback, useState, useEffect, useMemo } from 'react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useLayoutStore } from '@/lib/stores/layout.store';
import { useLayoutPersistence } from '@/lib/hooks/use-layout-persistence';
import { useKeyboardShortcuts } from '@/lib/hooks/use-keyboard-shortcuts';
import { WidgetPosition } from '@/types/layout';
import { generateAccessibilityAnnouncements } from '@/lib/utils/accessibility-announcements';
import { toast } from '@/hooks/use-toast';

export interface WidgetConfig {
  id: string;
  type: string;
  title: string;
  content: React.ReactNode;
  minWidth?: number;
  minHeight?: number;
  defaultWidth?: number;
  defaultHeight?: number;
  canResize?: boolean;
  canRemove?: boolean;
  settings?: Record<string, any>;
  gridPosition?: WidgetPosition;
}

interface WidgetContainerProps {
  widgets: WidgetConfig[];
  onWidgetOrderChange?: (widgets: WidgetConfig[]) => void;
  onWidgetRemove?: (widgetId: string) => void;
  onWidgetSettings?: (widgetId: string) => void;
  columns?: number;
  gap?: number;
  className?: string;
  enablePersistence?: boolean;
  enableUndoRedo?: boolean;
  dragContextType?: 'widgets' | 'rules' | 'mixed';
  showAccessibilityAnnouncements?: boolean;
}

interface SortableWidgetProps {
  widget: WidgetConfig;
  onRemove?: (id: string) => void;
  onSettings?: (id: string) => void;
  isExpanded: boolean;
  onToggleExpand: (id: string) => void;
  isDragging?: boolean;
  isOverlay?: boolean;
}

function SortableWidget({
  widget,
  onRemove,
  onSettings,
  isExpanded,
  onToggleExpand,
  isDragging = false,
  isOverlay = false,
}: SortableWidgetProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging: isSortableDragging } = useSortable({
    id: widget.id,
    disabled: isOverlay,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={!isOverlay ? setNodeRef : undefined}
      style={!isOverlay ? style : undefined}
      className={cn(
        'group relative',
        (isDragging || isSortableDragging) && 'z-50 opacity-50',
        isExpanded && 'md:col-span-2 lg:col-span-3',
        isOverlay && 'cursor-grabbing shadow-2xl',
      )}
    >
      <Card className={cn(
        "h-full overflow-hidden border-purple-100 bg-gray-50 transition-all duration-300",
        !isOverlay && "hover:shadow-lg hover:border-purple-200",
        isOverlay && "ring-2 ring-purple-600 ring-offset-2"
      )}>
        {/* Widget Header */}
        <div className="flex items-center justify-between border-b border-neutral-100 p-4">
          <div className="flex items-center gap-2">
            {!isOverlay && (
              <button
                className="cursor-move touch-none rounded p-1 transition-colors hover:bg-neutral-100"
                {...attributes}
                {...listeners}
                aria-label={`Drag to reorder ${widget.title}`}
                aria-roledescription="sortable"
                aria-describedby={`widget-${widget.id}-description`}
              >
                <GripVertical className="h-4 w-4 text-neutral-400" />
              </button>
            )}
            <h3 className="font-semibold text-neutral-900">{widget.title}</h3>
          </div>
          {!isOverlay && (
            <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onToggleExpand(widget.id)}
                className="h-8 w-8 p-0"
                aria-label={isExpanded ? 'Minimize widget' : 'Expand widget'}
              >
                {isExpanded ? (
                  <Minimize2 className="h-3.5 w-3.5 text-neutral-600" />
                ) : (
                  <Maximize2 className="h-3.5 w-3.5 text-neutral-600" />
                )}
              </Button>
              {onSettings && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSettings(widget.id)}
                  className="h-8 w-8 p-0"
                  aria-label={`Settings for ${widget.title}`}
                >
                  <Settings className="h-3.5 w-3.5 text-neutral-600" />
                </Button>
              )}
              {widget.canRemove !== false && onRemove && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemove(widget.id)}
                  className="h-8 w-8 p-0 hover:bg-red-50"
                  aria-label={`Remove ${widget.title}`}
                >
                  <X className="h-3.5 w-3.5 text-neutral-600 hover:text-red-600" />
                </Button>
              )}
            </div>
          )}
        </div>
        {/* Widget Content */}
        <div className="p-4" id={`widget-${widget.id}-description`}>
          {widget.content}
        </div>
      </Card>
    </div>
  );
}

export function WidgetContainer({
  widgets: initialWidgets,
  onWidgetOrderChange,
  onWidgetRemove,
  onWidgetSettings,
  columns = 3,
  gap = 6,
  className,
  enablePersistence = true,
  enableUndoRedo = true,
  dragContextType = 'widgets',
  showAccessibilityAnnouncements = true,
}: WidgetContainerProps) {
  const [widgets, setWidgets] = useState(initialWidgets);
  const [expandedWidgets, setExpandedWidgets] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);

  // Store integration
  const {
    currentLayout,
    moveWidget,
    removeWidget,
    addWidget: _addWidget,
    undo,
    redo,
    setDragState,
    clearDragState,
    addAnnouncement,
    preferences,
    history,
    historyIndex,
  } = useLayoutStore();

  // Persistence hook
  const {
    saveNow,
    hasUnsavedChanges,
    isSaving,
    saveError,
  } = useLayoutPersistence({
    autoSave: enablePersistence,
    autoSaveInterval: preferences.autoSaveInterval,
  });

  // Keyboard shortcuts
  const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts();

  // Sensors configuration
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  // Measuring configuration for better performance
  const measuringConfig = {
    droppable: {
      strategy: MeasuringStrategy.Always,
    },
    draggable: {
      measure: (element: HTMLElement) => {
        const rect = element.getBoundingClientRect();
        return {
          ...rect,
          width: rect.width,
          height: rect.height,
        };
      },
    },
  };

  // Accessibility announcements
  const _announcements: Announcements = useMemo(
    () => generateAccessibilityAnnouncements(dragContextType),
    [dragContextType]
  );

  // Register keyboard shortcuts
  useEffect(() => {
    if (!enableUndoRedo) return;

    const undoId = registerShortcut({
      key: 'z',
      ctrlKey: true,
      callback: () => {
        if (undo()) {
          toast({
            title: 'Undo',
            description: 'Action undone',
            duration: 2000,
          });
        }
      },
      description: 'Undo last action',
    });

    const redoId = registerShortcut({
      key: 'z',
      ctrlKey: true,
      shiftKey: true,
      callback: () => {
        if (redo()) {
          toast({
            title: 'Redo',
            description: 'Action redone',
            duration: 2000,
          });
        }
      },
      description: 'Redo last action',
    });

    const saveId = registerShortcut({
      key: 's',
      ctrlKey: true,
      callback: (e) => {
        e.preventDefault();
        if (enablePersistence && hasUnsavedChanges) {
          saveNow();
        }
      },
      description: 'Save layout',
    });

    return () => {
      unregisterShortcut(undoId);
      unregisterShortcut(redoId);
      unregisterShortcut(saveId);
    };
  }, [enableUndoRedo, enablePersistence, undo, redo, saveNow, hasUnsavedChanges, registerShortcut, unregisterShortcut]);

  // Sync widgets with layout store
  useEffect(() => {
    if (currentLayout?.widgets) {
      const updatedWidgets = initialWidgets.map(widget => {
        const layoutWidget = currentLayout.widgets.find(w => w.id === widget.id);
        if (layoutWidget) {
          return {
            ...widget,
            gridPosition: layoutWidget,
          };
        }
        return widget;
      });
      setWidgets(updatedWidgets);
    }
  }, [currentLayout, initialWidgets]);

  // React to prop updates (Comment 7 requirement)
  useEffect(() => {
    setWidgets(initialWidgets);
  }, [initialWidgets]);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const { active } = event;
      setActiveId(active.id);

      const widget = widgets.find(w => w.id === active.id);
      if (!widget) return;

      setDragState({
        isDragging: true,
        draggedItem: {
          id: active.id as string,
          type: 'widget',
          data: widget,
        },
      });

      if (showAccessibilityAnnouncements) {
        addAnnouncement({
          message: `Started dragging ${widget.title}`,
          severity: 'info',
          politeness: 'polite',
        });
      }
    },
    [widgets, setDragState, addAnnouncement, showAccessibilityAnnouncements]
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const { active: _active, over } = event;

      if (over) {
        setDragState({
          activeDropZone: over.id as string,
        });
      }
    },
    [setDragState]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      setActiveId(null);
      clearDragState();

      if (over && active.id !== over.id) {
        setWidgets((items) => {
          const oldIndex = items.findIndex((item) => item.id === active.id);
          const newIndex = items.findIndex((item) => item.id === over.id);
          const newOrder = arrayMove(items, oldIndex, newIndex);

          // Update layout store
          const widget = items[oldIndex];
          if (widget) {
            moveWidget(widget.id, {
              gridX: newIndex % columns,
              gridY: Math.floor(newIndex / columns),
            });
          }

          onWidgetOrderChange?.(newOrder);

          // Trigger persistence with debounced save (Comment 2 requirement)
          if (enablePersistence) {
            // The useLayoutPersistence hook handles debounced saving automatically
            // when the layout store updates
          }

          if (showAccessibilityAnnouncements && widget) {
            addAnnouncement({
              message: `Moved ${widget.title} to position ${newIndex + 1}`,
              severity: 'success',
              politeness: 'assertive',
              duration: 3000,
            });
          }

          return newOrder;
        });

        // Defensive cleanup: ensure expandedWidgets only contains valid widget IDs
        setExpandedWidgets((prev) => {
          const validIds = new Set(widgets.map(w => w.id));
          const filtered = new Set(Array.from(prev).filter(id => validIds.has(id)));
          return filtered;
        });
      }
    },
    [columns, clearDragState, moveWidget, onWidgetOrderChange, addAnnouncement, showAccessibilityAnnouncements, enablePersistence]
  );

  const handleDragCancel = useCallback(() => {
    setActiveId(null);
    clearDragState();

    if (showAccessibilityAnnouncements) {
      addAnnouncement({
        message: 'Drag cancelled',
        severity: 'info',
        politeness: 'polite',
      });
    }
  }, [clearDragState, addAnnouncement, showAccessibilityAnnouncements]);

  const handleRemoveWidget = useCallback(
    (widgetId: string) => {
      const widget = widgets.find(w => w.id === widgetId);
      if (!widget) return;

      setWidgets((items) => items.filter((item) => item.id !== widgetId));
      removeWidget(widgetId);
      onWidgetRemove?.(widgetId);

      // Clean up expanded widgets set (Comment 9 requirement)
      setExpandedWidgets((prev) => {
        const next = new Set(prev);
        next.delete(widgetId);
        return next;
      });

      const toastConfig: any = {
        title: 'Widget removed',
        description: `${widget.title} has been removed`,
      };

      if (enableUndoRedo) {
        toastConfig.action = (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (undo()) {
                toast({
                  title: 'Widget restored',
                  description: `${widget.title} has been restored`,
                });
              }
            }}
          >
            Undo
          </Button>
        );
      }

      toast(toastConfig);
    },
    [widgets, removeWidget, onWidgetRemove, enableUndoRedo, undo]
  );

  const handleToggleExpand = useCallback((widgetId: string) => {
    setExpandedWidgets((prev) => {
      const next = new Set(prev);
      if (next.has(widgetId)) {
        next.delete(widgetId);
      } else {
        next.add(widgetId);
      }
      return next;
    });
  }, []);

  const gridClassName = cn(
    'grid', // Removed gap-6 since we use inline style (Comment 8 requirement)
    columns === 1 && 'grid-cols-1',
    columns === 2 && 'grid-cols-1 md:grid-cols-2',
    columns === 3 && 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    columns === 4 && 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
    className,
  );

  const activeWidget = widgets.find(w => w.id === activeId);
  const _canUndo = historyIndex >= 0 && history.length > 0;
  const _canRedo = historyIndex < history.length - 1;

  return (
    <div className="relative">
      {/* Undo/Redo indicators */}
      {enableUndoRedo && (hasUnsavedChanges || isSaving) && (
        <div className="absolute -top-12 right-0 flex items-center gap-2">
          {hasUnsavedChanges && (
            <span className="text-sm text-muted-foreground">
              Unsaved changes
            </span>
          )}
          {isSaving && (
            <span className="text-sm text-muted-foreground">
              Saving...
            </span>
          )}
          {saveError && (
            <span className="text-sm text-destructive">
              Save failed
            </span>
          )}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
        measuring={measuringConfig}
        modifiers={[restrictToWindowEdges]}
      >
        <SortableContext items={widgets.map((w) => w.id)} strategy={rectSortingStrategy}>
          <div
            className={gridClassName}
            style={{ gap: `${gap * 0.25}rem` }}
            role="grid"
            aria-label="Dashboard widgets"
          >
            {widgets.map((widget) => (
              <SortableWidget
                key={widget.id}
                widget={widget}
                onRemove={handleRemoveWidget}
                {...(onWidgetSettings && { onSettings: onWidgetSettings })}
                isExpanded={expandedWidgets.has(widget.id)}
                onToggleExpand={handleToggleExpand}
              />
            ))}
          </div>
        </SortableContext>

        <DragOverlay
          dropAnimation={{
            duration: 200,
            easing: 'cubic-bezier(0.18, 0.67, 0.6, 1.22)',
          }}
        >
          {activeId && activeWidget ? (
            <SortableWidget
              widget={activeWidget}
              isExpanded={expandedWidgets.has(activeWidget.id)}
              onToggleExpand={() => {}}
              isOverlay
              isDragging
            />
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Screen reader announcements */}
      {showAccessibilityAnnouncements && (
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {/* Announcements will be rendered here by the store */}
        </div>
      )}
    </div>
  );
}