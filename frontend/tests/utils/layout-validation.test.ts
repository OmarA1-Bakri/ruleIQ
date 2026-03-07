import { describe, it, expect } from 'vitest';
import {
  validateWidgetLayout,
  validateRuleOrder,
  sanitizeLayoutData,
  resolveLayoutConflicts,
  validateLayoutPerformance,
  migrateLayout,
} from '@/lib/utils/layout-validation';
import type { DashboardLayout, RuleOrderConfig } from '@/types/layout';

// Helper to create a valid base layout
function createValidLayout(overrides: Partial<DashboardLayout> = {}): DashboardLayout {
  return {
    id: 'layout-1',
    userId: 'user-1',
    name: 'Test Layout',
    widgets: [
      { id: 'w1', gridX: 0, gridY: 0, width: 4, height: 3 },
      { id: 'w2', gridX: 4, gridY: 0, width: 4, height: 3 },
    ],
    ruleOrder: ['rule-1', 'rule-2'],
    gridCols: 12,
    rowHeight: 50,
    compactType: 'vertical',
    preventCollision: false,
    metadata: {
      createdAt: '2025-01-01T00:00:00Z',
      updatedAt: '2025-01-01T00:00:00Z',
      version: 1,
      isDefault: false,
      isShared: false,
    },
    ...overrides,
  };
}

describe('validateWidgetLayout', () => {
  it('validates a correct layout as valid', () => {
    const layout = createValidLayout();
    const result = validateWidgetLayout(layout);

    expect(result.valid).toBe(true);
    expect(result.errors.filter((e) => e.severity === 'error')).toHaveLength(0);
  });

  it('detects overlapping widgets', () => {
    const layout = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 6, height: 3 },
        { id: 'w2', gridX: 3, gridY: 0, width: 6, height: 3 }, // overlaps with w1
      ],
    });

    const result = validateWidgetLayout(layout);
    const overlapErrors = result.errors.filter((e) => e.message.includes('overlaps'));
    expect(overlapErrors.length).toBeGreaterThan(0);
  });

  it('skips overlap check for static widgets', () => {
    const layout = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 6, height: 3, static: true },
        { id: 'w2', gridX: 3, gridY: 0, width: 6, height: 3 }, // overlaps but w1 is static
      ],
    });

    const result = validateWidgetLayout(layout);
    const overlapErrors = result.errors.filter((e) => e.message.includes('overlaps'));
    expect(overlapErrors).toHaveLength(0);
  });

  it('detects out-of-bounds widgets', () => {
    const layout = createValidLayout({
      gridCols: 12,
      widgets: [
        { id: 'w1', gridX: 10, gridY: 0, width: 4, height: 3 }, // exceeds 12 cols
      ],
    });

    const result = validateWidgetLayout(layout);
    const boundErrors = result.errors.filter((e) => e.message.includes('beyond grid'));
    expect(boundErrors.length).toBeGreaterThan(0);
  });

  it('detects duplicate widget IDs', () => {
    const layout = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 3, height: 3 },
        { id: 'w1', gridX: 4, gridY: 0, width: 3, height: 3 }, // duplicate
      ],
    });

    const result = validateWidgetLayout(layout);
    const dupErrors = result.errors.filter((e) => e.message.includes('Duplicate widget ID'));
    expect(dupErrors.length).toBeGreaterThan(0);
  });

  it('warns when widget width is below minimum', () => {
    const layout = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 2, height: 3, minWidth: 4 },
      ],
    });

    const result = validateWidgetLayout(layout);
    const warnings = result.errors.filter(
      (e) => e.severity === 'warning' && e.message.includes('below minimum'),
    );
    expect(warnings.length).toBeGreaterThan(0);
  });

  it('warns when widget width exceeds maximum', () => {
    const layout = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 8, height: 3, maxWidth: 4 },
      ],
    });

    const result = validateWidgetLayout(layout);
    const warnings = result.errors.filter(
      (e) => e.severity === 'warning' && e.message.includes('exceeds maximum'),
    );
    expect(warnings.length).toBeGreaterThan(0);
  });

  it('warns when too many widgets', () => {
    const manyWidgets = Array.from({ length: 101 }, (_, i) => ({
      id: `w${i}`,
      gridX: 0,
      gridY: i,
      width: 1,
      height: 1,
    }));

    const layout = createValidLayout({ widgets: manyWidgets });
    const result = validateWidgetLayout(layout);
    const perfWarnings = result.errors.filter(
      (e) => e.severity === 'warning' && e.message.includes('Too many widgets'),
    );
    expect(perfWarnings.length).toBeGreaterThan(0);
  });

  it('detects schema validation errors', () => {
    // Create a layout with an invalid schema field
    const badLayout = {
      ...createValidLayout(),
      name: '', // min 1 char
    };

    const result = validateWidgetLayout(badLayout);
    expect(result.valid).toBe(false);
  });
});

