/**
 * React Performance Optimization Module for RuleIQ.
 * Implements code splitting, memoization, lazy loading, and virtualization.
 */

import React, { memo, useMemo, useCallback, lazy, Suspense, ComponentType } from 'react';
import dynamic from 'next/dynamic';
// @ts-expect-error react-window types may not match
import { FixedSizeList as List } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';

// Simple loading spinner component
const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-4">
    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900"></div>
  </div>
);

// ============================================
// Code Splitting & Lazy Loading
// ============================================

/**
 * Dynamic import with loading fallback
 */
export function lazyLoadComponent<T extends ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>,
  fallback: React.ReactNode = <LoadingSpinner />
) {
  const LazyComponent = lazy(importFunc);

  const WrappedComponent = (props: React.ComponentProps<T>) => (
    <Suspense fallback={fallback}>
      <LazyComponent {...props} />
    </Suspense>
  );
  WrappedComponent.displayName = `LazyLoaded(${importFunc.toString().slice(0, 50)})`;
  return WrappedComponent;
}

/**
 * Next.js dynamic import with options
 */
export function dynamicImport<P = {}>(
  importFunc: () => Promise<{ default: ComponentType<P> }>,
  options?: {
    loading?: () => React.JSX.Element;
    ssr?: boolean;
  }
) {
  return dynamic(importFunc, {
    loading: options?.loading || (() => <LoadingSpinner />),
    ssr: options?.ssr ?? true,
  });
}

// Lazy load heavy components
export const LazyAssessmentWizard = lazyLoadComponent(
  () => import('@/components/assessments/AssessmentWizard').then(module => ({ default: module.AssessmentWizard }))
);

// export const LazyDashboard = lazyLoadComponent(
//   () => import('@/components/dashboard/Dashboard')
// );

// export const LazyReportGenerator = lazyLoadComponent(
//   () => import('@/components/reports/ReportGenerator')
// );

// export const LazyEvidenceManager = lazyLoadComponent(
//   () => import('@/components/evidence/EvidenceManager')
// );

// ============================================
// Memoization Utilities
// ============================================

/**
 * Enhanced memo with deep comparison
 */
export function deepMemo<P extends object>(
  Component: React.FC<P>,
  propsAreEqual?: (prevProps: P, nextProps: P) => boolean
): React.NamedExoticComponent<P> {
  return memo(Component, propsAreEqual || deepEqual);
}

/**
 * Deep equality check for props
 */
function deepEqual<T>(a: T, b: T): boolean {
  if (a === b) return true;
  
  if (typeof a !== 'object' || typeof b !== 'object') return false;
  if (a === null || b === null) return false;
  
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  
  if (keysA.length !== keysB.length) return false;
  
  for (const key of keysA) {
    if (!keysB.includes(key)) return false;
    if (!deepEqual((a as any)[key], (b as any)[key])) return false;
  }
  
  return true;
}

/**
 * Memoized expensive computation hook
 */
export function useExpensiveComputation<T>(
  computeFn: () => T,
  deps: React.DependencyList
): T {
  return useMemo(computeFn, deps);
}

/**
 * Memoized callback with stable reference
 */
export function useStableCallback<T extends (...args: any[]) => any>(
  callback: T,
  deps: React.DependencyList
): T {
  return useCallback(callback, deps);
}

// ============================================
// Virtualization Components
// ============================================

interface VirtualListProps<T> {
  items: T[];
  height: number;
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
  overscan?: number;
}

/**
 * Virtualized list for large datasets
 */
export function VirtualList<T>({
  items,
  height,
  itemHeight,
  renderItem,
  overscan = 5,
}: VirtualListProps<T>) {
  const Row = useCallback(
    ({ index, style }: { index: number; style: React.CSSProperties }) => (
      <div style={style}>{renderItem(items[index], index)}</div>
    ),
    [items, renderItem]
  );
  
  return (
    <List
      height={height}
      itemCount={items.length}
      itemSize={itemHeight}
      width="100%"
      overscanCount={overscan}
    >
      {Row}
    </List>
  );
}

/**
 * Auto-sized virtual list
 */
export function AutoVirtualList<T>({
  items,
  itemHeight,
  renderItem,
  overscan = 5,
}: Omit<VirtualListProps<T>, 'height'>) {
  return (
    <AutoSizer>
      {({ height, width }) => (
        <List
          height={height}
          width={width}
          itemCount={items.length}
          itemSize={itemHeight}
          overscanCount={overscan}
        >
          {({ index, style }: { index: number; style: React.CSSProperties }) => (
            <div style={style}>{renderItem(items[index], index)}</div>
          )}
        </List>
      )}
    </AutoSizer>
  );
}

// ============================================
// Performance Monitoring
// ============================================

/**
 * Performance observer for React components
 */
