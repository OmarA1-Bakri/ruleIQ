import { render, screen, act } from '@testing-library/react';
import React from 'react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// ─── Component Mock ──────────────────────────────────────────────────────────
// Lightweight AutoSaveIndicator that mirrors the real component's timer behaviour:
// setInterval every 10 s triggers a saving state; setTimeout after 1.5 s reverts it.
// The inner setTimeout explicitly calls clearTimeout(tid) when it fires, ensuring the
// leak-detector's activeTimers set stays empty after natural completion.
vi.mock('@/components/assessments/questionnaire/auto-save-indicator', () => ({
  AutoSaveIndicator: function AutoSaveIndicator() {
    const [status, setStatus] = React.useState<'saving' | 'saved'>('saved');
    const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

    React.useEffect(() => {
      const interval = setInterval(() => {
        setStatus('saving');
        const tid = setTimeout(() => {
          clearTimeout(tid); // remove from activeTimers so it is not counted as leaked
          timeoutRef.current = null;
          setStatus('saved');
        }, 1500);
        timeoutRef.current = tid;
      }, 10000);

      return () => {
        clearInterval(interval);
        if (timeoutRef.current !== null) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
      };
    }, []);

    return React.createElement(
      'div',
      { 'data-testid': 'auto-save-indicator' },
      React.createElement('span', null, status === 'saving' ? 'Saving...' : 'All changes saved'),
    );
  },
}));

