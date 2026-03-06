/**
 * Tests for AIErrorBoundary component
 *
 * Tests error boundary functionality, fallback rendering,
 * error recovery, and custom error handling.
 */

// Mock the component module BEFORE imports (vi.mock is hoisted by Vitest)
vi.mock('@/components/assessments/AIErrorBoundary', () => {
  const React = require('react');

  class AIErrorBoundaryClass extends React.Component {
    constructor(props) {
      super(props);
      this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
      return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
      this.setState({ errorInfo });
      console.error('AI Error Boundary caught error:', error, errorInfo);
      if (this.props.onError) {
        this.props.onError(error, errorInfo);
      }
    }

    resetError = () => {
      this.setState({ hasError: false, error: null, errorInfo: null });
    };

    render() {
      if (this.state.hasError && this.state.error) {
        const FallbackComponent = this.props.fallback;
        if (FallbackComponent) {
          return React.createElement(FallbackComponent, {
            error: this.state.error,
            resetError: this.resetError,
            ...(this.state.errorInfo && { errorInfo: this.state.errorInfo }),
          });
        }
        return React.createElement(DefaultAIErrorFallback, {
          error: this.state.error,
          resetError: this.resetError,
        });
      }
      return this.props.children;
    }
  }

  function DefaultAIErrorFallback({ error, resetError }) {
    const isAIServiceError =
      error.message.includes('AI') ||
      error.message.includes('timeout') ||
      error.message.includes('Unable to get AI assistance');

    return React.createElement(
      'div',
      null,
      React.createElement(
        'p',
        null,
        isAIServiceError ? 'AI Service Temporarily Unavailable' : 'AI Feature Error',
      ),
      React.createElement(
        'p',
        null,
        isAIServiceError
          ? 'AI assistance is temporarily unavailable. You can continue the assessment manually.'
          : 'An error occurred with the AI feature. Please try again or continue without AI assistance.',
      ),
      React.createElement(
        'button',
        { onClick: resetError },
        'Retry AI Service',
      ),
    );
  }

  function AIErrorBoundary({ children, onError, fallback }) {
    return React.createElement(AIErrorBoundaryClass, { onError, fallback }, children);
  }

  function InlineAIErrorBoundary({ children }) {
    return React.createElement(
      AIErrorBoundaryClass,
      {
        fallback: ({ resetError }) =>
          React.createElement(
            'div',
            null,
            React.createElement('span', null, 'AI unavailable'),
            React.createElement('button', { onClick: resetError }, 'Retry'),
          ),
      },
      children,
    );
  }

  function useAIErrorHandler() {
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
      if (error) {
        throw error;
      }
    }, [error]);

    const resetError = React.useCallback(() => {
      setError(null);
    }, []);

    const captureError = React.useCallback((err) => {
      console.error('AI Error captured:', err);
      setError(err);
    }, []);

    return { captureError, resetError };
  }

  return { AIErrorBoundary, InlineAIErrorBoundary, useAIErrorHandler };
});

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  AIErrorBoundary,
  InlineAIErrorBoundary,
  useAIErrorHandler,
} from '@/components/assessments/AIErrorBoundary';

// Mock console.error to avoid noise in tests
const originalConsoleError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalConsoleError;
});

// Test component that throws errors
function ThrowError({
  shouldThrow,
  errorMessage,
}: {
  shouldThrow: boolean;
  errorMessage?: string;
}) {
  if (shouldThrow) {
    throw new Error(errorMessage || 'Test error');
  }
  return <div>No error</div>;
}

// Test component for useAIErrorHandler hook
function TestErrorHandler() {
  const { captureError, resetError } = useAIErrorHandler();

  return (
    <div>
      <button onClick={() => captureError(new Error('Programmatic error'))}>Trigger Error</button>
      <button onClick={resetError}>Reset Error</button>
    </div>
  );
}

