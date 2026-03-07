import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { MetricDisplay } from '@/components/ui/metric-display';

vi.mock('lucide-react', () => ({
  TrendingUp: () => React.createElement('svg', { 'data-testid': 'trending-up' }),
  TrendingDown: () => React.createElement('svg', { 'data-testid': 'trending-down' }),
}));

describe('MetricDisplay', () => {
  it('renders label text', () => {
    render(<MetricDisplay label="Total Users" value={1234} />);
    expect(screen.getByText('Total Users')).toBeInTheDocument();
  });

  it('renders string value', () => {
    render(<MetricDisplay label="Status" value="Active" />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders numeric value', () => {
    render(<MetricDisplay label="Count" value={42} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders without change indicator when change is not provided', () => {
    render(<MetricDisplay label="Score" value={90} />);
    expect(screen.queryByTestId('trending-up')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trending-down')).not.toBeInTheDocument();
  });

  it('renders TrendingUp icon when change.isPositive=true', () => {
    render(
      <MetricDisplay
        label="Revenue"
        value="$10k"
        change={{ value: 12, isPositive: true }}
      />,
    );
    expect(screen.getByTestId('trending-up')).toBeInTheDocument();
  });

  it('renders TrendingDown icon when change.isPositive=false', () => {
    render(
      <MetricDisplay
        label="Errors"
        value={5}
        change={{ value: 3, isPositive: false }}
      />,
    );
    expect(screen.getByTestId('trending-down')).toBeInTheDocument();
  });

  it('renders positive change value with + prefix', () => {
    render(
      <MetricDisplay
        label="Growth"
        value={100}
        change={{ value: 8, isPositive: true }}
      />,
    );
    expect(screen.getByText(/\+8%/)).toBeInTheDocument();
  });

  it('renders negative change value without + prefix', () => {
    render(
      <MetricDisplay
        label="Loss"
        value={50}
        change={{ value: 5, isPositive: false }}
      />,
    );
    expect(screen.getByText(/5%/)).toBeInTheDocument();
    expect(screen.queryByText(/\+5%/)).not.toBeInTheDocument();
  });

  it('renders period text when provided', () => {
    render(
      <MetricDisplay
        label="Revenue"
        value="$10k"
        change={{ value: 10, isPositive: true, period: 'vs last month' }}
      />,
    );
    expect(screen.getByText('vs last month')).toBeInTheDocument();
  });

  it('renders custom icon when provided', () => {
    render(
      <MetricDisplay
        label="Items"
        value={7}
        icon={<svg data-testid="custom-icon" />}
      />,
    );
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(
      <MetricDisplay
        label="Test"
        value={1}
        className="custom-metric"
        data-testid="metric"
      />,
    );
    // className is applied to the root div via the template literal
    const root = screen.getByText('Test').closest('div')?.parentElement;
    expect(root?.className).toContain('custom-metric');
  });

  it('applies text-success class for positive change', () => {
    render(
      <MetricDisplay
        label="Up"
        value={10}
        change={{ value: 5, isPositive: true }}
      />,
    );
    const changeEl = screen.getByText(/\+5%/).closest('div');
    expect(changeEl).toHaveClass('text-success');
  });

  it('applies text-error class for negative change', () => {
    render(
      <MetricDisplay
        label="Down"
        value={10}
        change={{ value: 5, isPositive: false }}
      />,
    );
    const changeEl = screen.getByText(/5%/).closest('div');
    expect(changeEl).toHaveClass('text-error');
  });
});
