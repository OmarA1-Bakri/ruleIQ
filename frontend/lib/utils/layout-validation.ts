import { z } from 'zod';
import {
  DashboardLayout,
  WidgetPosition,
  RuleOrderConfig,
  LayoutValidationError,
  LayoutConflictResolution,
} from '@/types/layout';

// Schema definitions for validation
const WidgetPositionSchema = z.object({
  id: z.string().min(1),
  gridX: z.number().min(0),
  gridY: z.number().min(0),
  width: z.number().min(1).max(12),
  height: z.number().min(1).max(12),
  minWidth: z.number().min(1).optional(),
  minHeight: z.number().min(1).optional(),
  maxWidth: z.number().max(12).optional(),
  maxHeight: z.number().max(12).optional(),
  static: z.boolean().optional(),
});

const DashboardLayoutSchema = z.object({
  id: z.string().min(1),
  userId: z.string().min(1),
  name: z.string().min(1).max(100),
  widgets: z.array(WidgetPositionSchema),
  ruleOrder: z.array(z.string()),
  gridCols: z.number().min(1).max(24).optional(),
  rowHeight: z.number().min(10).max(200).optional(),
  compactType: z.enum(['vertical', 'horizontal']).nullable().optional(),
  preventCollision: z.boolean().optional(),
  metadata: z.object({
    createdAt: z.string(),
    updatedAt: z.string(),
    version: z.number().min(0),
    isDefault: z.boolean().optional(),
    isShared: z.boolean().optional(),
  }),
});

const RuleOrderConfigSchema = z.object({
  ruleId: z.string().min(1),
  order: z.number().min(0),
  priority: z.enum(['P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']),
  framework: z.string().min(1),
  groupId: z.string().optional(),
  dependencies: z.array(z.string()).optional(),
});

// Grid constraints
const GRID_CONSTRAINTS = {
  MIN_COLS: 1,
  MAX_COLS: 24,
  MIN_ROWS: 1,
  MAX_ROWS: 100,
  MIN_WIDGET_SIZE: 1,
  MAX_WIDGET_SIZE: 12,
  DEFAULT_COLS: 12,
  DEFAULT_ROW_HEIGHT: 50,
};

// Performance limits
const PERFORMANCE_LIMITS = {
  MAX_WIDGETS: 100,
  MAX_RULES: 500,
  MAX_HISTORY_SIZE: 50,
  MAX_LAYOUT_SIZE_KB: 500,
};

// Validate widget layout
export function validateWidgetLayout(
  layout: DashboardLayout
): { valid: boolean; errors: LayoutValidationError[] } {
  const errors: LayoutValidationError[] = [];

  // Validate schema
  try {
    DashboardLayoutSchema.parse(layout);
  } catch (error) {
    if (error instanceof z.ZodError) {
      errors.push(
        ...error.errors.map(e => ({
          field: e.path.join('.'),
          message: e.message,
          severity: 'error' as const,
        }))
      );
    }
  }

  // Check for widget overlaps
  const overlaps = findWidgetOverlaps(layout.widgets);
  if (overlaps.length > 0) {
    overlaps.forEach(([w1, w2]) => {
      errors.push({
        field: 'widgets',
        message: `Widget "${w1.id}" overlaps with widget "${w2.id}"`,
        severity: 'error',
        suggestion: 'Adjust widget positions to prevent overlap',
      });
    });
  }

  // Check grid bounds
  const outOfBounds = findOutOfBoundsWidgets(
    layout.widgets,
    layout.gridCols || GRID_CONSTRAINTS.DEFAULT_COLS
  );
  if (outOfBounds.length > 0) {
    outOfBounds.forEach(widget => {
      errors.push({
        field: `widgets.${widget.id}`,
        message: `Widget "${widget.id}" extends beyond grid boundaries`,
        severity: 'error',
        suggestion: `Adjust position to fit within ${layout.gridCols || GRID_CONSTRAINTS.DEFAULT_COLS} columns`,
      });
    });
  }

  // Check for duplicate widget IDs
  const duplicateIds = findDuplicateIds(layout.widgets);
  if (duplicateIds.length > 0) {
    duplicateIds.forEach(id => {
      errors.push({
        field: 'widgets',
        message: `Duplicate widget ID: "${id}"`,
        severity: 'error',
        suggestion: 'Ensure all widget IDs are unique',
      });
    });
  }

  // Check widget size constraints
  layout.widgets.forEach(widget => {
    if (widget.minWidth && widget.width < widget.minWidth) {
      errors.push({
        field: `widgets.${widget.id}`,
        message: `Widget "${widget.id}" width is below minimum`,
        severity: 'warning',
        suggestion: `Increase width to at least ${widget.minWidth}`,
      });
    }
    if (widget.maxWidth && widget.width > widget.maxWidth) {
      errors.push({
        field: `widgets.${widget.id}`,
        message: `Widget "${widget.id}" width exceeds maximum`,
        severity: 'warning',
        suggestion: `Decrease width to at most ${widget.maxWidth}`,
      });
    }
  });

  // Performance checks
  if (layout.widgets.length > PERFORMANCE_LIMITS.MAX_WIDGETS) {
    errors.push({
      field: 'widgets',
      message: `Too many widgets (${layout.widgets.length} > ${PERFORMANCE_LIMITS.MAX_WIDGETS})`,
      severity: 'warning',
      suggestion: 'Consider reducing the number of widgets for better performance',
    });
  }

  return {
    valid: errors.filter(e => e.severity === 'error').length === 0,
    errors,
  };
}

