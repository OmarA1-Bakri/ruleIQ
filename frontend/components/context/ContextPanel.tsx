'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Settings,
  Save,
  Trash2,
  Plus,
  Search,
  Clock,
  Tag,
  Copy,
  Download
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';

interface ContextItem {
  id: string;
  key: string;
  value: any;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  timestamp: Date;
  source: 'user' | 'agent' | 'system';
  tags?: string[];
}

interface ContextPanelProps {
  context: Record<string, any>;
  onUpdateContext: (key: string, value: any) => void;
  onDeleteContext: (key: string) => void;
  onClearContext: () => void;
  className?: string;
}

export function ContextPanel({
  context,
  onUpdateContext,
  onDeleteContext,
  onClearContext,
  className,
}: ContextPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [selectedTab, setSelectedTab] = useState('current');

  // Convert context to items
  const contextItems: ContextItem[] = Object.entries(context).map(([key, value]) => ({
    id: key,
    key,
    value,
    type: Array.isArray(value) ? 'array' : typeof value as any,
    timestamp: new Date(), // In real app, track actual timestamps
    source: 'user', // In real app, track actual source
    tags: [], // In real app, support tagging
  }));

  // Filter items based on search
  const filteredItems = contextItems.filter(item =>
    item.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
    JSON.stringify(item.value).toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group items by type
  const groupedItems = filteredItems.reduce((acc, item) => {
    if (!acc[item.type]) acc[item.type] = [];
    acc[item.type]!.push(item);
    return acc;
  }, {} as Record<string, ContextItem[]>);

  // Start editing
  const startEdit = (key: string, value: any) => {
    setEditingKey(key);
    setEditValue(typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value));
  };

  // Save edit
  const saveEdit = () => {
    if (editingKey) {
      try {
        const parsed = editValue.startsWith('{') || editValue.startsWith('[')
          ? JSON.parse(editValue)
          : editValue;
        onUpdateContext(editingKey, parsed);
        setEditingKey(null);
      } catch (_e) {
        // If JSON parse fails, save as string
        onUpdateContext(editingKey, editValue);
        setEditingKey(null);
      }
    }
  };

  // Add new context item
  const addNewItem = () => {
    if (newKey && newValue) {
      try {
        const parsed = newValue.startsWith('{') || newValue.startsWith('[')
          ? JSON.parse(newValue)
          : newValue;
        onUpdateContext(newKey, parsed);
        setNewKey('');
        setNewValue('');
      } catch (_e) {
        onUpdateContext(newKey, newValue);
        setNewKey('');
        setNewValue('');
      }
    }
  };

  // Export context
  const exportContext = () => {
    const blob = new Blob([JSON.stringify(context, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `context-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy context to clipboard
  const copyContext = () => {
    navigator.clipboard.writeText(JSON.stringify(context, null, 2));
  };

  return (
    <Card className={cn("flex flex-col", className)}>
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            <h3 className="font-semibold">Context Management</h3>
          </div>
          <div className="flex items-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={copyContext}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Copy context</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={exportContext}
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export context</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={onClearContext}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Clear all context</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search context..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Content */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab} className="flex-1">
        <TabsList className="grid w-full grid-cols-3 p-4 h-auto">
          <TabsTrigger value="current">Current</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="add">Add New</TabsTrigger>
        </TabsList>

        {/* Current Context */}
        <TabsContent value="current" className="flex-1 p-4 pt-0">
          <ScrollArea className="h-[400px]">
            <Accordion type="multiple" className="space-y-2">
              {Object.entries(groupedItems).map(([type, items]) => (
                <AccordionItem key={type} value={type}>
                  <AccordionTrigger className="text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{type}</Badge>
                      <span>{items.length} items</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {items.map((item) => (
                        <div
                          key={item.id}
                          className="border rounded-lg p-3 space-y-2"
                        >
                          {editingKey === item.key ? (
                            <div className="space-y-2">
                              <Textarea
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                className="font-mono text-xs"
                                rows={5}
                              />
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  onClick={saveEdit}
                                >
                                  <Save className="w-3 h-3 mr-1" />
                                  Save
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setEditingKey(null)}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="font-medium text-sm">{item.key}</div>
                                  <div className="text-xs text-muted-foreground mt-1">
                                    <pre className="whitespace-pre-wrap">
                                      {typeof item.value === 'object'
                                        ? JSON.stringify(item.value, null, 2)
                                        : String(item.value)}
                                    </pre>
                                  </div>
                                </div>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6"
                                    onClick={() => startEdit(item.key, item.value)}
                                  >
                                    <Settings className="w-3 h-3" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6"
                                    onClick={() => onDeleteContext(item.key)}
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </Button>
                                </div>
                              </div>
                              {item.tags && item.tags.length > 0 && (
                                <div className="flex gap-1">
                                  {item.tags.map((tag) => (
                                    <Badge key={tag} variant="secondary" className="text-xs">
                                      <Tag className="w-3 h-3 mr-1" />
                                      {tag}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </ScrollArea>
        </TabsContent>

        {/* History */}
        <TabsContent value="history" className="p-4 pt-0">
          <div className="text-center text-muted-foreground py-8">
            <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Context history will be displayed here</p>
            <p className="text-sm mt-2">Track changes and revert to previous states</p>
          </div>
        </TabsContent>

        {/* Add New */}
        <TabsContent value="add" className="p-4 pt-0">
          <div className="space-y-4">
            <div>
              <Label htmlFor="newKey">Key</Label>
              <Input
                id="newKey"
                placeholder="Enter context key..."
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="newValue">Value (JSON or text)</Label>
              <Textarea
                id="newValue"
                placeholder="Enter value (supports JSON)..."
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                rows={5}
                className="font-mono text-sm"
              />
            </div>
            <Button
              onClick={addNewItem}
              disabled={!newKey || !newValue}
              className="w-full"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add to Context
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </Card>
  );
}