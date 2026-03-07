import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import {
  DashboardLayout,
  LayoutHistoryItem,
  DragOperation,
  WidgetPosition,
  AccessibilityAnnouncement,
  DragState,
  LayoutPreferences,
  DragOperationType,
} from '@/types/layout';

interface LayoutState {
  // Current layout
  currentLayout: DashboardLayout | null;

  // History management
  history: LayoutHistoryItem[];
  historyIndex: number;
  maxHistorySize: number;

  // Drag state
  dragState: DragState;

  // Preferences
  preferences: LayoutPreferences;

  // Accessibility
  announcements: AccessibilityAnnouncement[];

  // Persistence state
  isDirty: boolean;
  isSaving: boolean;
  lastSaved: string | null;
  saveError: string | null;

  // Actions
  moveWidget: (widgetId: string, newPosition: Partial<WidgetPosition>) => void;
  resizeWidget: (widgetId: string, size: { width: number; height: number }) => void;
  removeWidget: (widgetId: string) => void;
  addWidget: (widget: WidgetPosition) => void;

  moveRule: (ruleId: string, newOrder: number, groupId?: string) => void;
  batchMoveRules: (moves: Array<{ ruleId: string; newOrder: number }>) => void;

  undo: () => boolean;
  redo: () => boolean;
  clearHistory: () => void;

  saveLayout: (layout: DashboardLayout) => void;
  loadLayout: (layout: DashboardLayout) => void;
  resetLayout: () => void;

  setDragState: (state: Partial<DragState>) => void;
  clearDragState: () => void;

  setPreferences: (prefs: Partial<LayoutPreferences>) => void;

  addAnnouncement: (announcement: Omit<AccessibilityAnnouncement, 'id' | 'timestamp'>) => void;
  clearAnnouncements: () => void;

  markDirty: () => void;
  markClean: () => void;
  setSaveError: (error: string | null) => void;
}

// Debounce helper
const _debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): T => {
  let timeoutId: NodeJS.Timeout;
  return ((...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  }) as T;
};

// History compression helper
const compressHistory = (history: LayoutHistoryItem[], maxSize: number): LayoutHistoryItem[] => {
  if (history.length <= maxSize) return history;

  // Keep first and last items, compress middle
  const keepFirst = Math.floor(maxSize * 0.2);
  const keepLast = Math.floor(maxSize * 0.6);
  const compressed = [
    ...history.slice(0, keepFirst),
    ...history.slice(-keepLast),
  ];

  return compressed;
};

// Create operation description
const createOperationDescription = (
  type: DragOperationType,
  item: DragOperation['item'],
  _details?: any
): string => {
  switch (type) {
    case 'widget-reorder':
      return `Moved widget "${item.id}" to new position`;
    case 'widget-resize':
      return `Resized widget "${item.id}"`;
    case 'rule-reorder':
      return `Reordered rule "${item.id}"`;
    case 'cross-container-move':
      return `Moved ${item.type} "${item.id}" to different container`;
    case 'batch-operation':
      return `Batch operation on multiple items`;
    case 'layout-reset':
      return 'Reset layout to default';
    default:
      return 'Layout changed';
  }
};

