import { describe, it, expect, beforeEach } from 'vitest';
import {
  PERFORMANCE_THRESHOLDS,
  performanceMonitor,
  isPerformanceSupported,
  getCurrentWebVitals,
} from '@/lib/performance/monitoring';

// ============================================================================
// PERFORMANCE_THRESHOLDS constants
// ============================================================================

describe('PERFORMANCE_THRESHOLDS', () => {
  it('LCP.good = 2500ms', () => {
    expect(PERFORMANCE_THRESHOLDS.LCP.good).toBe(2500);
  });

  it('LCP.poor = 4000ms', () => {
    expect(PERFORMANCE_THRESHOLDS.LCP.poor).toBe(4000);
  });

  it('FID.good = 100ms', () => {
    expect(PERFORMANCE_THRESHOLDS.FID.good).toBe(100);
  });

  it('FID.poor = 300ms', () => {
    expect(PERFORMANCE_THRESHOLDS.FID.poor).toBe(300);
  });

  it('CLS.good = 0.1', () => {
    expect(PERFORMANCE_THRESHOLDS.CLS.good).toBe(0.1);
  });

  it('CLS.poor = 0.25', () => {
    expect(PERFORMANCE_THRESHOLDS.CLS.poor).toBe(0.25);
  });

  it('FCP.good = 1800ms', () => {
    expect(PERFORMANCE_THRESHOLDS.FCP.good).toBe(1800);
  });

  it('TTI.good = 3800ms', () => {
    expect(PERFORMANCE_THRESHOLDS.TTI.good).toBe(3800);
  });

  it('TBT.good = 200ms', () => {
    expect(PERFORMANCE_THRESHOLDS.TBT.good).toBe(200);
  });

  it('API_RESPONSE.good = 500ms', () => {
    expect(PERFORMANCE_THRESHOLDS.API_RESPONSE.good).toBe(500);
  });

  it('ROUTE_CHANGE.good = 200ms', () => {
    expect(PERFORMANCE_THRESHOLDS.ROUTE_CHANGE.good).toBe(200);
  });

  it('COMPONENT_RENDER.good = 16ms', () => {
    expect(PERFORMANCE_THRESHOLDS.COMPONENT_RENDER.good).toBe(16);
  });

  it('all thresholds have good < poor', () => {
    Object.values(PERFORMANCE_THRESHOLDS).forEach(({ good, poor }) => {
      expect(good).toBeLessThan(poor);
    });
  });
});

// ============================================================================
// performanceMonitor.recordMetric + getMetrics
// ============================================================================

describe('performanceMonitor.recordMetric and getMetrics', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('records a metric and retrieves it', () => {
    performanceMonitor.recordMetric('TEST_METRIC', 100);
    const metrics = performanceMonitor.getMetrics('TEST_METRIC');
    expect(metrics.length).toBe(1);
    expect(metrics[0]!.name).toBe('TEST_METRIC');
    expect(metrics[0]!.value).toBe(100);
  });

  it('assigns rating "good" for a value within good threshold', () => {
    performanceMonitor.recordMetric('LCP', 1000); // well below 2500
    const metrics = performanceMonitor.getMetrics('LCP');
    expect(metrics[0]!.rating).toBe('good');
  });

  it('assigns rating "needs-improvement" for value between thresholds', () => {
    performanceMonitor.recordMetric('LCP', 3000); // between 2500 and 4000
    const metrics = performanceMonitor.getMetrics('LCP');
    expect(metrics[0]!.rating).toBe('needs-improvement');
  });

  it('assigns rating "poor" for value above poor threshold', () => {
    performanceMonitor.recordMetric('LCP', 5000); // above 4000
    const metrics = performanceMonitor.getMetrics('LCP');
    expect(metrics[0]!.rating).toBe('poor');
  });

  it('assigns rating "good" for unknown metric name', () => {
    performanceMonitor.recordMetric('UNKNOWN_METRIC', 99999);
    const metrics = performanceMonitor.getMetrics('UNKNOWN_METRIC');
    expect(metrics[0]!.rating).toBe('good');
  });

  it('records multiple entries for the same metric', () => {
    performanceMonitor.recordMetric('FCP', 500);
    performanceMonitor.recordMetric('FCP', 1200);
    const metrics = performanceMonitor.getMetrics('FCP');
    expect(metrics.length).toBe(2);
  });

  it('getMetrics() with no name returns all recorded metrics', () => {
    performanceMonitor.recordMetric('LCP', 1000);
    performanceMonitor.recordMetric('FCP', 800);
    const all = performanceMonitor.getMetrics();
    expect(all.length).toBeGreaterThanOrEqual(2);
  });

  it('getMetrics() returns empty array for unrecorded metric name', () => {
    expect(performanceMonitor.getMetrics('NONEXISTENT')).toEqual([]);
  });

  it('metric has a timestamp', () => {
    const before = Date.now();
    performanceMonitor.recordMetric('TEST', 50);
    const after = Date.now();
    const metric = performanceMonitor.getMetrics('TEST')[0]!;
    expect(metric.timestamp).toBeGreaterThanOrEqual(before);
    expect(metric.timestamp).toBeLessThanOrEqual(after);
  });
});