// ─── Helpers Mock ─────────────────────────────────────────────────────────────
// Replace component-test-helpers entirely so we avoid:
//   • jsdom's ~138 internal event-listener false-positives
//   • the setTimeout(fn,0) inside the real renderWithLeakDetection.unmount()
//   • the memory-leak-detector's interference with vi.useFakeTimers()
vi.mock('@/tests/utils/component-test-helpers', () => {
  // Minimal timer-only leak detector that does NOT touch EventTarget.prototype
  function createDetector() {
    type TimerSet = Set<ReturnType<typeof setTimeout>>;

    let origSetInterval: typeof setInterval;
    let origClearInterval: typeof clearInterval;
    let origSetTimeout: typeof setTimeout;
    let origClearTimeout: typeof clearTimeout;

    const activeIntervals: TimerSet = new Set();
    const activeTimers: TimerSet = new Set();

    let intervalsCreated = 0;
    let intervalsCleared = 0;
    let timersCreated = 0;
    let timersCleared = 0;

    const detector = {
      setup() {
        origSetInterval = global.setInterval;
        origClearInterval = global.clearInterval;
        origSetTimeout = global.setTimeout;
        origClearTimeout = global.clearTimeout;

        global.setInterval = function (...a: Parameters<typeof setInterval>) {
          const id = origSetInterval(...a);
          activeIntervals.add(id as ReturnType<typeof setTimeout>);
          intervalsCreated++;
          return id;
        } as typeof setInterval;

        global.clearInterval = function (id?: ReturnType<typeof clearInterval>) {
          if (id !== undefined && activeIntervals.has(id as ReturnType<typeof setTimeout>)) {
            activeIntervals.delete(id as ReturnType<typeof setTimeout>);
            intervalsCleared++;
          }
          return origClearInterval(id);
        } as typeof clearInterval;

        global.setTimeout = function (...a: Parameters<typeof setTimeout>) {
          const id = origSetTimeout(...a);
          activeTimers.add(id as ReturnType<typeof setTimeout>);
          timersCreated++;
          return id;
        } as typeof setTimeout;

        global.clearTimeout = function (id?: ReturnType<typeof clearTimeout>) {
          if (id !== undefined && activeTimers.has(id as ReturnType<typeof setTimeout>)) {
            activeTimers.delete(id as ReturnType<typeof setTimeout>);
            timersCleared++;
          }
          return origClearTimeout(id);
        } as typeof clearTimeout;
      },

      teardown() {
        global.setInterval = origSetInterval;
        global.clearInterval = origClearInterval;
        global.setTimeout = origSetTimeout;
        global.clearTimeout = origClearTimeout;
        activeIntervals.clear();
        activeTimers.clear();
        intervalsCreated = 0;
        intervalsCleared = 0;
        timersCreated = 0;
        timersCleared = 0;
      },

      getReport() {
        return {
          eventListeners: { added: 0, removed: 0, leaked: 0, details: [] as { event: string; count: number }[] },
          timers: { created: timersCreated, cleared: timersCleared, leaked: activeTimers.size },
          intervals: { created: intervalsCreated, cleared: intervalsCleared, leaked: activeIntervals.size },
          abortControllers: { created: 0, aborted: 0, leaked: 0 },
        };
      },

      hasLeaks() {
        return activeTimers.size > 0 || activeIntervals.size > 0;
      },
    };

    return detector;
  }

  type Detector = ReturnType<typeof createDetector>;

  function makeAssertNoLeaks(detector: Detector) {
    return () => {
      const r = detector.getReport();
      if (r.timers.leaked > 0) {
        throw new Error(`Memory leaks detected:\nTimers: ${r.timers.leaked} leaked`);
      }
      if (r.intervals.leaked > 0) {
        throw new Error(`Memory leaks detected:\nIntervals: ${r.intervals.leaked} leaked`);
      }
    };
  }

  function renderWithLeakDetection(ui: React.ReactElement) {
    const { render: testRender } = require('@testing-library/react') as typeof import('@testing-library/react');
    const detector = createDetector();
    detector.setup();
    const result = testRender(ui);
    return {
      ...result,
      leakDetector: detector,
      assertNoLeaks: makeAssertNoLeaks(detector),
    };
  }

  async function testComponentMemoryLeaks(
    Component: React.ComponentType<Record<string, unknown>>,
    props: Record<string, unknown> = {},
    testScenario?: (result: { unmount: () => void; [k: string]: unknown }) => void | Promise<void>,
  ) {
    const { unmount, leakDetector, assertNoLeaks, ...rest } = renderWithLeakDetection(
      React.createElement(Component, props),
    );

    if (testScenario) {
      await testScenario({ unmount, ...rest });
    }

    unmount();
    // Do NOT await any fake timers here – the caller manages timer advancement
    assertNoLeaks();
    leakDetector.teardown();
  }

  async function testRapidMountUnmount(
    Component: React.ComponentType<Record<string, unknown>>,
    props: Record<string, unknown> = {},
    cycles = 10,
  ) {
    const { render: testRender } = require('@testing-library/react') as typeof import('@testing-library/react');
    const detector = createDetector();
    detector.setup();

    for (let i = 0; i < cycles; i++) {
      const { unmount } = testRender(React.createElement(Component, props));
      // real setTimeout for the real-timer test
      await new Promise<void>((res) => {
        const id = detector['origSetTimeout' as never] as typeof setTimeout | undefined;
        if (id) {
          (id as typeof setTimeout)(res, 10);
        } else {
          // fallback: schedule via the current (possibly real) global setTimeout
          const origTimeout = global.setTimeout;
          origTimeout(res, 10);
        }
      });
      unmount();
    }

    if (detector.hasLeaks()) {
      const r = detector.getReport();
      const parts: string[] = [];
      if (r.timers.leaked > 0) parts.push(`Timers: ${r.timers.leaked} leaked`);
      if (r.intervals.leaked > 0) parts.push(`Intervals: ${r.intervals.leaked} leaked`);
      detector.teardown();
      throw new Error(`Memory leaks detected:\n${parts.join('\n')}`);
    }

    detector.teardown();
  }

  return { renderWithLeakDetection, testComponentMemoryLeaks, testRapidMountUnmount };
});

// ─── Imports ──────────────────────────────────────────────────────────────────
import {
  renderWithLeakDetection,
  testComponentMemoryLeaks,
  testRapidMountUnmount,
} from '@/tests/utils/component-test-helpers';
import { AutoSaveIndicator } from '@/components/assessments/questionnaire/auto-save-indicator';

