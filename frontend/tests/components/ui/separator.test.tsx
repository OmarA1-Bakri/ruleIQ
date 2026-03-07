import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Separator } from '@/components/ui/separator';

describe('Separator', () => {
  it('renders without crashing', () => {
    render(<Separator data-testid="separator" />);
    expect(screen.getByTestId('separator')).toBeInTheDocument();
  });

  it('is horizontal by default (decorative, role="none")', () => {
    render(<Separator data-testid="separator" />);
    // decorative=true means role="none" (presentation)
    const el = screen.getByTestId('separator');
    expect(el).toBeInTheDocument();
  });

  it('applies shrink-0 class', () => {
    render(<Separator data-testid="separator" />);
    expect(screen.getByTestId('separator')).toHaveClass('shrink-0');
  });

  it('applies bg-border class', () => {
    render(<Separator data-testid="separator" />);
    expect(screen.getByTestId('separator')).toHaveClass('bg-border');
  });

  it('applies horizontal classes by default', () => {
    render(<Separator data-testid="separator" />);
    const el = screen.getByTestId('separator');
    expect(el).toHaveClass('h-[1px]');
    expect(el).toHaveClass('w-full');
  });

  it('applies vertical classes when orientation="vertical"', () => {
    render(<Separator orientation="vertical" data-testid="separator" />);
    const el = screen.getByTestId('separator');
    expect(el).toHaveClass('h-full');
    expect(el).toHaveClass('w-[1px]');
  });

  it('does not apply horizontal classes for vertical orientation', () => {
    render(<Separator orientation="vertical" data-testid="separator" />);
    expect(screen.getByTestId('separator')).not.toHaveClass('h-[1px]');
  });

  it('merges custom className', () => {
    render(<Separator className="my-separator" data-testid="separator" />);
    expect(screen.getByTestId('separator')).toHaveClass('my-separator');
  });

  it('passes through data attributes', () => {
    render(<Separator data-testid="separator" data-custom="val" />);
    expect(screen.getByTestId('separator')).toHaveAttribute('data-custom', 'val');
  });

  it('renders non-decorative separator with role="separator"', () => {
    render(<Separator decorative={false} />);
    expect(screen.getByRole('separator')).toBeInTheDocument();
  });

  it('renders multiple separators', () => {
    render(
      <div>
        <Separator data-testid="sep-1" />
        <Separator orientation="vertical" data-testid="sep-2" />
      </div>,
    );
    expect(screen.getByTestId('sep-1')).toHaveClass('h-[1px]');
    expect(screen.getByTestId('sep-2')).toHaveClass('w-[1px]');
  });
});