export const useLayoutStore = create<LayoutState>()(
  devtools(
    persist(
      immer((set, get) => ({
        // Initial state
        currentLayout: null,
        history: [],
        historyIndex: -1,
        maxHistorySize: 20,

        dragState: {
          isDragging: false,
          draggedItem: null,
          activeDropZone: null,
          dragOffset: { x: 0, y: 0 },
          initialPosition: { x: 0, y: 0 },
          currentPosition: { x: 0, y: 0 },
          preview: null,
        },

        preferences: {
          enableAutoSave: true,
          autoSaveInterval: 500,
          maxHistorySize: 20,
          enableAnimations: true,
          snapToGrid: true,
          gridSize: 10,
          showGridLines: false,
          enableKeyboardShortcuts: true,
          compactMode: false,
          announceMovements: true,
          highContrastMode: false,
        },

        announcements: [],
        isDirty: false,
        isSaving: false,
        lastSaved: null,
        saveError: null,

        // Widget actions
        moveWidget: (widgetId, newPosition) => set((state) => {
          if (!state.currentLayout) return;

          const widgetIndex = state.currentLayout.widgets.findIndex(w => w.id === widgetId);
          if (widgetIndex === -1) return;

          // Save previous state for history
          const previousState = { widgets: [...state.currentLayout.widgets] };

          // Update widget position
          state.currentLayout.widgets[widgetIndex] = {
            ...state.currentLayout.widgets[widgetIndex],
            ...newPosition,
          };

          // Add to history
          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'widget-reorder',
              source: { id: widgetId },
              destination: {},
              item: { id: widgetId, type: 'widget' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { widgets: state.currentLayout.widgets },
            description: createOperationDescription('widget-reorder', { id: widgetId, type: 'widget' }),
            canUndo: true,
            canRedo: false,
          };

          // Truncate future history if we're not at the end
          if (state.historyIndex < state.history.length - 1) {
            state.history = state.history.slice(0, state.historyIndex + 1);
          }

          state.history.push(historyItem);
          state.historyIndex++;

          // Compress history if needed
          if (state.history.length > state.maxHistorySize) {
            state.history = compressHistory(state.history, state.maxHistorySize);
            state.historyIndex = state.history.length - 1;
          }

          state.isDirty = true;

          // Add accessibility announcement
          if (state.preferences.announceMovements) {
            state.announcements.push({
              id: `announcement-${Date.now()}`,
              message: `Widget ${widgetId} moved to new position`,
              severity: 'info',
              timestamp: Date.now(),
              politeness: 'polite',
            });
          }
        }),

        resizeWidget: (widgetId, size) => set((state) => {
          if (!state.currentLayout) return;

          const widgetIndex = state.currentLayout.widgets.findIndex(w => w.id === widgetId);
          if (widgetIndex === -1) return;

          const previousState = { widgets: [...state.currentLayout.widgets] };

          state.currentLayout.widgets[widgetIndex] = {
            ...state.currentLayout.widgets[widgetIndex],
            ...size,
          };

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'widget-resize',
              source: { id: widgetId },
              destination: {},
              item: { id: widgetId, type: 'widget' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { widgets: state.currentLayout.widgets },
            description: createOperationDescription('widget-resize', { id: widgetId, type: 'widget' }),
            canUndo: true,
            canRedo: false,
          };

          if (state.historyIndex < state.history.length - 1) {
            state.history = state.history.slice(0, state.historyIndex + 1);
          }

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;
        }),

        removeWidget: (widgetId) => set((state) => {
          if (!state.currentLayout) return;

          const previousState = { widgets: [...state.currentLayout.widgets] };
          state.currentLayout.widgets = state.currentLayout.widgets.filter(w => w.id !== widgetId);

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'widget-reorder',
              source: { id: widgetId },
              destination: {},
              item: { id: widgetId, type: 'widget' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { widgets: state.currentLayout.widgets },
            description: `Removed widget "${widgetId}"`,
            canUndo: true,
            canRedo: false,
          };

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;
        }),

        addWidget: (widget) => set((state) => {
          if (!state.currentLayout) return;

          const previousState = { widgets: [...state.currentLayout.widgets] };
          state.currentLayout.widgets.push(widget);

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'widget-reorder',
              source: { id: widget.id },
              destination: {},
              item: { id: widget.id, type: 'widget' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { widgets: state.currentLayout.widgets },
            description: `Added widget "${widget.id}"`,
            canUndo: true,
            canRedo: false,
          };

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;
        }),

        // Rule actions
        moveRule: (ruleId, newOrder, _groupId) => set((state) => {
          if (!state.currentLayout) return;

          const previousState = { ruleOrder: [...state.currentLayout.ruleOrder] };

          // Remove rule from current position
          const currentIndex = state.currentLayout.ruleOrder.indexOf(ruleId);
          if (currentIndex !== -1) {
            state.currentLayout.ruleOrder.splice(currentIndex, 1);
          }

          // Insert at new position
          state.currentLayout.ruleOrder.splice(newOrder, 0, ruleId);

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'rule-reorder',
              source: { id: ruleId, index: currentIndex },
              destination: { index: newOrder },
              item: { id: ruleId, type: 'rule' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { ruleOrder: state.currentLayout.ruleOrder },
            description: createOperationDescription('rule-reorder', { id: ruleId, type: 'rule' }),
            canUndo: true,
            canRedo: false,
          };

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;

          if (state.preferences.announceMovements) {
            state.announcements.push({
              id: `announcement-${Date.now()}`,
              message: `Rule ${ruleId} moved to position ${newOrder + 1}`,
              severity: 'info',
              timestamp: Date.now(),
              politeness: 'polite',
            });
          }
        }),

        batchMoveRules: (moves) => set((state) => {
          if (!state.currentLayout) return;

          const previousState = { ruleOrder: [...state.currentLayout.ruleOrder] };

          // Apply all moves
          moves.forEach(({ ruleId, newOrder }) => {
            const currentIndex = state.currentLayout!.ruleOrder.indexOf(ruleId);
            if (currentIndex !== -1) {
              state.currentLayout!.ruleOrder.splice(currentIndex, 1);
              state.currentLayout!.ruleOrder.splice(newOrder, 0, ruleId);
            }
          });

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'batch-operation',
              source: { id: 'batch' },
              destination: {},
              item: { id: 'batch', type: 'rule', data: moves },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: { ruleOrder: state.currentLayout.ruleOrder },
            description: `Reordered ${moves.length} rules`,
            canUndo: true,
            canRedo: false,
          };

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;
        }),

        // History actions
        undo: () => {
          const state = get();
          if (state.historyIndex < 0 || state.history.length === 0) return false;

          set((draft) => {
            const historyItem = draft.history[draft.historyIndex];
            if (!historyItem || !draft.currentLayout) return;

            // Restore previous state
            Object.assign(draft.currentLayout, historyItem.previousState);
            draft.historyIndex--;
            draft.isDirty = true;

            if (draft.preferences.announceMovements) {
              draft.announcements.push({
                id: `announcement-${Date.now()}`,
                message: 'Undo: ' + historyItem.description,
                severity: 'info',
                timestamp: Date.now(),
                politeness: 'polite',
              });
            }
          });

          return true;
        },

        redo: () => {
          const state = get();
          if (state.historyIndex >= state.history.length - 1) return false;

          set((draft) => {
            draft.historyIndex++;
            const historyItem = draft.history[draft.historyIndex];
            if (!historyItem || !draft.currentLayout) return;

            // Restore current state
            Object.assign(draft.currentLayout, historyItem.currentState);
            draft.isDirty = true;

            if (draft.preferences.announceMovements) {
              draft.announcements.push({
                id: `announcement-${Date.now()}`,
                message: 'Redo: ' + historyItem.description,
                severity: 'info',
                timestamp: Date.now(),
                politeness: 'polite',
              });
            }
          });

          return true;
        },

        clearHistory: () => set((state) => {
          state.history = [];
          state.historyIndex = -1;
        }),

        // Layout management
        saveLayout: (layout) => set((state) => {
          state.currentLayout = layout;
          state.lastSaved = new Date().toISOString();
          state.isDirty = false;
          state.isSaving = false;
          state.saveError = null;
        }),

        loadLayout: (layout) => set((state) => {
          state.currentLayout = layout;
          state.history = [];
          state.historyIndex = -1;
          state.isDirty = false;
          state.lastSaved = new Date().toISOString();
        }),

        resetLayout: () => set((state) => {
          if (!state.currentLayout) return;

          const previousState = {
            widgets: [...state.currentLayout.widgets],
            ruleOrder: [...state.currentLayout.ruleOrder],
          };

          // Reset to default positions
          state.currentLayout.widgets = [];
          state.currentLayout.ruleOrder = [];

          const historyItem: LayoutHistoryItem = {
            id: `${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
            operation: {
              type: 'layout-reset',
              source: { id: 'layout' },
              destination: {},
              item: { id: 'layout', type: 'widget' },
              timestamp: Date.now(),
              userId: state.currentLayout.userId,
            },
            previousState,
            currentState: {
              widgets: state.currentLayout.widgets,
              ruleOrder: state.currentLayout.ruleOrder,
            },
            description: 'Reset layout to default',
            canUndo: true,
            canRedo: false,
          };

          state.history.push(historyItem);
          state.historyIndex++;
          state.isDirty = true;
        }),

        // Drag state
        setDragState: (newState) => set((state) => {
          Object.assign(state.dragState, newState);
        }),

        clearDragState: () => set((state) => {
          state.dragState = {
            isDragging: false,
            draggedItem: null,
            activeDropZone: null,
            dragOffset: { x: 0, y: 0 },
            initialPosition: { x: 0, y: 0 },
            currentPosition: { x: 0, y: 0 },
            preview: null,
          };
        }),

        // Preferences
        setPreferences: (prefs) => set((state) => {
          state.preferences = { ...state.preferences, ...prefs };
        }),

        // Announcements
        addAnnouncement: (announcement) => set((state) => {
          const newAnnouncement: AccessibilityAnnouncement = {
            ...announcement,
            id: `announcement-${Date.now()}-${Math.random()}`,
            timestamp: Date.now(),
          };

          state.announcements.push(newAnnouncement);

          // Auto-clear after duration
          if (announcement.duration) {
            setTimeout(() => {
              set((state) => {
                state.announcements = state.announcements.filter(
                  a => a.id !== newAnnouncement.id
                );
              });
            }, announcement.duration);
          }
        }),

        clearAnnouncements: () => set((state) => {
          state.announcements = [];
        }),

        // Persistence state
        markDirty: () => set((state) => {
          state.isDirty = true;
        }),

        markClean: () => set((state) => {
          state.isDirty = false;
          state.lastSaved = new Date().toISOString();
        }),

        setSaveError: (error) => set((state) => {
          state.saveError = error;
          state.isSaving = false;
        }),
      })),
      {
        name: 'layout-store',
        partialize: (state) => ({
          currentLayout: state.currentLayout,
          preferences: state.preferences,
        }),
      }
    )
  )
);