import { describe, it, expect } from 'vitest';

// Pure data files — no external dependencies
import { conversations, type Message, type Conversation } from '@/lib/data/chat-data';
import { frameworkOptions, controlMappingOptions } from '@/lib/data/mock-form-data';
import { editorData } from '@/lib/data/editor-data';
import { assessmentData } from '@/lib/data/questionnaire';

// ============================================================================
// chat-data: conversations
// ============================================================================

describe('conversations', () => {
  it('is a non-empty array', () => {
    expect(Array.isArray(conversations)).toBe(true);
    expect(conversations.length).toBeGreaterThan(0);
  });

  it('each conversation has id, title, messages', () => {
    conversations.forEach((conv: Conversation) => {
      expect(typeof conv.id).toBe('string');
      expect(conv.id.length).toBeGreaterThan(0);
      expect(typeof conv.title).toBe('string');
      expect(conv.title.length).toBeGreaterThan(0);
      expect(Array.isArray(conv.messages)).toBe(true);
    });
  });

  it('first conversation is about SOC 2', () => {
    expect(conversations[0]!.title).toContain('SOC 2');
  });

  it('has exactly 3 conversations', () => {
    expect(conversations.length).toBe(3);
  });

  it('conversation IDs are unique', () => {
    const ids = conversations.map((c: Conversation) => c.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });

  it('message senders are either "user" or "ai"', () => {
    conversations.forEach((conv: Conversation) => {
      conv.messages.forEach((msg: Message) => {
        expect(['user', 'ai']).toContain(msg.sender);
      });
    });
  });

  it('every message has id, text, sender, timestamp', () => {
    conversations.forEach((conv: Conversation) => {
      conv.messages.forEach((msg: Message) => {
        expect(typeof msg.id).toBe('string');
        expect(typeof msg.text).toBe('string');
        expect(typeof msg.sender).toBe('string');
        expect(typeof msg.timestamp).toBe('string');
      });
    });
  });

  it('first conversation first message is from user', () => {
    expect(conversations[0]!.messages[0]!.sender).toBe('user');
  });

  it('ai messages may have suggestions array', () => {
    const aiMessages = conversations.flatMap((c: Conversation) =>
      c.messages.filter((m: Message) => m.sender === 'ai'),
    );
    // At least one ai message exists
    expect(aiMessages.length).toBeGreaterThan(0);
    // If suggestions exist, they're arrays of strings
    aiMessages.forEach((msg: Message) => {
      if (msg.suggestions) {
        expect(Array.isArray(msg.suggestions)).toBe(true);
        msg.suggestions.forEach((s: string) => expect(typeof s).toBe('string'));
      }
    });
  });
});

// ============================================================================
// mock-form-data: frameworkOptions
// ============================================================================

describe('frameworkOptions', () => {
  it('is a non-empty array', () => {
    expect(Array.isArray(frameworkOptions)).toBe(true);
    expect(frameworkOptions.length).toBeGreaterThan(0);
  });

  it('has exactly 5 framework options', () => {
    expect(frameworkOptions.length).toBe(5);
  });

  it('each option has value and label', () => {
    frameworkOptions.forEach((opt) => {
      expect(typeof opt.value).toBe('string');
      expect(typeof opt.label).toBe('string');
      expect(opt.value.length).toBeGreaterThan(0);
      expect(opt.label.length).toBeGreaterThan(0);
    });
  });

  it('includes ISO 27001', () => {
    expect(frameworkOptions.some((o) => o.value === 'iso-27001')).toBe(true);
    expect(frameworkOptions.some((o) => o.label === 'ISO 27001')).toBe(true);
  });

  it('includes GDPR', () => {
    expect(frameworkOptions.some((o) => o.value === 'gdpr')).toBe(true);
  });

  it('includes SOC 2', () => {
    expect(frameworkOptions.some((o) => o.value === 'soc-2')).toBe(true);
  });

  it('includes HIPAA', () => {
    expect(frameworkOptions.some((o) => o.value === 'hipaa')).toBe(true);
  });

  it('includes PCI DSS', () => {
    expect(frameworkOptions.some((o) => o.value === 'pci-dss')).toBe(true);
  });

  it('all values are unique', () => {
    const values = frameworkOptions.map((o) => o.value);
    expect(new Set(values).size).toBe(values.length);
  });
});

// ============================================================================
// mock-form-data: controlMappingOptions
// ============================================================================

describe('controlMappingOptions', () => {
  it('has entries for all 5 frameworks', () => {
    expect(controlMappingOptions).toHaveProperty('iso-27001');
    expect(controlMappingOptions).toHaveProperty('soc-2');
    expect(controlMappingOptions).toHaveProperty('gdpr');
    expect(controlMappingOptions).toHaveProperty('hipaa');
    expect(controlMappingOptions).toHaveProperty('pci-dss');
  });

  it('each framework has 3 control options', () => {
    Object.values(controlMappingOptions).forEach((controls) => {
      expect(controls.length).toBe(3);
    });
  });

  it('each control has value and label', () => {
    Object.values(controlMappingOptions).forEach((controls) => {
      controls.forEach((ctrl) => {
        expect(typeof ctrl.value).toBe('string');
        expect(typeof ctrl.label).toBe('string');
      });
    });
  });

  it('ISO 27001 first control is A.5.1', () => {
    expect(controlMappingOptions['iso-27001']![0]!.value).toBe('a.5.1');
  });

  it('GDPR first control is Article 30', () => {
    expect(controlMappingOptions['gdpr']![0]!.value).toBe('art-30');
  });

  it('all control labels are non-empty strings', () => {
    Object.values(controlMappingOptions).forEach((controls) => {
      controls.forEach((ctrl) => {
        expect(ctrl.label.length).toBeGreaterThan(0);
      });
    });
  });
});

// ============================================================================
// editor-data: editorData
// ============================================================================

describe('editorData', () => {
  it('has metadata with author, createdAt, lastModified, status', () => {
    expect(editorData.metadata).toHaveProperty('author');
    expect(editorData.metadata).toHaveProperty('createdAt');
    expect(editorData.metadata).toHaveProperty('lastModified');
    expect(editorData.metadata).toHaveProperty('status');
  });

  it('author is "Jane Doe"', () => {
    expect(editorData.metadata.author).toBe('Jane Doe');
  });

  it('status is "In Review"', () => {
    expect(editorData.metadata.status).toBe('In Review');
  });

  it('has versions array with 5 entries', () => {
    expect(Array.isArray(editorData.versions)).toBe(true);
    expect(editorData.versions.length).toBe(5);
  });

  it('versions have id, author, timestamp, summary', () => {
    editorData.versions.forEach((v) => {
      expect(typeof v.id).toBe('number');
      expect(typeof v.author).toBe('string');
      expect(typeof v.timestamp).toBe('string');
      expect(typeof v.summary).toBe('string');
    });
  });

  it('versions are in descending order (latest first: id=5)', () => {
    expect(editorData.versions[0]!.id).toBe(5);
    expect(editorData.versions[editorData.versions.length - 1]!.id).toBe(1);
  });

  it('has comments array', () => {
    expect(Array.isArray(editorData.comments)).toBe(true);
    expect(editorData.comments.length).toBeGreaterThan(0);
  });

  it('each comment has id, author, timestamp, text, replies', () => {
    editorData.comments.forEach((c) => {
      expect(typeof c.id).toBe('string');
      expect(typeof c.author).toBe('string');
      expect(typeof c.timestamp).toBe('string');
      expect(typeof c.text).toBe('string');
      expect(Array.isArray(c.replies)).toBe(true);
    });
  });

  it('first comment has a reply', () => {
    expect(editorData.comments[0]!.replies.length).toBe(1);
  });

  it('second comment has no replies', () => {
    expect(editorData.comments[1]!.replies.length).toBe(0);
  });

  it('initialContent is a non-empty HTML string', () => {
    expect(typeof editorData.initialContent).toBe('string');
    expect(editorData.initialContent.length).toBeGreaterThan(0);
    expect(editorData.initialContent).toContain('<h1>');
  });
});

// ============================================================================
// questionnaire: assessmentData
// ============================================================================

describe('assessmentData', () => {
  it('has id, title, sections', () => {
    expect(assessmentData).toHaveProperty('id');
    expect(assessmentData).toHaveProperty('title');
    expect(assessmentData).toHaveProperty('sections');
  });

  it('id is "ASM-001"', () => {
    expect(assessmentData.id).toBe('ASM-001');
  });

  it('title is about GDPR', () => {
    expect(assessmentData.title).toContain('GDPR');
  });

  it('sections is a non-empty array', () => {
    expect(Array.isArray(assessmentData.sections)).toBe(true);
    expect(assessmentData.sections.length).toBeGreaterThan(0);
  });

  it('each section has id, title, progress, questions', () => {
    assessmentData.sections.forEach((section: any) => {
      expect(typeof section.id).toBe('string');
      expect(typeof section.title).toBe('string');
      expect(typeof section.progress).toBe('number');
      expect(Array.isArray(section.questions)).toBe(true);
    });
  });

  it('progress values are 0-100', () => {
    assessmentData.sections.forEach((section: any) => {
      expect(section.progress).toBeGreaterThanOrEqual(0);
      expect(section.progress).toBeLessThanOrEqual(100);
    });
  });

  it('section IDs are unique', () => {
    const ids = assessmentData.sections.map((s: any) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('each question has id, text, type', () => {
    assessmentData.sections.forEach((section: any) => {
      section.questions.forEach((q: any) => {
        expect(typeof q.id).toBe('string');
        expect(typeof q.text).toBe('string');
        expect(typeof q.type).toBe('string');
      });
    });
  });

  it('question types are valid', () => {
    const validTypes = ['radio', 'textarea', 'checkbox', 'text', 'select'];
    assessmentData.sections.forEach((section: any) => {
      section.questions.forEach((q: any) => {
        expect(validTypes).toContain(q.type);
      });
    });
  });

  it('radio and checkbox questions have options arrays', () => {
    assessmentData.sections.forEach((section: any) => {
      section.questions
        .filter((q: any) => q.type === 'radio' || q.type === 'checkbox')
        .forEach((q: any) => {
          expect(Array.isArray(q.options)).toBe(true);
          expect(q.options.length).toBeGreaterThan(0);
        });
    });
  });

  it('all question IDs are unique across sections', () => {
    const allIds = assessmentData.sections.flatMap((s: any) =>
      s.questions.map((q: any) => q.id),
    );
    expect(new Set(allIds).size).toBe(allIds.length);
  });
});
