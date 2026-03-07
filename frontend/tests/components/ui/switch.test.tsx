import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';
import { Switch } from '@/components/ui/switch';

describe('Switch', () => {
  it('renders without crashing', () => {
    render(<Switch data-testid="switch" />);
    expect(screen.getByTestId('switch')).toBeInTheDocument();
  });

  it('has role="switch"', () => {
    render(<Switch />);
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('has aria-checked="false" by default', () => {
    render(<Switch />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('has data-state="unchecked" by default', () => {
    render(<Switch data-testid="switch" />);
    expect(screen.getByTestId('switch')).toHaveAttribute('data-state', 'unchecked');
  });

  it('has aria-checked="true" when defaultChecked', () => {
    render(<Switch defaultChecked />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('has data-state="checked" when defaultChecked', () => {
    render(<Switch defaultChecked data-testid="switch" />);
    expect(screen.getByTestId('switch')).toHaveAttribute('data-state', 'checked');
  });

  it('toggles to checked on click', () => {
    render(<Switch />);
    const sw = screen.getByRole('switch');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'true');
  });

  it('is disabled when disabled prop is set', () => {
    render(<Switch disabled />);
    expect(screen.getByRole('switch')).toBeDisabled();
  });

  it('applies inline-flex class', () => {
    render(<Switch data-testid="switch" />);
    expect(screen.getByTestId('switch')).toHaveClass('inline-flex');
  });

  it('applies rounded-full class', () => {
    render(<Switch data-testid="switch" />);
    expect(screen.getByTestId('switch')).toHaveClass('rounded-full');
  });

  it('merges custom className', () => {
    render(<Switch className="custom-switch" data-testid="switch" />);
    expect(screen.getByTestId('switch')).toHaveClass('custom-switch');
  });

  it('calls onCheckedChange when toggled', () => {
    const onCheckedChange = vi.fn();
    render(<Switch onCheckedChange={onCheckedChange} />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it('forwards ref to root element', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Switch ref={ref} />);
    expect(ref.current).not.toBeNull();
  });
});