describe('validateRuleOrder', () => {
  it('validates correct rule order', () => {
    const rules: RuleOrderConfig[] = [
      { ruleId: 'r1', order: 0, priority: 'P0', framework: 'GDPR' },
      { ruleId: 'r2', order: 1, priority: 'P1', framework: 'ISO27001' },
    ];

    const result = validateRuleOrder(rules);
    expect(result.valid).toBe(true);
    expect(result.errors.filter((e) => e.severity === 'error')).toHaveLength(0);
  });

  it('detects duplicate rule IDs', () => {
    const rules: RuleOrderConfig[] = [
      { ruleId: 'r1', order: 0, priority: 'P0', framework: 'GDPR' },
      { ruleId: 'r1', order: 1, priority: 'P1', framework: 'ISO27001' }, // duplicate
    ];

    const result = validateRuleOrder(rules);
    const dupErrors = result.errors.filter((e) => e.message.includes('Duplicate rule ID'));
    expect(dupErrors.length).toBeGreaterThan(0);
  });

  it('warns about gaps in order sequence', () => {
    const rules: RuleOrderConfig[] = [
      { ruleId: 'r1', order: 0, priority: 'P0', framework: 'GDPR' },
      { ruleId: 'r2', order: 5, priority: 'P1', framework: 'ISO27001' }, // gap from 0 to 5
    ];

    const result = validateRuleOrder(rules);
    const gapWarnings = result.errors.filter(
      (e) => e.severity === 'warning' && e.message.includes('Gap in rule order'),
    );
    expect(gapWarnings.length).toBeGreaterThan(0);
  });

  it('detects missing dependency references', () => {
    const rules: RuleOrderConfig[] = [
      {
        ruleId: 'r1',
        order: 0,
        priority: 'P0',
        framework: 'GDPR',
        dependencies: ['nonexistent-rule'],
      },
    ];

    const result = validateRuleOrder(rules);
    const depErrors = result.errors.filter((e) =>
      e.message.includes('depends on non-existent rule'),
    );
    expect(depErrors.length).toBeGreaterThan(0);
  });

  it('detects circular dependencies', () => {
    const rules: RuleOrderConfig[] = [
      { ruleId: 'r1', order: 0, priority: 'P0', framework: 'GDPR', dependencies: ['r2'] },
      { ruleId: 'r2', order: 1, priority: 'P1', framework: 'GDPR', dependencies: ['r1'] },
    ];

    const result = validateRuleOrder(rules);
    const circularErrors = result.errors.filter((e) =>
      e.message.includes('Circular dependency'),
    );
    expect(circularErrors.length).toBeGreaterThan(0);
  });

  it('validates schema errors on individual rules', () => {
    const rules = [
      { ruleId: '', order: 0, priority: 'P0', framework: 'GDPR' }, // empty ruleId
    ] as RuleOrderConfig[];

    const result = validateRuleOrder(rules);
    expect(result.valid).toBe(false);
  });
});

