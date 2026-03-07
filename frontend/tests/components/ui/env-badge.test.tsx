import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { EnvBadge } from '@/components/ui/env-badge';

describe('EnvBadge', () => {
  it('renders without crashing', () => {
    // jsdom default hostname is "localhost" → shows DEV badge
    render(<EnvBadge />);
  });

  it('shows DEV label on localhost', () => {
    // jsdom sets window.location.hostname = "localhost" by default
    render(<EnvBadge />);
    expect(screen.getByText('DEV')).toBeInTheDocument();
  });

  it('applies blue color classes for DEV environment', () => {
    render(<EnvBadge />);
    const badge = screen.getByText('DEV').closest('div');
    expect(badge).toHaveClass('text-blue-500');
  });

  it('applies fixed positioning classes', () => {
    render(<EnvBadge />);
    const badge = screen.getByText('DEV').closest('div');
    expect(badge).toHaveClass('fixed');
    expect(badge).toHaveClass('z-50');
  });

  it('applies rounded-md class', () => {
    render(<EnvBadge />);
    const badge = screen.getByText('DEV').closest('div');
    expect(badge).toHaveClass('rounded-md');
  });

  it('applies text-xs font-medium classes', () => {
    render(<EnvBadge />);
    const badge = screen.getByText('DEV').closest('div');
    expect(badge).toHaveClass('text-xs');
    expect(badge).toHaveClass('font-medium');
  });

  it('renders nothing in production environment', () => {
    // Mock production hostname
    const originalHostname = window.location.hostname;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hostname: 'app.ruleiq.com' },
    });

    render(<EnvBadge />);
    expect(screen.queryByText('DEV')).not.toBeInTheDocument();
    expect(screen.queryByText('PROD')).not.toBeInTheDocument();

    // Restore
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hostname: originalHostname },
    });
  });

  it('shows STAGING label on staging hostname', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hostname: 'staging.ruleiq.com' },
    });

    render(<EnvBadge />);
    expect(screen.getByText('STAGING')).toBeInTheDocument();

    // Restore
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hostname: 'localhost' },
    });
  });
});
