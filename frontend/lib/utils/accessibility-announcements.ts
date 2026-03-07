import { Announcements } from '@dnd-kit/core';
import { AccessibilityAnnouncement } from '@/types/layout';

// Severity to politeness mapping
const severityToPoliteness = {
  info: 'polite',
  success: 'assertive',
  warning: 'assertive',
  error: 'assertive',
} as const;

// Timing configuration for announcements
const ANNOUNCEMENT_TIMING = {
  MIN_DELAY: 100, // Minimum delay between announcements
  MAX_FREQUENCY: 5000, // Maximum frequency for repeated announcements
  DEFAULT_DURATION: 3000, // Default display duration
  BATCH_DELAY: 500, // Delay for batched announcements
};

// Announcement templates for different operations
const announcementTemplates = {
  dragStart: {
    widget: 'Picked up widget {name}. Use arrow keys to move, space to drop.',
    rule: 'Picked up rule {name} at position {position}. Navigate to reorder.',
    group: 'Selected {count} items for batch operation.',
  },
  dragOver: {
    widget: 'Widget {name} is over {target}. {validity}',
    rule: 'Rule {name} is over position {position}.',
    group: 'Group is over {target} area.',
  },
  dragEnd: {
    widget: 'Dropped widget {name} at {position}. {result}',
    rule: 'Moved rule {name} from position {from} to position {to}.',
    group: 'Completed batch operation on {count} items.',
  },
  dragCancel: {
    widget: 'Cancelled moving widget {name}. Returned to original position.',
    rule: 'Cancelled reordering rule {name}.',
    group: 'Cancelled batch operation.',
  },
  collision: {
    valid: 'Valid drop zone.',
    invalid: 'Invalid drop zone. {reason}',
    occupied: 'Position occupied. Will swap with {target}.',
  },
  keyboard: {
    moveUp: 'Moving up',
    moveDown: 'Moving down',
    moveLeft: 'Moving left',
    moveRight: 'Moving right',
    select: 'Selected {name}',
    deselect: 'Deselected {name}',
    activate: 'Press space or enter to activate drag mode',
    deactivate: 'Press escape to cancel',
  },
  resize: {
    start: 'Resizing {name}. Use arrow keys to adjust size.',
    change: 'Size changed to {width} by {height}.',
    end: 'Resize complete. New size: {width} by {height}.',
  },
  batch: {
    start: 'Starting batch operation on {count} items.',
    progress: 'Processing item {current} of {total}.',
    complete: 'Batch operation complete. {successCount} succeeded, {failCount} failed.',
  },
};

// Format template with values
function formatTemplate(template: string, values: Record<string, any>): string {
  return template.replace(/{(\w+)}/g, (match, key) => {
    return values[key]?.toString() || match;
  });
}

// Generate move announcement
export function generateMoveAnnouncement(
  item: { id: string; name?: string; type: 'widget' | 'rule' | 'group' },
  fromPosition: { x?: number; y?: number; index?: number },
  toPosition: { x?: number; y?: number; index?: number }
): string {
  const name = item.name || item.id;

  if (item.type === 'widget') {
    const from = fromPosition.x !== undefined && fromPosition.y !== undefined
      ? `row ${fromPosition.y + 1}, column ${fromPosition.x + 1}`
      : 'original position';
    const to = toPosition.x !== undefined && toPosition.y !== undefined
      ? `row ${toPosition.y + 1}, column ${toPosition.x + 1}`
      : 'new position';

    return `Moved widget ${name} from ${from} to ${to}.`;
  }

  if (item.type === 'rule') {
    const from = fromPosition.index !== undefined
      ? `position ${fromPosition.index + 1}`
      : 'original position';
    const to = toPosition.index !== undefined
      ? `position ${toPosition.index + 1}`
      : 'new position';

    return `Moved rule ${name} from ${from} to ${to}.`;
  }

  return `Moved ${item.type} ${name} to new position.`;
}

// Generate drop announcement
export function generateDropAnnouncement(
  item: { id: string; name?: string; type: 'widget' | 'rule' | 'group' },
  dropZone: { id: string; name?: string; accepts?: string[] },
  success: boolean
): string {
  const itemName = item.name || item.id;
  const zoneName = dropZone.name || dropZone.id;

  if (!success) {
    const reason = dropZone.accepts && !dropZone.accepts.includes(item.type)
      ? `This zone only accepts ${dropZone.accepts.join(' or ')}.`
      : 'Invalid drop target.';

    return `Cannot drop ${item.type} ${itemName} on ${zoneName}. ${reason}`;
  }

  return `Successfully dropped ${item.type} ${itemName} on ${zoneName}.`;
}

