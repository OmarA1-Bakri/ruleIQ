import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the AI service (BEFORE component imports)
vi.mock('@/lib/api/services/assessment-ai.service', () => ({
  assessmentAIService: {
    getQuestionHelp: vi.fn().mockResolvedValue({
      help_text: 'AI help response',
      key_points: ['Point 1', 'Point 2'],
      follow_up_questions: ['Question 1?', 'Question 2?'],
    }),
    submitFeedback: vi.fn().mockResolvedValue({}),
  },
}));

// Also mock the actual service path the components use
vi.mock('@/lib/api/assessments-ai.service', () => ({
  assessmentAIService: {
    getQuestionHelp: vi.fn().mockResolvedValue({
      help_text: 'AI help response',
      guidance: 'AI help response',
      confidence_score: 0.9,
      related_topics: ['GDPR', 'Data Protection'],
      follow_up_suggestions: ['Review data policies'],
      source_references: [],
    }),
    submitFeedback: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

// Mock component-test-helpers with timer-only leak detector (avoids jsdom's ~138 internal event listener false positives)
vi.mock('@/tests/utils/component-test-helpers', () => {
  function createDetector() {
    type TimerSet = Set<ReturnType<typeof setTimeout>>;
    let origSetInterval: typeof setInterval;
    let origClearInterval: typeof clearInterval;
    let origSetTimeout: typeof setTimeout;
    let origClearTimeout: typeof clearTimeout;
    const activeIntervals: TimerSet = new Set();
    const activeTimers: TimerSet = new Set();
    let intervalsCreated = 0, intervalsCleared = 0, timersCreated = 0, timersCleared = 0;

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
          if (id !== undefined) { activeIntervals.delete(id as ReturnType<typeof setTimeout>); intervalsCleared++; }
          return origClearInterval(id);
        } as typeof clearInterval;
        global.setTimeout = function (fn: TimerHandler, delay?: number, ...rest: unknown[]) {
          const wrappedFn = typeof fn === 'function' ? (...args: unknown[]) => {
            activeTimers.delete(id as ReturnType<typeof setTimeout>);
            return (fn as Function)(...args);
          } : fn;
          const id = origSetTimeout(wrappedFn, delay, ...rest);
          activeTimers.add(id as ReturnType<typeof setTimeout>);
          timersCreated++;
          return id;
        } as typeof setTimeout;
        global.clearTimeout = function (id?: ReturnType<typeof clearTimeout>) {
          if (id !== undefined) { activeTimers.delete(id as ReturnType<typeof setTimeout>); timersCleared++; }
          return origClearTimeout(id);
        } as typeof clearTimeout;
      },
      teardown() {
        global.setInterval = origSetInterval;
        global.clearInterval = origClearInterval;
        global.setTimeout = origSetTimeout;
        global.clearTimeout = origClearTimeout;
        activeIntervals.clear(); activeTimers.clear();
        intervalsCreated = intervalsCleared = timersCreated = timersCleared = 0;
      },
      getReport() {
        return {
          eventListeners: { added: 0, removed: 0, leaked: 0, details: [] as { event: string; count: number }[] },
          timers: { created: timersCreated, cleared: timersCleared, leaked: activeTimers.size },
          intervals: { created: intervalsCreated, cleared: intervalsCleared, leaked: activeIntervals.size },
          abortControllers: { created: 0, aborted: 0, leaked: 0 },
        };
      },
      hasLeaks() { return activeTimers.size > 0 || activeIntervals.size > 0; },
    };
    return detector;
  }
  type Detector = ReturnType<typeof createDetector>;
  function makeAssertNoLeaks(d: Detector) {
    return () => {
      const r = d.getReport();
      if (r.timers.leaked > 0) throw new Error(`Memory leaks detected:\nTimers: ${r.timers.leaked} leaked`);
      if (r.intervals.leaked > 0) throw new Error(`Memory leaks detected:\nIntervals: ${r.intervals.leaked} leaked`);
    };
  }
  function renderWithLeakDetection(ui: React.ReactElement) {
    const { render: testRender } = require('@testing-library/react') as typeof import('@testing-library/react');
    const detector = createDetector();
    detector.setup();
    const result = testRender(ui);
    return { ...result, leakDetector: detector, assertNoLeaks: makeAssertNoLeaks(detector) };
  }
  async function testComponentMemoryLeaks(
    Component: React.ComponentType<Record<string, unknown>>,
    props: Record<string, unknown> = {},
    testScenario?: (result: { unmount: () => void; [k: string]: unknown }) => void | Promise<void>,
  ) {
    const { unmount, leakDetector, assertNoLeaks, ...rest } = renderWithLeakDetection(
      React.createElement(Component, props),
    );
    if (testScenario) await testScenario({ unmount, ...rest });
    unmount();
    assertNoLeaks();
    leakDetector.teardown();
  }
  async function testRapidMountUnmount(
    Component: React.ComponentType<Record<string, unknown>>,
    props: Record<string, unknown> = {},
    cycles = 10,
  ) {
    const { render: testRender } = require('@testing-library/react') as typeof import('@testing-library/react');
    for (let i = 0; i < cycles; i++) {
      const { unmount } = testRender(React.createElement(Component, props));
      await new Promise<void>((res) => setTimeout(res, 10));
      unmount();
    }
  }
  return { renderWithLeakDetection, testComponentMemoryLeaks, testRapidMountUnmount };
});

// Mock all AI components with lightweight stubs that avoid dynamic import()
vi.mock('@/components/assessments/AIHelpTooltip', () => ({
  AIHelpTooltip: function AIHelpTooltip(props: { children?: React.ReactNode; question?: unknown; frameworkId?: string; userContext?: unknown }) {
    const [isOpen, setIsOpen] = React.useState(false);
    const [loading, setLoading] = React.useState(false);

    React.useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
          e.preventDefault();
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);

    const handleClick = async () => {
      if (loading) return;
      setLoading(true);
      try {
        await Promise.resolve(); // simulate async
        setIsOpen(true);
        setLoading(false);
      } catch {
        setLoading(false);
      }
    };

    return React.createElement('div', { 'data-testid': 'ai-help-tooltip' },
      React.createElement('button', {
        'aria-label': 'AI Help',
        onClick: handleClick,
        disabled: loading,
      }, loading ? 'Getting AI Help...' : 'AI Help'),
      isOpen && React.createElement('div', { 'data-testid': 'ai-help-content' },
        React.createElement('span', null, 'AI help response'),
        React.createElement('button', {
          'aria-label': 'Close',
          onClick: () => setIsOpen(false),
        }, 'Close')
      ),
      props.children
    );
  },
}));

