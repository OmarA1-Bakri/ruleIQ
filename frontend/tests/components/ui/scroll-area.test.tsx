import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

describe('ScrollArea', () => {
  it('renders without crashing', () => {
    render(<ScrollArea data-testid="scroll-area">Content</ScrollArea>);
    expect(screen.getByTestId('scroll-area')).toBeInTheDocument();
  });

  it('renders its children', () => {
    render(<ScrollArea>Scrollable content</ScrollArea>);
    expect(screen.getByText('Scrollable content')).toBeInTheDocument();
  });

  it('applies overflow-hidden class', () => {
    render(<ScrollArea data-testid="scroll-area">Content</ScrollArea>);
    expect(screen.getByTestId('scroll-area')).toHaveClass('overflow-hidden');
  });

  it('applies relative class', () => {
    render(<ScrollArea data-testid="scroll-area">Content</ScrollArea>);
    expect(screen.getByTestId('scroll-area')).toHaveClass('relative');
  });

  it('merges custom className', () => {
    render(
      <ScrollArea className="custom-scroll" data-testid="scroll-area">
        Content
      </ScrollArea>,
    );
    expect(screen.getByTestId('scroll-area')).toHaveClass('custom-scroll');
  });

  it('renders multiple children', () => {
    render(
      <ScrollArea>
        <div data-testid="child-1">Item 1</div>
        <div data-testid="child-2">Item 2</div>
      </ScrollArea>,
    );
    expect(screen.getByTestId('child-1')).toBeInTheDocument();
    expect(screen.getByTestId('child-2')).toBeInTheDocument();
  });

  it('forwards ref to root element', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<ScrollArea ref={ref}>Content</ScrollArea>);
    expect(ref.current).not.toBeNull();
  });

  it('passes through data attributes', () => {
    render(
      <ScrollArea data-testid="scroll-area" data-custom="yes">
        Content
      </ScrollArea>,
    );
    expect(screen.getByTestId('scroll-area')).toHaveAttribute('data-custom', 'yes');
  });
});

describe('ScrollBar', () => {
  it('renders without crashing inside ScrollArea', () => {
    render(
      <ScrollArea>
        <ScrollBar data-testid="scrollbar" />
        Content
      </ScrollArea>,
    );
    // ScrollBar may not be visible in jsdom but should not throw
  });
});
