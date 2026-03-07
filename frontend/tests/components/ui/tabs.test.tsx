import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

function renderTabs(defaultValue = 'tab1') {
  return render(
    <Tabs defaultValue={defaultValue}>
      <TabsList>
        <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        <TabsTrigger value="tab3">Tab 3</TabsTrigger>
      </TabsList>
      <TabsContent value="tab1">Content for tab 1</TabsContent>
      <TabsContent value="tab2">Content for tab 2</TabsContent>
      <TabsContent value="tab3">Content for tab 3</TabsContent>
    </Tabs>,
  );
}

describe('Tabs', () => {
  it('renders all tab triggers', () => {
    renderTabs();
    expect(screen.getByText('Tab 1')).toBeInTheDocument();
    expect(screen.getByText('Tab 2')).toBeInTheDocument();
    expect(screen.getByText('Tab 3')).toBeInTheDocument();
  });

  it('renders the default active tab content', () => {
    renderTabs('tab1');
    expect(screen.getByText('Content for tab 1')).toBeInTheDocument();
  });

  it('default tab trigger has data-state="active"', () => {
    renderTabs('tab1');
    const tab1 = screen.getByText('Tab 1').closest('button');
    expect(tab1).toHaveAttribute('data-state', 'active');
  });

  it('non-default tab triggers have data-state="inactive"', () => {
    renderTabs('tab1');
    expect(screen.getByText('Tab 2').closest('button')).toHaveAttribute('data-state', 'inactive');
    expect(screen.getByText('Tab 3').closest('button')).toHaveAttribute('data-state', 'inactive');
  });

  it('tab triggers have role="tab"', () => {
    renderTabs();
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(3);
  });

  it('active trigger has aria-selected="true"', () => {
    renderTabs('tab2');
    const tab2 = screen.getByText('Tab 2').closest('[role="tab"]');
    expect(tab2).toHaveAttribute('aria-selected', 'true');
  });

  it('inactive triggers have aria-selected="false"', () => {
    renderTabs('tab1');
    const tab2 = screen.getByText('Tab 2').closest('[role="tab"]');
    expect(tab2).toHaveAttribute('aria-selected', 'false');
  });
});

describe('TabsList', () => {
  it('has role="tablist"', () => {
    renderTabs();
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('applies inline-flex class', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList data-testid="list">
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId('list')).toHaveClass('inline-flex');
  });

  it('applies rounded-md class', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList data-testid="list">
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId('list')).toHaveClass('rounded-md');
  });

  it('merges custom className', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList className="custom-list" data-testid="list">
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId('list')).toHaveClass('custom-list');
  });
});

describe('TabsTrigger', () => {
  it('renders as a button', () => {
    renderTabs();
    expect(screen.getByText('Tab 1').closest('button')).toBeInTheDocument();
  });

  it('is disabled when disabled prop is set', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">A</TabsTrigger>
          <TabsTrigger value="b" disabled>
            B
          </TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
        <TabsContent value="b">Content B</TabsContent>
      </Tabs>,
    );
    expect(screen.getByText('B').closest('button')).toBeDisabled();
  });

  it('merges custom className', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a" className="custom-trigger" data-testid="trigger">
            A
          </TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId('trigger')).toHaveClass('custom-trigger');
  });
});

describe('TabsContent', () => {
  it('has role="tabpanel"', () => {
    renderTabs();
    expect(screen.getByRole('tabpanel')).toBeInTheDocument();
  });

  it('merges custom className', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
        <TabsContent value="a" className="custom-content" data-testid="content">
          Content A
        </TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId('content')).toHaveClass('custom-content');
  });
});