describe('sanitizeLayoutData', () => {
  it('provides defaults for missing fields', () => {
    const sanitized = sanitizeLayoutData({});

    expect(sanitized.id).toBeDefined();
    expect(sanitized.userId).toBe('default');
    expect(sanitized.name).toBe('Untitled Layout');
    expect(sanitized.widgets).toEqual([]);
    expect(sanitized.ruleOrder).toEqual([]);
    expect(sanitized.gridCols).toBe(12);
    expect(sanitized.rowHeight).toBe(50);
    expect(sanitized.compactType).toBe('vertical');
    expect(sanitized.preventCollision).toBe(false);
    expect(sanitized.metadata).toBeDefined();
    expect(sanitized.metadata.version).toBe(1);
  });

  it('preserves provided values', () => {
    const input = {
      id: 'my-layout',
      userId: 'user-42',
      name: 'Custom Layout',
      gridCols: 8,
    };

    const sanitized = sanitizeLayoutData(input);

    expect(sanitized.id).toBe('my-layout');
    expect(sanitized.userId).toBe('user-42');
    expect(sanitized.name).toBe('Custom Layout');
    expect(sanitized.gridCols).toBe(8);
  });

  it('clamps widget positions to grid bounds', () => {
    const sanitized = sanitizeLayoutData({
      gridCols: 12,
      widgets: [
        { id: 'w1', gridX: -5, gridY: -3, width: 20, height: 15 },
      ],
    });

    const widget = sanitized.widgets[0];
    expect(widget.gridX).toBe(0); // clamped from -5
    expect(widget.gridY).toBe(0); // clamped from -3
    expect(widget.width).toBe(12); // max widget size
    expect(widget.height).toBe(12); // max widget size
  });

  it('removes duplicate widget IDs', () => {
    const sanitized = sanitizeLayoutData({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 3, height: 3 },
        { id: 'w1', gridX: 4, gridY: 0, width: 3, height: 3 }, // duplicate
        { id: 'w2', gridX: 8, gridY: 0, width: 3, height: 3 },
      ],
    });

    expect(sanitized.widgets.length).toBe(2);
    expect(sanitized.widgets.map((w) => w.id)).toEqual(['w1', 'w2']);
  });

  it('removes duplicate rule orders', () => {
    const sanitized = sanitizeLayoutData({
      ruleOrder: ['r1', 'r2', 'r1', 'r3', 'r2'],
    });

    expect(sanitized.ruleOrder).toEqual(['r1', 'r2', 'r3']);
  });
});

