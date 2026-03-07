import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

// ============================================================================
// Alert
// ============================================================================

describe('Alert', () => {
  it('renders with role="alert"', () => {
    render(<Alert>Alert content</Alert>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders children', () => {
    render(<Alert>Test alert message</Alert>);
    expect(screen.getByText('Test alert message')).toBeInTheDocument();
  });

  it('forwards ref to div element', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Alert ref={ref}>Content</Alert>);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe('DIV');
  });

  it('passes through data attributes', () => {
    render(<Alert data-testid="my-alert">Content</Alert>);
    expect(screen.getByTestId('my-alert')).toBeInTheDocument();
  });

  it('passes through aria attributes', () => {
    render(<Alert aria-labelledby="title-id">Content</Alert>);
    expect(screen.getByRole('alert')).toHaveAttribute('aria-labelledby', 'title-id');
  });

  it('renders default and destructive variants without error', () => {
    const { rerender } = render(<Alert variant="default">Default</Alert>);
    expect(screen.getByRole('alert')).toBeInTheDocument();

    rerender(<Alert variant="destructive">Destructive</Alert>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders complex children', () => {
    render(
      <Alert>
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Something went wrong.</AlertDescription>
      </Alert>,
    );
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong.')).toBeInTheDocument();
  });
});

// ============================================================================
// AlertTitle — uses cn() with string literals, classes will be applied
// ============================================================================

describe('AlertTitle', () => {
  it('renders title text', () => {
    render(
      <Alert>
        <AlertTitle>Alert Title</AlertTitle>
      </Alert>,
    );
    expect(screen.getByText('Alert Title')).toBeInTheDocument();
  });

  it('renders as an h5 element', () => {
    const { container } = render(
      <Alert>
        <AlertTitle>Title</AlertTitle>
      </Alert>,
    );
    expect(container.querySelector('h5')).toBeInTheDocument();
  });

  it('applies font-medium class from cn() string literal', () => {
    render(
      <Alert>
        <AlertTitle data-testid="title">Title</AlertTitle>
      </Alert>,
    );
    expect(screen.getByTestId('title')).toHaveClass('font-medium');
  });

  it('applies leading-none class', () => {
    render(
      <Alert>
        <AlertTitle data-testid="title">Title</AlertTitle>
      </Alert>,
    );
    expect(screen.getByTestId('title')).toHaveClass('leading-none');
  });

  it('merges custom className', () => {
    render(
      <Alert>
        <AlertTitle className="custom-title" data-testid="title">Title</AlertTitle>
      </Alert>,
    );
    expect(screen.getByTestId('title')).toHaveClass('custom-title');
  });

  it('forwards ref to h5 element', () => {
    const ref = React.createRef<HTMLParagraphElement>();
    render(
      <Alert>
        <AlertTitle ref={ref}>Title</AlertTitle>
      </Alert>,
    );
    expect(ref.current?.tagName).toBe('H5');
  });
});

// ============================================================================
// AlertDescription — uses cn() with string literals
// ============================================================================

describe('AlertDescription', () => {
  it('renders description text', () => {
    render(
      <Alert>
        <AlertDescription>Alert description text</AlertDescription>
      </Alert>,
    );
    expect(screen.getByText('Alert description text')).toBeInTheDocument();
  });

  it('renders as a div element', () => {
    const { container } = render(
      <Alert>
        <AlertDescription data-testid="desc">Description</AlertDescription>
      </Alert>,
    );
    const desc = screen.getByTestId('desc');
    expect(desc.tagName).toBe('DIV');
  });

  it('applies text-sm class from cn() string literal', () => {
    render(
      <Alert>
        <AlertDescription data-testid="desc">Description</AlertDescription>
      </Alert>,
    );
    expect(screen.getByTestId('desc')).toHaveClass('text-sm');
  });

  it('merges custom className', () => {
    render(
      <Alert>
        <AlertDescription className="custom-desc" data-testid="desc">Description</AlertDescription>
      </Alert>,
    );
    expect(screen.getByTestId('desc')).toHaveClass('custom-desc');
  });

  it('forwards ref to div element', () => {
    const ref = React.createRef<HTMLParagraphElement>();
    render(
      <Alert>
        <AlertDescription ref={ref}>Description</AlertDescription>
      </Alert>,
    );
    expect(ref.current?.tagName).toBe('DIV');
  });
});

// ============================================================================
// Composition
// ============================================================================

describe('Alert composition', () => {
  it('renders full alert with title and description', () => {
    render(
      <Alert>
        <AlertTitle>Important Notice</AlertTitle>
        <AlertDescription>Please read this carefully before proceeding.</AlertDescription>
      </Alert>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Important Notice')).toBeInTheDocument();
    expect(screen.getByText('Please read this carefully before proceeding.')).toBeInTheDocument();
  });

  it('renders multiple alerts independently', () => {
    render(
      <div>
        <Alert data-testid="alert-1">
          <AlertTitle>First Alert</AlertTitle>
        </Alert>
        <Alert data-testid="alert-2">
          <AlertTitle>Second Alert</AlertTitle>
        </Alert>
      </div>,
    );
    expect(screen.getByText('First Alert')).toBeInTheDocument();
    expect(screen.getByText('Second Alert')).toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(2);
  });

  it('handles alert with no title or description (plain content)', () => {
    render(
      <Alert>
        <p>Plain message without sub-components</p>
      </Alert>,
    );
    expect(screen.getByText('Plain message without sub-components')).toBeInTheDocument();
  });
});
