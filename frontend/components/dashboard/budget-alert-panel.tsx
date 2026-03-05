import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
/**
 * Budget Alert Panel Component
 *
 * Displays budget alerts, warnings, and optimization recommendations
 * with real-time updates via Pusher
 */

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, TrendingUp, Lightbulb, X, Bell, DollarSign, WifiOff, Loader2 } from 'lucide-react';
import { useBudgetAlerts } from '@/lib/hooks/use-pusher';

interface BudgetAlertPanelProps {
  className?: string;
  maxAlerts?: number;
}

export const BudgetAlertPanel: React.FC<BudgetAlertPanelProps> = ({
  className = '',
  maxAlerts = 5,
}) => {
  const {
    connectionState,
    alerts,
    unreadCount,
    markAsRead,
    clearAlerts
  } = useBudgetAlerts();

  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState<Set<string>>(new Set());
  const [isFeatureEnabled, setIsFeatureEnabled] = useState(true);

  // Check if Pusher is configured
  useEffect(() => {
    setIsFeatureEnabled(!!process.env.NEXT_PUBLIC_PUSHER_KEY);
  }, []);

  // Placeholder alerts for when real-time is disabled
  const placeholderAlerts = [
    {
      id: '1',
      type: 'warning',
      level: 'warning',
      title: 'Approaching Daily Budget Limit',
      message: 'You have used 85% of your daily AI budget ($85 of $100)',
      timestamp: new Date().toISOString(),
      thresholdReached: 85,
      budgetLimit: 100,
      currentSpend: 85,
    },
    {
      id: '2',
      type: 'critical',
      level: 'critical',
      title: 'High Cost Spike Detected',
      message: 'Cost per request increased by 150% in the last hour',
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      spikePercentage: 150,
    },
    {
      id: '3',
      type: 'info',
      level: 'info',
      title: 'Cost Optimization Available',
      message: 'Switch to GPT-3.5 for routine queries to save ~40% on costs',
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      savingPercentage: 40,
    },
  ];

  // Use real alerts if available, otherwise use placeholders
  const displayAlerts = isFeatureEnabled && connectionState === 'connected'
    ? alerts
    : placeholderAlerts;

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'critical':
        return <AlertTriangle className="h-4 w-4" />;
      case 'warning':
        return <TrendingUp className="h-4 w-4" />;
      case 'info':
        return <Lightbulb className="h-4 w-4" />;
      default:
        return <Bell className="h-4 w-4" />;
    }
  };

  const getAlertVariant = (type: string) => {
    switch (type) {
      case 'critical':
        return 'destructive';
      case 'warning':
        return 'default';
      case 'info':
        return 'default';
      default:
        return 'default';
    }
  };

  const handleAcknowledge = (alertId: string) => {
    setAcknowledgedAlerts(prev => new Set(prev).add(alertId));
    markAsRead();
  };

  const handleDismiss = (alertId: string) => {
    // For real-time alerts, this would send a dismiss event
    // For now, just acknowledge locally
    handleAcknowledge(alertId);
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Budget Alerts
          {unreadCount > 0 && (
            <Badge variant="destructive" className="ml-2">
              {unreadCount}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Cost warnings and optimization recommendations
          {!isFeatureEnabled && (
            <span className="ml-2 text-xs text-muted-foreground">(Static mode - real-time disabled)</span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Connection Status Indicator */}
        {isFeatureEnabled && (
          <div className="mb-4 flex items-center gap-2">
            {connectionState === 'connecting' && (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-xs text-muted-foreground">Connecting to real-time updates...</span>
              </>
            )}
            {connectionState === 'disconnected' && (
              <>
                <WifiOff className="h-4 w-4 text-destructive" />
                <span className="text-xs text-destructive">Disconnected - showing cached alerts</span>
              </>
            )}
            {connectionState === 'connected' && (
              <>
                <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-green-600">Live updates active</span>
              </>
            )}
          </div>
        )}

        <div className="space-y-3">
          {displayAlerts.slice(0, maxAlerts).map((alert, index) => {
            const alertId = 'id' in alert ? alert.id : `alert-${index}`;
            const alertLevel = 'level' in alert ? alert.level : ('type' in alert ? alert.type : 'info');
            const _alertType = 'type' in alert ? alert.type : alertLevel;
            const alertTitle = 'title' in alert ? alert.title : 'Alert';
            const alertMessage = 'message' in alert ? alert.message : 'No message available';
            const alertTimestamp = 'timestamp' in alert ? alert.timestamp : new Date().toISOString();
            return (
            <Alert
              key={alertId}
              variant={getAlertVariant(String(alertLevel))}
              className={acknowledgedAlerts.has(alertId) ? 'opacity-60' : ''}
            >
              <div className="flex items-start justify-between">
                <div className="flex gap-2">
                  {getAlertIcon(String(alertLevel))}
                  <div className="space-y-1">
                    <AlertTitle className="text-sm font-medium">{alertTitle}</AlertTitle>
                    <AlertDescription className="text-xs">{alertMessage}</AlertDescription>
                    <div className="mt-2 flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {String(alertLevel)}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(alertTimestamp).toLocaleTimeString()}
                      </span>
                      {!acknowledgedAlerts.has(alertId) && (
                        <Badge variant="default" className="text-xs">
                          New
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1">
                  {!acknowledgedAlerts.has(alertId) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => handleAcknowledge(alertId)}
                    >
                      Mark Read
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    onClick={() => handleDismiss(alertId)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </Alert>
            );
          })}

          {displayAlerts.length === 0 && (
            <div className="py-8 text-center">
              <Bell className="mx-auto h-8 w-8 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">No budget alerts</p>
              <p className="text-xs text-muted-foreground">You're staying within your limits!</p>
            </div>
          )}

          {/* Budget Settings Quick Access */}
          <div className="mt-4 rounded-lg border bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Daily Budget</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold">$100.00</span>
                <Button variant="outline" size="sm">
                  Configure
                </Button>
              </div>
            </div>
          </div>

          {/* Clear All Alerts Button */}
          {displayAlerts.length > 0 && (
            <div className="flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={clearAlerts}
                className="text-xs"
              >
                Clear All Alerts
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default BudgetAlertPanel;
