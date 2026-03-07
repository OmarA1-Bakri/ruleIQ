import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from '@/components/ui/pagination';

vi.mock('lucide-react', () => ({
  ChevronLeft: () => React.createElement('svg', { 'data-testid': 'chevron-left' }),
  ChevronRight: () => React.createElement('svg', { 'data-testid': 'chevron-right' }),
  MoreHorizontal: () => React.createElement('svg', { 'data-testid': 'more-horizontal' }),
}));

describe('Pagination', () => {
  it('renders a nav element', () => {
    render(<Pagination data-testid="pagination" />);
    expect(screen.getByTestId('pagination').tagName).toBe('NAV');
  });

  it('has role="navigation"', () => {
    render(<Pagination />);
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('has aria-label="pagination"', () => {
    render(<Pagination />);
    expect(screen.getByRole('navigation')).toHaveAttribute('aria-label', 'pagination');
  });

  it('applies justify-center class', () => {
    render(<Pagination data-testid="pagination" />);
    expect(screen.getByTestId('pagination')).toHaveClass('justify-center');
  });

  it('merges custom className', () => {
    render(<Pagination className="custom-pagination" data-testid="pagination" />);
    expect(screen.getByTestId('pagination')).toHaveClass('custom-pagination');
  });
});

describe('PaginationContent', () => {
  it('renders a ul element', () => {
    render(
      <Pagination>
        <PaginationContent data-testid="content" />
      </Pagination>,
    );
    expect(screen.getByTestId('content').tagName).toBe('UL');
  });

  it('applies flex class', () => {
    render(
      <Pagination>
        <PaginationContent data-testid="content" />
      </Pagination>,
    );
    expect(screen.getByTestId('content')).toHaveClass('flex');
  });
});

describe('PaginationItem', () => {
  it('renders a li element', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem data-testid="item" />
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('item').tagName).toBe('LI');
  });
});

describe('PaginationLink', () => {
  it('renders an anchor element', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationLink href="#" data-testid="link">
              1
            </PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('link').tagName).toBe('A');
  });

  it('sets aria-current="page" when isActive', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationLink href="#" isActive data-testid="link">
              1
            </PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('link')).toHaveAttribute('aria-current', 'page');
  });

  it('does not set aria-current when not active', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationLink href="#" data-testid="link">
              2
            </PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('link')).not.toHaveAttribute('aria-current');
  });
});

describe('PaginationPrevious', () => {
  it('renders "Previous" text', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByText('Previous')).toBeInTheDocument();
  });

  it('has aria-label="Go to previous page"', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByLabelText('Go to previous page')).toBeInTheDocument();
  });

  it('renders ChevronLeft icon', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('chevron-left')).toBeInTheDocument();
  });
});

describe('PaginationNext', () => {
  it('renders "Next" text', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationNext href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByText('Next')).toBeInTheDocument();
  });

  it('has aria-label="Go to next page"', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationNext href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByLabelText('Go to next page')).toBeInTheDocument();
  });
});

describe('PaginationEllipsis', () => {
  it('renders "More pages" sr-only text', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByText('More pages')).toBeInTheDocument();
  });

  it('renders MoreHorizontal icon', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByTestId('more-horizontal')).toBeInTheDocument();
  });
});
