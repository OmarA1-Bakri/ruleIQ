'use client';

import React, { useState, useMemo } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
  MeasuringStrategy,
  UniqueIdentifier,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToVerticalAxis, restrictToParentElement } from '@dnd-kit/modifiers';
import { cn } from '@/lib/utils';
import { useLayoutStore } from '@/lib/stores/layout.store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import {
  GripVertical,
  MoreVertical,
  Edit,
  Copy,
  Trash2,
  EyeOff,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Clock,
  Filter,
} from 'lucide-react';

interface Rule {
  id: string;
  name: string;
  description?: string;
  priority: 'P0' | 'P1' | 'P2' | 'P3' | 'P4' | 'P5' | 'P6' | 'P7';
  framework: string;
  status: 'active' | 'inactive' | 'draft' | 'pending';
  category?: string;
  lastModified?: string;
  violations?: number;
  compliance?: number;
}

interface RuleListProps {
  rules: Rule[];
  onRuleClick?: (rule: Rule) => void;
  onRuleEdit?: (rule: Rule) => void;
  onRuleDelete?: (rule: Rule) => void;
  onRuleDuplicate?: (rule: Rule) => void;
  onOrderChange?: (rules: Rule[]) => void;
  onRuleOrderChange?: (ruleIds: string[]) => void;
  enableReordering?: boolean;
  enableBulkOperations?: boolean;
  showMetadata?: boolean;
  filterOptions?: {
    priorities?: string[];
    frameworks?: string[];
    statuses?: string[];
  };
  className?: string;
}

interface SortableRuleProps {
  rule: Rule;
  isSelected: boolean;
  isDragging?: boolean;
  onToggleSelect: (id: string) => void;
  onRuleClick?: (rule: Rule) => void;
  onRuleEdit?: (rule: Rule) => void;
  onRuleDelete?: (rule: Rule) => void;
  onRuleDuplicate?: (rule: Rule) => void;
  showMetadata?: boolean;
  enableReordering?: boolean;
}

const priorityColors: Record<string, string> = {
  P0: 'bg-red-500 text-white',
  P1: 'bg-orange-500 text-white',
  P2: 'bg-yellow-500 text-white',
  P3: 'bg-blue-500 text-white',
  P4: 'bg-green-500 text-white',
  P5: 'bg-purple-500 text-white',
  P6: 'bg-pink-500 text-white',
  P7: 'bg-gray-500 text-white',
};

const statusIcons: Record<string, React.ReactNode> = {
  active: <CheckCircle className="h-4 w-4 text-green-500" />,
  inactive: <EyeOff className="h-4 w-4 text-gray-400" />,
  draft: <Clock className="h-4 w-4 text-yellow-500" />,
  pending: <AlertCircle className="h-4 w-4 text-orange-500" />,
};

