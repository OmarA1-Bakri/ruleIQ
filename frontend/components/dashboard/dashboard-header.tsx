'use client';

import { Search, Bell, Clock, AlertTriangle, Users, User } from 'lucide-react';
import * as React from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { TooltipProvider } from '@/components/ui/tooltip';
import { usePresenceChannel } from '@/lib/hooks/use-pusher';

export function DashboardHeader() {
  const [searchValue, setSearchValue] = React.useState('');
  const [isFeatureEnabled, setIsFeatureEnabled] = React.useState(true);

  // Presence channel for online users
  const { connectionState, members, onlineCount } = usePresenceChannel();

  // Check if Pusher is configured
  React.useEffect(() => {
    setIsFeatureEnabled(!!process.env.NEXT_PUBLIC_PUSHER_KEY);
  }, []);
  const [timeUntilAudit, setTimeUntilAudit] = React.useState({
    days: 15,
    hours: 8,
    minutes: 42,
    seconds: 30,
  });

  // Countdown timer effect
  React.useEffect(() => {
    const timer = setInterval(() => {
      setTimeUntilAudit((prev) => {
        let { days, hours, minutes, seconds } = prev;

        if (seconds > 0) {
          seconds--;
        } else if (minutes > 0) {
          minutes--;
          seconds = 59;
        } else if (hours > 0) {
          hours--;
          minutes = 59;
          seconds = 59;
        } else if (days > 0) {
          days--;
          hours = 23;
          minutes = 59;
          seconds = 59;
        }

        return { days, hours, minutes, seconds };
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTime = (value: number) => value.toString().padStart(2, '0');

  return (
    <TooltipProvider>
      <header
        className="flex h-16 shrink-0 items-center justify-between gap-4 border-b px-6"
        style={{
          borderBottomColor: 'rgba(233, 236, 239, 0.2)',
        }}
      >
        {/* Search Bar */}
        <div className="flex-1">
          <div className="relative max-w-md">
            <Search
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
              style={{ color: '#8b5cf657D' }}
            />
            <Input
              type="search"
              placeholder="Search compliance data, policies, reports..."
              className="w-full border-0 py-2 pl-10 pr-4 text-sm focus-visible:ring-1 focus-visible:ring-offset-0"
              style={{
                backgroundColor: 'rgba(240, 234, 214, 0.1)',
                color: '#8b5cf6AD6',
                borderColor: 'rgba(233, 236, 239, 0.2)',
              }}
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
            />
          </div>
        </div>

        {/* Countdown Clock */}
        <div className="flex flex-1 justify-center">
          <div className="flex items-center space-x-2 rounded-lg bg-purple-50 px-3 py-1">
            <Clock className="h-4 w-4 text-purple-600" />
            <div className="flex items-center space-x-1 font-mono text-sm text-neutral-700">
              <span className="text-xs text-neutral-500">Next Audit:</span>
              <span className="font-semibold">{formatTime(timeUntilAudit.days)}d</span>
              <span className="text-neutral-400">:</span>
              <span className="font-semibold">{formatTime(timeUntilAudit.hours)}h</span>
              <span className="text-neutral-400">:</span>
              <span className="font-semibold">{formatTime(timeUntilAudit.minutes)}m</span>
              <span style={{ color: '#8b5cf657D' }}>:</span>
              <span className="font-semibold">{formatTime(timeUntilAudit.seconds)}s</span>
            </div>
          </div>
        </div>

        {/* Online Presence Indicator */}
        <div className="flex items-center gap-4">
          {isFeatureEnabled && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex items-center gap-2 hover:bg-white/10"
                >
                  <Users className="h-4 w-4" />
                  <span className="text-sm">
                    {connectionState === 'connected' ? onlineCount : '--'}
                  </span>
                  <div className={`h-2 w-2 rounded-full ${
                    connectionState === 'connected'
                      ? 'bg-green-500 animate-pulse'
                      : connectionState === 'connecting'
                      ? 'bg-yellow-500 animate-pulse'
                      : 'bg-gray-400'
                  }`} />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuLabel>Online Users</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {connectionState === 'connected' && members.length > 0 ? (
                  <div className="max-h-60 overflow-y-auto">
                    {members.map((member: any) => (
                      <DropdownMenuItem key={member.id} className="flex items-center gap-2">
                        <User className="h-3 w-3" />
                        <span className="text-sm">{member.info?.name || `User ${member.id}`}</span>
                      </DropdownMenuItem>
                    ))}
                  </div>
                ) : connectionState === 'connecting' ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    Connecting...
                  </div>
                ) : (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    {!isFeatureEnabled ? 'Real-time disabled' : 'No users online'}
                  </div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>

        {/* Alerts Indicator */}
        <div className="flex flex-1 justify-end">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="relative hover:bg-white/10"
                style={{ color: '#8b5cf6AD6' }}
              >
                <Bell className="h-5 w-5" />
                <Badge
                  className="absolute -right-1 -top-1 flex h-5 w-5 animate-pulse items-center justify-center rounded-full p-0 text-xs"
                  style={{
                    backgroundColor: '#8b5cf6F61',
                    color: '#ffffffFFF',
                  }}
                >
                  5
                </Badge>
                <span className="sr-only">View alerts (5 new)</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-96"
              style={{
                backgroundColor: '#8b5cf6AD6',
                borderColor: 'rgba(233, 236, 239, 0.2)',
              }}
            >
              <DropdownMenuLabel
                className="flex items-center justify-between"
                style={{ color: '#8b5cf6147' }}
              >
                <span>Alerts & Notifications</span>
                <Badge
                  variant="secondary"
                  className="text-xs"
                  style={{ backgroundColor: '#8b5cf6F61', color: '#ffffffFFF' }}
                >
                  5 new
                </Badge>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <div className="max-h-80 overflow-y-auto">
                <div className="space-y-1">
                  <div className="hover:bg-grey-300/20 rounded-sm p-3">
                    <div className="flex items-start space-x-3">
                      <AlertTriangle className="mt-0.5 h-4 w-4" style={{ color: '#8b5cf6107' }} />
                      <div className="flex-1 space-y-1">
                        <div className="text-sm font-medium" style={{ color: '#8b5cf6147' }}>
                          GDPR Assessment Overdue
                        </div>
                        <div className="text-xs" style={{ color: '#8b5cf657D' }}>
                          The quarterly GDPR assessment was due 2 days ago. Please complete
                          immediately.
                        </div>
                        <div className="text-xs" style={{ color: '#8b5cf657D' }}>
                          2 hours ago
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  );
}
