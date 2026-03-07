'use client';

import React, { useState } from 'react';
import { Agent } from '@/lib/websocket/types';
import { cn } from '@/lib/utils';
import {
  Search,
  Grid,
  List,
  Settings,
  Play,
  Shield,
  Cpu,
  Zap,
  Brain,
  Code,
  FileText,
  Database,
  Globe,
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
import { PersonaCard } from './PersonaCard';

interface AgentSelectorProps {
  agents: Agent[];
  selectedAgentId: string | null;
  onSelectAgent: (agentId: string) => void;
  onConfigureAgent?: (agentId: string) => void;
  className?: string;
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

// Mock agent categories for demo
const agentCategories = {
  'Technical': ['developer', 'devops', 'qa', 'security'],
  'Analytical': ['analyst', 'data-scientist', 'researcher'],
  'Creative': ['writer', 'designer'],
  'Specialized': ['compliance', 'legal', 'finance'],
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

export function AgentSelector({
  agents,
  selectedAgentId,
  onSelectAgent,
  onConfigureAgent,
  className,
}: AgentSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterCapability, setFilterCapability] = useState<string>('all');
  const [showOnlyActive, setShowOnlyActive] = useState(false);

  // Get unique capabilities from all agents
  const allCapabilities = Array.from(
    new Set(agents.flatMap(agent => agent.capabilities))
  );

  // Filter agents
  const filteredAgents = agents.filter(agent => {
    const matchesSearch = searchQuery === '' ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.personaType.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.capabilities.some(cap => cap.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesCategory = filterCategory === 'all' ||
      Object.entries(agentCategories).some(([cat, personas]) =>
        cat === filterCategory && personas.includes(agent.personaType)
      );
    
    const matchesCapability = filterCapability === 'all' ||
      agent.capabilities.includes(filterCapability);
    
    const matchesActive = !showOnlyActive || agent.isActive;
    
    return matchesSearch && matchesCategory && matchesCapability && matchesActive;
  });

  // Group agents by category
  const groupedAgents = filteredAgents.reduce((acc, agent) => {
    const category = Object.entries(agentCategories).find(([_, personas]) =>
      personas.includes(agent.personaType)
    )?.[0] || 'Other';
    
    if (!acc[category]) acc[category] = [];
    acc[category].push(agent);
    return acc;
  }, {} as Record<string, Agent[]>);

  return (
    <Card className={cn("flex flex-col", className)}>
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center gap-2">
            <Bot className="w-5 h-5" />
            Select Agent
          </h3>
          <div className="flex items-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={viewMode === 'grid' ? 'default' : 'ghost'}
                    size="icon"
                    onClick={() => setViewMode('grid')}
                  >
                    <Grid className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Grid view</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={viewMode === 'list' ? 'default' : 'ghost'}
                    size="icon"
                    onClick={() => setViewMode('list')}
                  >
                    <List className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>List view</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={showOnlyActive ? 'default' : 'ghost'}
                    size="icon"
                    onClick={() => setShowOnlyActive(!showOnlyActive)}
                  >
                    <Play className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Show only active</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          
          <div className="flex gap-2">
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {Object.keys(agentCategories).map(cat => (
                  <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={filterCapability} onValueChange={setFilterCapability}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Capability" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Capabilities</SelectItem>
                {allCapabilities.map(cap => (
                  <SelectItem key={cap} value={cap}>{cap}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Agent List/Grid */}
      <ScrollArea className="flex-1">
        <div className="p-4">
          {filteredAgents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No agents found</p>
              <p className="text-sm mt-2">Try adjusting your filters</p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredAgents.map((agent) => {
                const props: any = {
                  key: agent.id,
                  agent,
                  isSelected: agent.id === selectedAgentId,
                  onSelect: () => onSelectAgent(agent.id),
                };
                if (onConfigureAgent) {
                  props.onConfigure = onConfigureAgent;
                }
                return <PersonaCard key={agent.id} {...props} />;
              })}
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedAgents).map(([category, categoryAgents]) => (
                <div key={category}>
                  <h4 className="font-medium text-sm text-muted-foreground mb-2">
                    {category} ({categoryAgents.length})
                  </h4>
                  <div className="space-y-2">
                    {categoryAgents.map((agent) => {
                      const Icon: React.ElementType = personaIcons[agent.personaType] || Bot;
                      const isSelected = agent.id === selectedAgentId;
                      
                      return (
                        <Card
                          key={agent.id}
                          className={cn(
                            "p-3 cursor-pointer transition-all hover:shadow-md",
                            isSelected && "ring-2 ring-primary"
                          )}
                          onClick={() => onSelectAgent(agent.id)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className={cn(
                                "w-10 h-10 rounded-full flex items-center justify-center",
                                agent.isActive
                                  ? "bg-gradient-to-br from-blue-500 to-purple-600 text-white"
                                  : "bg-muted text-muted-foreground"
                              )}>
                                {React.createElement(Icon, { className: "w-5 h-5" })}
                              </div>
                              <div>
                                <div className="font-medium">{agent.name}</div>
                                <div className="text-sm text-muted-foreground">
                                  {agent.personaType}
                                </div>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              {agent.currentTrustLevel !== undefined && (
                                <Badge variant="outline" className="text-xs">
                                  L{agent.currentTrustLevel}
                                </Badge>
                              )}
                              
                              {agent.isActive ? (
                                <Badge variant="default" className="text-xs">
                                  Active
                                </Badge>
                              ) : (
                                <Badge variant="secondary" className="text-xs">
                                  Inactive
                                </Badge>
                              )}
                              
                              {onConfigureAgent && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onConfigureAgent(agent.id);
                                  }}
                                >
                                  <Settings className="w-4 h-4" />
                                </Button>
                              )}
                            </div>
                          </div>
                          
                          {agent.capabilities.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {agent.capabilities.slice(0, 3).map((cap) => (
                                <Badge key={cap} variant="secondary" className="text-xs">
                                  {cap}
                                </Badge>
                              ))}
                              {agent.capabilities.length > 3 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{agent.capabilities.length - 3}
                                </Badge>
                              )}
                            </div>
                          )}
                        </Card>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </Card>
  );
}