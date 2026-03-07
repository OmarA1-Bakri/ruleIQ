import { describe, it, expect } from 'vitest';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card';

import { render, screen } from '../../utils';

describe('Card Components', () => {
  it('renders Card with all subcomponents', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Test Title</CardTitle>
          <CardDescription>Test Description</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Test content</p>
        </CardContent>
        <CardFooter>
          <p>Test footer</p>
        </CardFooter>
      </Card>,
    );

    expect(screen.getByText('Test Title')).toBeInTheDocument();
    expect(screen.getByText('Test Description')).toBeInTheDocument();
    expect(screen.getByText('Test content')).toBeInTheDocument();
    expect(screen.getByText('Test footer')).toBeInTheDocument();
  });

  it('applies correct CSS classes', () => {
    const { container } = render(
      <Card data-testid="card">
        <CardHeader data-testid="header">
          <CardTitle data-testid="title">Title</CardTitle>
          <CardDescription data-testid="description">Description</CardDescription>
        </CardHeader>
        <CardContent data-testid="content">Content</CardContent>
        <CardFooter data-testid="footer">Footer</CardFooter>
      </Card>,
    );

    const card = screen.getByTestId('card');
    const header = screen.getByTestId('header');
    const title = screen.getByTestId('title');
    const description = screen.getByTestId('description');
    const content = screen.getByTestId('content');
    const footer = screen.getByTestId('footer');

    // Card uses rounded-xl (not rounded-lg) and includes transition and overflow utilities.
    // Note: the test environment's clsx mock does not fully expand nested arrays, so only
    // classes defined as direct string arguments to cn() are reliably present here.
    expect(card).toHaveClass('rounded-xl');
    expect(card).toHaveClass('relative');
    expect(card).toHaveClass('overflow-hidden');
    expect(header).toHaveClass('flex', 'flex-col', 'space-y-1.5', 'p-6');
    expect(title).toHaveClass('text-2xl', 'font-semibold');
    expect(description).toHaveClass('text-sm', 'text-muted-foreground');
    expect(content).toHaveClass('p-6', 'pt-0');
    expect(footer).toHaveClass('flex', 'items-center', 'p-6', 'pt-0');
  });

  it('accepts custom className', () => {
    render(
      <Card className="custom-card" data-testid="card">
        <CardHeader className="custom-header" data-testid="header">
          <CardTitle className="custom-title" data-testid="title">
            Title
          </CardTitle>
        </CardHeader>
      </Card>,
    );

    expect(screen.getByTestId('card')).toHaveClass('custom-card');
    expect(screen.getByTestId('header')).toHaveClass('custom-header');
    expect(screen.getByTestId('title')).toHaveClass('custom-title');
  });

  it('renders without optional components', () => {
    render(
      <Card>
        <CardContent>Just content</CardContent>
      </Card>,
    );

    expect(screen.getByText('Just content')).toBeInTheDocument();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
});
