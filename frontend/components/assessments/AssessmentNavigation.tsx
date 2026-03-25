'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Grid } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { type AssessmentFramework, type AssessmentProgress } from '@/lib/assessment-engine/types';
import { cn } from '@/lib/utils';

interface AssessmentNavigationProps {
  framework: AssessmentFramework;
  currentSectionIndex: number;
  progress: AssessmentProgress;
  onSectionClick: (sectionIndex: number) => void;
}

export function AssessmentNavigation({
  framework,
  currentSectionIndex,
  progress,
  onSectionClick,
}: AssessmentNavigationProps) {
  const hasPreviousSection = currentSectionIndex > 0;
  const hasNextSection = currentSectionIndex < framework.sections.length - 1;
  const [isNavigatorOpen, setIsNavigatorOpen] = useState(false);

  return (
    <>
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSectionClick(currentSectionIndex - 1)}
              disabled={!hasPreviousSection}
              className="flex-1 justify-start"
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              <span className="truncate">
                {hasPreviousSection && framework.sections[currentSectionIndex - 1]?.title}
              </span>
            </Button>

            <div className="flex items-center gap-1 px-4">
              {framework.sections.map((section, index) => (
                <button
                  key={`section-${section.id || index}`}
                  onClick={() => onSectionClick(index)}
                  className={cn(
                    'h-2 w-2 rounded-full transition-all',
                    index === currentSectionIndex
                      ? 'w-6 bg-primary'
                      : 'bg-muted-foreground/30 hover:bg-muted-foreground/50',
                  )}
                  aria-label={`Go to section ${index + 1}`}
                />
              ))}
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSectionClick(currentSectionIndex + 1)}
              disabled={!hasNextSection}
              className="flex-1 justify-end"
            >
              <span className="truncate">
                {hasNextSection && framework.sections[currentSectionIndex + 1]?.title}
              </span>
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </div>

          <div className="mt-4 border-t pt-4">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setIsNavigatorOpen(true)}
            >
              <Grid className="mr-2 h-4 w-4" />
              View All Sections ({framework.sections.length})
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={isNavigatorOpen} onOpenChange={setIsNavigatorOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{framework.name} Sections</DialogTitle>
            <DialogDescription>
              Jump directly to any section. Overall progress: {progress.percentComplete}% complete.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-2">
            {framework.sections.map((section, index) => {
              const isCurrent = index === currentSectionIndex;
              const isVisited = index < currentSectionIndex;

              return (
                <button
                  key={`navigator-${section.id || index}`}
                  type="button"
                  onClick={() => {
                    onSectionClick(index);
                    setIsNavigatorOpen(false);
                  }}
                  className={cn(
                    'rounded-lg border p-4 text-left transition-colors',
                    isCurrent
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/40 hover:bg-muted/40',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Section {index + 1}
                      </p>
                      <p className="font-semibold">{section.title}</p>
                    </div>
                    <span
                      className={cn(
                        'rounded-full px-2 py-1 text-xs font-medium',
                        isCurrent
                          ? 'bg-primary text-primary-foreground'
                          : isVisited
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {isCurrent ? 'Current' : isVisited ? 'Visited' : 'Upcoming'}
                    </span>
                  </div>

                  {section.description && (
                    <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {section.description}
                    </p>
                  )}

                  <p className="mt-3 text-xs text-muted-foreground">
                    {section.questions.length} questions
                  </p>
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