const SortableRule: React.FC<SortableRuleProps> = ({
  rule,
  isSelected,
  isDragging,
  onToggleSelect,
  onRuleClick,
  onRuleEdit,
  onRuleDelete,
  onRuleDuplicate,
  showMetadata = true,
  enableReordering = true,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({
    id: rule.id,
    disabled: !enableReordering,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'relative group',
        isSortableDragging && 'opacity-50',
        isDragging && 'opacity-50'
      )}
    >
      <Card
        className={cn(
          'transition-all hover:shadow-md',
          isSelected && 'ring-2 ring-primary',
          isSortableDragging && 'shadow-lg'
        )}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            {/* Drag Handle */}
            {enableReordering && (
              <button
                className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity cursor-move"
                {...attributes}
                {...listeners}
                aria-label={`Reorder ${rule.name}`}
              >
                <GripVertical className="h-5 w-5 text-gray-400" />
              </button>
            )}

            {/* Checkbox for bulk operations */}
            <Checkbox
              checked={isSelected}
              onCheckedChange={() => onToggleSelect(rule.id)}
              aria-label={`Select ${rule.name}`}
              className="mt-1"
            />

            {/* Rule Content */}
            <div
              className="flex-1 cursor-pointer"
              onClick={() => onRuleClick?.(rule)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onRuleClick?.(rule);
                }
              }}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-sm">{rule.name}</h4>
                    <Badge className={cn('text-xs', priorityColors[rule.priority])}>
                      {rule.priority}
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {rule.framework}
                    </Badge>
                    {statusIcons[rule.status]}
                  </div>

                  {rule.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {rule.description}
                    </p>
                  )}

                  {showMetadata && (
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      {rule.category && (
                        <span className="flex items-center gap-1">
                          <ChevronRight className="h-3 w-3" />
                          {rule.category}
                        </span>
                      )}
                      {rule.violations !== undefined && (
                        <span className="flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />
                          {rule.violations} violations
                        </span>
                      )}
                      {rule.compliance !== undefined && (
                        <span className="flex items-center gap-1">
                          <CheckCircle className="h-3 w-3" />
                          {rule.compliance}% compliant
                        </span>
                      )}
                      {rule.lastModified && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {rule.lastModified}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions Menu */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-4 w-4" />
                      <span className="sr-only">Rule actions</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        onRuleEdit?.(rule);
                      }}
                    >
                      <Edit className="mr-2 h-4 w-4" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        onRuleDuplicate?.(rule);
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      Duplicate
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        onRuleDelete?.(rule);
                      }}
                      className="text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export const RuleList: React.FC<RuleListProps> = ({
  rules: initialRules,
  onRuleClick,
  onRuleEdit,
  onRuleDelete,
  onRuleDuplicate,
  onOrderChange,
  onRuleOrderChange,
  enableReordering = true,
  enableBulkOperations = true,
  showMetadata = true,
  filterOptions,
  className,
}) => {
  const [rules, setRules] = useState(initialRules);
  const [selectedRules, setSelectedRules] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);
  const [activeFilters, setActiveFilters] = useState({
    priority: null as string | null,
    framework: null as string | null,
    status: null as string | null,
  });

  const { moveRule, batchMoveRules, addAnnouncement } = useLayoutStore();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const measuringConfig = {
    droppable: {
      strategy: MeasuringStrategy.Always,
    },
  };

  const filteredRules = useMemo(() => {
    return rules.filter((rule) => {
      if (activeFilters.priority && rule.priority !== activeFilters.priority) {
        return false;
      }
      if (activeFilters.framework && rule.framework !== activeFilters.framework) {
        return false;
      }
      if (activeFilters.status && rule.status !== activeFilters.status) {
        return false;
      }
      return true;
    });
  }, [rules, activeFilters]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id);
    addAnnouncement({
      message: `Started dragging rule ${event.active.id}`,
      severity: 'info',
      politeness: 'polite',
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setRules((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);

        const newOrder = arrayMove(items, oldIndex, newIndex);

        // Update store
        moveRule(active.id as string, newIndex);

        // Notify parent with rule IDs as required
        onOrderChange?.(newOrder);
        // Also call onRuleOrderChange if provided (Comment 1 requirement)
        const ruleIds = newOrder.map(item => item.id);
        onRuleOrderChange?.(ruleIds);

        addAnnouncement({
          message: `Moved rule ${active.id} to position ${newIndex + 1}`,
          severity: 'success',
          politeness: 'assertive',
        });

        return newOrder;
      });
    }

    setActiveId(null);
  };

  const handleDragCancel = () => {
    setActiveId(null);
    addAnnouncement({
      message: 'Drag cancelled',
      severity: 'info',
      politeness: 'polite',
    });
  };

  const toggleRuleSelection = (ruleId: string) => {
    setSelectedRules((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) {
        next.delete(ruleId);
      } else {
        next.add(ruleId);
      }
      return next;
    });
  };

  const selectAllRules = () => {
    setSelectedRules(new Set(filteredRules.map((r) => r.id)));
  };

  const deselectAllRules = () => {
    setSelectedRules(new Set());
  };

  const handleBulkDelete = () => {
    const rulesToDelete = rules.filter((r) => selectedRules.has(r.id));
    rulesToDelete.forEach((rule) => onRuleDelete?.(rule));
    setSelectedRules(new Set());
  };

  const _handleBulkStatusChange = (_status: Rule['status']) => {
    // Handle bulk status change
    const updates = Array.from(selectedRules).map((id, index) => ({
      ruleId: id,
      newOrder: index,
    }));
    batchMoveRules(updates);
    setSelectedRules(new Set());
  };

  const activeRule = rules.find((r) => r.id === activeId);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Filters and Bulk Actions */}
      {(filterOptions || enableBulkOperations) && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {filterOptions && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Filter className="mr-2 h-4 w-4" />
                    Filter
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48">
                  {filterOptions.priorities && (
                    <>
                      <div className="px-2 py-1.5 text-sm font-semibold">Priority</div>
                      {filterOptions.priorities.map((priority) => (
                        <DropdownMenuItem
                          key={priority}
                          onClick={() =>
                            setActiveFilters((prev) => ({
                              ...prev,
                              priority: prev.priority === priority ? null : priority,
                            }))
                          }
                        >
                          <Badge className={cn('mr-2', priorityColors[priority])}>
                            {priority}
                          </Badge>
                          {activeFilters.priority === priority && '✓'}
                        </DropdownMenuItem>
                      ))}
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {/* Add more filter options as needed */}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {enableBulkOperations && selectedRules.size > 0 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={deselectAllRules}
                >
                  Clear Selection ({selectedRules.size})
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkDelete}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Selected
                </Button>
              </>
            )}
          </div>

          {enableBulkOperations && (
            <Button
              variant="ghost"
              size="sm"
              onClick={selectAllRules}
            >
              Select All
            </Button>
          )}
        </div>
      )}

      {/* Rule List */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
        measuring={measuringConfig}
        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
      >
        <SortableContext
          items={filteredRules.map((r) => r.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2" role="list" aria-label="Rules list">
            {filteredRules.map((rule) => (
              <SortableRule
                key={rule.id}
                rule={rule}
                isSelected={selectedRules.has(rule.id)}
                onToggleSelect={toggleRuleSelection}
                {...(onRuleClick && { onRuleClick })}
                {...(onRuleEdit && { onRuleEdit })}
                {...(onRuleDelete && { onRuleDelete })}
                {...(onRuleDuplicate && { onRuleDuplicate })}
                showMetadata={showMetadata}
                enableReordering={enableReordering}
              />
            ))}
          </div>
        </SortableContext>

        <DragOverlay>
          {activeId && activeRule ? (
            <Card className="shadow-xl">
              <CardContent className="p-4">
                <div className="flex items-center gap-2">
                  <GripVertical className="h-5 w-5 text-gray-400" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-sm">{activeRule.name}</h4>
                      <Badge className={cn('text-xs', priorityColors[activeRule.priority])}>
                        {activeRule.priority}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Empty State */}
      {filteredRules.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          {activeFilters.priority || activeFilters.framework || activeFilters.status
            ? 'No rules match the selected filters.'
            : 'No rules available.'}
        </div>
      )}
    </div>
  );
};