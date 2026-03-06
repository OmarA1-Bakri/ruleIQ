import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the layout types used by the store
vi.mock('@/types/layout', () => ({
  // The types are just TypeScript interfaces; the store only imports them for type annotations.
  // We don't need to mock anything for runtime, but this prevents import errors.
}));

// We test the layout store by dynamically importing it after mocks are set up.
// Zustand stores are singletons, so we use vi.resetModules() between tests.

function createMockLayout(overrides: Record<string, any> = {}) {
  return {
    id: 'layout-1',
    userId: 'user-1',
    widgets: [
      { id: 'w-1', x: 0, y: 0, width: 2, height: 2, type: 'compliance-score' },
      { id: 'w-2', x: 2, y: 0, width: 2, height: 2, type: 'pending-tasks' },
    ],
    ruleOrder: ['rule-1', 'rule-2', 'rule-3'],
    ...overrides,
  };
}

async function getStore() {
  const mod = await import('@/lib/stores/layout.store');
  return mod.useLayoutStore;
}

describe('Layout Store', () => {
  beforeEach(() => {
    vi.resetModules();
    // Clear localStorage to avoid persisted state from leaking between tests
    localStorage.clear();
  });

  // ── Initial State ──────────────────────────────────────

  describe('initial state', () => {
    it('has null currentLayout', async () => {
      const useStore = await getStore();
      expect(useStore.getState().currentLayout).toBeNull();
    });

    it('has empty history', async () => {
      const useStore = await getStore();
      expect(useStore.getState().history).toEqual([]);
      expect(useStore.getState().historyIndex).toBe(-1);
    });

    it('has default drag state', async () => {
      const useStore = await getStore();
      const { dragState } = useStore.getState();
      expect(dragState.isDragging).toBe(false);
      expect(dragState.draggedItem).toBeNull();
      expect(dragState.activeDropZone).toBeNull();
    });

    it('has default preferences', async () => {
      const useStore = await getStore();
      const { preferences } = useStore.getState();
      expect(preferences.enableAutoSave).toBe(true);
      expect(preferences.snapToGrid).toBe(true);
      expect(preferences.gridSize).toBe(10);
      expect(preferences.enableKeyboardShortcuts).toBe(true);
      expect(preferences.compactMode).toBe(false);
      expect(preferences.announceMovements).toBe(true);
    });

    it('has clean persistence state', async () => {
      const useStore = await getStore();
      expect(useStore.getState().isDirty).toBe(false);
      expect(useStore.getState().isSaving).toBe(false);
      expect(useStore.getState().lastSaved).toBeNull();
      expect(useStore.getState().saveError).toBeNull();
    });
  });

  // ── saveLayout ─────────────────────────────────────────

  describe('saveLayout', () => {
    it('sets currentLayout and marks clean', async () => {
      const useStore = await getStore();
      const layout = createMockLayout();

      useStore.getState().saveLayout(layout as any);

      expect(useStore.getState().currentLayout).toEqual(layout);
      expect(useStore.getState().isDirty).toBe(false);
      expect(useStore.getState().isSaving).toBe(false);
      expect(useStore.getState().saveError).toBeNull();
      expect(useStore.getState().lastSaved).toBeTruthy();
    });
  });

  // ── loadLayout ─────────────────────────────────────────

  describe('loadLayout', () => {
    it('sets layout and clears history', async () => {
      const useStore = await getStore();
      const layout = createMockLayout();

      useStore.getState().loadLayout(layout as any);

      expect(useStore.getState().currentLayout).toEqual(layout);
      expect(useStore.getState().history).toEqual([]);
      expect(useStore.getState().historyIndex).toBe(-1);
      expect(useStore.getState().isDirty).toBe(false);
    });
  });

  // ── moveWidget ─────────────────────────────────────────

  describe('moveWidget', () => {
    it('does nothing when no layout is loaded', async () => {
      const useStore = await getStore();
      useStore.getState().moveWidget('w-1', { x: 5 });
      expect(useStore.getState().currentLayout).toBeNull();
    });

    it('updates widget position and adds history', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveWidget('w-1', { x: 5, y: 3 });

      const state = useStore.getState();
      const widget = state.currentLayout!.widgets.find((w: any) => w.id === 'w-1');
      expect(widget.x).toBe(5);
      expect(widget.y).toBe(3);
      expect(state.history).toHaveLength(1);
      expect(state.historyIndex).toBe(0);
      expect(state.isDirty).toBe(true);
    });

    it('does nothing for non-existent widget', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveWidget('non-existent', { x: 5 });

      // History should still be empty
      expect(useStore.getState().history).toHaveLength(0);
    });

    it('adds accessibility announcement when announceMovements is enabled', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveWidget('w-1', { x: 5 });

      const announcements = useStore.getState().announcements;
      expect(announcements.length).toBeGreaterThanOrEqual(1);
      expect(announcements[announcements.length - 1].message).toContain('w-1');
    });
  });

  // ── resizeWidget ───────────────────────────────────────

  describe('resizeWidget', () => {
    it('updates widget size and adds history', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().resizeWidget('w-1', { width: 4, height: 3 });

      const state = useStore.getState();
      const widget = state.currentLayout!.widgets.find((w: any) => w.id === 'w-1');
      expect(widget.width).toBe(4);
      expect(widget.height).toBe(3);
      expect(state.history).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });

    it('does nothing for non-existent widget', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().resizeWidget('non-existent', { width: 4, height: 3 });

      expect(useStore.getState().history).toHaveLength(0);
    });
  });

  // ── removeWidget ───────────────────────────────────────

  describe('removeWidget', () => {
    it('removes widget from layout and adds history', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().removeWidget('w-1');

      const state = useStore.getState();
      expect(state.currentLayout!.widgets).toHaveLength(1);
      expect(state.currentLayout!.widgets[0].id).toBe('w-2');
      expect(state.history).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });
  });

  // ── addWidget ──────────────────────────────────────────

  describe('addWidget', () => {
    it('adds widget to layout and adds history', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      const newWidget = { id: 'w-3', x: 0, y: 2, width: 2, height: 2, type: 'activity-feed' };
      useStore.getState().addWidget(newWidget as any);

      const state = useStore.getState();
      expect(state.currentLayout!.widgets).toHaveLength(3);
      expect(state.currentLayout!.widgets[2].id).toBe('w-3');
      expect(state.history).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });
  });

  // ── moveRule ───────────────────────────────────────────

  describe('moveRule', () => {
    it('moves a rule to a new position', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveRule('rule-3', 0);

      const state = useStore.getState();
      expect(state.currentLayout!.ruleOrder[0]).toBe('rule-3');
      expect(state.history).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });

    it('adds accessibility announcement for rule move', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveRule('rule-2', 0);

      const announcements = useStore.getState().announcements;
      expect(announcements.length).toBeGreaterThanOrEqual(1);
      expect(announcements[announcements.length - 1].message).toContain('rule-2');
    });
  });

  // ── batchMoveRules ─────────────────────────────────────

  describe('batchMoveRules', () => {
    it('applies multiple rule moves and adds single history entry', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().batchMoveRules([
        { ruleId: 'rule-3', newOrder: 0 },
        { ruleId: 'rule-1', newOrder: 2 },
      ]);

      const state = useStore.getState();
      expect(state.history).toHaveLength(1);
      expect(state.history[0].description).toContain('2 rules');
      expect(state.isDirty).toBe(true);
    });
  });

  // ── undo / redo ────────────────────────────────────────

  describe('undo', () => {
    it('returns false when no history exists', async () => {
      const useStore = await getStore();
      const result = useStore.getState().undo();
      expect(result).toBe(false);
    });

    it('returns false when no layout is loaded', async () => {
      const useStore = await getStore();
      const result = useStore.getState().undo();
      expect(result).toBe(false);
    });

    it('restores previous widget state', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      // Perform an action
      useStore.getState().moveWidget('w-1', { x: 99, y: 99 });
      expect(useStore.getState().currentLayout!.widgets[0].x).toBe(99);

      // Undo
      const result = useStore.getState().undo();
      expect(result).toBe(true);
      expect(useStore.getState().historyIndex).toBe(-1);
    });

    it('adds undo announcement when announceMovements is enabled', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);
      useStore.getState().moveWidget('w-1', { x: 99 });

      const prevAnnouncementCount = useStore.getState().announcements.length;
      useStore.getState().undo();

      expect(useStore.getState().announcements.length).toBeGreaterThan(prevAnnouncementCount);
      const lastAnnouncement = useStore.getState().announcements[useStore.getState().announcements.length - 1];
      expect(lastAnnouncement.message).toContain('Undo');
    });
  });

  describe('redo', () => {
    it('returns false when at end of history', async () => {
      const useStore = await getStore();
      const result = useStore.getState().redo();
      expect(result).toBe(false);
    });

    it('redoes an undone action', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().moveWidget('w-1', { x: 50 });
      useStore.getState().undo();

      const result = useStore.getState().redo();
      expect(result).toBe(true);
      expect(useStore.getState().historyIndex).toBe(0);
    });

    it('adds redo announcement', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);
      useStore.getState().moveWidget('w-1', { x: 50 });
      useStore.getState().undo();

      const prevCount = useStore.getState().announcements.length;
      useStore.getState().redo();

      expect(useStore.getState().announcements.length).toBeGreaterThan(prevCount);
      const last = useStore.getState().announcements[useStore.getState().announcements.length - 1];
      expect(last.message).toContain('Redo');
    });
  });

  // ── clearHistory ───────────────────────────────────────

  describe('clearHistory', () => {
    it('clears all history entries', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);
      useStore.getState().moveWidget('w-1', { x: 5 });
      useStore.getState().moveWidget('w-2', { x: 10 });

      expect(useStore.getState().history.length).toBeGreaterThan(0);

      useStore.getState().clearHistory();

      expect(useStore.getState().history).toEqual([]);
      expect(useStore.getState().historyIndex).toBe(-1);
    });
  });

  // ── resetLayout ────────────────────────────────────────

  describe('resetLayout', () => {
    it('clears widgets and ruleOrder and adds history', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      useStore.getState().resetLayout();

      const state = useStore.getState();
      expect(state.currentLayout!.widgets).toEqual([]);
      expect(state.currentLayout!.ruleOrder).toEqual([]);
      expect(state.history).toHaveLength(1);
      expect(state.history[0].description).toContain('Reset layout');
      expect(state.isDirty).toBe(true);
    });

    it('does nothing when no layout is loaded', async () => {
      const useStore = await getStore();
      useStore.getState().resetLayout();
      expect(useStore.getState().currentLayout).toBeNull();
    });
  });

  // ── Drag State ─────────────────────────────────────────

  describe('setDragState', () => {
    it('updates drag state partially', async () => {
      const useStore = await getStore();
      useStore.getState().setDragState({ isDragging: true });

      expect(useStore.getState().dragState.isDragging).toBe(true);
      // Other drag state properties should remain unchanged
      expect(useStore.getState().dragState.draggedItem).toBeNull();
    });
  });

  describe('clearDragState', () => {
    it('resets drag state to defaults', async () => {
      const useStore = await getStore();
      useStore.getState().setDragState({ isDragging: true });
      useStore.getState().clearDragState();

      const { dragState } = useStore.getState();
      expect(dragState.isDragging).toBe(false);
      expect(dragState.draggedItem).toBeNull();
      expect(dragState.activeDropZone).toBeNull();
    });
  });

  // ── Preferences ────────────────────────────────────────

  describe('setPreferences', () => {
    it('updates preferences partially', async () => {
      const useStore = await getStore();
      useStore.getState().setPreferences({ compactMode: true, gridSize: 20 });

      const { preferences } = useStore.getState();
      expect(preferences.compactMode).toBe(true);
      expect(preferences.gridSize).toBe(20);
      // Other preferences should remain unchanged
      expect(preferences.enableAutoSave).toBe(true);
    });
  });

  // ── Announcements ──────────────────────────────────────

  describe('addAnnouncement', () => {
    it('adds an announcement with generated id and timestamp', async () => {
      const useStore = await getStore();
      useStore.getState().addAnnouncement({
        message: 'Test announcement',
        severity: 'info',
        politeness: 'polite',
      });

      const announcements = useStore.getState().announcements;
      expect(announcements).toHaveLength(1);
      expect(announcements[0].message).toBe('Test announcement');
      expect(announcements[0].id).toBeTruthy();
      expect(announcements[0].timestamp).toBeGreaterThan(0);
    });
  });

  describe('clearAnnouncements', () => {
    it('clears all announcements', async () => {
      const useStore = await getStore();
      useStore.getState().addAnnouncement({
        message: 'Test 1',
        severity: 'info',
        politeness: 'polite',
      });
      useStore.getState().addAnnouncement({
        message: 'Test 2',
        severity: 'warning',
        politeness: 'assertive',
      });

      expect(useStore.getState().announcements).toHaveLength(2);

      useStore.getState().clearAnnouncements();

      expect(useStore.getState().announcements).toEqual([]);
    });
  });

  // ── Persistence State ──────────────────────────────────

  describe('markDirty', () => {
    it('sets isDirty to true', async () => {
      const useStore = await getStore();
      expect(useStore.getState().isDirty).toBe(false);

      useStore.getState().markDirty();

      expect(useStore.getState().isDirty).toBe(true);
    });
  });

  describe('markClean', () => {
    it('sets isDirty to false and updates lastSaved', async () => {
      const useStore = await getStore();
      useStore.getState().markDirty();
      expect(useStore.getState().isDirty).toBe(true);

      useStore.getState().markClean();

      expect(useStore.getState().isDirty).toBe(false);
      expect(useStore.getState().lastSaved).toBeTruthy();
    });
  });

  describe('setSaveError', () => {
    it('sets save error and stops saving', async () => {
      const useStore = await getStore();
      useStore.getState().setSaveError('Network error');

      expect(useStore.getState().saveError).toBe('Network error');
      expect(useStore.getState().isSaving).toBe(false);
    });

    it('clears save error when set to null', async () => {
      const useStore = await getStore();
      useStore.getState().setSaveError('Error');
      useStore.getState().setSaveError(null);

      expect(useStore.getState().saveError).toBeNull();
    });
  });

  // ── History Truncation ─────────────────────────────────

  describe('history management', () => {
    it('truncates future history when new action is performed after undo', async () => {
      const useStore = await getStore();
      useStore.getState().loadLayout(createMockLayout() as any);

      // Perform two moves
      useStore.getState().moveWidget('w-1', { x: 1 });
      useStore.getState().moveWidget('w-1', { x: 2 });
      expect(useStore.getState().history).toHaveLength(2);

      // Undo one step
      useStore.getState().undo();
      expect(useStore.getState().historyIndex).toBe(0);

      // Perform a new action - this should truncate the future history
      useStore.getState().moveWidget('w-1', { x: 3 });
      expect(useStore.getState().history).toHaveLength(2); // only 2, not 3
    });
  });
});
