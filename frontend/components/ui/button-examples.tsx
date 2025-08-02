import { Plus, Download, Edit, Trash2, Eye, Settings } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function ButtonExamples() {
  return (
    <div className="space-y-6">
      {/* Dashboard Actions */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Dashboard Actions</CardTitle>
          <CardDescription className="text-neutral-600">
            Common button combinations used in dashboard interfaces
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="default" size="default">
              <Plus className="h-4 w-4" />
              New Assessment
            </Button>
            <Button variant="secondary" size="default">
              <Download className="h-4 w-4" />
              Export Report
            </Button>
            <Button variant="ghost" size="default">
              <Settings className="h-4 w-4" />
              Settings
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table Actions */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle style={{ color: '#F0EAD6' }}>Table Row Actions</CardTitle>
          <CardDescription style={{ color: '#6C757D' }}>
            Action buttons typically used in data tables
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" size="sm">
              <Eye className="h-3 w-3" />
              View
            </Button>
            <Button variant="ghost" size="sm">
              <Edit className="h-3 w-3" />
              Edit
            </Button>
            <Button variant="destructive" size="sm">
              <Trash2 className="h-3 w-3" />
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Form Actions */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle style={{ color: '#F0EAD6' }}>Form Actions</CardTitle>
          <CardDescription style={{ color: '#6C757D' }}>
            Button combinations for form submissions and actions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="default" size="lg">
              Save Changes
            </Button>
            <Button variant="secondary" size="lg">
              Cancel
            </Button>
            <Button variant="ghost" size="lg">
              Reset Form
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Status Actions */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle style={{ color: '#F0EAD6' }}>Status Actions</CardTitle>
          <CardDescription style={{ color: '#6C757D' }}>
            Buttons for different status-based actions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="success" size="default">
              Approve Assessment
            </Button>
            <Button variant="outline" size="default">
              Mark for Review
            </Button>
            <Button variant="destructive" size="default">
              Reject Submission
            </Button>
            <Button variant="secondary" size="default">
              Feature Request
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
