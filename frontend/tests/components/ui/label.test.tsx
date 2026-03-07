import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Label } from '@/components/ui/label';

describe('Label', () => {
  it('renders without crashing', () => {
    render(<Label data-testid="label">My Label</Label>);
    expect(screen.getByTestId('label')).toBeInTheDocument();
  });

  it('renders text content', () => {
    render(<Label>Click me</Label>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('has correct element type (label)', () => {
    render(<Label data-testid="label">Text</Label>);
    expect(screen.getByTestId('label').tagName).toBe('LABEL');
  });

  it('applies text-sm class', () => {
    render(<Label data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('text-sm');
  });

  it('applies font-medium class', () => {
    render(<Label data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('font-medium');
  });

  it('merges custom className', () => {
    render(<Label className="custom-label" data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('custom-label');
  });

  it('associates with input via htmlFor', () => {
    render(
      <div>
        <Label htmlFor="my-input">Name</Label>
        <input id="my-input" />
      </div>,
    );
    const label = screen.getByText('Name');
    expect(label).toHaveAttribute('for', 'my-input');
  });

  it('forwards ref to label element', () => {
    const ref = React.createRef<HTMLLabelElement>();
    render(<Label ref={ref}>Text</Label>);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe('LABEL');
  });

  it('passes through data attributes', () => {
    render(<Label data-testid="label" data-custom="yes">Text</Label>);
    expect(screen.getByTestId('label')).toHaveAttribute('data-custom', 'yes');
  });
});

describe('Label variants', () => {
  it('applies text-foreground class for default variant', () => {
    render(<Label data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('text-foreground');
  });

  it('applies text-error class for error variant', () => {
    render(<Label variant="error" data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('text-error');
  });

  it('applies text-success class for success variant', () => {
    render(<Label variant="success" data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('text-success');
  });

  it('applies text-muted-foreground class for muted variant', () => {
    render(<Label variant="muted" data-testid="label">Text</Label>);
    expect(screen.getByTestId('label')).toHaveClass('text-muted-foreground');
  });
});
