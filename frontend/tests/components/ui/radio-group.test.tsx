import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

vi.mock('lucide-react', () => ({
  Circle: () => React.createElement('svg', { 'data-testid': 'circle-icon' }),
}));

function renderGroup(defaultValue?: string) {
  return render(
    <RadioGroup defaultValue={defaultValue} data-testid="group">
      <RadioGroupItem value="a" data-testid="item-a" id="opt-a" />
      <RadioGroupItem value="b" data-testid="item-b" id="opt-b" />
      <RadioGroupItem value="c" data-testid="item-c" id="opt-c" />
    </RadioGroup>,
  );
}

describe('RadioGroup', () => {
  it('renders without crashing', () => {
    renderGroup();
    expect(screen.getByTestId('group')).toBeInTheDocument();
  });

  it('applies grid class', () => {
    renderGroup();
    expect(screen.getByTestId('group')).toHaveClass('grid');
  });

  it('applies gap-2 class', () => {
    renderGroup();
    expect(screen.getByTestId('group')).toHaveClass('gap-2');
  });

  it('merges custom className', () => {
    render(
      <RadioGroup className="custom-group" data-testid="group">
        <RadioGroupItem value="a" />
      </RadioGroup>,
    );
    expect(screen.getByTestId('group')).toHaveClass('custom-group');
  });

  it('renders all radio items', () => {
    renderGroup();
    expect(screen.getAllByRole('radio')).toHaveLength(3);
  });

  it('has aria-checked="false" for all items by default', () => {
    renderGroup();
    screen.getAllByRole('radio').forEach((item) => {
      expect(item).toHaveAttribute('aria-checked', 'false');
    });
  });

  it('sets defaultValue correctly', () => {
    renderGroup('b');
    expect(screen.getByTestId('item-b')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('item-a')).toHaveAttribute('aria-checked', 'false');
  });
});

describe('RadioGroupItem', () => {
  it('has role="radio"', () => {
    renderGroup();
    const items = screen.getAllByRole('radio');
    expect(items[0]).toBeInTheDocument();
  });

  it('applies rounded-full class', () => {
    renderGroup();
    screen.getAllByRole('radio').forEach((item) => {
      expect(item).toHaveClass('rounded-full');
    });
  });

  it('applies h-4 w-4 classes', () => {
    renderGroup();
    screen.getAllByRole('radio').forEach((item) => {
      expect(item).toHaveClass('h-4');
      expect(item).toHaveClass('w-4');
    });
  });

  it('is disabled when disabled prop is set', () => {
    render(
      <RadioGroup>
        <RadioGroupItem value="a" disabled data-testid="item" />
      </RadioGroup>,
    );
    expect(screen.getByTestId('item')).toBeDisabled();
  });

  it('merges custom className', () => {
    render(
      <RadioGroup>
        <RadioGroupItem value="a" className="custom-item" data-testid="item" />
      </RadioGroup>,
    );
    expect(screen.getByTestId('item')).toHaveClass('custom-item');
  });

  it('forwards ref to radio button element', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(
      <RadioGroup>
        <RadioGroupItem value="a" ref={ref} />
      </RadioGroup>,
    );
    expect(ref.current).not.toBeNull();
  });
});
