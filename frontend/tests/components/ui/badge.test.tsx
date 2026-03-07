import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Badge, badgeVariants } from '@/components/ui/badge';

// ============================================================================
// badgeVariants unit tests — test the CVA function directly
// ============================================================================

describe('badgeVariants', () => {
  it('default variant includes base classes', () => {
    const cls = badgeVariants({ variant: 'default' });
    expect(cls).toContain('inline-flex');
    expect(cls).toContain('rounded-full');
    expect(cls).toContain('text-xs');
    expect(cls).toContain('font-semibold');
  });

  it('default variant (no arg) matches explicit default', () => {
    expect(badgeVariants({})).toBe(badgeVariants({ variant: 'default' }));
  });

  it('destructive variant includes destructive bg class', () => {
    const cls = badgeVariants({ variant: 'destructive' });
    expect(cls).toContain('bg-destructive');
    expect(cls).toContain('text-destructive-foreground');
  });

  it('secondary variant includes secondary bg class', () => {
    const cls = badgeVariants({ variant: 'secondary' });
    expect(cls).toContain('bg-secondary');
    expect(cls).toContain('text-secondary-foreground');
  });

  it('outline variant includes text-foreground', () => {
    const cls = badgeVariants({ variant: 'outline' });
    expect(cls).toContain('text-foreground');
  });

  it('success variant includes success bg class', () => {
    const cls = badgeVariants({ variant: 'success' });
    expect(cls).toContain('bg-success/20');
  });

  it('approved variant includes success bg class (same as success)', () => {
    const cls = badgeVariants({ variant: 'approved' });
    expect(cls).toContain('bg-success/20');
  });

  it('pending variant includes warning bg class', () => {
    const cls = badgeVariants({ variant: 'pending' });
    expect(cls).toContain('bg-warning/20');
  });

  it('rejected variant includes error bg class', () => {
    const cls = badgeVariants({ variant: 'rejected' });
    expect(cls).toContain('bg-error/20');
  });

  it('tag variant includes oxford-blue class', () => {
    const cls = badgeVariants({ variant: 'tag' });
    expect(cls).toContain('bg-oxford-blue/50');
  });

  it('brand variant behaves like default', () => {
    const cls = badgeVariants({ variant: 'brand' });
    expect(cls).toContain('bg-primary');
    expect(cls).toContain('text-primary-foreground');
  });
});

// ============================================================================
// Badge component rendering tests
// ============================================================================

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Test badge</Badge>);
    expect(screen.getByText('Test badge')).toBeInTheDocument();
  });

  it('renders as a div element', () => {
    render(<Badge data-testid="badge">Badge</Badge>);
    expect(screen.getByTestId('badge').tagName).toBe('DIV');
  });

  it('passes through HTML data attributes', () => {
    render(<Badge data-testid="my-badge">Status</Badge>);
    expect(screen.getByTestId('my-badge')).toBeInTheDocument();
  });

  it('passes through aria attributes', () => {
    render(<Badge aria-label="Status badge">Active</Badge>);
    const badge = screen.getByText('Active');
    expect(badge).toHaveAttribute('aria-label', 'Status badge');
  });

  it('renders with no children', () => {
    const { container } = render(<Badge />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders with complex children', () => {
    render(
      <Badge>
        <span>Active</span>
        <span>Status</span>
      </Badge>,
    );
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('passes through onClick handler', () => {
    const handleClick = vi.fn();
    render(<Badge onClick={handleClick} data-testid="clickable-badge">Click me</Badge>);
    screen.getByTestId('clickable-badge').click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('passes through role attribute', () => {
    render(<Badge role="status" data-testid="status-badge">Active</Badge>);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders different text content for different variants', () => {
    const { rerender } = render(<Badge variant="success">Compliant</Badge>);
    expect(screen.getByText('Compliant')).toBeInTheDocument();

    rerender(<Badge variant="rejected">Failed</Badge>);
    expect(screen.getByText('Failed')).toBeInTheDocument();

    rerender(<Badge variant="pending">Pending Review</Badge>);
    expect(screen.getByText('Pending Review')).toBeInTheDocument();
  });

  it('renders number children', () => {
    render(<Badge>{42}</Badge>);
    expect(screen.getByText('42')).toBeInTheDocument();
  });
});
