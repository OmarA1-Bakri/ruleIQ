import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';
import { Toggle } from '@/components/ui/toggle';

describe('Toggle', () => {
  it('renders without crashing', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toBeInTheDocument();
  });

  it('renders as a button', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle').tagName).toBe('BUTTON');
  });

  it('has data-state="off" by default', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveAttribute('data-state', 'off');
  });

  it('has data-state="on" when defaultPressed', () => {
    render(<Toggle defaultPressed data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveAttribute('data-state', 'on');
  });

  it('toggles to on state on click', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    fireEvent.click(screen.getByTestId('toggle'));
    expect(screen.getByTestId('toggle')).toHaveAttribute('data-state', 'on');
  });

  it('toggles back to off on second click', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    const btn = screen.getByTestId('toggle');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('data-state', 'off');
  });

  it('is disabled when disabled prop is set', () => {
    render(<Toggle disabled data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toBeDisabled();
  });

  it('applies inline-flex class', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveClass('inline-flex');
  });

  it('applies rounded-md class', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveClass('rounded-md');
  });

  it('applies text-sm font-medium classes', () => {
    render(<Toggle data-testid="toggle">B</Toggle>);
    const el = screen.getByTestId('toggle');
    expect(el).toHaveClass('text-sm');
    expect(el).toHaveClass('font-medium');
  });

  it('merges custom className', () => {
    render(<Toggle className="custom-toggle" data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveClass('custom-toggle');
  });

  it('calls onPressedChange when clicked', () => {
    const onPressedChange = vi.fn();
    render(<Toggle onPressedChange={onPressedChange} data-testid="toggle">B</Toggle>);
    fireEvent.click(screen.getByTestId('toggle'));
    expect(onPressedChange).toHaveBeenCalledWith(true);
  });

  it('applies outline variant border class', () => {
    render(<Toggle variant="outline" data-testid="toggle">B</Toggle>);
    expect(screen.getByTestId('toggle')).toHaveClass('border');
  });

  it('forwards ref to button element', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Toggle ref={ref}>B</Toggle>);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe('BUTTON');
  });
});