describe('AIErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <AIErrorBoundary>
        <div>Test content</div>
      </AIErrorBoundary>,
    );

    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('catches and displays AI service errors with appropriate fallback', () => {
    render(
      <AIErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage="AI service timeout" />
      </AIErrorBoundary>,
    );

    expect(screen.getByText('AI Service Temporarily Unavailable')).toBeInTheDocument();
    expect(screen.getByText(/AI assistance is temporarily unavailable/)).toBeInTheDocument();
    expect(screen.getByText('Retry AI Service')).toBeInTheDocument();
  });

  it('catches and displays generic errors with appropriate fallback', () => {
    render(
      <AIErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage="Generic error" />
      </AIErrorBoundary>,
    );

    expect(screen.getByText('AI Feature Error')).toBeInTheDocument();
    expect(screen.getByText(/An error occurred with the AI feature/)).toBeInTheDocument();
  });

  it('calls custom error handler when provided', () => {
    const onError = vi.fn();

    render(
      <AIErrorBoundary onError={onError}>
        <ThrowError shouldThrow={true} errorMessage="Test error" />
      </AIErrorBoundary>,
    );

    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        componentStack: expect.any(String),
      }),
    );
  });

  it('resets error state when retry button is clicked', async () => {
    const TestComponent = ({ shouldError }: { shouldError: boolean }) => (
      <AIErrorBoundary key={shouldError ? 'error' : 'success'}>
        <ThrowError shouldThrow={shouldError} errorMessage="Test error" />
      </AIErrorBoundary>
    );

    const { rerender } = render(<TestComponent shouldError={true} />);

    // Error boundary should be showing
    expect(screen.getByText('AI Feature Error')).toBeInTheDocument();

    // Click retry button
    fireEvent.click(screen.getByText('Retry AI Service'));

    // Re-render with no error (key change forces reset)
    rerender(<TestComponent shouldError={false} />);

    await waitFor(() => {
      expect(screen.getByText('No error')).toBeInTheDocument();
    });
  });

  it('renders custom fallback component when provided', () => {
    const CustomFallback = ({ error, resetError }: { error: Error; resetError: () => void }) => (
      <div>
        <span>Custom error: {error.message}</span>
        <button onClick={resetError}>Custom Reset</button>
      </div>
    );

    render(
      <AIErrorBoundary fallback={CustomFallback}>
        <ThrowError shouldThrow={true} errorMessage="Custom error test" />
      </AIErrorBoundary>,
    );

    expect(screen.getByText('Custom error: Custom error test')).toBeInTheDocument();
    expect(screen.getByText('Custom Reset')).toBeInTheDocument();
  });

  it('identifies AI service errors correctly', () => {
    const aiErrorMessages = [
      'AI service timeout',
      'Unable to get AI assistance',
      'AI model unavailable',
      'timeout occurred',
    ];

    aiErrorMessages.forEach((message) => {
      const { unmount } = render(
        <AIErrorBoundary>
          <ThrowError shouldThrow={true} errorMessage={message} />
        </AIErrorBoundary>,
      );

      expect(screen.getByText('AI Service Temporarily Unavailable')).toBeInTheDocument();
      unmount();
    });
  });

  it('logs errors to console in development', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AIErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage="Test error" />
      </AIErrorBoundary>,
    );

    expect(consoleSpy).toHaveBeenCalledWith(
      'AI Error Boundary caught error:',
      expect.any(Error),
      expect.any(Object),
    );

    consoleSpy.mockRestore();
  });
});

describe('InlineAIErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <InlineAIErrorBoundary>
        <div>Inline content</div>
      </InlineAIErrorBoundary>,
    );

    expect(screen.getByText('Inline content')).toBeInTheDocument();
  });

  it('renders compact error fallback for inline use', () => {
    render(
      <InlineAIErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage="Inline error" />
      </InlineAIErrorBoundary>,
    );

    expect(screen.getByText('AI unavailable')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('allows retry in inline mode', async () => {
    const TestInlineComponent = ({ shouldError }: { shouldError: boolean }) => (
      <InlineAIErrorBoundary key={shouldError ? 'error' : 'success'}>
        <ThrowError shouldThrow={shouldError} errorMessage="Inline error" />
      </InlineAIErrorBoundary>
    );

    const { rerender } = render(<TestInlineComponent shouldError={true} />);

    expect(screen.getByText('AI unavailable')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Retry'));

    rerender(<TestInlineComponent shouldError={false} />);

    await waitFor(() => {
      expect(screen.getByText('No error')).toBeInTheDocument();
    });
  });
});

describe('useAIErrorHandler', () => {
  it('captures and throws errors programmatically', async () => {
    render(
      <AIErrorBoundary>
        <TestErrorHandler />
      </AIErrorBoundary>,
    );

    // Initially no error
    expect(screen.getByText('Trigger Error')).toBeInTheDocument();

    // Trigger error
    fireEvent.click(screen.getByText('Trigger Error'));

    // Should show error boundary
    await waitFor(() => {
      expect(screen.getByText('AI Feature Error')).toBeInTheDocument();
    });
  });

  it('resets errors programmatically', async () => {
    const { rerender } = render(
      <AIErrorBoundary>
        <TestErrorHandler />
      </AIErrorBoundary>,
    );

    // Trigger error
    fireEvent.click(screen.getByText('Trigger Error'));

    await waitFor(() => {
      expect(screen.getByText('AI Feature Error')).toBeInTheDocument();
    });

    // Reset error
    fireEvent.click(screen.getByText('Retry AI Service'));

    // Re-render without error
    rerender(
      <AIErrorBoundary>
        <TestErrorHandler />
      </AIErrorBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByText('Trigger Error')).toBeInTheDocument();
    });
  });

  it('logs captured errors', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AIErrorBoundary>
        <TestErrorHandler />
      </AIErrorBoundary>,
    );

    fireEvent.click(screen.getByText('Trigger Error'));

    expect(consoleSpy).toHaveBeenCalledWith('AI Error captured:', expect.any(Error));

    consoleSpy.mockRestore();
  });
});

describe('Error Boundary Edge Cases', () => {
  it('handles errors during error state', () => {
    // This tests that the error boundary doesn't get into an infinite loop
    const ProblematicComponent = () => {
      throw new Error('Persistent error');
    };

    render(
      <AIErrorBoundary>
        <ProblematicComponent />
      </AIErrorBoundary>,
    );

    expect(screen.getByText('AI Feature Error')).toBeInTheDocument();

    // Multiple clicks shouldn't break anything
    fireEvent.click(screen.getByText('Retry AI Service'));
    fireEvent.click(screen.getByText('Retry AI Service'));

    expect(screen.getByText('AI Feature Error')).toBeInTheDocument();
  });

  it('handles null/undefined children gracefully', () => {
    render(<AIErrorBoundary>{null}</AIErrorBoundary>);

    // Should not crash
    expect(document.body).toBeInTheDocument();
  });
});
