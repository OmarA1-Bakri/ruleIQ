import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Skeleton } from '@/components/ui/skeleton';

describe('Skeleton', () => {
  it('renders a div element', () => {
    render(<Skeleton data-testid="skeleton" />);
    expect(screen.getByTestId('skeleton').tagName).toBe('DIV');
  });

  it('applies animate-shimmer class', () => {
    render(<Skeleton data-testid="skeleton" />);
    expect(screen.getByTestId('skeleton')).toHaveClass('animate-shimmer');
  });

  it('applies rounded-lg class', () => {
    render(<Skeleton data-testid="skeleton" />);
    expect(screen.getByTestId('skeleton')).toHaveClass('rounded-lg');
  });

  it('merges custom className', () => {
    render(<Skeleton className="h-4 w-full" data-testid="skeleton" />);
    const el = screen.getByTestId('skeleton');
    expect(el).toHaveClass('h-4');
    expect(el).toHaveClass('w-full');
  });

  it('passes through data attributes', () => {
    render(<Skeleton data-testid="skeleton" data-custom="value" />);
    expect(screen.getByTestId('skeleton')).toHaveAttribute('data-custom', 'value');
  });

  it('passes through aria attributes', () => {
    render(<Skeleton data-testid="skeleton" aria-label="Loading..." />);
    expect(screen.getByTestId('skeleton')).toHaveAttribute('aria-label', 'Loading...');
  });

  it('renders multiple skeletons independently', () => {
    render(
      <div>
        <Skeleton data-testid="sk-1" className="h-4" />
        <Skeleton data-testid="sk-2" className="h-8" />
        <Skeleton data-testid="sk-3" className="h-12" />
      </div>,
    );
    expect(screen.getByTestId('sk-1')).toHaveClass('h-4');
    expect(screen.getByTestId('sk-2')).toHaveClass('h-8');
    expect(screen.getByTestId('sk-3')).toHaveClass('h-12');
  });

  it('renders without className prop', () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