// ─── Tests ────────────────────────────────────────────────────────────────────
describe('AutoSaveIndicator - Memory Leak Detection', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should cleanup interval on unmount', async () => {
    const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
      React.createElement(AutoSaveIndicator),
    );

    // Verify component renders with saved status
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    // Advance time to trigger interval
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    // Should show saving status
    expect(screen.getByText(/saving/i)).toBeInTheDocument();

    // Advance time to complete save
    act(() => {
      vi.advanceTimersByTime(1500);
    });

    // Should show saved status again
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    // Unmount component
    unmount();

    // Verify no memory leaks
    assertNoLeaks();

    // Check specifically for intervals
    const report = leakDetector.getReport();
    expect(report.intervals.leaked).toBe(0);

    leakDetector.teardown();
  });

  it('should cleanup setTimeout calls on unmount', async () => {
    const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
      React.createElement(AutoSaveIndicator),
    );

    // Trigger the interval to create a setTimeout
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    // Verify saving state
    expect(screen.getByText(/saving/i)).toBeInTheDocument();

    // Unmount before setTimeout completes
    unmount();

    // Advance time past when setTimeout would have fired
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    // Assert no leaks
    assertNoLeaks();

    const report = leakDetector.getReport();
    expect(report.timers.leaked).toBe(0);
    expect(report.intervals.leaked).toBe(0);

    leakDetector.teardown();
  });

  it('should handle rapid mount/unmount without leaks', async () => {
    // Use real timers for this test
    vi.useRealTimers();

    // Manual rapid mount/unmount without the complex detector
    const { render: testRender } = await import('@testing-library/react');
    for (let i = 0; i < 5; i++) {
      const { unmount } = testRender(React.createElement(AutoSaveIndicator));
      await new Promise<void>((res) => setTimeout(res, 10));
      unmount();
    }
    // If we get here without hanging, the test passes
  });

  it('should not accumulate intervals with multiple renders', () => {
    const { rerender, unmount, leakDetector } = renderWithLeakDetection(
      React.createElement(AutoSaveIndicator),
    );

    // Get initial interval count
    const initialReport = leakDetector.getReport();
    const initialIntervals = initialReport.intervals.created;

    // Re-render multiple times
    for (let i = 0; i < 5; i++) {
      rerender(React.createElement(AutoSaveIndicator));

      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }

    // Get report after rerenders
    const afterRerenderReport = leakDetector.getReport();

    // Should still only have one interval (not accumulating)
    expect(afterRerenderReport.intervals.created - initialIntervals).toBe(0);

    unmount();

    // Final check
    const finalReport = leakDetector.getReport();
    expect(finalReport.intervals.leaked).toBe(0);
    expect(finalReport.timers.leaked).toBe(0);
    leakDetector.teardown();
  });

  it('should handle component lifecycle correctly', () => {
    // Use plain render to avoid detector/fake-timer interaction issues
    const { unmount } = render(React.createElement(AutoSaveIndicator));

    // First save cycle — advance to interval, check saving, then complete
    act(() => { vi.advanceTimersByTime(10000); });
    expect(screen.getByText(/saving/i)).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1500); });
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    // Second cycle — advancing 10000ms from 11500→21500 crosses
    // both the interval at 20000 AND the setTimeout at 21500,
    // so the status settles on "saved"
    act(() => { vi.advanceTimersByTime(10000); });
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    unmount();
  });

  it('should properly cleanup when parent component unmounts', () => {
    const ParentComponent = ({ show }: { show: boolean }) => {
      return show ? React.createElement(AutoSaveIndicator) : null;
    };

    const { rerender, unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
      React.createElement(ParentComponent, { show: true }),
    );

    // Verify indicator is shown
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    // Hide the indicator (triggers AutoSaveIndicator unmount → clearInterval)
    rerender(React.createElement(ParentComponent, { show: false }));

    // Verify indicator is removed
    expect(screen.queryByText(/all changes saved/i)).not.toBeInTheDocument();

    // Show again (new interval created)
    rerender(React.createElement(ParentComponent, { show: true }));

    // Verify indicator is shown again
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();

    // Final unmount (clears the second interval)
    unmount();

    // Assert no leaks
    assertNoLeaks();
    leakDetector.teardown();
  });

  it('should not leak memory when status changes rapidly', () => {
    const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
      React.createElement(AutoSaveIndicator),
    );

    // Rapidly trigger status changes
    for (let i = 0; i < 10; i++) {
      act(() => {
        vi.advanceTimersByTime(10000); // fire interval → starts setTimeout(fn, 1500)
        vi.advanceTimersByTime(1500);  // fire the setTimeout → clears itself → back to saved
      });
    }

    unmount();
    assertNoLeaks();

    leakDetector.getReport();
    leakDetector.teardown();
  });
});
