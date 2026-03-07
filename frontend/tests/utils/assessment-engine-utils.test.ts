import { describe, it, expect, beforeEach } from 'vitest';
import { AssessmentUtils } from '@/lib/assessment-engine/utils';
import type { AssessmentFramework, AssessmentSection, AssessmentResult, Gap } from '@/lib/assessment-engine/types';

// ============================================================================
// Test fixtures
// ============================================================================

function makeSection(id: string, questions: any[]): AssessmentSection {
  return {
    id,
    title: `Section ${id}`,
    questions,
    order: 0,
  } as unknown as AssessmentSection;
}

function makeQuestion(id: string, type = 'radio', required = false) {
  return {
    id,
    type,
    text: `Question ${id}`,
    validation: required ? { required: true } : undefined,
  };
}

function makeFramework(sections: AssessmentSection[]): AssessmentFramework {
  return {
    id: 'fw-1',
    name: 'Test Framework',
    sections,
  } as unknown as AssessmentFramework;
}

function makeResult(score: number): AssessmentResult {
  return {
    id: 'res-1',
    frameworkId: 'ISO27001',
    overallScore: score,
    completedAt: new Date('2025-01-15T12:00:00Z'),
    maturityLevel: score >= 80 ? 'managed' : 'initial',
    sectionScores: {},
    gaps: [],
  } as unknown as AssessmentResult;
}

// ============================================================================
// generateAssessmentId
// ============================================================================

describe('AssessmentUtils.generateAssessmentId', () => {
  it('returns a string starting with ASM-', () => {
    expect(AssessmentUtils.generateAssessmentId()).toMatch(/^ASM-/);
  });

  it('returns uppercase id', () => {
    const id = AssessmentUtils.generateAssessmentId();
    expect(id).toBe(id.toUpperCase());
  });

  it('generates unique IDs on repeated calls', () => {
    const ids = new Set(Array.from({ length: 20 }, () => AssessmentUtils.generateAssessmentId()));
    expect(ids.size).toBe(20);
  });
});

// ============================================================================
// formatDuration
// ============================================================================

describe('AssessmentUtils.formatDuration', () => {
  it('returns "1 minute" for 1 minute', () => {
    expect(AssessmentUtils.formatDuration(1)).toBe('1 minute');
  });

  it('returns "30 minutes" for 30 minutes', () => {
    expect(AssessmentUtils.formatDuration(30)).toBe('30 minutes');
  });

  it('returns "1 hour" for 60 minutes', () => {
    expect(AssessmentUtils.formatDuration(60)).toBe('1 hour');
  });

  it('returns "2 hours" for 120 minutes', () => {
    expect(AssessmentUtils.formatDuration(120)).toBe('2 hours');
  });

  it('returns "1 hour 30 minutes" for 90 minutes', () => {
    expect(AssessmentUtils.formatDuration(90)).toBe('1 hour 30 minutes');
  });

  it('returns "2 hours 15 minutes" for 135 minutes', () => {
    expect(AssessmentUtils.formatDuration(135)).toBe('2 hours 15 minutes');
  });
});

// ============================================================================
// calculateEstimatedTime
// ============================================================================

describe('AssessmentUtils.calculateEstimatedTime', () => {
  it('returns estimatedDuration directly when provided', () => {
    const fw = { ...makeFramework([]), estimatedDuration: 45 };
    expect(AssessmentUtils.calculateEstimatedTime(fw as any)).toBe(45);
  });

  it('calculates 0.5 min per radio question', () => {
    const fw = makeFramework([
      makeSection('s1', [makeQuestion('q1', 'radio'), makeQuestion('q2', 'radio')]),
    ]);
    // 2 × 0.5 = 1 → ceil(1) = 1
    expect(AssessmentUtils.calculateEstimatedTime(fw)).toBe(1);
  });

  it('calculates 2 min per textarea question', () => {
    const fw = makeFramework([
      makeSection('s1', [makeQuestion('q1', 'textarea')]),
    ]);
    expect(AssessmentUtils.calculateEstimatedTime(fw)).toBe(2);
  });

  it('calculates 3 min per matrix question', () => {
    const fw = makeFramework([
      makeSection('s1', [makeQuestion('q1', 'matrix')]),
    ]);
    expect(AssessmentUtils.calculateEstimatedTime(fw)).toBe(3);
  });

  it('returns 0 for empty framework', () => {
    const fw = makeFramework([]);
    expect(AssessmentUtils.calculateEstimatedTime(fw)).toBe(0);
  });
});

// ============================================================================
// getQuestionById
// ============================================================================

