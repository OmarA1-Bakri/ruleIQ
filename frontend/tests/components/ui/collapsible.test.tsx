import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';

function renderCollapsible(defaultOpen = false) {
  return render(
    <Collapsible defaultOpen={defaultOpen} data-testid="collapsible">
      <CollapsibleTrigger data-testid="trigger">Toggle</CollapsibleTrigger>
      <CollapsibleContent data-testid="content">Hidden content</CollapsibleContent>
    </Collapsible>,
  );
}

describe('Collapsible', () => {
  it('renders without crashing', () => {
    renderCollapsible();
    expect(screen.getByTestId('collapsible')).toBeInTheDocument();
  });

  it('renders the trigger', () => {
    renderCollapsible();
    expect(screen.getByTestId('trigger')).toBeInTheDocument();
    expect(screen.getByText('Toggle')).toBeInTheDocument();
  });

  it('hides content by default when closed', () => {
    renderCollapsible(false);
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument();
  });

  it('shows content when defaultOpen=true', () => {
    renderCollapsible(true);
    expect(screen.getByText('Hidden content')).toBeInTheDocument();
  });

  it('opens content on trigger click', () => {
    renderCollapsible(false);
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Hidden content')).toBeInTheDocument();
  });

  it('closes content on second trigger click', () => {
    renderCollapsible(false);
    const trigger = screen.getByTestId('trigger');
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument();
  });

  it('trigger has aria-controls pointing to content', () => {
    renderCollapsible(true);
    const trigger = screen.getByTestId('trigger');
    const controls = trigger.getAttribute('aria-controls');
    expect(controls).toBeTruthy();
  });

  it('trigger has aria-expanded="false" when closed', () => {
    renderCollapsible(false);
    expect(screen.getByTestId('trigger')).toHaveAttribute('aria-expanded', 'false');
  });

  it('trigger has aria-expanded="true" when open', () => {
    renderCollapsible(true);
    expect(screen.getByTestId('trigger')).toHaveAttribute('aria-expanded', 'true');
  });

  it('renders custom content inside CollapsibleContent', () => {
    render(
      <Collapsible defaultOpen>
        <CollapsibleTrigger>Open</CollapsibleTrigger>
        <CollapsibleContent>
          <ul>
            <li data-testid="item-1">Item 1</li>
            <li data-testid="item-2">Item 2</li>
          </ul>
        </CollapsibleContent>
      </Collapsible>,
    );
    expect(screen.getByTestId('item-1')).toBeInTheDocument();
    expect(screen.getByTestId('item-2')).toBeInTheDocument();
  });
});