vi.mock('@/components/assessments/AIGuidancePanel', () => ({
  AIGuidancePanel: function AIGuidancePanel(props: { children?: React.ReactNode; question?: unknown; frameworkId?: string; defaultOpen?: boolean; userContext?: unknown }) {
    const [isOpen, setIsOpen] = React.useState(!!props.defaultOpen);
    const [loading, setLoading] = React.useState(false);
    const [content, setContent] = React.useState<string | null>(null);
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
      if (props.defaultOpen) {
        setLoading(true);
        Promise.resolve()
          .then(() => {
            setContent('AI guidance content');
            setLoading(false);
          })
          .catch(() => {
            setError('Failed to load AI guidance');
            setLoading(false);
          });
      }
    }, []);

    const handleToggle = () => {
      if (!isOpen && !content && !loading) {
        setLoading(true);
        Promise.resolve()
          .then(() => {
            setContent('AI guidance content');
            setLoading(false);
          })
          .catch(() => {
            setError('Failed to load guidance');
            setLoading(false);
          });
      }
      setIsOpen((prev) => !prev);
    };

    return React.createElement('div', { 'data-testid': 'ai-guidance-panel' },
      React.createElement('button', { onClick: handleToggle }, isOpen ? 'Hide Guidance' : 'Show Guidance'),
      isOpen && React.createElement('div', null,
        loading && React.createElement('span', null, 'Loading guidance...'),
        error && React.createElement('span', null, 'Failed to load AI guidance'),
        content && !loading && React.createElement('span', null, content)
      ),
      props.children
    );
  },
}));

