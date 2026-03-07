import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';
import { Textarea } from '@/components/ui/textarea';

describe('Textarea', () => {
  it('renders a textarea element', () => {
    render(<Textarea data-testid="textarea" />);
    expect(screen.getByTestId('textarea').tagName).toBe('TEXTAREA');
  });

  it('is accessible via role="textbox"', () => {
    render(<Textarea />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('applies base classes from cn() string literals', () => {
    render(<Textarea data-testid="textarea" />);
    const el = screen.getByTestId('textarea');
    expect(el).toHaveClass('flex');
    expect(el).toHaveClass('w-full');
    expect(el).toHaveClass('rounded-md');
    expect(el).toHaveClass('border');
    expect(el).toHaveClass('text-sm');
  });

  it('merges custom className', () => {
    render(<Textarea className="custom-class" data-testid="textarea" />);
    expect(screen.getByTestId('textarea')).toHaveClass('custom-class');
  });

  it('renders placeholder text', () => {
    render(<Textarea placeholder="Enter text here" />);
    expect(screen.getByPlaceholderText('Enter text here')).toBeInTheDocument();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Textarea disabled data-testid="textarea" />);
    expect(screen.getByTestId('textarea')).toBeDisabled();
  });

  it('forwards ref to textarea element', () => {
    const ref = React.createRef<HTMLTextAreaElement>();
    render(<Textarea ref={ref} />);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe('TEXTAREA');
  });

  it('accepts typed input', () => {
    render(<Textarea />);
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello, world!' } });
    expect(textarea.value).toBe('Hello, world!');
  });

  it('calls onChange handler', () => {
    const onChange = vi.fn();
    render(<Textarea onChange={onChange} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('passes through name and id attributes', () => {
    render(<Textarea name="my-textarea" id="my-id" data-testid="textarea" />);
    const el = screen.getByTestId('textarea');
    expect(el).toHaveAttribute('name', 'my-textarea');
    expect(el).toHaveAttribute('id', 'my-id');
  });

  it('passes through rows attribute', () => {
    render(<Textarea rows={5} data-testid="textarea" />);
    expect(screen.getByTestId('textarea')).toHaveAttribute('rows', '5');
  });
});

describe('Textarea variants', () => {
  it('applies error border class when error=true', () => {
    render(<Textarea error data-testid="textarea" />);
    expect(screen.getByTestId('textarea')).toHaveClass('border-error');
  });

  it('applies success border class when success=true', () => {
    render(<Textarea success data-testid="textarea" />);
    expect(screen.getByTestId('textarea')).toHaveClass('border-success');
  });

  it('neither error nor success classes applied by default', () => {
    render(<Textarea data-testid="textarea" />);
    const el = screen.getByTestId('textarea');
    expect(el).not.toHaveClass('border-error');
    expect(el).not.toHaveClass('border-success');
  });

  it('renders multiple textareas independently', () => {
    render(
      <div>
        <Textarea placeholder="First" />
        <Textarea placeholder="Second" />
      </div>,
    );
    expect(screen.getByPlaceholderText('First')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Second')).toBeInTheDocument();
  });
});
