import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  generateMoveAnnouncement,
  generateDropAnnouncement,
  generateRuleReorderAnnouncement,
  generateCollisionAnnouncement,
  generateKeyboardNavAnnouncement,
  createTimedAnnouncement,
  AnnouncementQueue,
} from '@/lib/utils/accessibility-announcements';

describe('generateMoveAnnouncement', () => {
  it('generates widget move with coordinates', () => {
    const result = generateMoveAnnouncement(
      { id: 'w1', name: 'Score Widget', type: 'widget' },
      { x: 0, y: 0 },
      { x: 2, y: 3 },
    );

    expect(result).toBe(
      'Moved widget Score Widget from row 1, column 1 to row 4, column 3.',
    );
  });

  it('uses id when name is not provided', () => {
    const result = generateMoveAnnouncement(
      { id: 'widget-abc', type: 'widget' },
      { x: 1, y: 0 },
      { x: 3, y: 2 },
    );

    expect(result).toContain('widget-abc');
  });

  it('falls back to "original position" and "new position" when coords missing', () => {
    const result = generateMoveAnnouncement(
      { id: 'w1', name: 'Test', type: 'widget' },
      {},
      {},
    );

    expect(result).toBe('Moved widget Test from original position to new position.');
  });

  it('generates rule move with index', () => {
    const result = generateMoveAnnouncement(
      { id: 'r1', name: 'Rule Alpha', type: 'rule' },
      { index: 0 },
      { index: 4 },
    );

    expect(result).toBe('Moved rule Rule Alpha from position 1 to position 5.');
  });

  it('handles rule move without index', () => {
    const result = generateMoveAnnouncement(
      { id: 'r1', name: 'Rule Beta', type: 'rule' },
      {},
      {},
    );

    expect(result).toBe('Moved rule Rule Beta from original position to new position.');
  });

  it('handles group type with generic message', () => {
    const result = generateMoveAnnouncement(
      { id: 'g1', name: 'My Group', type: 'group' },
      { x: 0, y: 0 },
      { x: 1, y: 1 },
    );

    expect(result).toBe('Moved group My Group to new position.');
  });
});

describe('generateDropAnnouncement', () => {
  it('generates success announcement', () => {
    const result = generateDropAnnouncement(
      { id: 'w1', name: 'Score Widget', type: 'widget' },
      { id: 'zone-1', name: 'Dashboard Area' },
      true,
    );

    expect(result).toBe(
      'Successfully dropped widget Score Widget on Dashboard Area.',
    );
  });

  it('generates failure announcement with accepts reason', () => {
    const result = generateDropAnnouncement(
      { id: 'w1', name: 'My Widget', type: 'widget' },
      { id: 'zone-2', name: 'Rules Zone', accepts: ['rule'] },
      false,
    );

    expect(result).toContain('Cannot drop widget My Widget on Rules Zone');
    expect(result).toContain('This zone only accepts rule.');
  });

  it('generates failure without accepts info', () => {
    const result = generateDropAnnouncement(
      { id: 'w1', name: 'Widget', type: 'widget' },
      { id: 'zone-3', name: 'Invalid Zone' },
      false,
    );

    expect(result).toContain('Invalid drop target.');
  });

  it('uses id when name is missing', () => {
    const result = generateDropAnnouncement(
      { id: 'item-123', type: 'rule' },
      { id: 'drop-zone-456' },
      true,
    );

    expect(result).toContain('item-123');
    expect(result).toContain('drop-zone-456');
  });
});

describe('generateRuleReorderAnnouncement', () => {
  it('generates reorder announcement moving down', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r1', name: 'GDPR Rule' },
      0,
      3,
      10,
    );

    expect(result).toBe(
      'Moved rule GDPR Rule down 3 positions from 1 to 4 of 10.',
    );
  });

  it('generates reorder announcement moving up', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r2', name: 'ISO Rule' },
      5,
      2,
      10,
    );

    expect(result).toBe(
      'Moved rule ISO Rule up 3 positions from 6 to 3 of 10.',
    );
  });

  it('handles single position move', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r3', name: 'Rule C' },
      3,
      4,
      10,
    );

    expect(result).toContain('1 position');
    expect(result).not.toContain('positions');
  });

  it('handles no movement (same index)', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r4', name: 'Rule D' },
      2,
      2,
      5,
    );

    expect(result).toBe('Rule Rule D remains at position 3 of 5.');
  });

  it('includes priority when provided', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r5', name: 'Rule E', priority: 'P0' },
      0,
      2,
      5,
    );

    expect(result).toContain('(P0)');
  });

  it('omits priority when not provided', () => {
    const result = generateRuleReorderAnnouncement(
      { id: 'r6', name: 'Rule F' },
      0,
      1,
      5,
    );

    expect(result).not.toContain('(');
  });
});