describe('resolveLayoutConflicts', () => {
  const baseLayout = createValidLayout();

  it('uses last-write-wins by default', () => {
    const local = createValidLayout({
      metadata: {
        ...baseLayout.metadata,
        updatedAt: '2025-06-01T00:00:00Z',
      },
    });
    const remote = createValidLayout({
      metadata: {
        ...baseLayout.metadata,
        updatedAt: '2025-01-01T00:00:00Z',
      },
    });

    const result = resolveLayoutConflicts(local, remote);
    // Local is newer, should be returned
    expect(result.metadata.updatedAt).toBe('2025-06-01T00:00:00Z');
  });

  it('picks remote when remote is newer in last-write-wins', () => {
    const local = createValidLayout({
      metadata: {
        ...baseLayout.metadata,
        updatedAt: '2025-01-01T00:00:00Z',
      },
    });
    const remote = createValidLayout({
      metadata: {
        ...baseLayout.metadata,
        updatedAt: '2025-06-01T00:00:00Z',
      },
    });

    const result = resolveLayoutConflicts(local, remote, 'last-write-wins');
    expect(result.metadata.updatedAt).toBe('2025-06-01T00:00:00Z');
  });

  it('merges widgets from both layouts (local takes precedence)', () => {
    const local = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 6, height: 3 }, // local version of w1
        { id: 'w3', gridX: 0, gridY: 4, width: 4, height: 3 }, // local-only widget
      ],
    });
    const remote = createValidLayout({
      widgets: [
        { id: 'w1', gridX: 0, gridY: 0, width: 4, height: 3 }, // remote version of w1
        { id: 'w2', gridX: 4, gridY: 0, width: 4, height: 3 }, // remote-only widget
      ],
    });

    const result = resolveLayoutConflicts(local, remote, 'merge');

    // Should contain all 3 unique widget IDs
    const widgetIds = result.widgets.map((w) => w.id);
    expect(widgetIds).toContain('w1');
    expect(widgetIds).toContain('w2');
    expect(widgetIds).toContain('w3');

    // w1 should use local version (width 6, not 4)
    const w1 = result.widgets.find((w) => w.id === 'w1');
    expect(w1?.width).toBe(6);
  });

  it('merges rule orders from both layouts', () => {
    const local = createValidLayout({ ruleOrder: ['r1', 'r3'] });
    const remote = createValidLayout({ ruleOrder: ['r1', 'r2'] });

    const result = resolveLayoutConflicts(local, remote, 'merge');

    expect(result.ruleOrder).toContain('r1');
    expect(result.ruleOrder).toContain('r2');
    expect(result.ruleOrder).toContain('r3');
  });

  it('returns local for user-choice strategy', () => {
    const local = createValidLayout({ name: 'Local' });
    const remote = createValidLayout({ name: 'Remote' });

    const result = resolveLayoutConflicts(local, remote, 'user-choice');
    expect(result.name).toBe('Local');
  });
});

describe('validateLayoutPerformance', () => {
  it('returns valid for a small layout', () => {
    const layout = createValidLayout();
    const result = validateLayoutPerformance(layout);

    expect(result.valid).toBe(true);
    expect(result.warnings).toHaveLength(0);
  });

  it('warns about too many widgets', () => {
    const manyWidgets = Array.from({ length: 101 }, (_, i) => ({
      id: `w${i}`,
      gridX: 0,
      gridY: i,
      width: 1,
      height: 1,
    }));

    const layout = createValidLayout({ widgets: manyWidgets });
    const result = validateLayoutPerformance(layout);

    const widgetWarning = result.warnings.find((w) => w.includes('Too many widgets'));
    expect(widgetWarning).toBeDefined();
  });

  it('warns about too many rules', () => {
    const manyRules = Array.from({ length: 501 }, (_, i) => `rule-${i}`);
    const layout = createValidLayout({ ruleOrder: manyRules });

    const result = validateLayoutPerformance(layout);

    const ruleWarning = result.warnings.find((w) => w.includes('Too many rules'));
    expect(ruleWarning).toBeDefined();
  });
});

describe('migrateLayout', () => {
  it('migrates from version 1 to version 2 (adds compactType)', () => {
    const layout = createValidLayout();
    // Remove compactType to simulate v1
    const v1Layout = { ...layout, compactType: undefined as any };

    const result = migrateLayout(v1Layout, 1, 2);

    expect(result.compactType).toBe('vertical');
    expect(result.metadata.version).toBe(2);
  });

  it('migrates from version 2 to version 3 (adds static to widgets)', () => {
    const layout = createValidLayout();

    const result = migrateLayout(layout, 2, 3);

    result.widgets.forEach((widget) => {
      expect(widget.static).toBeDefined();
    });
    expect(result.metadata.version).toBe(3);
  });

  it('migrates across multiple versions', () => {
    const layout = createValidLayout();

    const result = migrateLayout(layout, 1, 3);

    expect(result.metadata.version).toBe(3);
    expect(result.compactType).toBeDefined();
  });

  it('returns layout unchanged for unknown version', () => {
    const layout = createValidLayout();

    const result = migrateLayout(layout, 99, 100);
    expect(result.metadata.version).toBe(100);
  });
});
