'use client';

/**
 * ComplianceScoreWidget — stub.
 * The real widget lives at components/dashboard/compliance-score-widget.tsx.
 * This stub allows imports from the widgets/ sub-path that tests use.
 */

import React from 'react';

interface Framework {
  name: string;
  score: number;
  status: string;
}

interface ComplianceScoreWidgetProps {
  score?: number;
  trend?: 'up' | 'down' | 'flat';
  previousScore?: number;
  frameworks?: Framework[];
  onViewDetails?: () => void;
}

export function ComplianceScoreWidget({
  score,
  frameworks,
  onViewDetails,
}: ComplianceScoreWidgetProps) {
  return (
    <div data-testid="compliance-score-widget-stub">
      {score !== undefined && <span>{score}%</span>}
      {frameworks?.map((f) => (
        <div key={f.name}>
          <span>{f.name}</span>
          <span>{f.score}%</span>
        </div>
      ))}
      <button type="button" onClick={onViewDetails}>
        View Details
      </button>
    </div>
  );
}
