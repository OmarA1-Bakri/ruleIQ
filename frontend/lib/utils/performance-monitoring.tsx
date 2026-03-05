// Performance monitoring utilities for stores and API calls
import React from 'react';

interface PerformanceEntry {
  operation: string;
  duration: number;
  timestamp: number;
  success: boolean;
  error?: string;
  metadata?: Record<string, any>;
}

class PerformanceMonitor {
  private entries: PerformanceEntry[] = [];
  private maxEntries = 1000;
  private enabled =
    process.env.NODE_ENV === 'development' ||
    process.env['NEXT_PUBLIC_ENABLE_PERFORMANCE_MONITORING'] === 'true';

  // Record a performance entry
  record(entry: PerformanceEntry) {
    if (!this.enabled) return;

    this.entries.push(entry);

    // Keep only the most recent entries
    if (this.entries.length > this.maxEntries) {
      this.entries = this.entries.slice(-this.maxEntries);
    }

    // Log slow operations
    if (entry.duration > 1000) {
      // intentionally empty - slow operation detected, logged via monitoring service
    }

    // In production, you might want to send this to a monitoring service
    if (process.env.NODE_ENV === 'production') {
      this.sendToMonitoringService(entry);
    }
  }

  // Get performance metrics
  getMetrics() {
    if (!this.enabled) return null;

    const now = Date.now();
    const last5Minutes = this.entries.filter((e) => now - e.timestamp < 5 * 60 * 1000);

    return {
      totalOperations: last5Minutes.length,
      averageDuration:
        last5Minutes.reduce((sum, e) => sum + e.duration, 0) / last5Minutes.length || 0,
      successRate: last5Minutes.filter((e) => e.success).length / last5Minutes.length || 0,
      slowOperations: last5Minutes.filter((e) => e.duration > 1000).length,
      byOperation: this.groupByOperation(last5Minutes),
    };
  }

  // Get entries for debugging
  getEntries(limit = 100) {
    if (!this.enabled) return [];
    return this.entries.slice(-limit);
  }

  // Clear all entries
  clear() {
    this.entries = [];
  }

  private groupByOperation(entries: PerformanceEntry[]) {
    const grouped: Record<string, { count: number; avgDuration: number; successRate: number }> = {};

    entries.forEach((entry) => {
      if (!grouped[entry.operation]) {
        grouped[entry.operation] = { count: 0, avgDuration: 0, successRate: 0 };
      }
      grouped[entry.operation]!.count++;
    });

    Object.keys(grouped).forEach((operation) => {
      const operationEntries = entries.filter((e) => e.operation === operation);
      grouped[operation]!.avgDuration =
        operationEntries.reduce((sum, e) => sum + e.duration, 0) / operationEntries.length;
      grouped[operation]!.successRate =
        operationEntries.filter((e) => e.success).length / operationEntries.length;
    });

    return grouped;
  }

  private sendToMonitoringService(entry: PerformanceEntry) {
    // In a real app, you'd send this to a service like Sentry, DataDog, etc.
    // For now, we'll just log it
    if (entry.duration > 2000 || !entry.success) {
      // intentionally empty - production monitoring service integration placeholder
    }
  }
}

// Global performance monitor instance
export const performanceMonitor = new PerformanceMonitor();

// Helper function to wrap async operations with performance monitoring
export function withPerformanceMonitoring<T>(
  operation: string,
  fn: () => Promise<T>,
  metadata?: Record<string, any>,
): Promise<T> {
  const startTime = performance.now();

  return fn()
    .then((result) => {
      const duration = performance.now() - startTime;
      performanceMonitor.record({
        operation,
        duration,
        timestamp: Date.now(),
        success: true,
        metadata,
      });
      return result;
    })
    .catch((error) => {
      const duration = performance.now() - startTime;
      performanceMonitor.record({
        operation,
        duration,
        timestamp: Date.now(),
        success: false,
        error: error?.message || String(error),
        metadata,
      });
      throw error;
    });
}

// Zustand middleware for performance monitoring
export const performanceMiddleware = (config: any) => (set: any, get: any, api: any) => {
  const originalSet = set;

  // Wrap set function to monitor state changes
  const monitoredSet = (partial: any, replace?: boolean, action?: string) => {
    const startTime = performance.now();

    try {
      const result = originalSet(partial, replace, action);
      const duration = performance.now() - startTime;

      if (action && duration > 100) {
        performanceMonitor.record({
          operation: `store.${action}`,
          duration,
          timestamp: Date.now(),
          success: true,
          metadata: { replace, hasPartial: !!partial },
        });
      }

      return result;
    } catch (error) {
      const duration = performance.now() - startTime;
      performanceMonitor.record({
        operation: `store.${action}`,
        duration,
        timestamp: Date.now(),
        success: false,
        error: error instanceof Error ? error.message : String(error),
        metadata: { replace, hasPartial: !!partial },
      });
      throw error;
    }
  };

  return config(monitoredSet, get, api);
};

// React hook for performance metrics
export function usePerformanceMetrics() {
  const getMetrics = () => performanceMonitor.getMetrics();
  const getEntries = (limit?: number) => performanceMonitor.getEntries(limit);
  const clear = () => performanceMonitor.clear();

  return {
    getMetrics,
    getEntries,
    clear,
  };
}

// Performance debugging component (for development)
export function PerformanceDebugger() {
  if (process.env.NODE_ENV !== 'development') return null;

  const metrics = performanceMonitor.getMetrics();

  if (!metrics) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '10px',
        right: '10px',
        background: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        padding: '10px',
        borderRadius: '5px',
        fontSize: '12px',
        zIndex: 9999,
        maxWidth: '300px',
      }}
    >
      <div>Performance Metrics (5min)</div>
      <div>Operations: {metrics.totalOperations}</div>
      <div>Avg Duration: {metrics.averageDuration.toFixed(2)}ms</div>
      <div>Success Rate: {(metrics.successRate * 100).toFixed(1)}%</div>
      <div>Slow Ops: {metrics.slowOperations}</div>
      <div style={{ marginTop: '5px', fontSize: '11px' }}>
        {Object.entries(metrics.byOperation).map(([op, data]) => (
          <div key={op}>
            {op}: {data.count} ({data.avgDuration.toFixed(1)}ms,{' '}
            {(data.successRate * 100).toFixed(1)}%)
          </div>
        ))}
      </div>
    </div>
  );
}

// Export for global access
declare global {
  interface Window {
    performanceMonitor: PerformanceMonitor;
  }
}

if (typeof window !== 'undefined') {
  window.performanceMonitor = performanceMonitor;
}
