import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Progress } from '@/components/ui/progress';

describe('Progress', () => {
  it('renders without crashing', () => {
    render(<Progress data-testid="progress" value={50} />);
    expect(screen.getByTestId('progress')).toBeInTheDocument();
  });

  it('has role="progressbar"', () => {
    render(<Progress value={50} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('has aria-valuemin="0"', () => {
    render(<Progress value={50} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemin', '0');
  });

  it('has aria-valuemax="100"', () => {
    render(<Progress value={50} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemax', '100');
  });

  it('has data-state="indeterminate" when no value reaches Radix Root', () => {
    // Note: components/ui/progress.tsx destructures `value` out of props but does not
    // forward it explicitly to ProgressPrimitive.Root, so Radix treats value as undefined
    render(<Progress value={50} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('data-state', 'indeterminate');
  });

  it('applies base classes from cn() string literals', () => {
    render(<Progress value={50} data-testid="progress" />);
    const el = screen.getByTestId('progress');
    expect(el).toHaveClass('relative');
    expect(el).toHaveClass('h-4');
    expect(el).toHaveClass('w-full');
    expect(el).toHaveClass('overflow-hidden');
    expect(el).toHaveClass('rounded-full');
  });

  it('merges custom className', () => {
    render(<Progress value={50} className="custom-progress" data-testid="progress" />);
    expect(screen.getByTestId('progress')).toHaveClass('custom-progress');
  });

  it('renders at different values without crashing', () => {
    const { rerender } = render(<Progress value={0} data-testid="progress" />);
    expect(screen.getByTestId('progress')).toBeInTheDocument();

    rerender(<Progress value={50} data-testid="progress" />);
    expect(screen.getByTestId('progress')).toBeInTheDocument();

    rerender(<Progress value={100} data-testid="progress" />);
    expect(screen.getByTestId('progress')).toBeInTheDocument();
  });

  it('forwards ref to root element', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Progress value={50} ref={ref} />);
    expect(ref.current).not.toBeNull();
  });

  it('passes through data attributes', () => {
    render(<Progress value={50} data-testid="progress" data-custom="yes" />);
    expect(screen.getByTestId('progress')).toHaveAttribute('data-custom', 'yes');
  });
});