// Generate rule reordering announcement
export function generateRuleReorderAnnouncement(
  rule: { id: string; name?: string; priority?: string },
  fromIndex: number,
  toIndex: number,
  totalRules: number
): string {
  const name = rule.name || rule.id;
  const priority = rule.priority ? ` (${rule.priority})` : '';

  if (fromIndex === toIndex) {
    return `Rule ${name}${priority} remains at position ${fromIndex + 1} of ${totalRules}.`;
  }

  const direction = toIndex > fromIndex ? 'down' : 'up';
  const positions = Math.abs(toIndex - fromIndex);

  return `Moved rule ${name}${priority} ${direction} ${positions} position${positions > 1 ? 's' : ''} from ${fromIndex + 1} to ${toIndex + 1} of ${totalRules}.`;
}

// Generate collision announcement
export function generateCollisionAnnouncement(
  draggedItem: { id: string; name?: string },
  collidingItem: { id: string; name?: string },
  action: 'swap' | 'push' | 'invalid'
): string {
  const draggedName = draggedItem.name || draggedItem.id;
  const collidingName = collidingItem.name || collidingItem.id;

  switch (action) {
    case 'swap':
      return `Will swap ${draggedName} with ${collidingName}.`;
    case 'push':
      return `Will push ${collidingName} to make room for ${draggedName}.`;
    case 'invalid':
      return `Cannot place ${draggedName} here. Position occupied by ${collidingName}.`;
    default:
      return `Collision detected between ${draggedName} and ${collidingName}.`;
  }
}

// Generate keyboard navigation announcement
export function generateKeyboardNavAnnouncement(
  action: string,
  target?: { id: string; name?: string; position?: number }
): string {
  const templates: Record<string, string> = {
    'focus-next': 'Focused on next item{target}',
    'focus-previous': 'Focused on previous item{target}',
    'select': 'Selected {target}',
    'deselect': 'Deselected {target}',
    'activate-drag': 'Drag mode activated for {target}. Use arrow keys to move.',
    'cancel-drag': 'Drag cancelled. {target} returned to original position.',
    'move-up': 'Moving {target} up',
    'move-down': 'Moving {target} down',
    'move-left': 'Moving {target} left',
    'move-right': 'Moving {target} right',
    'drop': 'Dropped {target} at current position',
  };

  const template = templates[action] || 'Action performed';
  const targetInfo = target
    ? ` ${target.name || target.id}${target.position !== undefined ? ` at position ${target.position}` : ''}`
    : '';

  return template.replace('{target}', targetInfo);
}

// Create announcement with timing control
export function createTimedAnnouncement(
  message: string,
  severity: AccessibilityAnnouncement['severity'] = 'info',
  duration?: number
): AccessibilityAnnouncement {
  return {
    id: `announcement-${Date.now()}-${Math.random()}`,
    message,
    severity,
    timestamp: Date.now(),
    duration: duration || ANNOUNCEMENT_TIMING.DEFAULT_DURATION,
    politeness: severityToPoliteness[severity] as 'polite' | 'assertive',
  };
}

// Batch announcements to prevent spam
export class AnnouncementQueue {
  private queue: AccessibilityAnnouncement[] = [];
  private processing = false;
  private lastAnnouncementTime = 0;
  private batchTimeout: NodeJS.Timeout | null = null;

  add(announcement: AccessibilityAnnouncement): void {
    this.queue.push(announcement);

    if (!this.processing) {
      this.processBatch();
    }
  }

  private processBatch(): void {
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
    }

