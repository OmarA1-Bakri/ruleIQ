import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';

// lucide-react ESM named import fix (same as breadcrumb/accordion)
vi.mock('lucide-react', () => ({
  Check: () => React.createElement('svg', { 'data-testid': 'check-icon' }),
}));

import { Checkbox } from '@/components/ui/checkbox';

describe('Checkbox', () => {
  it('renders without crashing', () => {
    render(<Checkbox data-testid="checkbox" />);
    expect(screen.getByTestId('checkbox')).toBeInTheDocument();
  });

  it('renders as a button element (Radix checkbox)', () => {
    render(<Checkbox data-testid="checkbox" />);
    expect(screen.getByTestId('checkbox').tagName).toBe('BUTTON');
  });

  it('has role="checkbox"', () => {
    render(<Checkbox />);
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
  });

  it('is unchecked by default', () => {
    render(<Checkbox />);
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toHaveAttribute('aria-checked', 'false');
  });

  it('can be checked by clicking', () => {
    render(<Checkbox />);
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(checkbox).toHaveAttribute('aria-checked', 'true');
  });

  it('renders in checked state when defaultChecked=true', () => {
    render(<Checkbox defaultChecked />);
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'true');
  });

  it('is disabled when disabled prop is set', () => {
    render(<Checkbox disabled />);
    expect(screen.getByRole('checkbox')).toBeDisabled();
  });

  it('merges custom className', () => {
    render(<Checkbox className="custom-checkbox" data-testid="checkbox" />);
    expect(screen.getByTestId('checkbox')).toHaveClass('custom-checkbox');
  });

  it('applies base Radix classes from cn() string literal', () => {
    render(<Checkbox data-testid="checkbox" />);
    const el = screen.getByTestId('checkbox');
    // shrink-0, rounded-sm, border are applied via cn() string literals
    expect(el).toHaveClass('shrink-0');
    expect(el).toHaveClass('rounded-sm');
    expect(el).toHaveClass('border');
  });

  it('passes through data attributes', () => {
    render(<Checkbox data-testid="my-checkbox" data-custom="value" />);
    expect(screen.getByTestId('my-checkbox')).toHaveAttribute('data-custom', 'value');
  });

  it('forwards ref to underlying element', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Checkbox ref={ref} />);
    expect(ref.current).not.toBeNull();
  });

  it('calls onCheckedChange when clicked', () => {
    const onCheckedChange = vi.fn();
    render(<Checkbox onCheckedChange={onCheckedChange} />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });
});

describe('Checkbox variants', () => {
  it('applies error classes when error=true', () => {
    render(<Checkbox error data-testid="checkbox" />);
    expect(screen.getByTestId('checkbox')).toHaveClass('border-error');
  });

  it('applies success classes when success=true', () => {
    render(<Checkbox success data-testid="checkbox" />);
    expect(screen.getByTestId('checkbox')).toHaveClass('border-success');
  });

  it('renders multiple checkboxes independently', () => {
    render(
      <div>
        <Checkbox data-testid="cb-1" />
        <Checkbox data-testid="cb-2" defaultChecked />
      </div>,
    );
    expect(screen.getByTestId('cb-1')).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByTestId('cb-2')).toHaveAttribute('aria-checked', 'true');
  });
});
