/**
 * Performance Monitoring Utilities for ruleIQ
 *
 * This module provides utilities for monitoring and measuring application performance
 * including Core Web Vitals, custom metrics, and performance budgets.
 */

// Performance thresholds based on Core Web Vitals
export const PERFORMANCE_THRESHOLDS = {
  // Core Web Vitals
  LCP: { good: 2500, poor: 4000 }, // Largest Contentful Paint (ms)
  FID: { good: 100, poor: 300 }, // First Input Delay (ms)
  CLS: { good: 0.1, poor: 0.25 }, // Cumulative Layout Shift

  // Additional metrics
  FCP: { good: 1800, poor: 3000 }, // First Contentful Paint (ms)
  TTI: { good: 3800, poor: 7300 }, // Time to Interactive (ms)
  TBT: { good: 200, poor: 600 }, // Total Blocking Time (ms)

  // Custom metrics
  API_RESPONSE: { good: 500, poor: 2000 }, // API response time (ms)
  ROUTE_CHANGE: { good: 200, poor: 1000 }, // Route change time (ms)
  COMPONENT_RENDER: { good: 16, poor: 50 }, // Component render time (ms)
} as const;

export interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  url: string;
  userAgent: string;
  connectionType?: string;
  rating: 'good' | 'needs-improvement' | 'poor';
}

export interface WebVitalsMetrics {
  lcp?: PerformanceMetric;
  fid?: PerformanceMetric;
  cls?: PerformanceMetric;
  fcp?: PerformanceMetric;
  ttfb?: PerformanceMetric;
}

class PerformanceMonitor {
  private metrics: Map<string, PerformanceMetric[]> = new Map();
  private observers: PerformanceObserver[] = [];
  private isEnabled: boolean = true;

  constructor() {
    this.initializeObservers();
  }

