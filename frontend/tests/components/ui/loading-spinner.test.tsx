import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

describe('LoadingSpinner', () => {
  it('renders without crashing', () => {
    render(<LoadingSpinner data-testid="spinner" />);
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('applies flex and items-center classes to wrapper', () => {
    render(<LoadingSpinner data-testid="spinner" />);
    const el = screen.getByTestId('spinner');
    expect(el).toHaveClass('flex');
    expect(el).toHaveClass('items-center');
    expect(el).toHaveClass('justify-center');
  });

  it('renders inner spin element', () => {
    render(<LoadingSpinner data-testid="spinner" />);
    const spinner = screen.getByTestId('spinner');
    const inner = spinner.firstChild as HTMLElement;
    expect(inner).toHaveClass('animate-spin');
    expect(inner).toHaveClass('rounded-full');
  });

  it('applies md size classes by default (w-8 h-8)', () => {
    render(<LoadingSpinner data-testid="spinner" />);
    const spinner = screen.getByTestId('spinner');
    const inner = spinner.firstChild as HTMLElement;
    expect(inner).toHaveClass('w-8');
    expect(inner).toHaveClass('h-8');
  });

  it('applies sm size classes (w-4 h-4)', () => {
    render(<LoadingSpinner size="sm" data-testid="spinner" />);
    const spinner = screen.getByTestId('spinner');
    const inner = spinner.firstChild as HTMLElement;
    expect(inner).toHaveClass('w-4');
    expect(inner).toHaveClass('h-4');
  });

  it('applies lg size classes (w-12 h-12)', () => {
    render(<LoadingSpinner size="lg" data-testid="spinner" />);
    const spinner = screen.getByTestId('spinner');
    const inner = spinner.firstChild as HTMLElement;
    expect(inner).toHaveClass('w-12');
    expect(inner).toHaveClass('h-12');
  });

  it('merges custom className on wrapper', () => {
    render(<LoadingSpinner className="custom-class" data-testid="spinner" />);
    expect(screen.getByTestId('spinner')).toHaveClass('custom-class');
  });

  it('passes through data attributes to wrapper', () => {
    render(<LoadingSpinner data-testid="spinner" data-custom="val" />);
    expect(screen.getByTestId('spinner')).toHaveAttribute('data-custom', 'val');
  });

  it('renders multiple spinners independently', () => {
    render(
      <div>
        <LoadingSpinner size="sm" data-testid="sm-spinner" />
        <LoadingSpinner size="lg" data-testid="lg-spinner" />
      </div>,
    );
    const sm = screen.getByTestId('sm-spinner').firstChild as HTMLElement;
    const lg = screen.getByTestId('lg-spinner').firstChild as HTMLElement;
    expect(sm).toHaveClass('w-4');
    expect(lg).toHaveClass('w-12');
  });
});