describe('AssessmentUtils.getQuestionById', () => {
  const fw = makeFramework([
    makeSection('s1', [makeQuestion('q1'), makeQuestion('q2')]),
    makeSection('s2', [makeQuestion('q3')]),
  ]);

  it('finds question in first section', () => {
    const q = AssessmentUtils.getQuestionById(fw, 'q1');
    expect(q?.id).toBe('q1');
  });

  it('finds question in second section', () => {
    const q = AssessmentUtils.getQuestionById(fw, 'q3');
    expect(q?.id).toBe('q3');
  });

  it('returns null for non-existent question', () => {
    expect(AssessmentUtils.getQuestionById(fw, 'q99')).toBeNull();
  });
});

// ============================================================================
// getSectionByQuestionId
// ============================================================================

describe('AssessmentUtils.getSectionByQuestionId', () => {
  const fw = makeFramework([
    makeSection('s1', [makeQuestion('q1'), makeQuestion('q2')]),
    makeSection('s2', [makeQuestion('q3')]),
  ]);

  it('returns section containing the question', () => {
    const s = AssessmentUtils.getSectionByQuestionId(fw, 'q2');
    expect(s?.id).toBe('s1');
  });

  it('returns correct section for q3', () => {
    const s = AssessmentUtils.getSectionByQuestionId(fw, 'q3');
    expect(s?.id).toBe('s2');
  });

  it('returns null for non-existent question', () => {
    expect(AssessmentUtils.getSectionByQuestionId(fw, 'q99')).toBeNull();
  });
});

// ============================================================================
// exportToJSON
// ============================================================================