// Validate rule order
export function validateRuleOrder(
  rules: RuleOrderConfig[]
): { valid: boolean; errors: LayoutValidationError[] } {
  const errors: LayoutValidationError[] = [];

  // Validate schema
  rules.forEach((rule, index) => {
    try {
      RuleOrderConfigSchema.parse(rule);
    } catch (error) {
      if (error instanceof z.ZodError) {
        errors.push(
          ...error.errors.map(e => ({
            field: `rules[${index}].${e.path.join('.')}`,
            message: e.message,
            severity: 'error' as const,
          }))
        );
      }
    }
  });

  // Check for duplicate rule IDs
  const ruleIds = new Set<string>();
  const duplicates = new Set<string>();
  rules.forEach(rule => {
    if (ruleIds.has(rule.ruleId)) {
      duplicates.add(rule.ruleId);
    }
    ruleIds.add(rule.ruleId);
  });

  if (duplicates.size > 0) {
    duplicates.forEach(id => {
      errors.push({
        field: 'rules',
        message: `Duplicate rule ID: "${id}"`,
        severity: 'error',
        suggestion: 'Ensure all rule IDs are unique',
      });
    });
  }

  // Check order sequence
  const orders = rules.map(r => r.order).sort((a, b) => a - b);
  for (let i = 1; i < orders.length; i++) {
    if (orders[i]! - orders[i - 1]! > 1) {
      errors.push({
        field: 'rules',
        message: `Gap in rule order sequence between ${orders[i - 1]} and ${orders[i]}`,
        severity: 'warning',
        suggestion: 'Consider reindexing rules for continuous ordering',
      });
    }
  }

  // Check dependencies
  rules.forEach(rule => {
    if (rule.dependencies) {
      rule.dependencies.forEach(depId => {
        if (!ruleIds.has(depId)) {
          errors.push({
            field: `rules.${rule.ruleId}.dependencies`,
            message: `Rule "${rule.ruleId}" depends on non-existent rule "${depId}"`,
            severity: 'error',
            suggestion: 'Remove invalid dependency or add the missing rule',
          });
        }
      });
    }
  });

  // Check for circular dependencies
  const circularDeps = findCircularDependencies(rules);
  if (circularDeps.length > 0) {
    circularDeps.forEach(cycle => {
      errors.push({
        field: 'rules',
        message: `Circular dependency detected: ${cycle.join(' → ')}`,
        severity: 'error',
        suggestion: 'Remove one of the dependencies to break the cycle',
      });
    });
  }

  return {
    valid: errors.filter(e => e.severity === 'error').length === 0,
    errors,
  };
}

