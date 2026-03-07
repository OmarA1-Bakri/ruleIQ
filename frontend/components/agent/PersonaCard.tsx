'use client';

import React from 'react';
import { Agent, TrustLevel } from '@/lib/websocket/types';
import { cn } from '@/lib/utils';
import {
  Shield,
  Cpu,
  Zap,
  Brain,
  Code,
  FileText,
  Database,
  Globe,
  Play,
  Pause,
  Settings,
  Info,
  CheckCircle
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface PersonaCardProps {
  agent: Agent;
  isSelected: boolean;
  onSelect: () => void;
  onConfigure?: (agentId: string) => void;
  showDetails?: boolean;
}

// Agent persona types with icons
const personaIcons: Record<string, React.ElementType> = {
  'developer': Code,
  'analyst': Brain,
  'writer': FileText,
  'data-scientist': Database,
  'devops': Cpu,
  'security': Shield,
  'qa': Zap,
  'researcher': Globe,
  'default': Bot,
};

// Trust level configurations
const trustLevelConfig = {
  [TrustLevel.L0_OBSERVED]: {
    label: 'Observed',
    color: 'text-red-500',
    bgColor: 'bg-red-50 dark:bg-red-950',
    description: 'Requires approval for all actions',
  },
  [TrustLevel.L1_ASSISTED]: {
    label: 'Assisted',
    color: 'text-orange-500',
    bgColor: 'bg-orange-50 dark:bg-orange-950',
    description: 'Can suggest with approval',
  },
  [TrustLevel.L2_SUPERVISED]: {
    label: 'Supervised',
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-50 dark:bg-yellow-950',
    description: 'Executes with monitoring',
  },
  [TrustLevel.L3_DELEGATED]: {
    label: 'Delegated',
    color: 'text-blue-500',
    bgColor: 'bg-blue-50 dark:bg-blue-950',
    description: 'Autonomous in scope',
  },
  [TrustLevel.L4_AUTONOMOUS]: {
    label: 'Autonomous',
    color: 'text-green-500',
    bgColor: 'bg-green-50 dark:bg-green-950',
    description: 'Full autonomy',
  },
};

function Bot(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="18" height="10" x="3" y="11" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" x2="8" y1="16" y2="16" />
      <line x1="16" x2="16" y1="16" y2="16" />
    </svg>
  );
}

export function PersonaCard({
  agent,
  isSelected,
  onSelect,
  onConfigure,
  showDetails = false,
}: PersonaCardProps) {
  const Icon: React.ElementType = personaIcons[agent.personaType] || Bot;
  const trustConfig = agent.currentTrustLevel !== undefined
    ? trustLevelConfig[agent.currentTrustLevel]
    : null;

  // Mock performance metrics
  const metrics = {
    successRate: 92,
    avgResponseTime: 1.2,
    tasksCompleted: 156,
    uptime: 99.5,
  };

  return (
    <Card
      className={cn(
        "relative overflow-hidden cursor-pointer transition-all hover:shadow-lg",
        isSelected && "ring-2 ring-primary",
        !agent.isActive && "opacity-60"
      )}
      onClick={onSelect}
    >
      {/* Background Gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-600/5" />
      
      {/* Selected Indicator */}
      {isSelected && (
        <div className="absolute top-2 right-2">
          <CheckCircle className="w-5 h-5 text-primary" />
        </div>
      )}

      <div className="relative p-4 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center transition-all",
              agent.isActive
                ? "bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-lg"
                : "bg-muted text-muted-foreground"
            )}>
              {React.createElement(Icon, { className: "w-6 h-6" })}
            </div>
            <div>
              <h4 className="font-semibold">{agent.name}</h4>
              <p className="text-sm text-muted-foreground capitalize">
                {agent.personaType.replace('-', ' ')}
              </p>
            </div>
          </div>
          
          {/* Status Badge */}
          <Badge
            variant={agent.isActive ? "default" : "secondary"}
            className="text-xs"
          >
            {agent.isActive ? (
              <>
                <Play className="w-3 h-3 mr-1" />
                Active
              </>
            ) : (
              <>
                <Pause className="w-3 h-3 mr-1" />
                Inactive
              </>
            )}
          </Badge>
        </div>

        {/* Trust Level */}
        {trustConfig && (
          <div className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-full",
            trustConfig.bgColor
          )}>
            <Shield className={cn("w-4 h-4", trustConfig.color)} />
            <span className={cn("text-sm font-medium", trustConfig.color)}>
              L{agent.currentTrustLevel} - {trustConfig.label}
            </span>
          </div>
        )}

        {/* Capabilities */}
        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">Capabilities</div>
          <div className="flex flex-wrap gap-1">
            {agent.capabilities.slice(0, 4).map((capability) => (
              <Badge key={capability} variant="outline" className="text-xs">
                {capability}
              </Badge>
            ))}
            {agent.capabilities.length > 4 && (
              <Badge variant="outline" className="text-xs">
                +{agent.capabilities.length - 4} more
              </Badge>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        {showDetails && (
          <div className="grid grid-cols-2 gap-2 pt-2 border-t">
            <div>
              <div className="text-xs text-muted-foreground">Success Rate</div>
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium">{metrics.successRate}%</span>
                <Progress value={metrics.successRate} className="h-1 flex-1" />
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Response</div>
              <div className="text-sm font-medium">{metrics.avgResponseTime}s avg</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Tasks</div>
              <div className="text-sm font-medium">{metrics.tasksCompleted}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Uptime</div>
              <div className="text-sm font-medium">{metrics.uptime}%</div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={(e) => e.stopPropagation()}
              >
                <Info className="w-4 h-4 mr-1" />
                Details
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {React.createElement(Icon, { className: "w-5 h-5" })}
                  {agent.name}
                </DialogTitle>
                <DialogDescription>
                  {agent.personaType} Agent - {trustConfig?.description}
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4 mt-4">
                {/* Full Capabilities */}
                <div>
                  <h4 className="font-medium mb-2">Full Capabilities</h4>
                  <div className="flex flex-wrap gap-2">
                    {agent.capabilities.map((capability) => (
                      <Badge key={capability} variant="secondary">
                        {capability}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Configuration */}
                {agent.config && (
                  <div>
                    <h4 className="font-medium mb-2">Configuration</h4>
                    <pre className="bg-muted p-3 rounded-lg text-xs overflow-x-auto">
                      {JSON.stringify(agent.config, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Performance Metrics */}
                <div>
                  <h4 className="font-medium mb-2">Performance Metrics</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Success Rate</span>
                        <span className="text-sm font-medium">{metrics.successRate}%</span>
                      </div>
                      <Progress value={metrics.successRate} />
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Uptime</span>
                        <span className="text-sm font-medium">{metrics.uptime}%</span>
                      </div>
                      <Progress value={metrics.uptime} />
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mt-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Avg Response</div>
                      <div className="text-2xl font-bold">{metrics.avgResponseTime}s</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Tasks Done</div>
                      <div className="text-2xl font-bold">{metrics.tasksCompleted}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Trust Level</div>
                      <div className="text-2xl font-bold">L{agent.currentTrustLevel || 0}</div>
                    </div>
                  </div>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {onConfigure && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={(e) => {
                e.stopPropagation();
                onConfigure(agent.id);
              }}
            >
              <Settings className="w-4 h-4 mr-1" />
              Configure
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}