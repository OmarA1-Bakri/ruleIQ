'use client';

import React, { useState } from 'react';
import { Session, TrustLevel } from '@/lib/websocket/types';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
  Clock,
  MessageSquare,
  Activity,
  Download,
  Upload,
  Trash2,
  PlayCircle,
  PauseCircle,
  ChevronRight,
  Search,
  BarChart3,
  Shield
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface SessionManagerProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onExportSession: (sessionId: string) => void;
  onImportSession: (file: File) => void;
}

export function SessionManager({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  onExportSession,
  onImportSession,
}: SessionManagerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTrust, setFilterTrust] = useState<string>('all');
  const [showAnalytics, setShowAnalytics] = useState(false);

  // Filter sessions
  const filteredSessions = sessions.filter(session => {
    const matchesSearch = searchQuery === '' || 
      session.id.includes(searchQuery) ||
      session.agentId.includes(searchQuery);
    
    const matchesTrust = filterTrust === 'all' || 
      session.trustLevel === parseInt(filterTrust);
    
    return matchesSearch && matchesTrust;
  });

  // Sort sessions by most recent
  const sortedSessions = [...filteredSessions].sort((a, b) => 
    new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
  );

  // Calculate session analytics
  const analytics = {
    totalSessions: sessions.length,
    activeSessions: sessions.filter(s => !s.endedAt).length,
    totalMessages: sessions.reduce((acc, s) => acc + s.messages.length, 0),
    avgTrustLevel: sessions.reduce((acc, s) => acc + s.trustLevel, 0) / sessions.length || 0,
    avgDuration: sessions
      .filter(s => s.endedAt)
      .reduce((acc, s) => {
        const duration = new Date(s.endedAt!).getTime() - new Date(s.startedAt).getTime();
        return acc + duration;
      }, 0) / sessions.filter(s => s.endedAt).length || 0,
  };

  // Get trust level color
  const getTrustColor = (level: TrustLevel) => {
    switch (level) {
      case TrustLevel.L0_OBSERVED: return 'text-red-500';
      case TrustLevel.L1_ASSISTED: return 'text-orange-500';
      case TrustLevel.L2_SUPERVISED: return 'text-yellow-500';
      case TrustLevel.L3_DELEGATED: return 'text-blue-500';
      case TrustLevel.L4_AUTONOMOUS: return 'text-green-500';
      default: return 'text-gray-500';
    }
  };

  // Handle file import
  const handleFileImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onImportSession(file);
    }
  };

  return (
    <Card className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Session Manager
          </h3>
          <div className="flex items-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowAnalytics(!showAnalytics)}
                  >
                    <BarChart3 className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Analytics</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => document.getElementById('import-session')?.click()}
                  >
                    <Upload className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Import session</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <Button size="sm" onClick={onCreateSession}>
              New Session
            </Button>
          </div>
        </div>

        {/* Search and Filter */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={filterTrust} onValueChange={setFilterTrust}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Trust Level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Levels</SelectItem>
              <SelectItem value="0">L0 - Observed</SelectItem>
              <SelectItem value="1">L1 - Assisted</SelectItem>
              <SelectItem value="2">L2 - Supervised</SelectItem>
              <SelectItem value="3">L3 - Delegated</SelectItem>
              <SelectItem value="4">L4 - Autonomous</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Analytics Panel */}
      {showAnalytics && (
        <div className="border-b p-4 bg-muted/50">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <div className="text-2xl font-bold">{analytics.totalSessions}</div>
              <div className="text-xs text-muted-foreground">Total Sessions</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{analytics.activeSessions}</div>
              <div className="text-xs text-muted-foreground">Active</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{analytics.totalMessages}</div>
              <div className="text-xs text-muted-foreground">Messages</div>
            </div>
            <div>
              <div className="text-2xl font-bold">L{Math.round(analytics.avgTrustLevel)}</div>
              <div className="text-xs text-muted-foreground">Avg Trust</div>
            </div>
            <div>
              <div className="text-2xl font-bold">
                {Math.round(analytics.avgDuration / 60000)}m
              </div>
              <div className="text-xs text-muted-foreground">Avg Duration</div>
            </div>
          </div>
        </div>
      )}

      {/* Session List */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {sortedSessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No sessions found</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={onCreateSession}
              >
                Start New Session
              </Button>
            </div>
          ) : (
            sortedSessions.map((session) => {
              const isActive = session.id === activeSessionId;
              const isOngoing = !session.endedAt;
              const duration = session.endedAt
                ? new Date(session.endedAt).getTime() - new Date(session.startedAt).getTime()
                : Date.now() - new Date(session.startedAt).getTime();

              return (
                <Card
                  key={session.id}
                  className={cn(
                    "p-3 cursor-pointer transition-all hover:shadow-md",
                    isActive && "ring-2 ring-primary"
                  )}
                  onClick={() => onSelectSession(session.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        {isOngoing ? (
                          <PlayCircle className="w-4 h-4 text-green-500" />
                        ) : (
                          <PauseCircle className="w-4 h-4 text-muted-foreground" />
                        )}
                        <span className="font-medium text-sm">
                          Session {session.id.slice(0, 8)}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {session.messages.length} msgs
                        </Badge>
                      </div>
                      
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDistanceToNow(new Date(session.startedAt), { addSuffix: true })}
                        </span>
                        <span className="flex items-center gap-1">
                          <Activity className="w-3 h-3" />
                          {Math.round(duration / 60000)}m
                        </span>
                        <span className={cn("flex items-center gap-1", getTrustColor(session.trustLevel))}>
                          <Shield className="w-3 h-3" />
                          L{session.trustLevel}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={(e) => {
                                e.stopPropagation();
                                onExportSession(session.id);
                              }}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Export session</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteSession(session.id);
                              }}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete session</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>

                      {isActive && (
                        <ChevronRight className="w-4 h-4 text-primary" />
                      )}
                    </div>
                  </div>
                </Card>
              );
            })
          )}
        </div>
      </ScrollArea>

      {/* Hidden file input */}
      <input
        id="import-session"
        type="file"
        accept=".json"
        className="hidden"
        onChange={handleFileImport}
      />
    </Card>
  );
}