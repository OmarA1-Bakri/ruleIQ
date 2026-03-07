import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';

// Fix: the global Proxy-based lucide-react mock in setup.ts doesn't work for ESM named
// imports during module transform. Use an explicit factory mock here instead.
vi.mock('lucide-react', () => ({
  ChevronDown: () => React.createElement('svg', { 'data-testid': 'chevron-down-icon' }),
}));

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';

// Helper to render a standard accordion
function renderAccordion(type: 'single' | 'multiple' = 'single') {
  return render(
    <Accordion type={type} collapsible>
      <AccordionItem value="item-1">
        <AccordionTrigger>Section 1</AccordionTrigger>
        <AccordionContent>Content for section 1</AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-2">
        <AccordionTrigger>Section 2</AccordionTrigger>
        <AccordionContent>Content for section 2</AccordionContent>
      </AccordionItem>
    </Accordion>,
  );
}

describe('Accordion', () => {
  it('renders all accordion items', () => {
    renderAccordion();
    expect(screen.getByText('Section 1')).toBeInTheDocument();
    expect(screen.getByText('Section 2')).toBeInTheDocument();
  });

  it('renders triggers as buttons', () => {
    renderAccordion();
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
  });

  it('triggers have aria-expanded attribute', () => {
    renderAccordion();
    const button = screen.getByText('Section 1').closest('button');
    expect(button).toHaveAttribute('aria-expanded');
  });

  it('triggers are initially collapsed (aria-expanded="false")', () => {
    renderAccordion();
    const button1 = screen.getByText('Section 1').closest('button');
    const button2 = screen.getByText('Section 2').closest('button');
    expect(button1).toHaveAttribute('aria-expanded', 'false');
    expect(button2).toHaveAttribute('aria-expanded', 'false');
  });

  it('clicking trigger expands the item', () => {
    renderAccordion();
    const button = screen.getByText('Section 1').closest('button')!;
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('clicking expanded trigger collapses it (collapsible=true)', () => {
    renderAccordion();
    const button = screen.getByText('Section 1').closest('button')!;
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('only one item expanded at a time (type="single")', () => {
    renderAccordion('single');
    const button1 = screen.getByText('Section 1').closest('button')!;
    const button2 = screen.getByText('Section 2').closest('button')!;

    fireEvent.click(button1);
    expect(button1).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(button2);
    expect(button2).toHaveAttribute('aria-expanded', 'true');
    expect(button1).toHaveAttribute('aria-expanded', 'false');
  });

  it('multiple items can be expanded (type="multiple")', () => {
    render(
      <Accordion type="multiple">
        <AccordionItem value="item-1">
          <AccordionTrigger>Section 1</AccordionTrigger>
          <AccordionContent>Content 1</AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-2">
          <AccordionTrigger>Section 2</AccordionTrigger>
          <AccordionContent>Content 2</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );

    const button1 = screen.getByText('Section 1').closest('button')!;
    const button2 = screen.getByText('Section 2').closest('button')!;

    fireEvent.click(button1);
    fireEvent.click(button2);

    expect(button1).toHaveAttribute('aria-expanded', 'true');
    expect(button2).toHaveAttribute('aria-expanded', 'true');
  });

  it('renders with a default value expanded', () => {
    render(
      <Accordion type="single" defaultValue="item-1" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Section 1</AccordionTrigger>
          <AccordionContent>Content 1</AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-2">
          <AccordionTrigger>Section 2</AccordionTrigger>
          <AccordionContent>Content 2</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    const button1 = screen.getByText('Section 1').closest('button')!;
    expect(button1).toHaveAttribute('aria-expanded', 'true');
  });
});

describe('AccordionItem', () => {
  it('applies border-b class', () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1" data-testid="accordion-item">
          <AccordionTrigger>Title</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    expect(screen.getByTestId('accordion-item')).toHaveClass('border-b');
  });

  it('merges custom className', () => {
    render(
      <Accordion type="single">
        <AccordionItem value="item-1" className="custom-item" data-testid="accordion-item">
          <AccordionTrigger>Title</AccordionTrigger>
          <AccordionContent>Content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );
    expect(screen.getByTestId('accordion-item')).toHaveClass('custom-item');
  });
});

describe('AccordionContent', () => {
  it('shows content when expanded', () => {
    render(
      <Accordion type="single" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Title</AccordionTrigger>
          <AccordionContent>Expandable content</AccordionContent>
        </AccordionItem>
      </Accordion>,
    );

    const button = screen.getByText('Title').closest('button')!;
    fireEvent.click(button);
    expect(screen.getByText('Expandable content')).toBeVisible();
  });
});
