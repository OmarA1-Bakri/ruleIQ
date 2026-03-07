import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '../../utils';

vi.mock('lucide-react', () => ({
  Loader2: () => React.createElement('svg', { 'data-testid': 'loader-icon' }),
}));
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog';

function renderAlertDialog(open = false) {
  return render(
    <AlertDialog defaultOpen={open}>
      <AlertDialogTrigger data-testid="trigger">Open</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Are you sure?</AlertDialogTitle>
          <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="cancel">Cancel</AlertDialogCancel>
          <AlertDialogAction data-testid="confirm">Confirm</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>,
  );
}

describe('AlertDialog', () => {
  it('renders trigger without crashing', () => {
    renderAlertDialog();
    expect(screen.getByTestId('trigger')).toBeInTheDocument();
  });

  it('does not show content when closed', () => {
    renderAlertDialog(false);
    expect(screen.queryByText('Are you sure?')).not.toBeInTheDocument();
  });

  it('shows content when defaultOpen=true', () => {
    renderAlertDialog(true);
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('shows description when open', () => {
    renderAlertDialog(true);
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument();
  });

  it('opens on trigger click', () => {
    renderAlertDialog(false);
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('renders AlertDialogAction with button classes', () => {
    renderAlertDialog(true);
    const confirm = screen.getByTestId('confirm');
    expect(confirm.tagName).toBe('BUTTON');
  });

  it('renders AlertDialogCancel with button classes', () => {
    renderAlertDialog(true);
    const cancel = screen.getByTestId('cancel');
    expect(cancel.tagName).toBe('BUTTON');
  });

  it('content has role="alertdialog"', () => {
    renderAlertDialog(true);
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });

  it('closes on cancel click', () => {
    renderAlertDialog(true);
    fireEvent.click(screen.getByTestId('cancel'));
    expect(screen.queryByText('Are you sure?')).not.toBeInTheDocument();
  });
});

describe('AlertDialogHeader', () => {
  it('applies flex flex-col classes', () => {
    render(
      <AlertDialog defaultOpen>
        <AlertDialogContent>
          <AlertDialogHeader data-testid="header">
            <AlertDialogTitle>Title</AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>,
    );
    expect(screen.getByTestId('header')).toHaveClass('flex');
    expect(screen.getByTestId('header')).toHaveClass('flex-col');
  });
});

describe('AlertDialogTitle', () => {
  it('applies text-lg font-semibold', () => {
    renderAlertDialog(true);
    const title = screen.getByText('Are you sure?');
    expect(title).toHaveClass('text-lg');
    expect(title).toHaveClass('font-semibold');
  });
});

describe('AlertDialogDescription', () => {
  it('applies text-sm text-muted-foreground', () => {
    renderAlertDialog(true);
    const desc = screen.getByText('This action cannot be undone.');
    expect(desc).toHaveClass('text-sm');
    expect(desc).toHaveClass('text-muted-foreground');
  });
});
