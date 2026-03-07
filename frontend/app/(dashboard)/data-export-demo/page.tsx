'use client';

import { type ColumnDef } from '@tanstack/react-table';
import { Download } from 'lucide-react';
import { toast } from 'sonner';

import { DataTableColumnHeader } from '@/components/assessments/data-table-column-header';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { AppSidebar } from '@/components/navigation/app-sidebar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { DataTableWithExport } from '@/components/ui/data-table-with-export';
import { DataExporter, transformDataForExport, exportPresets } from '@/lib/utils/export-utils';

// Demo data
const demoComplianceData = [
  {
    id: '1',
    framework_name: 'ISO 27001',
    compliance_score: 92,
    last_assessed: '2024-01-15T10:00:00Z',
    status: 'compliant',
    controls_implemented: 108,
    total_controls: 114,
    risk_level: 'low',
  },
  {
    id: '2',
    framework_name: 'GDPR',
    compliance_score: 88,
    last_assessed: '2024-01-10T14:30:00Z',
    status: 'compliant',
    controls_implemented: 52,
    total_controls: 59,
    risk_level: 'medium',
  },
  {
    id: '3',
    framework_name: 'Cyber Essentials',
    compliance_score: 95,
    last_assessed: '2024-01-20T09:00:00Z',
    status: 'compliant',
    controls_implemented: 38,
    total_controls: 40,
    risk_level: 'low',
  },
  {
    id: '4',
    framework_name: 'PCI DSS',
    compliance_score: 78,
    last_assessed: '2024-01-05T16:00:00Z',
    status: 'non-compliant',
    controls_implemented: 195,
    total_controls: 250,
    risk_level: 'high',
  },
  {
    id: '5',
    framework_name: 'SOC 2',
    compliance_score: 85,
    last_assessed: '2024-01-12T11:00:00Z',
    status: 'compliant',
    controls_implemented: 51,
    total_controls: 60,
    risk_level: 'medium',
  },
];

// Column definitions
const columns: ColumnDef<(typeof demoComplianceData)[0]>[] = [
  {
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && 'indeterminate')
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: 'framework_name',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Framework" />,
  },
  {
    accessorKey: 'compliance_score',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Score" />,
    cell: ({ row }) => {
      const score = row.getValue('compliance_score') as number;
      return (
        <div className="flex items-center">
          <span className="font-medium">{score}%</span>
          <div className="ml-2 h-2 w-16 overflow-hidden rounded-full bg-gray-200">
            <div
              className={`h-full ${score >= 90 ? 'bg-success' : score >= 80 ? 'bg-warning' : 'bg-error'}`}
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
      );
    },
  },
  {
    accessorKey: 'status',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
      const status = row.getValue('status') as string;
      return (
        <Badge
          variant="outline"
          className={
            status === 'compliant' ? 'border-success text-success' : 'border-error text-error'
          }
        >
          {status}
        </Badge>
      );
    },
  },
  {
    accessorKey: 'controls_implemented',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Controls" />,
    cell: ({ row }) => {
      const implemented = row.getValue('controls_implemented') as number;
      const total = row.original.total_controls;
      return `${implemented}/${total}`;
    },
  },
  {
    accessorKey: 'risk_level',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Risk" />,
    cell: ({ row }) => {
      const risk = row.getValue('risk_level') as string;
      const colorMap = {
        low: 'text-success',
        medium: 'text-warning',
        high: 'text-error',
      };
      return (
        <span className={`font-medium ${colorMap[risk as keyof typeof colorMap]}`}>
          {risk.toUpperCase()}
        </span>
      );
    },
  },
  {
    accessorKey: 'last_assessed',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Last Assessed" />,
    cell: ({ row }) => {
      const date = new Date(row.getValue('last_assessed') as string);
      return date.toLocaleDateString();
    },
  },
];

export default function DataExportDemoPage() {
  // Advanced export with formatting
  const handleAdvancedExport = async (format: 'pdf' | 'xlsx') => {
    // Transform data with presets
    const transformedData = transformDataForExport(
      demoComplianceData,
      exportPresets.compliance.columnMapping,
      exportPresets.compliance.valueFormatters,
    );

    try {
      if (format === 'pdf') {
        DataExporter.exportToPDF(transformedData, {
          filename: 'compliance-report',
          headers: Object.values(exportPresets.compliance.columnMapping || {}),
        });
        toast.success('PDF report generated successfully');
      } else {
        DataExporter.exportToExcel(transformedData, {
          filename: 'compliance-data',
          headers: Object.values(exportPresets.compliance.columnMapping || {}),
        });
        toast.success('Excel file generated successfully');
      }
    } catch (_error) {
      toast.error('Export failed. Please try again.');

    }
  };

  // Export with progress for large datasets
  const handleLargeDataExport = async () => {
    // Simulate large dataset
    const largeData = Array(5000)
      .fill(0)
      .map((_, i) => ({
        ...demoComplianceData[i % demoComplianceData.length],
        id: `${i + 1}`,
      }));

    toast.promise(
      DataExporter.exportWithProgress(largeData, 'csv', (_progress) => {
      }),
      {
        loading: 'Exporting large dataset...',
        success: 'Export completed successfully!',
        error: 'Export failed',
      },
    );
  };

  return (
    <div className="flex flex-1">
      <AppSidebar />
      <div className="flex-1 overflow-auto">
        <DashboardHeader />
        <div className="space-y-6 p-6">
          {/* Page Header */}
          <div>
            <h1 className="text-3xl font-bold text-navy">Data Export Demo</h1>
            <p className="text-muted-foreground">
              Demonstrating advanced data export capabilities with multiple formats
            </p>
          </div>

          {/* Main Data Table with Export */}
          <Card>
            <CardHeader>
              <CardTitle>Compliance Framework Data</CardTitle>
              <CardDescription>
                Select rows and use the export button to download data in various formats
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DataTableWithExport
                columns={columns}
                data={demoComplianceData}
                exportFilename="compliance-frameworks"
              />
            </CardContent>
          </Card>

          {/* Advanced Export Options */}
          <Card>
            <CardHeader>
              <CardTitle>Advanced Export Options</CardTitle>
              <CardDescription>
                Generate formatted reports with custom styling and data transformation
              </CardDescription>
            </CardHeader>
            <CardContent className="flex gap-4">
              <Button variant="outline" onClick={() => handleAdvancedExport('pdf')}>
                <Download className="mr-2 h-4 w-4" />
                Generate PDF Report
              </Button>
              <Button variant="outline" onClick={() => handleAdvancedExport('xlsx')}>
                <Download className="mr-2 h-4 w-4" />
                Generate Excel Report
              </Button>
              <Button variant="outline" onClick={handleLargeDataExport}>
                <Download className="mr-2 h-4 w-4" />
                Export Large Dataset (5k rows)
              </Button>
            </CardContent>
          </Card>

          {/* Export Features */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Multiple Formats</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Export data in CSV, JSON, TXT, PDF, and Excel formats
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Selective Export</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Export all data or only selected rows based on your needs
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Data Transformation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Apply formatting and transformations during export
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