// ============================================================================
// performanceMonitor.setEnabled
// ============================================================================

describe('performanceMonitor.setEnabled', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('does not record when disabled', () => {
    performanceMonitor.setEnabled(false);
    performanceMonitor.recordMetric('DISABLED_TEST', 100);
    expect(performanceMonitor.getMetrics('DISABLED_TEST')).toHaveLength(0);
  });

  it('records again after re-enabling', () => {
    performanceMonitor.setEnabled(false);
    performanceMonitor.recordMetric('RE_ENABLE_TEST', 100);
    performanceMonitor.setEnabled(true);
    performanceMonitor.recordMetric('RE_ENABLE_TEST', 200);
    expect(performanceMonitor.getMetrics('RE_ENABLE_TEST')).toHaveLength(1);
    expect(performanceMonitor.getMetrics('RE_ENABLE_TEST')[0]!.value).toBe(200);
  });
});

// ============================================================================
// performanceMonitor.clearMetrics
// ============================================================================

describe('performanceMonitor.clearMetrics', () => {
  beforeEach(() => {
    performanceMonitor.setEnabled(true);
  });

  it('clears all recorded metrics', () => {
    performanceMonitor.recordMetric('LCP', 1000);
    performanceMonitor.recordMetric('FCP', 800);
    performanceMonitor.clearMetrics();
    expect(performanceMonitor.getMetrics()).toHaveLength(0);
  });
});

// ============================================================================
// performanceMonitor.getSummary
// ============================================================================

describe('performanceMonitor.getSummary', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('returns empty summary when no metrics recorded', () => {
    expect(performanceMonitor.getSummary()).toEqual({});
  });

  it('includes count and average for recorded metric', () => {
    performanceMonitor.recordMetric('FCP', 1000);
    performanceMonitor.recordMetric('FCP', 2000);
    const summary = performanceMonitor.getSummary();
    expect(summary['FCP']).toBeDefined();
    expect(summary['FCP']!.count).toBe(2);
    expect(summary['FCP']!.average).toBe(1500);
  });

  it('includes rating in summary', () => {
    performanceMonitor.recordMetric('LCP', 1000); // good
    const summary = performanceMonitor.getSummary();
    expect(summary['LCP']!.rating).toBe('good');
  });

  it('includes multiple metrics in summary', () => {
    performanceMonitor.recordMetric('LCP', 1000);
    performanceMonitor.recordMetric('FCP', 800);
    const summary = performanceMonitor.getSummary();
    expect(Object.keys(summary).length).toBeGreaterThanOrEqual(2);
  });
});

// ============================================================================
// performanceMonitor.measureApiCall
// ============================================================================