// Sanitize layout data
export function sanitizeLayoutData(layout: Partial<DashboardLayout>): DashboardLayout {
  // Provide defaults for missing fields
  const sanitized: DashboardLayout = {
    id: layout.id || `layout-${Date.now()}`,
    userId: layout.userId || 'default',
    name: layout.name || 'Untitled Layout',
    widgets: layout.widgets || [],
    ruleOrder: layout.ruleOrder || [],
    gridCols: layout.gridCols || GRID_CONSTRAINTS.DEFAULT_COLS,
    rowHeight: layout.rowHeight || GRID_CONSTRAINTS.DEFAULT_ROW_HEIGHT,
    compactType: layout.compactType !== undefined ? layout.compactType : 'vertical',
    preventCollision: layout.preventCollision !== undefined ? layout.preventCollision : false,
    metadata: {
      createdAt: layout.metadata?.createdAt || new Date().toISOString(),
      updatedAt: layout.metadata?.updatedAt || new Date().toISOString(),
      version: layout.metadata?.version || 1,
      isDefault: layout.metadata?.isDefault || false,
      isShared: layout.metadata?.isShared || false,
    },
  };

  // Sanitize widget positions
  sanitized.widgets = sanitized.widgets.map(widget => ({
    ...widget,
    gridX: Math.max(0, Math.min(widget.gridX, (sanitized.gridCols || GRID_CONSTRAINTS.DEFAULT_COLS) - 1)),
    gridY: Math.max(0, Math.min(widget.gridY, GRID_CONSTRAINTS.MAX_ROWS - 1)),
    width: Math.max(GRID_CONSTRAINTS.MIN_WIDGET_SIZE, Math.min(widget.width, GRID_CONSTRAINTS.MAX_WIDGET_SIZE)),
    height: Math.max(GRID_CONSTRAINTS.MIN_WIDGET_SIZE, Math.min(widget.height, GRID_CONSTRAINTS.MAX_WIDGET_SIZE)),
  }));

  // Remove duplicate widget IDs
  const seenIds = new Set<string>();
  sanitized.widgets = sanitized.widgets.filter(widget => {
    if (seenIds.has(widget.id)) {
      return false;
    }
    seenIds.add(widget.id);
    return true;
  });

  // Remove duplicate rule orders
  sanitized.ruleOrder = Array.from(new Set(sanitized.ruleOrder));

  return sanitized;
}

// Helper functions
function findWidgetOverlaps(widgets: WidgetPosition[]): Array<[WidgetPosition, WidgetPosition]> {
  const overlaps: Array<[WidgetPosition, WidgetPosition]> = [];

  for (let i = 0; i < widgets.length - 1; i++) {
    for (let j = i + 1; j < widgets.length; j++) {
      const w1 = widgets[i]!;
      const w2 = widgets[j]!;

      if (w1.static || w2.static) continue; // Skip static widgets

      const overlap =
        w1.gridX < w2.gridX + w2.width &&
        w1.gridX + w1.width > w2.gridX &&
        w1.gridY < w2.gridY + w2.height &&
        w1.gridY + w1.height > w2.gridY;

      if (overlap) {
        overlaps.push([w1, w2]);
      }
    }
  }

  return overlaps;
}

function findOutOfBoundsWidgets(widgets: WidgetPosition[], gridCols: number): WidgetPosition[] {
  return widgets.filter(widget => {
    return (
      widget.gridX < 0 ||
      widget.gridY < 0 ||
      widget.gridX + widget.width > gridCols ||
      widget.gridY + widget.height > GRID_CONSTRAINTS.MAX_ROWS
    );
  });
}

function findDuplicateIds(widgets: WidgetPosition[]): string[] {
  const ids = new Map<string, number>();
  widgets.forEach(widget => {
    ids.set(widget.id, (ids.get(widget.id) || 0) + 1);
  });

  return Array.from(ids.entries())
    .filter(([, count]) => count > 1)
    .map(([id]) => id);
}

function findCircularDependencies(rules: RuleOrderConfig[]): string[][] {
  const graph = new Map<string, string[]>();
  rules.forEach(rule => {
    graph.set(rule.ruleId, rule.dependencies || []);
  });

  const cycles: string[][] = [];
  const visited = new Set<string>();
  const stack = new Set<string>();

  function dfs(node: string, path: string[]): void {
    if (stack.has(node)) {
      const cycleStart = path.indexOf(node);
      cycles.push(path.slice(cycleStart).concat(node));
      return;
    }

    if (visited.has(node)) return;

    visited.add(node);
    stack.add(node);
    path.push(node);

    const neighbors = graph.get(node) || [];
    for (const neighbor of neighbors) {
      dfs(neighbor, [...path]);
    }

    stack.delete(node);
  }

  for (const ruleId of graph.keys()) {
    if (!visited.has(ruleId)) {
      dfs(ruleId, []);
    }
  }

  return cycles;
}

