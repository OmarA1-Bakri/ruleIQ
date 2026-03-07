'use client';

import React, { Component, ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  AlertTriangle, 
  RefreshCw, 
  MessageCircle, 
  Shield,
  Bug
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface IQErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  errorId: string;
}

interface IQErrorBoundaryProps {
  children: ReactNode;
  fallbackComponent?: React.ComponentType<{
    error: Error;
    resetError: () => void;
    errorId: string;
  }>;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  className?: string;
}

class IQErrorBoundary extends Component<IQErrorBoundaryProps, IQErrorBoundaryState> {
  constructor(props: IQErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    };
  }

  static getDerivedStateFromError(error: Error): Partial<IQErrorBoundaryState> {
    return {
      hasError: true,
      error,
      errorId: `iq-error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    
    // Log to console for debugging
    console.error('IQ Agent Error:', error, errorInfo);
    
    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);

    // TODO: Send to error tracking service
    // trackError('iq_agent_error', {
    //   error: error.message,
    //   stack: error.stack,
    //   componentStack: errorInfo.componentStack,
    //   errorId: this.state.errorId
    // });
  }

  resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    });
  };

  render() {
    if (this.state.hasError) {
      const { fallbackComponent: FallbackComponent } = this.props;
      
      if (FallbackComponent && this.state.error) {
        return (
          <FallbackComponent 
            error={this.state.error}
            resetError={this.resetError}
            errorId={this.state.errorId}
          />
        );
      }

      return (
        <Card className={cn('border-l-4 border-l-red-500 bg-red-50', this.props.className)}>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-100">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div className="flex-1">
                <CardTitle className="text-lg text-red-700">
                  IQ Agent Error
                </CardTitle>
                <p className="text-sm text-red-600 mt-1">
                  An error occurred while processing your compliance query
                </p>
              </div>
              <Badge variant="outline" className="text-xs text-red-700 border-red-200">
                <Bug className="w-3 h-3 mr-1" />
                Error ID: {this.state.errorId}
              </Badge>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Error Details */}
            <div className="p-3 bg-red-100 rounded-lg border border-red-200">
              <h4 className="font-medium text-red-800 mb-2">What happened?</h4>
              <p className="text-sm text-red-700">
                {this.state.error?.message || 'An unexpected error occurred during GraphRAG analysis'}
              </p>
            </div>

            {/* Troubleshooting Steps */}
            <div>
              <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Troubleshooting Steps
              </h4>
              <div className="space-y-2 text-sm text-gray-700">
                <div className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">1</span>
                  <span>Try refreshing and asking your question again</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">2</span>
                  <span>Check your internet connection</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">3</span>
                  <span>Try rephrasing your compliance question</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">4</span>
                  <span>Use regular chat mode as a fallback</span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button 
                onClick={this.resetError}
                className="flex items-center gap-2"
                variant="outline"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </Button>
              
              <Button 
                onClick={() => window.location.reload()}
                variant="outline"
                className="flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh Page
              </Button>

              <Button 
                onClick={() => {
                  // Switch to regular chat mode
                  // This would trigger a state change in the parent component
                }}
                variant="secondary"
                className="flex items-center gap-2"
              >
                <MessageCircle className="w-4 h-4" />
                Use Regular Chat
              </Button>
            </div>

            {/* Technical Details (Collapsed by default) */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-600 hover:text-gray-800">
                  Technical Details (Development Only)
                </summary>
                <div className="mt-2 p-3 bg-gray-100 rounded text-xs font-mono overflow-auto max-h-40">
                  <div className="mb-2">
                    <strong>Error:</strong> {this.state.error.message}
                  </div>
                  <div className="mb-2">
                    <strong>Stack:</strong>
                    <pre className="whitespace-pre-wrap">{this.state.error.stack}</pre>
                  </div>
                  {this.state.errorInfo && (
                    <div>
                      <strong>Component Stack:</strong>
                      <pre className="whitespace-pre-wrap">{this.state.errorInfo.componentStack}</pre>
                    </div>
                  )}
                </div>
              </details>
            )}
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

export { IQErrorBoundary };

// Functional error fallback component for specific use cases
export function IQErrorFallback({ 
  error, 
  resetError, 
  errorId,
  showDetails = false 
}: {
  error: Error;
  resetError: () => void;
  errorId: string;
  showDetails?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
      <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
      <div className="flex-1">
        <h3 className="font-medium text-red-800">IQ Agent Unavailable</h3>
        <p className="text-sm text-red-600 mt-1">
          {error.message || 'Unable to process compliance query at this time'}
        </p>
        {showDetails && (
          <p className="text-xs text-red-500 mt-1">
            Error ID: {errorId}
          </p>
        )}
      </div>
      <Button 
        onClick={resetError}
        size="sm"
        variant="outline"
        className="flex items-center gap-1"
      >
        <RefreshCw className="w-3 h-3" />
        Retry
      </Button>
    </div>
  );
}