  /**
   * Initialize performance observers for Core Web Vitals
   */
  private initializeObservers(): void {
    if (typeof window === 'undefined') return;

    try {
      // Largest Contentful Paint (LCP)
      this.observeMetric('largest-contentful-paint', (entries) => {
        const lastEntry = entries[entries.length - 1];
        this.recordMetric('LCP', lastEntry.startTime);
      });

      // First Input Delay (FID)
      this.observeMetric('first-input', (entries) => {
        const firstEntry = entries[0] as any;
        const fid = firstEntry.processingStart - firstEntry.startTime;
        this.recordMetric('FID', fid);
      });

      // Cumulative Layout Shift (CLS)
      let clsValue = 0;
      this.observeMetric('layout-shift', (entries) => {
        for (const entry of entries) {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value;
          }
        }
        this.recordMetric('CLS', clsValue);
      });

      // First Contentful Paint (FCP)
      this.observeMetric('paint', (entries) => {
        const fcpEntry = entries.find((entry) => entry.name === 'first-contentful-paint');
        if (fcpEntry) {
          this.recordMetric('FCP', fcpEntry.startTime);
        }
      });

      // Navigation timing
      this.observeNavigationTiming();
    } catch (_error) {
    }
  }

  /**
   * Observe specific performance entry types
   */
  private observeMetric(entryType: string, callback: (entries: PerformanceEntry[]) => void): void {
    try {
      const observer = new PerformanceObserver((list) => {
        callback(list.getEntries());
      });

      observer.observe({ entryTypes: [entryType] });
      this.observers.push(observer);
    } catch (_error) {
    }
  }

  /**
   * Observe navigation timing metrics
   */
  private observeNavigationTiming(): void {
    if (typeof window === 'undefined') return;

    window.addEventListener('load', () => {
      const navigation = performance.getEntriesByType(
        'navigation',
      )[0] as PerformanceNavigationTiming;

      if (navigation) {
        // Time to First Byte (TTFB)
        const ttfb = navigation.responseStart - navigation.requestStart;
        this.recordMetric('TTFB', ttfb);

        // DOM Content Loaded
        const dcl = navigation.domContentLoadedEventEnd - navigation.fetchStart;
        this.recordMetric('DCL', dcl);

        // Load Complete
        const loadComplete = navigation.loadEventEnd - navigation.fetchStart;
        this.recordMetric('LOAD', loadComplete);
      }
    });
  }

  /**
   * Record a performance metric
   */
  public recordMetric(name: string, value: number, url?: string): void {
    if (!this.isEnabled) return;

    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      url: url || window.location.href,
      userAgent: navigator.userAgent,
      connectionType: this.getConnectionType(),
      rating: this.getRating(name, value),
    };

    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }

    this.metrics.get(name)!.push(metric);

    // Send to analytics if configured
    this.sendToAnalytics(metric);

    // Log performance issues
    if (metric.rating === 'poor') {
    }
  }

  /**
   * Get connection type information
   */
  private getConnectionType(): string | undefined {
    const connection =
      (navigator as any).connection ||
      (navigator as any).mozConnection ||
      (navigator as any).webkitConnection;
    return connection?.effectiveType;
  }

  /**
   * Rate a metric value based on thresholds
   */
  private getRating(name: string, value: number): 'good' | 'needs-improvement' | 'poor' {
    const threshold = PERFORMANCE_THRESHOLDS[name as keyof typeof PERFORMANCE_THRESHOLDS];

    if (!threshold) return 'good';

    if (value <= threshold.good) return 'good';
    if (value <= threshold.poor) return 'needs-improvement';
    return 'poor';
  }

  /**
   * Send metric to analytics service
   */
  private sendToAnalytics(metric: PerformanceMetric): void {
    // In a real application, you would send this to your analytics service
    // For example: Google Analytics, DataDog, New Relic, etc.

    if (process.env.NODE_ENV === 'development') {
    }

    // Example: Send to Google Analytics
    if (typeof window !== 'undefined' && 'gtag' in window) {
      (window as any).gtag('event', 'performance_metric', {
        metric_name: metric.name,
        metric_value: metric.value,
        metric_rating: metric.rating,
        custom_map: {
          metric_name: 'metric_name',
          metric_value: 'metric_value',
          metric_rating: 'metric_rating',
        },
      });
    }
  }

  /**
   * Measure custom performance metrics
   */
  public measureCustomMetric(name: string, fn: () => void | Promise<void>): Promise<number> {
    return new Promise(async (resolve) => {
      const startTime = performance.now();

      try {
        await fn();
      } catch (_error) {
      }

      const duration = performance.now() - startTime;
      this.recordMetric(name, duration);
      resolve(duration);
    });
  }

  /**
   * Measure API call performance
   */
  public measureApiCall(
    url: string,
    method: string = 'GET',
  ): {
    start: () => void;
    end: (success: boolean) => void;
  } {
    let startTime: number;

    return {
      start: () => {
        startTime = performance.now();
      },
      end: (success: boolean) => {
        const duration = performance.now() - startTime;
        this.recordMetric(`API_${method}_${success ? 'SUCCESS' : 'ERROR'}`, duration, url);
      },
    };
  }

  /**
   * Measure route change performance
   */
  public measureRouteChange(
    from: string,
    to: string,
  ): {
    start: () => void;
    end: () => void;
  } {
    let startTime: number;

    return {
      start: () => {
        startTime = performance.now();
      },
      end: () => {
        const duration = performance.now() - startTime;
        this.recordMetric('ROUTE_CHANGE', duration, `${from} -> ${to}`);
      },
    };
  }

  /**
   * Get all recorded metrics
   */
  public getMetrics(name?: string): PerformanceMetric[] {
    if (name) {
      return this.metrics.get(name) || [];
    }

    const allMetrics: PerformanceMetric[] = [];
    for (const metrics of this.metrics.values()) {
      allMetrics.push(...metrics);
    }

    return allMetrics.sort((a, b) => b.timestamp - a.timestamp);
  }

  /**
   * Get performance summary
   */
  public getSummary(): Record<string, { count: number; average: number; rating: string }> {
    const summary: Record<string, { count: number; average: number; rating: string }> = {};

    for (const [name, metrics] of this.metrics.entries()) {
      const values = metrics.map((m) => m.value);
      const average = values.reduce((sum, val) => sum + val, 0) / values.length;
      const rating = this.getRating(name, average);

      summary[name] = {
        count: metrics.length,
        average: Math.round(average * 100) / 100,
        rating,
      };
    }

    return summary;
  }

  /**
   * Clear all metrics
   */
  public clearMetrics(): void {
    this.metrics.clear();
  }

  /**
   * Enable or disable monitoring
   */
  public setEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }

  /**
   * Disconnect all observers
   */
  public disconnect(): void {
    this.observers.forEach((observer) => observer.disconnect());
    this.observers = [];
  }
}

// Create singleton instance
export const performanceMonitor = new PerformanceMonitor();

/**
 * React hook for performance monitoring
 */
export function usePerformanceMonitor() {
  return {
    recordMetric: performanceMonitor.recordMetric.bind(performanceMonitor),
    measureCustomMetric: performanceMonitor.measureCustomMetric.bind(performanceMonitor),
    measureApiCall: performanceMonitor.measureApiCall.bind(performanceMonitor),
    measureRouteChange: performanceMonitor.measureRouteChange.bind(performanceMonitor),
    getMetrics: performanceMonitor.getMetrics.bind(performanceMonitor),
    getSummary: performanceMonitor.getSummary.bind(performanceMonitor),
  };
}

/**
 * Performance decorator for measuring function execution time
 */
export function measurePerformance(metricName: string) {
  return function (_target: any, _propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value;

    descriptor.value = async function (...args: unknown[]) {
      return performanceMonitor.measureCustomMetric(metricName, () => method.apply(this, args));
    };

    return descriptor;
  };
}

/**
 * Utility to check if performance API is available
 */
export function isPerformanceSupported(): boolean {
  return (
    typeof window !== 'undefined' && 'performance' in window && 'PerformanceObserver' in window
  );
}

/**
 * Get current Core Web Vitals
 */
export function getCurrentWebVitals(): WebVitalsMetrics {
  const metrics = performanceMonitor.getMetrics();

  return {
    lcp: metrics.find((m) => m.name === 'LCP'),
    fid: metrics.find((m) => m.name === 'FID'),
    cls: metrics.find((m) => m.name === 'CLS'),
    fcp: metrics.find((m) => m.name === 'FCP'),
    ttfb: metrics.find((m) => m.name === 'TTFB'),
  };
}
