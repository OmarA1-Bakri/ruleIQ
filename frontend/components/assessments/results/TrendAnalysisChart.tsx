'use client';

import React, { useState, useMemo, useRef, useEffect, useLayoutEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { TrendDataPoint } from '@/types/assessment-results';

/**
 * TrendAnalysisChart Component
 * 
 * IMPLEMENTATION CHOICE: Custom SVG Chart
 * 
 * This component uses a custom SVG implementation instead of Recharts for the following reasons:
 * 
 * 1. **Performance**: Direct SVG manipulation is more performant for simple line charts,
 *    avoiding the overhead of a full charting library for straightforward visualizations.
 * 
 * 2. **Bundle Size**: Eliminates the ~150KB+ dependency of Recharts, keeping the bundle lean.
 * 
 * 3. **Customization**: Provides complete control over animations, interactions, and styling
 *    without being constrained by library abstractions.
 * 
 * 4. **Accessibility**: Direct control over ARIA attributes, keyboard navigation, and
 *    screen reader announcements for better accessibility compliance.
 * 
 * 5. **Specific Requirements**: The trend chart has specific interaction patterns (keyboard
 *    navigation, custom tooltips, period selection) that are simpler to implement directly.
 * 
 * TRADE-OFFS:
 * - More code to maintain compared to using a library
 * - Need to implement features like responsive sizing manually
 * - Requires more testing for edge cases
 * 
 * MIGRATION PATH:
 * If migrating to Recharts is desired, the component interface remains the same.
 * Only the internal implementation would change, keeping the API contract intact.
 */
export interface TrendAnalysisChartProps {
  data: TrendDataPoint[];
  className?: string;
}

type TimePeriod = '30d' | '3m' | '6m' | '1y';

const TIME_PERIODS: { value: TimePeriod; label: string; days: number }[] = [
  { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '3m', label: 'Last 3 months', days: 90 },
  { value: '6m', label: 'Last 6 months', days: 180 },
  { value: '1y', label: 'Last year', days: 365 },
];

// Neural Purple theme colors
const COLORS = {
  primary: '#8b5cf6BD9',
  secondary: '#8b5cf66D4',
  accent: '#8b5cf6E0B',
  success: '#8b5cf6981',
  magenta: '#8b5cf62B6',
  indigo: '#8b5cf6CF8',
  lime: '#8b5cf6635',
  danger: '#8b5cf6444',
  neuralPurple: '#8b5cf6CF6',
  purple: '#8b5cf64FC',
};

const CHART_COLORS = [
  COLORS.primary,
  COLORS.secondary,
  COLORS.accent,
  COLORS.success,
  COLORS.magenta,
  COLORS.indigo,
  COLORS.lime,
  COLORS.neuralPurple,
  COLORS.purple,
];

export function TrendAnalysisChart({ data, className }: TrendAnalysisChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<TimePeriod>('3m');
  const [hoveredPoint, setHoveredPoint] = useState<{
    dataIndex: number;
    x: number;
    y: number;
  } | null>(null);
  const [focusedPoint, setFocusedPoint] = useState<number | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 400 });
  const [tooltipDimensions, setTooltipDimensions] = useState({ width: 250, height: 150 });
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Filter data based on selected time period
  const filteredData = useMemo(() => {
    const period = TIME_PERIODS.find(p => p.value === selectedPeriod);
    if (!period || data.length === 0) return data;

    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - period.days);

    return data.filter(point => new Date(point.date) >= cutoffDate).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }, [data, selectedPeriod]);

  // Get all unique section names
  const sectionNames = useMemo(() => {
    const sections = new Set<string>();
    filteredData.forEach(point => {
      Object.keys(point.sectionScores).forEach(section => sections.add(section));
    });
    return Array.from(sections).slice(0, 8); // Limit to 8 sections for readability
  }, [filteredData]);

  // Chart dimensions and padding
  const chartWidth = dimensions.width;
  const chartHeight = dimensions.height;
  const padding = { top: 20, right: 20, bottom: 60, left: 60 };
  const innerWidth = Math.max(0, chartWidth - padding.left - padding.right);
  const innerHeight = Math.max(0, chartHeight - padding.top - padding.bottom);

  // Measure tooltip dimensions when it's shown
  useLayoutEffect(() => {
    if (hoveredPoint && tooltipRef.current) {
      const rect = tooltipRef.current.getBoundingClientRect();
      setTooltipDimensions({
        width: rect.width + 20, // Add margin
        height: rect.height + 20  // Add margin
      });
    }
  }, [hoveredPoint]);

  // Set up ResizeObserver to make chart responsive
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) {
          setDimensions({
            width: Math.min(width, 1200), // Max width for readability
            height: Math.min(width * 0.5, 600), // Maintain aspect ratio, max height
          });
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Calculate scales
  const xScale = useMemo(() => {
    if (filteredData.length === 0) return { min: 0, max: 1, scale: (_x: number) => 0 };
    
    const minTime = Math.min(...filteredData.map(d => new Date(d.date).getTime()));
    const maxTime = Math.max(...filteredData.map(d => new Date(d.date).getTime()));
    const range = maxTime - minTime || 1;
    
    return {
      min: minTime,
      max: maxTime,
      scale: (time: number) => ((time - minTime) / range) * innerWidth
    };
  }, [filteredData, innerWidth]);

  const yScale = useMemo(() => {
    const scale = (score: number) => innerHeight - (score / 100) * innerHeight;
    return { scale };
  }, [innerHeight]);

  // Generate path data for lines
  const generatePath = (scores: (number | undefined)[]) => {
    if (scores.length === 0) return '';

    const segments: string[] = [];
    let currentSegment: string[] = [];

    scores.forEach((score, index) => {
      if (score !== undefined && score !== null && filteredData[index]) {
        const x = xScale.scale(new Date(filteredData[index].date).getTime());
        const y = yScale.scale(score);
        currentSegment.push(`${x},${y}`);
      } else {
        // If we have a segment, add it and start a new one
        if (currentSegment.length > 0) {
          segments.push(`M ${currentSegment.join(' L ')}`);
          currentSegment = [];
        }
      }
    });

    // Add the last segment if it exists
    if (currentSegment.length > 0) {
      segments.push(`M ${currentSegment.join(' L ')}`);
    }

    return segments.join(' ');
  };

  // Calculate percentage change
  const calculateChange = (current: number, previous: number) => {
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  // Format date for display
  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Handle mouse events for tooltips
  const handleMouseMove = (event: React.MouseEvent<SVGElement>) => {
    if (filteredData.length === 0) return;

    const svgRect = event.currentTarget.getBoundingClientRect();
    // Get the positioned container (the div with className="relative w-full")
    const relativeContainer = event.currentTarget.parentElement;
    if (!relativeContainer) return;
    const relativeRect = relativeContainer.getBoundingClientRect();

    // Calculate coordinates relative to SVG plot area for finding nearest point
    const xInChart = event.clientX - svgRect.left - padding.left;
    const _yInChart = event.clientY - svgRect.top - padding.top;

    // Find closest data point
    let closestIndex = 0;
    let minDistance = Infinity;

    filteredData.forEach((point, index) => {
      const pointX = xScale.scale(new Date(point.date).getTime());
      const distance = Math.abs(pointX - xInChart);
      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = index;
      }
    });

    if (minDistance < 50) { // Only show tooltip if close enough
      // Calculate tooltip position relative to the positioned container
      const tooltipX = event.clientX - relativeRect.left;
      const tooltipY = event.clientY - relativeRect.top;
      
      // Clamp within the positioned container bounds with margin using dynamic dimensions
      const clampedX = Math.min(Math.max(10, tooltipX), relativeRect.width - tooltipDimensions.width);
      const clampedY = Math.min(Math.max(10, tooltipY), relativeRect.height - tooltipDimensions.height);
      
      setHoveredPoint({
        dataIndex: closestIndex,
        x: clampedX,
        y: clampedY
      });
    } else {
      setHoveredPoint(null);
    }
  };

  const handleMouseLeave = () => {
    setHoveredPoint(null);
  };

  // Keyboard navigation for accessibility
  const handleKeyDown = (event: React.KeyboardEvent<SVGElement>) => {
    if (filteredData.length === 0) return;

    let newFocusedPoint = focusedPoint ?? 0;

    switch (event.key) {
      case 'ArrowLeft':
        event.preventDefault();
        newFocusedPoint = Math.max(0, newFocusedPoint - 1);
        break;
      case 'ArrowRight':
        event.preventDefault();
        newFocusedPoint = Math.min(filteredData.length - 1, newFocusedPoint + 1);
        break;
      case 'Home':
        event.preventDefault();
        newFocusedPoint = 0;
        break;
      case 'End':
        event.preventDefault();
        newFocusedPoint = filteredData.length - 1;
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        // Announce the current point details
        if (chartRef.current && filteredData[newFocusedPoint]) {
          const point = filteredData[newFocusedPoint]!; // Safe because we check above
          const announcement = `Date: ${formatDate(point.date)}, Overall Score: ${point.overallScore}%`;
          // Create a screen reader announcement
          const ariaLive = document.createElement('div');
          ariaLive.setAttribute('role', 'status');
          ariaLive.setAttribute('aria-live', 'polite');
          ariaLive.className = 'sr-only';
          ariaLive.textContent = announcement;
          document.body.appendChild(ariaLive);
          setTimeout(() => document.body.removeChild(ariaLive), 1000);
        }
        break;
      default:
        return;
    }

    setFocusedPoint(newFocusedPoint);
    // Show tooltip for focused point
    if (chartRef.current && filteredData[newFocusedPoint]) {
      const relativeContainer = chartRef.current.parentElement;
      if (!relativeContainer) return;
      
      const relativeRect = relativeContainer.getBoundingClientRect();
      const chartRect = chartRef.current.getBoundingClientRect();
      
      const point = filteredData[newFocusedPoint]!;
      // Calculate point position in SVG coordinate space
      const pointX = xScale.scale(new Date(point.date).getTime());
      const pointY = yScale.scale(point.overallScore);
      
      // Convert to tooltip position relative to the positioned container
      const tooltipX = (chartRect.left - relativeRect.left) + padding.left + pointX;
      const tooltipY = (chartRect.top - relativeRect.top) + padding.top + pointY;
      
      // Clamp within the positioned container bounds using dynamic dimensions
      const clampedX = Math.min(Math.max(10, tooltipX), relativeRect.width - tooltipDimensions.width);
      const clampedY = Math.min(Math.max(10, tooltipY), relativeRect.height - tooltipDimensions.height);
      
      setHoveredPoint({
        dataIndex: newFocusedPoint,
        x: clampedX,
        y: clampedY
      });
    }
  };

  if (data.length === 0) {
    return (
      <Card className={cn('w-full', className)}>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Trend Analysis</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full bg-neutral-100 p-4">
              <svg
                className="h-8 w-8 text-neutral-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-neutral-900">No Historical Data</h3>
            <p className="mb-4 max-w-md text-sm text-neutral-600">
              Complete more assessments to see your compliance score trends over time. Regular assessments help track your progress and identify improvement areas.
            </p>
            <Button variant="outline" size="sm">
              Take Another Assessment
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Trend Analysis</span>
          <div className="flex gap-1">
            {TIME_PERIODS.map((period) => (
              <Button
                key={period.value}
                variant={selectedPeriod === period.value ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setSelectedPeriod(period.value)}
                className="text-xs"
              >
                {period.label}
              </Button>
            ))}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div ref={containerRef} className="space-y-6">
          {/* Legend */}
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2">
              <div 
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: COLORS.primary }}
              />
              <span className="text-sm font-medium">Overall Score</span>
            </div>
            {sectionNames.map((section, index) => (
              <div key={section} className="flex items-center gap-2">
                <div 
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: CHART_COLORS[index + 1] || CHART_COLORS[index % CHART_COLORS.length] }}
                />
                <span className="text-sm text-neutral-600">{section}</span>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="relative w-full">
            <svg
              ref={chartRef}
              width="100%"
              height="100%"
              className="w-full overflow-visible focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              preserveAspectRatio="xMidYMid meet"
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              onKeyDown={handleKeyDown}
              tabIndex={0}
              role="img"
              aria-label={`Trend analysis chart showing compliance scores over ${selectedPeriod === '30d' ? 'the last 30 days' : selectedPeriod === '3m' ? 'the last 3 months' : selectedPeriod === '6m' ? 'the last 6 months' : 'the last year'}. Use arrow keys to navigate between data points.`}
            >
              {/* Grid lines */}
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#8b5cf64EA" strokeWidth="1" opacity="0.3"/>
                </pattern>
              </defs>
              <rect 
                x={padding.left} 
                y={padding.top} 
                width={innerWidth} 
                height={innerHeight} 
                fill="url(#grid)" 
              />

              {/* Y-axis labels */}
              {[0, 25, 50, 75, 100].map((score) => (
                <g key={score}>
                  <text
                    x={padding.left - 10}
                    y={padding.top + yScale.scale(score) + 4}
                    textAnchor="end"
                    className="fill-neutral-500 text-xs"
                  >
                    {score}%
                  </text>
                  <line
                    x1={padding.left}
                    y1={padding.top + yScale.scale(score)}
                    x2={padding.left + innerWidth}
                    y2={padding.top + yScale.scale(score)}
                    stroke="#8b5cf64EA"
                    strokeWidth="1"
                    opacity="0.5"
                  />
                </g>
              ))}

              {/* X-axis labels */}
              {filteredData.map((point, index) => {
                if (index % Math.ceil(filteredData.length / 6) === 0) {
                  const x = padding.left + xScale.scale(new Date(point.date).getTime());
                  return (
                    <text
                      key={index}
                      x={x}
                      y={chartHeight - 20}
                      textAnchor="middle"
                      className="fill-neutral-500 text-xs"
                    >
                      {formatDate(point.date)}
                    </text>
                  );
                }
                return null;
              })}

              {/* Chart area */}
              <g transform={`translate(${padding.left}, ${padding.top})`}>
                {/* Overall score line */}
                <path
                  d={generatePath(filteredData.map(d => d.overallScore))}
                  fill="none"
                  stroke={COLORS.primary}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Section score lines */}
                {sectionNames.map((section, index) => (
                  <path
                    key={section}
                    d={generatePath(filteredData.map(d => d.sectionScores[section]))}
                    fill="none"
                    stroke={CHART_COLORS[index + 1] || CHART_COLORS[index % CHART_COLORS.length]}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity="0.8"
                  />
                ))}

                {/* Data points */}
                {filteredData.map((point, index) => {
                  const x = xScale.scale(new Date(point.date).getTime());
                  const y = yScale.scale(point.overallScore);
                  const isFocused = focusedPoint === index;
                  return (
                    <g key={index}>
                      <circle
                        cx={x}
                        cy={y}
                        r={isFocused ? "6" : "4"}
                        fill={COLORS.primary}
                        stroke={isFocused ? COLORS.accent : "white"}
                        strokeWidth={isFocused ? "3" : "2"}
                        className="cursor-pointer hover:r-6 transition-all"
                        role="button"
                        tabIndex={-1}
                        aria-label={`Data point ${index + 1} of ${filteredData.length}: ${formatDate(point.date)}, Score: ${point.overallScore}%`}
                      />
                      {isFocused && (
                        <circle
                          cx={x}
                          cy={y}
                          r="8"
                          fill="none"
                          stroke={COLORS.primary}
                          strokeWidth="2"
                          className="animate-pulse"
                        />
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* Tooltip */}
            {hoveredPoint && filteredData[hoveredPoint.dataIndex] && (
              <div
                ref={tooltipRef}
                className="pointer-events-none absolute z-10 rounded-lg border bg-white p-3 shadow-lg"
                style={{
                  left: `${hoveredPoint.x}px`,
                  top: `${hoveredPoint.y}px`,
                  transform: 'translate(-50%, -110%)',
                  maxWidth: typeof window !== 'undefined' && window.innerWidth < 480 ? '200px' : '300px'
                }}
              >
                {(() => {
                  const tooltipPoint = filteredData[hoveredPoint.dataIndex]!;
                  const previousPoint = hoveredPoint.dataIndex > 0 && filteredData[hoveredPoint.dataIndex - 1] 
                    ? filteredData[hoveredPoint.dataIndex - 1]! 
                    : null;
                  const change = previousPoint 
                    ? calculateChange(tooltipPoint.overallScore, previousPoint.overallScore)
                    : 0;

                  return (
                    <div className="space-y-2">
                      <div className="text-sm font-semibold">
                        {formatDate(tooltipPoint.date)}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-4">
                          <span className="text-sm">Overall Score:</span>
                          <span className="font-semibold" style={{ color: COLORS.primary }}>
                            {tooltipPoint.overallScore}%
                          </span>
                        </div>
                        {previousPoint && (
                          <div className="text-xs text-neutral-500">
                            <span className={change >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {change >= 0 ? '+' : ''}{change.toFixed(1)}% from previous
                            </span>
                          </div>
                        )}
                      </div>
                      {sectionNames.slice(0, 3).map((section) => {
                        const score = tooltipPoint.sectionScores[section];
                        if (score === undefined) return null;
                        return (
                          <div key={section} className="flex items-center justify-between gap-4">
                            <span className="text-xs text-neutral-600">{section}:</span>
                            <span className="text-xs font-medium">{score}%</span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Summary stats */}
          {filteredData.length > 1 && (() => {
            const lastPoint = filteredData[filteredData.length - 1];
            const firstPoint = filteredData[0];
            if (!lastPoint || !firstPoint) return null;
            
            const overallChange = calculateChange(
              lastPoint.overallScore,
              firstPoint.overallScore
            );
            return (
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <div className="rounded-lg bg-neutral-50 p-3">
                  <div className="text-xs text-neutral-500">Latest Score</div>
                  <div className="text-lg font-semibold" style={{ color: COLORS.primary }}>
                    {lastPoint.overallScore}%
                  </div>
                </div>
                <div className="rounded-lg bg-neutral-50 p-3">
                  <div className="text-xs text-neutral-500">Change</div>
                  <div className={cn(
                    "text-lg font-semibold",
                    overallChange >= 0 ? "text-green-600" : "text-red-600"
                  )}>
                    {overallChange >= 0 ? '+' : ''}{overallChange.toFixed(1)}%
                  </div>
                </div>
              <div className="rounded-lg bg-neutral-50 p-3">
                <div className="text-xs text-neutral-500">Best Score</div>
                <div className="text-lg font-semibold text-green-600">
                  {Math.max(...filteredData.map(d => d.overallScore))}%
                </div>
              </div>
              <div className="rounded-lg bg-neutral-50 p-3">
                <div className="text-xs text-neutral-500">Assessments</div>
                <div className="text-lg font-semibold text-neutral-700">
                  {filteredData.length}
                </div>
              </div>
            </div>
            );
          })()}
        </div>
      </CardContent>
    </Card>
  );
}