import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';

// Fix: the global Proxy-based lucide-react mock in setup.ts doesn't work for ESM named
// imports during module transform. Use an explicit factory mock here instead.
vi.mock('lucide-react', () => ({
  ChevronRight: () => React.createElement('svg', { 'data-testid': 'chevron-right-icon' }),
  MoreHorizontal: () => React.createElement('svg', { 'data-testid': 'more-horizontal-icon' }),
}));

import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbEllipsis,
} from '@/components/ui/breadcrumb';

describe('Breadcrumb', () => {
  it('renders as a nav element', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbPage>Home</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('has aria-label="breadcrumb"', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbPage>Page</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByRole('navigation')).toHaveAttribute('aria-label', 'breadcrumb');
  });

  it('passes through additional props', () => {
    render(
      <Breadcrumb data-testid="breadcrumb-nav">
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbPage>Home</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('breadcrumb-nav')).toBeInTheDocument();
  });
});

describe('BreadcrumbList', () => {
  it('renders as an ordered list', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList data-testid="list">
          <BreadcrumbItem><BreadcrumbPage>Item</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('list').tagName).toBe('OL');
  });

  it('applies flex class from cn() string literal', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList data-testid="list">
          <BreadcrumbItem><BreadcrumbPage>Item</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('list')).toHaveClass('flex');
  });

  it('applies text-sm class', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList data-testid="list">
          <BreadcrumbItem><BreadcrumbPage>Item</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('list')).toHaveClass('text-sm');
  });

  it('merges custom className', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList className="custom-list" data-testid="list">
          <BreadcrumbItem><BreadcrumbPage>Item</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('list')).toHaveClass('custom-list');
  });
});

describe('BreadcrumbItem', () => {
  it('renders as a list item', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem data-testid="item">
            <BreadcrumbPage>Home</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('item').tagName).toBe('LI');
  });

  it('applies inline-flex class', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem data-testid="item">
            <BreadcrumbPage>Home</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('item')).toHaveClass('inline-flex');
  });

  it('renders children', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/home">Home</BreadcrumbLink>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByText('Home')).toBeInTheDocument();
  });
});

describe('BreadcrumbLink', () => {
  it('renders as an anchor element', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/home" data-testid="link">Home</BreadcrumbLink>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    const link = screen.getByTestId('link');
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', '/home');
  });

  it('renders link text', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/docs">Documentation</BreadcrumbLink>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByText('Documentation')).toBeInTheDocument();
  });

  it('merges custom className', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/" className="custom-link" data-testid="link">Home</BreadcrumbLink>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('link')).toHaveClass('custom-link');
  });
});

describe('BreadcrumbPage', () => {
  it('renders the current page text', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage>Current Page</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByText('Current Page')).toBeInTheDocument();
  });

  it('has aria-current="page"', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage data-testid="page">Current</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('page')).toHaveAttribute('aria-current', 'page');
  });

  it('has aria-disabled="true"', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage data-testid="page">Current</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('page')).toHaveAttribute('aria-disabled', 'true');
  });

  it('applies text-foreground class', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage data-testid="page">Current</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByTestId('page')).toHaveClass('text-foreground');
  });
});

describe('BreadcrumbSeparator', () => {
  it('renders with role="presentation"', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">Home</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Current</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByRole('presentation', { hidden: true })).toBeInTheDocument();
  });
});

describe('BreadcrumbEllipsis', () => {
  it('renders an ellipsis indicator', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbEllipsis />
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );
    expect(screen.getByText('More')).toBeInTheDocument();
  });
});

describe('Breadcrumb composition', () => {
  it('renders a full breadcrumb trail', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">Home</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink href="/docs">Docs</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Getting Started</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    );

    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Docs')).toBeInTheDocument();
    expect(screen.getByText('Getting Started')).toBeInTheDocument();
  });
});
