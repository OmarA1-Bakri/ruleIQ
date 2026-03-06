import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardNavigation, type NavigationItem } from '@/lib/hooks/use-keyboard-navigation';

function fireKey(key: string, extras: Partial<KeyboardEvent> = {}): void {
  const event = new KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
    ...extras,
  });
  document.dispatchEvent(event);
}

const items: NavigationItem[] = [
  { id: 'item-1', label: 'Alpha' },
  { id: 'item-2', label: 'Beta' },
  { id: 'item-3', label: 'Charlie' },
  { id: 'item-4', label: 'Delta' },
];

describe('useKeyboardNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with focusedIndex 0', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({ items }),
    );
    expect(result.current.focusedIndex).toBe(0);
    expect(result.current.searchBuffer).toBe('');
  });

  describe('vertical navigation', () => {
    it('moves down with ArrowDown', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, orientation: 'vertical' }),
      );

      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(1);

      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(2);
    });

    it('moves up with ArrowUp', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, orientation: 'vertical' }),
      );

      // Start at 0, ArrowUp with loop should go to last
      act(() => { fireKey('ArrowUp'); });
      expect(result.current.focusedIndex).toBe(3);
    });

    it('loops from last to first with ArrowDown', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, orientation: 'vertical', loop: true }),
      );

      // Navigate to end
      act(() => { fireKey('ArrowDown'); });
      act(() => { fireKey('ArrowDown'); });
      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(3);

      // Should loop back to 0
      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(0);
    });
  });

  describe('no-loop mode', () => {
    it('clamps at boundaries when loop is false', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, loop: false }),
      );

      // At 0, ArrowUp should stay at 0
      act(() => { fireKey('ArrowUp'); });
      expect(result.current.focusedIndex).toBe(0);

      // Navigate to end
      act(() => { fireKey('ArrowDown'); });
      act(() => { fireKey('ArrowDown'); });
      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(3);

      // Should stay at 3
      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(3);
    });
  });

  describe('horizontal navigation', () => {
    it('uses ArrowLeft/ArrowRight for horizontal orientation', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, orientation: 'horizontal' }),
      );

      act(() => { fireKey('ArrowRight'); });
      expect(result.current.focusedIndex).toBe(1);

      act(() => { fireKey('ArrowLeft'); });
      expect(result.current.focusedIndex).toBe(0);
    });
  });

  describe('disabled items', () => {
    it('skips disabled items', () => {
      const itemsWithDisabled: NavigationItem[] = [
        { id: '1', label: 'A' },
        { id: '2', label: 'B', disabled: true },
        { id: '3', label: 'C' },
      ];

      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: itemsWithDisabled, skipDisabled: true }),
      );

      act(() => { fireKey('ArrowDown'); });
      // Should skip item 2 (disabled) and go to item 3 (index 2)
      expect(result.current.focusedIndex).toBe(2);
    });
  });

  describe('Home and End keys', () => {
    it('Home key navigates to first item', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      // Move to index 2 first
      act(() => { fireKey('ArrowDown'); });
      act(() => { fireKey('ArrowDown'); });
      expect(result.current.focusedIndex).toBe(2);

      act(() => { fireKey('Home'); });
      expect(result.current.focusedIndex).toBe(0);
    });

    it('End key navigates to last item', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { fireKey('End'); });
      expect(result.current.focusedIndex).toBe(3);
    });

    it('Home/End keys are disabled when homeEndKeys is false', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items, homeEndKeys: false }),
      );

      act(() => { fireKey('End'); });
      expect(result.current.focusedIndex).toBe(0); // unchanged

      act(() => { fireKey('Home'); });
      expect(result.current.focusedIndex).toBe(0); // unchanged
    });

    it('Home skips disabled items at the start', () => {
      const disabledFirst: NavigationItem[] = [
        { id: '1', label: 'A', disabled: true },
        { id: '2', label: 'B' },
        { id: '3', label: 'C' },
      ];

      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: disabledFirst, skipDisabled: true }),
      );

      // Navigate away first
      act(() => { fireKey('ArrowDown'); });

      act(() => { fireKey('Home'); });
      expect(result.current.focusedIndex).toBe(1); // skips disabled at index 0
    });

    it('End skips disabled items at the end', () => {
      const disabledLast: NavigationItem[] = [
        { id: '1', label: 'A' },
        { id: '2', label: 'B' },
        { id: '3', label: 'C', disabled: true },
      ];

      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: disabledLast, skipDisabled: true }),
      );

      act(() => { fireKey('End'); });
      expect(result.current.focusedIndex).toBe(1); // skips disabled at end
    });
  });

  describe('Enter and Space selection', () => {
    it('calls onSelect with Enter key', () => {
      const onSelect = vi.fn();
      renderHook(() =>
        useKeyboardNavigation({ items, onSelect }),
      );

      act(() => { fireKey('Enter'); });
      expect(onSelect).toHaveBeenCalledWith(items[0], 0);
    });

    it('calls onSelect with Space key', () => {
      const onSelect = vi.fn();
      renderHook(() =>
        useKeyboardNavigation({ items, onSelect }),
      );

      act(() => { fireKey(' '); });
      expect(onSelect).toHaveBeenCalledWith(items[0], 0);
    });

    it('does not call onSelect for disabled items', () => {
      const onSelect = vi.fn();
      const disabledItems: NavigationItem[] = [
        { id: '1', label: 'A', disabled: true },
      ];

      renderHook(() =>
        useKeyboardNavigation({ items: disabledItems, onSelect }),
      );

      act(() => { fireKey('Enter'); });
      expect(onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Escape key', () => {
    it('calls onEscape callback', () => {
      const onEscape = vi.fn();
      renderHook(() =>
        useKeyboardNavigation({ items, onEscape }),
      );

      act(() => { fireKey('Escape'); });
      expect(onEscape).toHaveBeenCalled();
    });
  });

  describe('expand/collapse for nested items', () => {
    const nestedItems: NavigationItem[] = [
      { id: '1', label: 'Parent', children: [{ id: '1a', label: 'Child A' }] },
      { id: '2', label: 'Sibling' },
    ];

    it('expands item with ArrowRight when isNested', () => {
      const onExpand = vi.fn();
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: nestedItems, isNested: true, onExpand }),
      );

      act(() => { fireKey('ArrowRight'); });
      expect(result.current.isItemExpanded('1')).toBe(true);
      expect(onExpand).toHaveBeenCalledWith(nestedItems[0], true);
    });

    it('collapses expanded item with ArrowLeft when isNested', () => {
      const onExpand = vi.fn();
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: nestedItems, isNested: true, onExpand }),
      );

      // Expand first
      act(() => { fireKey('ArrowRight'); });
      expect(result.current.isItemExpanded('1')).toBe(true);

      // Collapse
      act(() => { fireKey('ArrowLeft'); });
      expect(result.current.isItemExpanded('1')).toBe(false);
      expect(onExpand).toHaveBeenLastCalledWith(nestedItems[0], false);
    });
  });

  describe('utility methods', () => {
    it('navigateToIndex sets focused index', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.navigateToIndex(2); });
      expect(result.current.focusedIndex).toBe(2);
    });

    it('navigateToIndex ignores out-of-range indices', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.navigateToIndex(100); });
      expect(result.current.focusedIndex).toBe(0); // unchanged

      act(() => { result.current.navigateToIndex(-1); });
      expect(result.current.focusedIndex).toBe(0); // unchanged
    });

    it('navigateToItem finds item by ID', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.navigateToItem('item-3'); });
      expect(result.current.focusedIndex).toBe(2);
    });

    it('navigateToItem does nothing for unknown ID', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.navigateToItem('nonexistent'); });
      expect(result.current.focusedIndex).toBe(0);
    });

    it('navigateNext and navigatePrev move focus', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.navigateNext(); });
      expect(result.current.focusedIndex).toBe(1);

      act(() => { result.current.navigatePrev(); });
      expect(result.current.focusedIndex).toBe(0);
    });

    it('expandItem and collapseItem manage expanded state', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.expandItem('item-1'); });
      expect(result.current.isItemExpanded('item-1')).toBe(true);

      act(() => { result.current.collapseItem('item-1'); });
      expect(result.current.isItemExpanded('item-1')).toBe(false);
    });

    it('toggleItem toggles expanded state', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => { result.current.toggleItem('item-1'); });
      expect(result.current.isItemExpanded('item-1')).toBe(true);

      act(() => { result.current.toggleItem('item-1'); });
      expect(result.current.isItemExpanded('item-1')).toBe(false);
    });

    it('expandAll expands all items with children', () => {
      const nestedItems: NavigationItem[] = [
        { id: '1', label: 'A', children: [{ id: '1a', label: 'A1' }] },
        { id: '2', label: 'B' },
        { id: '3', label: 'C', children: [{ id: '3a', label: 'C1' }] },
      ];

      const { result } = renderHook(() =>
        useKeyboardNavigation({ items: nestedItems }),
      );

      act(() => { result.current.expandAll(); });
      expect(result.current.isItemExpanded('1')).toBe(true);
      expect(result.current.isItemExpanded('2')).toBe(false); // no children
      expect(result.current.isItemExpanded('3')).toBe(true);
    });

    it('collapseAll collapses everything', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      act(() => {
        result.current.expandItem('item-1');
        result.current.expandItem('item-2');
      });

      act(() => { result.current.collapseAll(); });
      expect(result.current.isItemExpanded('item-1')).toBe(false);
      expect(result.current.isItemExpanded('item-2')).toBe(false);
    });

    it('isItemFocused returns correct boolean', () => {
      const { result } = renderHook(() =>
        useKeyboardNavigation({ items }),
      );

      expect(result.current.isItemFocused(0)).toBe(true);
      expect(result.current.isItemFocused(1)).toBe(false);

      act(() => { result.current.navigateToIndex(2); });
      expect(result.current.isItemFocused(2)).toBe(true);
      expect(result.current.isItemFocused(0)).toBe(false);
    });
  });
});