// Conflict resolution
export function resolveLayoutConflicts(
  local: DashboardLayout,
  remote: DashboardLayout,
  strategy: LayoutConflictResolution['strategy'] = 'last-write-wins'
): DashboardLayout {
  switch (strategy) {
    case 'last-write-wins':
      // Use the version with the most recent update time
      return new Date(local.metadata.updatedAt) > new Date(remote.metadata.updatedAt)
        ? local
        : remote;

    case 'merge':
      // Merge both layouts, preferring local changes for widgets
      return {
        ...remote,
        widgets: mergeWidgets(local.widgets, remote.widgets),
        ruleOrder: mergeRuleOrders(local.ruleOrder, remote.ruleOrder),
        metadata: {
          ...remote.metadata,
          updatedAt: new Date().toISOString(),
          version: Math.max(local.metadata.version, remote.metadata.version) + 1,
        },
      };

    case 'user-choice':
      // This would typically show a dialog to the user
      // For now, default to local version
      return local;

    default:
      return local;
  }
}

function mergeWidgets(
  local: WidgetPosition[],
  remote: WidgetPosition[]
): WidgetPosition[] {
  const merged = new Map<string, WidgetPosition>();

  // Add all remote widgets first
  remote.forEach(widget => {
    merged.set(widget.id, widget);
  });

  // Override with local widgets (local takes precedence)
  local.forEach(widget => {
    merged.set(widget.id, widget);
  });

  return Array.from(merged.values());
}

function mergeRuleOrders(local: string[], remote: string[]): string[] {
  const merged = new Set<string>();

  // Preserve order from remote, add new items from local
  remote.forEach(id => merged.add(id));
  local.forEach(id => merged.add(id));

  return Array.from(merged);
}

// Migration utilities
export function migrateLayout(
  layout: DashboardLayout,
  fromVersion: number,
  toVersion: number
): DashboardLayout {
  let migrated = { ...layout };

  // Apply migrations sequentially
  for (let v = fromVersion + 1; v <= toVersion; v++) {
    migrated = applyMigration(migrated, v);
  }

  migrated.metadata.version = toVersion;
  return migrated;
}

function applyMigration(layout: DashboardLayout, version: number): DashboardLayout {
  switch (version) {
    case 2:
      // Example: Add new field in version 2
      return {
        ...layout,
        compactType: layout.compactType || 'vertical',
      };

    case 3:
      // Example: Change data structure in version 3
      return {
        ...layout,
        widgets: layout.widgets.map(w => ({
          ...w,
          static: w.static || false,
        })),
      };

    default:
      return layout;
  }
}

// Performance validation
export function validateLayoutPerformance(
  layout: DashboardLayout
): { valid: boolean; warnings: string[] } {
  const warnings: string[] = [];

  // Check layout size
  const layoutSize = JSON.stringify(layout).length / 1024; // KB
  if (layoutSize > PERFORMANCE_LIMITS.MAX_LAYOUT_SIZE_KB) {
    warnings.push(
      `Layout size (${layoutSize.toFixed(2)}KB) exceeds recommended limit (${PERFORMANCE_LIMITS.MAX_LAYOUT_SIZE_KB}KB)`
    );
  }

  // Check widget count
  if (layout.widgets.length > PERFORMANCE_LIMITS.MAX_WIDGETS) {
    warnings.push(
      `Too many widgets (${layout.widgets.length}). Consider reducing to improve performance.`
    );
  }

  // Check rule count
  if (layout.ruleOrder.length > PERFORMANCE_LIMITS.MAX_RULES) {
    warnings.push(
      `Too many rules (${layout.ruleOrder.length}). Consider paginating or filtering.`
    );
  }

  // Check for deeply nested structures
  const maxDepth = calculateMaxDepth(layout);
  if (maxDepth > 10) {
    warnings.push(
      `Layout structure is too deeply nested (depth: ${maxDepth}). This may impact performance.`
    );
  }

  return {
    valid: warnings.length === 0,
    warnings,
  };
}

function calculateMaxDepth(obj: any, currentDepth = 0): number {
  if (typeof obj !== 'object' || obj === null) {
    return currentDepth;
  }

  let maxDepth = currentDepth;
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      const depth = calculateMaxDepth(obj[key], currentDepth + 1);
      maxDepth = Math.max(maxDepth, depth);
    }
  }

  return maxDepth;
}