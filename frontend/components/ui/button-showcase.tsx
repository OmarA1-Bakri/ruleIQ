import { Download, Plus, Settings, Heart, Star, ArrowRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function ButtonShowcase() {
  return (
    <div className="space-y-8">
      {/* Primary Buttons */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Primary Buttons</CardTitle>
          <CardDescription className="text-neutral-600">
            Teal background with white text for primary actions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="default" size="sm">
                <Plus className="h-3 w-3" />
                Small Primary
              </Button>
              <Button variant="default" size="default">
                <Download className="h-4 w-4" />
                Medium Primary
              </Button>
              <Button variant="default" size="lg">
                <Settings className="h-5 w-5" />
                Large Primary
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="default" size="sm" disabled>
                Disabled Small
              </Button>
              <Button variant="default" size="default" disabled>
                Disabled Medium
              </Button>
              <Button variant="default" size="lg" disabled>
                Disabled Large
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Secondary Buttons */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Secondary Buttons</CardTitle>
          <CardDescription className="text-neutral-600">
            White background with teal border and text for secondary actions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="secondary" size="sm">
                <Heart className="h-3 w-3" />
                Small Secondary
              </Button>
              <Button variant="secondary" size="default">
                <Star className="h-4 w-4" />
                Medium Secondary
              </Button>
              <Button variant="secondary" size="lg">
                <ArrowRight className="h-5 w-5" />
                Large Secondary
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="secondary" size="sm" disabled>
                Disabled Small
              </Button>
              <Button variant="secondary" size="default" disabled>
                Disabled Medium
              </Button>
              <Button variant="secondary" size="lg" disabled>
                Disabled Large
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Ghost Buttons */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Ghost Buttons</CardTitle>
          <CardDescription className="text-neutral-600">
            Transparent background with neutral text for subtle actions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="ghost" size="sm">
                <Plus className="h-3 w-3" />
                Small Ghost
              </Button>
              <Button variant="ghost" size="default">
                <Download className="h-4 w-4" />
                Medium Ghost
              </Button>
              <Button variant="ghost" size="lg">
                <Settings className="h-5 w-5" />
                Large Ghost
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="ghost" size="sm" disabled>
                Disabled Small
              </Button>
              <Button variant="ghost" size="default" disabled>
                Disabled Medium
              </Button>
              <Button variant="ghost" size="lg" disabled>
                Disabled Large
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Additional Variants */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Additional Variants</CardTitle>
          <CardDescription className="text-neutral-600">
            Extra button variants for specific use cases
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="secondary" size="default">
                <Star className="h-4 w-4" />
                Accent Button
              </Button>
              <Button variant="success" size="default">
                <Plus className="h-4 w-4" />
                Success Button
              </Button>
              <Button variant="outline" size="default">
                <Settings className="h-4 w-4" />
                Warning Button
              </Button>
              <Button variant="destructive" size="default">
                <Download className="h-4 w-4" />
                Error Button
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Usage Examples */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Usage Examples</CardTitle>
          <CardDescription className="text-neutral-600">
            Common button combinations and use cases
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* Action Group */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-neutral-900">
                Action Group
              </h4>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="default" size="default">
                  Save Changes
                </Button>
                <Button variant="secondary" size="default">
                  Cancel
                </Button>
                <Button variant="ghost" size="default">
                  Reset
                </Button>
              </div>
            </div>

            {/* Form Actions */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-neutral-900">
                Form Actions
              </h4>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="default" size="lg">
                  <Plus className="h-5 w-5" />
                  Create Assessment
                </Button>
                <Button variant="secondary" size="lg">
                  <Download className="h-5 w-5" />
                  Export Data
                </Button>
              </div>
            </div>

            {/* Status Actions */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-neutral-900">
                Status Actions
              </h4>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="success" size="sm">
                  Approve
                </Button>
                <Button variant="outline" size="sm">
                  Review
                </Button>
                <Button variant="destructive" size="sm">
                  Reject
                </Button>
                <Button variant="ghost" size="sm">
                  View Details
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