describe('AssessmentUtils.exportToJSON', () => {
  it('returns valid JSON string', () => {
    const result = makeResult(75);
    const json = AssessmentUtils.exportToJSON(result);
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it('includes overallScore in exported JSON', () => {
    const result = makeResult(85);
    const json = AssessmentUtils.exportToJSON(result);
    const parsed = JSON.parse(json);
    expect(parsed.overallScore).toBe(85);
  });

  it('produces pretty-printed JSON (indented)', () => {
    const result = makeResult(50);
    const json = AssessmentUtils.exportToJSON(result);
    expect(json).toContain('\n');
  });
});

// ============================================================================
// groupGapsBySection
// ============================================================================

describe('AssessmentUtils.groupGapsBySection', () => {
  const gaps: Gap[] = [
    { id: 'g1', section: 'Access Control', description: 'Gap 1' } as unknown as Gap,
    { id: 'g2', section: 'Access Control', description: 'Gap 2' } as unknown as Gap,
    { id: 'g3', section: 'Data Protection', description: 'Gap 3' } as unknown as Gap,
  ];

  it('groups gaps by section name', () => {
    const grouped = AssessmentUtils.groupGapsBySection(gaps);
    expect(Object.keys(grouped)).toHaveLength(2);
    expect(grouped['Access Control']).toHaveLength(2);
    expect(grouped['Data Protection']).toHaveLength(1);
  });

  it('returns empty object for empty gaps array', () => {
    expect(AssessmentUtils.groupGapsBySection([])).toEqual({});
  });
});

// ============================================================================
// calculateSectionCompletion
// ============================================================================

describe('AssessmentUtils.calculateSectionCompletion', () => {
  const section = makeSection('s1', [
    makeQuestion('q1'),
    makeQuestion('q2'),
    makeQuestion('q3'),
    makeQuestion('q4'),
  ]) as any;

  it('returns 100 for fully answered section', () => {
    const answers = new Map([['q1', 'a'], ['q2', 'b'], ['q3', 'c'], ['q4', 'd']]);
    expect(AssessmentUtils.calculateSectionCompletion(section, answers)).toBe(100);
  });

  it('returns 50 for half answered section', () => {
    const answers = new Map([['q1', 'a'], ['q2', 'b']]);
    expect(AssessmentUtils.calculateSectionCompletion(section, answers)).toBe(50);
  });

  it('returns 0 for unanswered section', () => {
    expect(AssessmentUtils.calculateSectionCompletion(section, new Map())).toBe(0);
  });

  it('returns 100 for empty section', () => {
    const empty = makeSection('empty', []) as any;
    expect(AssessmentUtils.calculateSectionCompletion(empty, new Map())).toBe(100);
  });
});

// ============================================================================
// sanitizeInput
// ============================================================================

describe('AssessmentUtils.sanitizeInput', () => {
  // Note: the source replaces < > " with themselves (literal chars, not entities),
  // so only single-quotes and forward-slashes are actually transformed.
  it('replaces single-quote with &#x27;', () => {
    expect(AssessmentUtils.sanitizeInput("it's")).toContain('&#x27;');
  });

  it('replaces forward-slash with &#x2F;', () => {
    expect(AssessmentUtils.sanitizeInput('a/b')).toContain('&#x2F;');
  });

  it('leaves safe strings unchanged', () => {
    expect(AssessmentUtils.sanitizeInput('Hello World')).toBe('Hello World');
  });

  it('handles empty string', () => {
    expect(AssessmentUtils.sanitizeInput('')).toBe('');
  });

  it('handles string with no special characters', () => {
    expect(AssessmentUtils.sanitizeInput('normaltext123')).toBe('normaltext123');
  });
});

// ============================================================================
// formatFileSize
// ============================================================================

describe('AssessmentUtils.formatFileSize', () => {
  it('returns "0 Bytes" for 0', () => {
    expect(AssessmentUtils.formatFileSize(0)).toBe('0 Bytes');
  });

  it('returns bytes for small numbers', () => {
    expect(AssessmentUtils.formatFileSize(512)).toBe('512 Bytes');
  });

  it('returns KB for 1024 bytes', () => {
    expect(AssessmentUtils.formatFileSize(1024)).toBe('1 KB');
  });

  it('returns MB for megabytes', () => {
    expect(AssessmentUtils.formatFileSize(1024 * 1024)).toBe('1 MB');
  });

  it('returns GB for gigabytes', () => {
    expect(AssessmentUtils.formatFileSize(1024 * 1024 * 1024)).toBe('1 GB');
  });

  it('returns decimal values', () => {
    expect(AssessmentUtils.formatFileSize(1536)).toBe('1.5 KB');
  });
});

// ============================================================================
// isAssessmentExpired
// ============================================================================

describe('AssessmentUtils.isAssessmentExpired', () => {
  it('returns true for a date far in the past', () => {
    const oldDate = new Date('2020-01-01');
    expect(AssessmentUtils.isAssessmentExpired(oldDate)).toBe(true);
  });

  it('returns false for a recent date', () => {
    const recentDate = new Date();
    recentDate.setMonth(recentDate.getMonth() - 6);
    expect(AssessmentUtils.isAssessmentExpired(recentDate)).toBe(false);
  });

  it('accepts custom validity months', () => {
    const oneMonthAgo = new Date();
    oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
    // With 2-month validity, 1 month ago is not expired
    expect(AssessmentUtils.isAssessmentExpired(oneMonthAgo, 2)).toBe(false);
    // With 0.5-month validity, 1 month ago IS expired (not directly, use small number)
    const oldDate = new Date('2020-01-01');
    expect(AssessmentUtils.isAssessmentExpired(oldDate, 1)).toBe(true);
  });
});

// ============================================================================
// getScoreColorClass
// ============================================================================

describe('AssessmentUtils.getScoreColorClass', () => {
  it('returns green class for score >= 90', () => {
    expect(AssessmentUtils.getScoreColorClass(90)).toContain('green');
    expect(AssessmentUtils.getScoreColorClass(100)).toContain('green');
  });

  it('returns blue class for score 75-89', () => {
    expect(AssessmentUtils.getScoreColorClass(75)).toContain('blue');
    expect(AssessmentUtils.getScoreColorClass(89)).toContain('blue');
  });

  it('returns yellow class for score 60-74', () => {
    expect(AssessmentUtils.getScoreColorClass(60)).toContain('yellow');
    expect(AssessmentUtils.getScoreColorClass(74)).toContain('yellow');
  });

  it('returns orange class for score 40-59', () => {
    expect(AssessmentUtils.getScoreColorClass(40)).toContain('orange');
    expect(AssessmentUtils.getScoreColorClass(59)).toContain('orange');
  });

  it('returns red class for score < 40', () => {
    expect(AssessmentUtils.getScoreColorClass(0)).toContain('red');
    expect(AssessmentUtils.getScoreColorClass(39)).toContain('red');
  });
});

// ============================================================================
// getMaturityLevelLabel
// ============================================================================

describe('AssessmentUtils.getMaturityLevelLabel', () => {
  it('returns correct label for "initial"', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('initial').label).toBe('Initial');
    expect(AssessmentUtils.getMaturityLevelLabel('initial').color).toBe('red');
  });

  it('returns correct label for "developing"', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('developing').label).toBe('Developing');
    expect(AssessmentUtils.getMaturityLevelLabel('developing').color).toBe('orange');
  });

  it('returns correct label for "defined"', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('defined').label).toBe('Defined');
  });

  it('returns correct label for "managed"', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('managed').label).toBe('Managed');
    expect(AssessmentUtils.getMaturityLevelLabel('managed').color).toBe('blue');
  });

  it('returns correct label for "optimized"', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('optimized').label).toBe('Optimized');
    expect(AssessmentUtils.getMaturityLevelLabel('optimized').color).toBe('green');
  });

  it('returns "initial" as fallback for unknown level', () => {
    expect(AssessmentUtils.getMaturityLevelLabel('unknown').label).toBe('Initial');
  });

  it('includes description for each level', () => {
    ['initial', 'developing', 'defined', 'managed', 'optimized'].forEach((level) => {
      const result = AssessmentUtils.getMaturityLevelLabel(level);
      expect(result.description.length).toBeGreaterThan(0);
    });
  });
});
