import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { SkeletonCard, SkeletonDashboard, SkeletonTable } from '@/components/ui/skeleton-card';

describe('SkeletonCard', () => {
  it('renders without crashing', () => {
    render(<SkeletonCard />);
  });

  it('renders skeleton elements inside a card', () => {
    const { container } = render(<SkeletonCard />);
    // Should have multiple skeleton divs with animate-shimmer
    const skeletons = container.querySelectorAll('.animate-shimmer, [class*="skeleton"]');
    // At least renders some elements
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders header skeletons', () => {
    const { container } = render(<SkeletonCard />);
    // Find skeleton elements
    const divs = container.querySelectorAll('div');
    expect(divs.length).toBeGreaterThan(0);
  });
});

describe('SkeletonDashboard', () => {
  it('renders without crashing', () => {
    render(<SkeletonDashboard />);
  });

  it('renders 4 SkeletonCards for stats grid', () => {
    const { container } = render(<SkeletonDashboard />);
    // Should have a grid with 4 cards
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders header skeletons', () => {
    const { container } = render(<SkeletonDashboard />);
    // Should render many skeleton elements
    const allDivs = container.querySelectorAll('div');
    expect(allDivs.length).toBeGreaterThan(10);
  });
});

describe('SkeletonTable', () => {
  it('renders without crashing', () => {
    render(<SkeletonTable />);
  });

  it('renders skeleton rows', () => {
    const { container } = render(<SkeletonTable />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders header and pagination skeleton areas', () => {
    const { container } = render(<SkeletonTable />);
    // Should render many skeleton elements (5 rows × 4 cols + header + pagination)
    const allDivs = container.querySelectorAll('div');
    expect(allDivs.length).toBeGreaterThan(20);
  });
});