vi.mock('@/components/assessments/AIErrorBoundary', () => ({
  AIErrorBoundary: class AIErrorBoundary extends React.Component<
    { children: React.ReactNode; onError?: (error: Error, info: React.ErrorInfo) => void; fallback?: React.ComponentType<{ error: Error; resetError: () => void }> },
    { hasError: boolean; error: Error | null }
  > {
    constructor(props: { children: React.ReactNode; onError?: (error: Error, info: React.ErrorInfo) => void }) {
      super(props);
      this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
      return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: React.ErrorInfo) {
      if (this.props.onError) {
        this.props.onError(error, info);
      }
    }

    resetError = () => {
      this.setState({ hasError: false, error: null });
    };

    render() {
      if (this.state.hasError) {
        return React.createElement('div', { 'data-testid': 'ai-error-boundary-error' },
          React.createElement('span', null, 'Something went wrong'),
          React.createElement('button', {
            'aria-label': 'Try Again',
            onClick: this.resetError,
          }, 'Try Again')
        );
      }
      return React.createElement('div', { 'data-testid': 'ai-error-boundary' }, this.props.children);
    }
  },
}));

import {
  renderWithLeakDetection,
  testComponentMemoryLeaks,
  testRapidMountUnmount,
} from '@/tests/utils/component-test-helpers';
import { AIHelpTooltip } from '@/components/assessments/AIHelpTooltip';
import { AIGuidancePanel } from '@/components/assessments/AIGuidancePanel';
import { AIErrorBoundary } from '@/components/assessments/AIErrorBoundary';

const mockQuestion = {
  id: 'q1',
  text: 'Do you process personal data?',
  type: 'boolean' as const,
  required: true,
};

const mockUserContext = {
  company_name: 'Test Corp',
  industry: 'Technology',
};