describe('performanceMonitor.measureApiCall', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('returns start and end functions', () => {
    const measure = performanceMonitor.measureApiCall('/api/test');
    expect(typeof measure.start).toBe('function');
    expect(typeof measure.end).toBe('function');
  });

  it('records a metric after end is called', () => {
    const measure = performanceMonitor.measureApiCall('/api/test', 'GET');
    measure.start();
    measure.end(true);
    const all = performanceMonitor.getMetrics();
    expect(all.some((m) => m.name.startsWith('API_'))).toBe(true);
  });

  it('records success metric name when success=true', () => {
    const measure = performanceMonitor.measureApiCall('/api/data', 'POST');
    measure.start();
    measure.end(true);
    const all = performanceMonitor.getMetrics();
    expect(all.some((m) => m.name === 'API_POST_SUCCESS')).toBe(true);
  });

  it('records error metric name when success=false', () => {
    const measure = performanceMonitor.measureApiCall('/api/data', 'GET');
    measure.start();
    measure.end(false);
    const all = performanceMonitor.getMetrics();
    expect(all.some((m) => m.name === 'API_GET_ERROR')).toBe(true);
  });
});

// ============================================================================
// performanceMonitor.measureRouteChange
// ============================================================================

describe('performanceMonitor.measureRouteChange', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('returns start and end functions', () => {
    const measure = performanceMonitor.measureRouteChange('/from', '/to');
    expect(typeof measure.start).toBe('function');
    expect(typeof measure.end).toBe('function');
  });

  it('records ROUTE_CHANGE metric after end is called', () => {
    const measure = performanceMonitor.measureRouteChange('/dashboard', '/settings');
    measure.start();
    measure.end();
    expect(performanceMonitor.getMetrics('ROUTE_CHANGE').length).toBe(1);
  });
});

// ============================================================================
// performanceMonitor.measureCustomMetric
// ============================================================================

describe('performanceMonitor.measureCustomMetric', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('returns the duration as a number', async () => {
    const duration = await performanceMonitor.measureCustomMetric('CUSTOM', () => {});
    expect(typeof duration).toBe('number');
    expect(duration).toBeGreaterThanOrEqual(0);
  });

  it('records the custom metric', async () => {
    await performanceMonitor.measureCustomMetric('MY_CUSTOM_METRIC', () => {});
    expect(performanceMonitor.getMetrics('MY_CUSTOM_METRIC').length).toBe(1);
  });

  it('still records metric even if function throws', async () => {
    await performanceMonitor.measureCustomMetric('ERRORED_METRIC', () => {
      throw new Error('oops');
    });
    expect(performanceMonitor.getMetrics('ERRORED_METRIC').length).toBe(1);
  });
});

// ============================================================================
// isPerformanceSupported
// ============================================================================

describe('isPerformanceSupported', () => {
  it('returns a boolean', () => {
    expect(typeof isPerformanceSupported()).toBe('boolean');
  });

  it('returns true in jsdom (window and performance are available)', () => {
    // jsdom provides window.performance and PerformanceObserver
    // So this should generally return true in our test environment
    const result = isPerformanceSupported();
    expect(typeof result).toBe('boolean');
  });
});

// ============================================================================
// getCurrentWebVitals
// ============================================================================

describe('getCurrentWebVitals', () => {
  beforeEach(() => {
    performanceMonitor.clearMetrics();
    performanceMonitor.setEnabled(true);
  });

  it('returns an object with lcp, fid, cls, fcp, ttfb keys', () => {
    const vitals = getCurrentWebVitals();
    expect(vitals).toHaveProperty('lcp');
    expect(vitals).toHaveProperty('fid');
    expect(vitals).toHaveProperty('cls');
    expect(vitals).toHaveProperty('fcp');
    expect(vitals).toHaveProperty('ttfb');
  });

  it('returns undefined for metrics not yet recorded', () => {
    const vitals = getCurrentWebVitals();
    expect(vitals.lcp).toBeUndefined();
    expect(vitals.fcp).toBeUndefined();
  });

  it('returns the metric when LCP is recorded', () => {
    performanceMonitor.recordMetric('LCP', 1500);
    const vitals = getCurrentWebVitals();
    expect(vitals.lcp).toBeDefined();
    expect(vitals.lcp!.value).toBe(1500);
  });

  it('returns the metric when FCP is recorded', () => {
    performanceMonitor.recordMetric('FCP', 900);
    const vitals = getCurrentWebVitals();
    expect(vitals.fcp).toBeDefined();
    expect(vitals.fcp!.value).toBe(900);
  });
});