describe('generateCollisionAnnouncement', () => {
  it('generates swap announcement', () => {
    const result = generateCollisionAnnouncement(
      { id: 'w1', name: 'Widget A' },
      { id: 'w2', name: 'Widget B' },
      'swap',
    );

    expect(result).toBe('Will swap Widget A with Widget B.');
  });

  it('generates push announcement', () => {
    const result = generateCollisionAnnouncement(
      { id: 'w1', name: 'Widget A' },
      { id: 'w2', name: 'Widget B' },
      'push',
    );

    expect(result).toBe('Will push Widget B to make room for Widget A.');
  });

  it('generates invalid announcement', () => {
    const result = generateCollisionAnnouncement(
      { id: 'w1', name: 'Widget A' },
      { id: 'w2', name: 'Widget B' },
      'invalid',
    );

    expect(result).toBe('Cannot place Widget A here. Position occupied by Widget B.');
  });

  it('uses id when name is not provided', () => {
    const result = generateCollisionAnnouncement(
      { id: 'widget-1' },
      { id: 'widget-2' },
      'swap',
    );

    expect(result).toContain('widget-1');
    expect(result).toContain('widget-2');
  });
});

describe('generateKeyboardNavAnnouncement', () => {
  it('generates select announcement with target', () => {
    const result = generateKeyboardNavAnnouncement('select', {
      id: 'w1',
      name: 'Score Widget',
    });

    expect(result).toContain('Selected');
    expect(result).toContain('Score Widget');
  });

  it('generates move-up announcement', () => {
    const result = generateKeyboardNavAnnouncement('move-up', {
      id: 'w1',
      name: 'Widget',
    });

    expect(result).toContain('Moving');
    expect(result).toContain('up');
  });

  it('generates activate-drag announcement', () => {
    const result = generateKeyboardNavAnnouncement('activate-drag', {
      id: 'w1',
      name: 'Item',
    });

    expect(result).toContain('Drag mode activated');
  });

  it('includes position in target info when provided', () => {
    const result = generateKeyboardNavAnnouncement('select', {
      id: 'w1',
      name: 'Widget',
      position: 3,
    });

    expect(result).toContain('at position 3');
  });

  it('handles unknown action gracefully', () => {
    const result = generateKeyboardNavAnnouncement('unknown-action');
    expect(result).toBe('Action performed');
  });

  it('handles no target', () => {
    const result = generateKeyboardNavAnnouncement('drop');
    expect(result).toContain('Dropped');
  });
});

describe('createTimedAnnouncement', () => {
  it('creates announcement with default severity and duration', () => {
    const announcement = createTimedAnnouncement('Test message');

    expect(announcement.message).toBe('Test message');
    expect(announcement.severity).toBe('info');
    expect(announcement.duration).toBe(3000);
    expect(announcement.politeness).toBe('polite');
    expect(announcement.id).toContain('announcement-');
    expect(announcement.timestamp).toBeDefined();
  });

  it('creates announcement with custom severity', () => {
    const announcement = createTimedAnnouncement('Error occurred', 'error');

    expect(announcement.severity).toBe('error');
    expect(announcement.politeness).toBe('assertive');
  });

  it('creates success announcement with assertive politeness', () => {
    const announcement = createTimedAnnouncement('Done', 'success');

    expect(announcement.severity).toBe('success');
    expect(announcement.politeness).toBe('assertive');
  });

  it('creates warning announcement with assertive politeness', () => {
    const announcement = createTimedAnnouncement('Watch out', 'warning');

    expect(announcement.severity).toBe('warning');
    expect(announcement.politeness).toBe('assertive');
  });

  it('uses custom duration when provided', () => {
    const announcement = createTimedAnnouncement('Quick', 'info', 1000);
    expect(announcement.duration).toBe(1000);
  });
});

describe('AnnouncementQueue', () => {
  let queue: AnnouncementQueue;

  beforeEach(() => {
    vi.useFakeTimers();
    queue = new AnnouncementQueue();
  });

  afterEach(() => {
    queue.clear();
    vi.useRealTimers();
  });

  it('can be instantiated', () => {
    expect(queue).toBeInstanceOf(AnnouncementQueue);
  });

  it('accepts announcements via add()', () => {
    const announcement = createTimedAnnouncement('Test');
    expect(() => queue.add(announcement)).not.toThrow();
  });

  it('clears the queue', () => {
    queue.add(createTimedAnnouncement('Item 1'));
    queue.add(createTimedAnnouncement('Item 2'));
    expect(() => queue.clear()).not.toThrow();
  });
});
