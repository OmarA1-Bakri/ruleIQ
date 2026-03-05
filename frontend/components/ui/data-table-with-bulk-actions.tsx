'use client';

import {
  type ColumnDef,
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { Download, Trash2, Archive, CheckCircle } from 'lucide-react';
import * as React from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface BulkAction<T> {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  handler: (selectedRows: Record<string, boolean>, data: T[]) => void | Promise<void>;
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
}

interface DataTableWithBulkActionsProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  bulkActions?: BulkAction<TData>[];
  onExport?: (format: 'csv' | 'excel' | 'json') => void;
}

export function DataTableWithBulkActions<TData, TValue>({
  columns,
  data,
  bulkActions = [],
  onExport,
}: DataTableWithBulkActionsProps<TData, TValue>) {
  const [rowSelection, setRowSelection] = React.useState({});
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnVisibility,
      rowSelection,
      columnFilters,
    },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  });

  const selectedCount = Object.keys(rowSelection).length;
  const selectedData = table.getFilteredSelectedRowModel().rows.map((row) => row.original);

  // Default bulk actions if none provided
  const defaultBulkActions: BulkAction<TData>[] = [
    {
      id: 'archive',
      label: 'Archive',
      icon: Archive,
      handler: async (_selection, _items) => {
        // Implement archive logic
      },
    },
    {
      id: 'delete',
      label: 'Delete',
      icon: Trash2,
      variant: 'destructive',
      handler: async (_selection, _items) => {
        // Implement delete logic
      },
    },
  ];

  const actions = bulkActions.length > 0 ? bulkActions : defaultBulkActions;

  return (
    <div className="relative w-full">
      {/* Bulk Actions Bar */}
      {selectedCount > 0 && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 animate-in slide-in-from-bottom-4">
          <Card className="border-gold/20 shadow-lg">
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-gold" />
                <span className="text-sm font-medium">{selectedCount} selected</span>
              </div>
              <div className="h-4 w-px bg-border" />
              {actions.map((action) => (
                <Button
                  key={action.id}
                  variant={action.variant || 'outline'}
                  size="sm"
                  onClick={() => action.handler(rowSelection, selectedData)}
                  className="gap-2"
                >
                  <action.icon className="h-4 w-4" />
                  {action.label}
                </Button>
              ))}
              {onExport && (
                <>
                  <div className="h-4 w-px bg-border" />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onExport('csv')}
                    className="gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Export
                  </Button>
                </>
              )}
              <Button variant="ghost" size="sm" onClick={() => setRowSelection({})}>
                Clear
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Data Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} data-state={row.getIsSelected() && 'selected'}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between space-x-2 py-4">
        <div className="text-sm text-muted-foreground">
          {selectedCount > 0 && <span>{selectedCount} of </span>}
          {table.getFilteredRowModel().rows.length} row(s)
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