export class PerformanceMonitor {
  private observer: PerformanceObserver | null = null;
  private metrics: Map<string, number[]> = new Map();
  
  start() {
    if (typeof window === 'undefined' || !window.PerformanceObserver) return;
    
    this.observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'measure') {
          this.recordMetric(entry.name, entry.duration);
        }
      }
    });
    
    this.observer.observe({ entryTypes: ['measure'] });
  }
  
  stop() {
    this.observer?.disconnect();
  }
  
  measure(name: string, startMark: string, endMark: string) {
    if (typeof window !== 'undefined' && window.performance) {
      performance.measure(name, startMark, endMark);
    }
  }
  
  mark(name: string) {
    if (typeof window !== 'undefined' && window.performance) {
      performance.mark(name);
    }
  }
  
  private recordMetric(name: string, duration: number) {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }
    this.metrics.get(name)!.push(duration);
    
    // Log slow renders
    if (duration > 16) {
      console.warn(`Slow render detected: ${name} took ${duration.toFixed(2)}ms`);
    }
  }
  
  getMetrics() {
    const result: Record<string, any> = {};
    
    this.metrics.forEach((values, name) => {
      const sorted = values.sort((a, b) => a - b);
      result[name] = {
        count: values.length,
        mean: values.reduce((a, b) => a + b, 0) / values.length,
        median: sorted[Math.floor(sorted.length / 2)],
        p95: sorted[Math.floor(sorted.length * 0.95)],
        p99: sorted[Math.floor(sorted.length * 0.99)],
      };
    });
    
    return result;
  }
}

// ============================================
// Optimized Hooks
// ============================================

/**
 * Debounced value hook
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = React.useState(value);
  
  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);
  
  return debouncedValue;
}

/**
 * Throttled callback hook
 */
export function useThrottledCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const lastRun = React.useRef(Date.now());
  
  return useCallback(
    ((...args) => {
      if (Date.now() - lastRun.current >= delay) {
        lastRun.current = Date.now();
        return callback(...args);
      }
    }) as T,
    [callback, delay]
  );
}

/**
 * Intersection observer hook for lazy loading
 */
export function useIntersectionObserver(
  ref: React.RefObject<Element | null>,
  options?: IntersectionObserverInit
): boolean {
  const [isIntersecting, setIsIntersecting] = React.useState(false);
  
  React.useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);
    
    if (ref.current) {
      observer.observe(ref.current);
    }
    
    return () => {
      observer.disconnect();
    };
  }, [ref, options]);
  
  return isIntersecting;
}

// ============================================
// Image Optimization
// ============================================

interface OptimizedImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  lazy?: boolean;
  placeholder?: string;
  className?: string;
}

/**
 * Optimized image component with lazy loading
 */
export const OptimizedImage = memo<OptimizedImageProps>(({
  src,
  alt,
  width,
  height,
  lazy = true,
  placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3Crect width="1" height="1" fill="%23CCC"/%3E%3C/svg%3E',
  className,
}) => {
  const imgRef = React.useRef<HTMLImageElement>(null);
  const isVisible = useIntersectionObserver(imgRef, { threshold: 0.1 });
  const [imgSrc, setImgSrc] = React.useState(lazy ? placeholder : src);
  
  React.useEffect(() => {
    if (isVisible && lazy && imgSrc === placeholder) {
      setImgSrc(src);
    }
  }, [isVisible, lazy, src, placeholder, imgSrc]);
  
  return (
    <img
      ref={imgRef}
      src={imgSrc}
      alt={alt}
      width={width}
      height={height}
      className={className}
      loading={lazy ? 'lazy' : undefined}
    />
  );
});

OptimizedImage.displayName = 'OptimizedImage';

// ============================================
// Bundle Splitting Configuration
// ============================================

export const bundleSplitConfig = {
  // Vendor chunks
  vendor: ['react', 'react-dom', 'next'],
  
  // Feature chunks
  features: {
    assessments: ['@/components/assessments', '@/lib/assessment-engine'],
    dashboard: ['@/components/dashboard', '@/lib/stores/dashboard.store'],
    evidence: ['@/components/evidence', '@/lib/stores/evidence.store'],
    chat: ['@/components/chat', '@/lib/stores/chat.store'],
    reports: ['@/components/reports', '@/lib/api/reports.service'],
  },
  
  // Route-based splitting
  routes: {
    '/dashboard': ['dashboard', 'charts'],
    '/assessments': ['assessments', 'forms'],
    '/evidence': ['evidence', 'file-upload'],
    '/reports': ['reports', 'pdf-generation'],
  },
};

// ============================================
// Component Utilities
// ============================================

/**
 * Error boundary wrapper
 */
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error boundary caught:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback || <div>Something went wrong.</div>;
    }
    
    return this.props.children;
  }
}

// Export performance monitor singleton
export const performanceMonitor = new PerformanceMonitor();