import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';

describe('Avatar', () => {
  it('renders without crashing', () => {
    render(
      <Avatar data-testid="avatar">
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('avatar')).toBeInTheDocument();
  });

  it('applies rounded-full class', () => {
    render(
      <Avatar data-testid="avatar">
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('avatar')).toHaveClass('rounded-full');
  });

  it('merges custom className', () => {
    render(
      <Avatar className="h-16 w-16" data-testid="avatar">
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('avatar')).toHaveClass('h-16');
    expect(screen.getByTestId('avatar')).toHaveClass('w-16');
  });

  it('forwards ref to the root element', () => {
    const ref = React.createRef<HTMLSpanElement>();
    render(
      <Avatar ref={ref}>
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(ref.current).not.toBeNull();
  });
});

describe('AvatarFallback', () => {
  it('renders fallback text', () => {
    render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('renders with initials', () => {
    render(
      <Avatar>
        <AvatarFallback>OA</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText('OA')).toBeInTheDocument();
  });

  it('merges custom className', () => {
    render(
      <Avatar>
        <AvatarFallback className="bg-blue-500" data-testid="fallback">AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('fallback')).toHaveClass('bg-blue-500');
  });

  it('applies flex class from cn() string literal', () => {
    render(
      <Avatar>
        <AvatarFallback data-testid="fallback">AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('fallback')).toHaveClass('flex');
  });

  it('applies rounded-full class', () => {
    render(
      <Avatar>
        <AvatarFallback data-testid="fallback">AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId('fallback')).toHaveClass('rounded-full');
  });
});

describe('Avatar composition', () => {
  it('renders avatar with fallback when no image', () => {
    render(
      <Avatar>
        <AvatarImage src="" alt="User" />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    // Fallback text should be present in DOM
    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('renders multiple avatars independently', () => {
    render(
      <div>
        <Avatar data-testid="avatar-1">
          <AvatarFallback>AA</AvatarFallback>
        </Avatar>
        <Avatar data-testid="avatar-2">
          <AvatarFallback>BB</AvatarFallback>
        </Avatar>
      </div>,
    );
    expect(screen.getByText('AA')).toBeInTheDocument();
    expect(screen.getByText('BB')).toBeInTheDocument();
    expect(screen.getByTestId('avatar-1')).toBeInTheDocument();
    expect(screen.getByTestId('avatar-2')).toBeInTheDocument();
  });
});