    this.batchTimeout = setTimeout(() => {
      this.processQueue();
    }, ANNOUNCEMENT_TIMING.BATCH_DELAY);
  }

  private async processQueue(): Promise<void> {
    if (this.queue.length === 0) {
      this.processing = false;
      return;
    }

    this.processing = true;
    const now = Date.now();
    const timeSinceLastAnnouncement = now - this.lastAnnouncementTime;

    // Ensure minimum delay between announcements
    if (timeSinceLastAnnouncement < ANNOUNCEMENT_TIMING.MIN_DELAY) {
      await new Promise(resolve =>
        setTimeout(resolve, ANNOUNCEMENT_TIMING.MIN_DELAY - timeSinceLastAnnouncement)
      );
    }

    // Group similar announcements
    const grouped = this.groupSimilarAnnouncements();

    // Process grouped announcements
    for (const announcement of grouped) {
      this.announce(announcement);
      this.lastAnnouncementTime = Date.now();

      // Small delay between different announcements
      if (grouped.length > 1) {
        await new Promise(resolve => setTimeout(resolve, ANNOUNCEMENT_TIMING.MIN_DELAY));
      }
    }

    this.queue = [];
    this.processing = false;
  }

  private groupSimilarAnnouncements(): AccessibilityAnnouncement[] {
    const grouped = new Map<string, AccessibilityAnnouncement[]>();

    for (const announcement of this.queue) {
      const key = `${announcement.severity}-${announcement.message.slice(0, 20)}`;
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)!.push(announcement);
    }

    // Combine similar announcements
    const combined: AccessibilityAnnouncement[] = [];
    for (const [_key, group] of grouped.entries()) {
      if (group.length === 1) {
        combined.push(group[0]);
      } else {
        // Combine into a single announcement
        combined.push({
          ...group[0],
          message: `${group[0].message} (${group.length} similar actions)`,
        });
      }
    }

    return combined;
  }

  private announce(announcement: AccessibilityAnnouncement): void {
    // This would integrate with the actual announcement system
    // For now, we'll log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`[A11y ${announcement.severity}]: ${announcement.message}`);
    }

    // Dispatch to store or announcement system
    if (typeof window !== 'undefined' && window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('accessibility-announcement', {
        detail: announcement,
      }));
    }
  }

  clear(): void {
    this.queue = [];
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
  }
}

// Global announcement queue instance
export const announcementQueue = new AnnouncementQueue();

// Generate dnd-kit compatible announcements
export function generateAccessibilityAnnouncements(
  contextType: 'widgets' | 'rules' | 'mixed' = 'widgets'
): Announcements {
  return {
    onDragStart({ active }) {
      const type = contextType === 'rules' ? 'rule' : 'widget';
      const name = active.data.current?.name || active.id;
      return formatTemplate(announcementTemplates.dragStart[type], { name });
    },

    onDragOver({ active, over }) {
      if (!over) return '';

      const type = contextType === 'rules' ? 'rule' : 'widget';
      const name = active.data.current?.name || active.id;
      const target = over.data.current?.name || over.id;
      const validity = over.data.current?.accepts?.includes(type)
        ? 'Valid drop zone.'
        : 'Invalid drop zone.';

      return formatTemplate(announcementTemplates.dragOver[type], {
        name,
        target,
        validity,
        position: over.data.current?.position || '',
      });
    },

    onDragEnd({ active, over }) {
      if (!over) {
        const type = contextType === 'rules' ? 'rule' : 'widget';
        const name = active.data.current?.name || active.id;
        return formatTemplate(announcementTemplates.dragCancel[type], { name });
      }

      const type = contextType === 'rules' ? 'rule' : 'widget';
      const name = active.data.current?.name || active.id;
      const from = active.data.current?.position || 'original position';
      const to = over.data.current?.position || 'new position';
      const result = 'Operation successful.';

      return formatTemplate(announcementTemplates.dragEnd[type], {
        name,
        from,
        to,
        position: to,
        result,
      });
    },

    onDragCancel({ active }) {
      const type = contextType === 'rules' ? 'rule' : 'widget';
      const name = active.data.current?.name || active.id;
      return formatTemplate(announcementTemplates.dragCancel[type], { name });
    },
  };
}

// Internationalization support
export function createI18nAnnouncements(
  _locale: string,
  _translations: Record<string, any>
): typeof announcementTemplates {
  // This would load locale-specific templates
  // For now, return default English templates
  return announcementTemplates;
}

// Custom hook for announcement management
export function useAnnouncements() {
  const announce = (
    message: string,
    severity: AccessibilityAnnouncement['severity'] = 'info',
    duration?: number
  ) => {
    const announcement = createTimedAnnouncement(message, severity, duration);
    announcementQueue.add(announcement);
  };

  const announceMove = (
    item: { id: string; name?: string; type: 'widget' | 'rule' | 'group' },
    from: { x?: number; y?: number; index?: number },
    to: { x?: number; y?: number; index?: number }
  ) => {
    const message = generateMoveAnnouncement(item, from, to);
    announce(message, 'success');
  };

  const announceDrop = (
    item: { id: string; name?: string; type: 'widget' | 'rule' | 'group' },
    dropZone: { id: string; name?: string; accepts?: string[] },
    success: boolean
  ) => {
    const message = generateDropAnnouncement(item, dropZone, success);
    announce(message, success ? 'success' : 'error');
  };

  return {
    announce,
    announceMove,
    announceDrop,
    clearQueue: () => announcementQueue.clear(),
  };
}