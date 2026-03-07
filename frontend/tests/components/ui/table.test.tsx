import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '../../utils';
import {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
} from '@/components/ui/table';

function renderFullTable() {
  return render(
    <Table data-testid="table">
      <TableCaption>Caption text</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>Row 1 A</TableCell>
          <TableCell>Row 1 B</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Row 2 A</TableCell>
          <TableCell>Row 2 B</TableCell>
        </TableRow>
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell>Footer A</TableCell>
          <TableCell>Footer B</TableCell>
        </TableRow>
      </TableFooter>
    </Table>,
  );
}

describe('Table', () => {
  it('renders a table element', () => {
    render(<Table data-testid="table" />);
    expect(screen.getByTestId('table').tagName).toBe('TABLE');
  });

  it('wraps in overflow div when responsive=true (default)', () => {
    render(<Table data-testid="table" />);
    const table = screen.getByTestId('table');
    expect(table.parentElement).toHaveClass('overflow-x-auto');
  });

  it('does not wrap in overflow div when responsive=false', () => {
    render(<Table responsive={false} data-testid="table" />);
    const table = screen.getByTestId('table');
    // parent is the render container, not the overflow div
    expect(table.parentElement).not.toHaveClass('overflow-x-auto');
  });

  it('applies w-full class', () => {
    render(<Table data-testid="table" />);
    expect(screen.getByTestId('table')).toHaveClass('w-full');
  });

  it('applies text-sm class', () => {
    render(<Table data-testid="table" />);
    expect(screen.getByTestId('table')).toHaveClass('text-sm');
  });

  it('merges custom className', () => {
    render(<Table className="custom-table" data-testid="table" />);
    expect(screen.getByTestId('table')).toHaveClass('custom-table');
  });

  it('forwards ref to table element', () => {
    const ref = React.createRef<HTMLTableElement>();
    render(<Table ref={ref} />);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe('TABLE');
  });

  it('renders full table with all sub-components', () => {
    renderFullTable();
    expect(screen.getByText('Caption text')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Row 1 A')).toBeInTheDocument();
    expect(screen.getByText('Footer A')).toBeInTheDocument();
  });
});

describe('TableHeader', () => {
  it('renders a thead element', () => {
    render(
      <table>
        <TableHeader data-testid="thead" />
      </table>,
    );
    expect(screen.getByTestId('thead').tagName).toBe('THEAD');
  });

  it('merges custom className', () => {
    render(
      <table>
        <TableHeader className="custom-thead" data-testid="thead" />
      </table>,
    );
    expect(screen.getByTestId('thead')).toHaveClass('custom-thead');
  });
});

describe('TableBody', () => {
  it('renders a tbody element', () => {
    render(
      <table>
        <TableBody data-testid="tbody" />
      </table>,
    );
    expect(screen.getByTestId('tbody').tagName).toBe('TBODY');
  });
});

describe('TableRow', () => {
  it('renders a tr element', () => {
    render(
      <table>
        <tbody>
          <TableRow data-testid="tr" />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId('tr').tagName).toBe('TR');
  });

  it('applies border-b class', () => {
    render(
      <table>
        <tbody>
          <TableRow data-testid="tr" />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId('tr')).toHaveClass('border-b');
  });

  it('merges custom className', () => {
    render(
      <table>
        <tbody>
          <TableRow className="custom-row" data-testid="tr" />
        </tbody>
      </table>,
    );
    expect(screen.getByTestId('tr')).toHaveClass('custom-row');
  });
});

describe('TableHead', () => {
  it('renders a th element', () => {
    render(
      <table>
        <thead>
          <tr>
            <TableHead data-testid="th">Heading</TableHead>
          </tr>
        </thead>
      </table>,
    );
    expect(screen.getByTestId('th').tagName).toBe('TH');
  });

  it('applies h-12 class', () => {
    render(
      <table>
        <thead>
          <tr>
            <TableHead data-testid="th">Heading</TableHead>
          </tr>
        </thead>
      </table>,
    );
    expect(screen.getByTestId('th')).toHaveClass('h-12');
  });
});

describe('TableCell', () => {
  it('renders a td element', () => {
    render(
      <table>
        <tbody>
          <tr>
            <TableCell data-testid="td">Cell</TableCell>
          </tr>
        </tbody>
      </table>,
    );
    expect(screen.getByTestId('td').tagName).toBe('TD');
  });

  it('applies p-4 class', () => {
    render(
      <table>
        <tbody>
          <tr>
            <TableCell data-testid="td">Cell</TableCell>
          </tr>
        </tbody>
      </table>,
    );
    expect(screen.getByTestId('td')).toHaveClass('p-4');
  });
});

describe('TableCaption', () => {
  it('renders a caption element', () => {
    render(
      <table>
        <TableCaption data-testid="caption">Caption</TableCaption>
      </table>,
    );
    expect(screen.getByTestId('caption').tagName).toBe('CAPTION');
  });

  it('applies mt-4 class', () => {
    render(
      <table>
        <TableCaption data-testid="caption">Caption</TableCaption>
      </table>,
    );
    expect(screen.getByTestId('caption')).toHaveClass('mt-4');
  });
});