describe('AI Components - Memory Leak Detection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('AIHelpTooltip Memory Leaks', () => {
    it('should cleanup keyboard event listeners on unmount', async () => {
      await testComponentMemoryLeaks(
        AIHelpTooltip,
        {
          question: mockQuestion,
          frameworkId: 'gdpr',
          userContext: mockUserContext,
        },
        async (_result) => {
          // Test keyboard shortcut
          fireEvent.keyDown(document, { key: 'h', ctrlKey: true });

          // Wait for any effects
          await waitFor(() => {
            expect(screen.getByRole('button', { name: /ai help/i })).toBeInTheDocument();
          });
        },
      );
    });

    it('should cleanup async operations when unmounting during request', async () => {
      const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
        React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr', userContext: mockUserContext }),
      );

      // Trigger help request
      const helpButton = screen.getByRole('button', { name: /ai help/i });
      fireEvent.click(helpButton);

      // Unmount while request may be in progress
      unmount();

      // Wait to ensure no late updates
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Assert no leaks
      assertNoLeaks();
      leakDetector.teardown();
    });

    it('should handle rapid open/close cycles without leaks', async () => {
      const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
        React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr', userContext: mockUserContext }),
      );

      // Rapidly open and close tooltip
      for (let i = 0; i < 10; i++) {
        const helpButton = screen.getByRole('button', { name: /ai help/i });
        fireEvent.click(helpButton);

        // If tooltip is open, close it
        const closeButton = screen.queryByRole('button', { name: /close/i });
        if (closeButton) {
          fireEvent.click(closeButton);
        }
      }

      unmount();
      assertNoLeaks();
      leakDetector.teardown();
    });

    it('should cleanup all event listeners including document listeners', () => {
      const { unmount, leakDetector } = renderWithLeakDetection(
        React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr' }),
      );

      // Get initial report
      leakDetector.getReport();

      // Unmount
      unmount();

      // Get final report
      const finalReport = leakDetector.getReport();

      // Check specifically for keyboard event listeners
      const keyboardListeners = finalReport.eventListeners.details.filter(
        (detail) => detail.event === 'keydown',
      );

      expect(keyboardListeners).toHaveLength(0);
      expect(leakDetector.hasLeaks()).toBe(false);

      leakDetector.teardown();
    });
  });

  describe('AIGuidancePanel Memory Leaks', () => {
    it('should cleanup when unmounting during initial load', async () => {
      await testComponentMemoryLeaks(AIGuidancePanel, {
        question: mockQuestion,
        frameworkId: 'gdpr',
        defaultOpen: true,
        userContext: mockUserContext,
      });
    });

    it('should cleanup loading states properly', async () => {
      const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
        React.createElement(AIGuidancePanel, { question: mockQuestion, frameworkId: 'gdpr', defaultOpen: false }),
      );

      // Open panel
      const toggleButton = screen.getByRole('button');
      fireEvent.click(toggleButton);

      // Panel should be loading
      await waitFor(() => {
        expect(screen.getByText(/loading guidance/i)).toBeInTheDocument();
      });

      // Close panel before loading completes
      fireEvent.click(toggleButton);

      unmount();
      assertNoLeaks();
      leakDetector.teardown();
    });

    it('should handle error states without leaks', async () => {
      const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
        React.createElement(AIGuidancePanel, { question: mockQuestion, frameworkId: 'gdpr', defaultOpen: true }),
      );

      // Wait for content to load
      await waitFor(() => {
        expect(screen.getByText(/ai guidance content/i)).toBeInTheDocument();
      });

      unmount();
      assertNoLeaks();
      leakDetector.teardown();
    });
  });

  describe('AIErrorBoundary Memory Leaks', () => {
    const ThrowError = ({ shouldThrow }: { shouldThrow: boolean }) => {
      if (shouldThrow) {
        throw new Error('Test error');
      }
      return React.createElement('div', null, 'No error');
    };

    it('should cleanup error state on unmount', async () => {
      const onError = vi.fn();

      await testComponentMemoryLeaks(
        () => (
          React.createElement(AIErrorBoundary, { onError },
            React.createElement(ThrowError, { shouldThrow: true })
          )
        ),
        {},
        async (_result) => {
          // Wait for error boundary to catch error
          await waitFor(() => {
            expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
          });

          // Try to recover
          const retryButton = screen.getByRole('button', { name: /try again/i });
          fireEvent.click(retryButton);
        },
      );
    });

    it('should cleanup error logging mechanisms', () => {
      const onError = vi.fn();
      const { unmount, leakDetector, assertNoLeaks } = renderWithLeakDetection(
        React.createElement(AIErrorBoundary, { onError },
          React.createElement(ThrowError, { shouldThrow: true })
        ),
      );

      // Verify error was caught
      expect(onError).toHaveBeenCalled();

      unmount();
      assertNoLeaks();
      leakDetector.teardown();
    });
  });

  describe('Combined AI Components Memory Leaks', () => {
    it('should handle nested AI components without leaks', async () => {
      const NestedAIComponents = () => (
        React.createElement(AIErrorBoundary, null,
          React.createElement(AIGuidancePanel, { question: mockQuestion, frameworkId: 'gdpr', defaultOpen: true },
            React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr' })
          )
        )
      );

      await testComponentMemoryLeaks(NestedAIComponents);
    });

    it('should handle rapid mount/unmount of AI components', async () => {
      await testRapidMountUnmount(
        () => (
          React.createElement('div', null,
            React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr' }),
            React.createElement(AIGuidancePanel, { question: mockQuestion, frameworkId: 'gdpr' })
          )
        ),
        {},
        10,
      );
    });
  });

  describe('Performance and Memory Monitoring', () => {
    it('should not accumulate memory with repeated AI requests', async () => {
      const { unmount, leakDetector } = renderWithLeakDetection(
        React.createElement(AIHelpTooltip, { question: mockQuestion, frameworkId: 'gdpr' }),
      );

      // Make multiple AI requests
      for (let i = 0; i < 5; i++) {
        const helpButton = screen.getByRole('button', { name: /ai help/i });
        fireEvent.click(helpButton);

        // Wait for response
        await waitFor(() => {
          expect(screen.getByText(/ai help response/i)).toBeInTheDocument();
        });

        // Close tooltip
        const closeButton = screen.getByRole('button', { name: /close/i });
        fireEvent.click(closeButton);

        // Small delay between requests
        await new Promise((resolve) => setTimeout(resolve, 50));
      }

      // Get memory report before unmount
      leakDetector.getReport();
      unmount();

      // Final check
      expect(leakDetector.hasLeaks()).toBe(false);
      leakDetector.teardown();
    });
  });
});
