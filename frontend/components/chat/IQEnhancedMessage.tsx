'use client';

import React, { useState } from 'react';
import { ChatMessage } from '@/types/api';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { 
  Check, 
  CheckCheck, 
  Clock, 
  AlertCircle, 
  Brain,
  User,
  Settings,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IQComplianceResponse } from './IQComplianceResponse';
import { IQTrustIndicator } from './IQTrustIndicator';
import { useIQAgentStore } from '@/lib/stores/iq-agent.store';

interface IQEnhancedMessageProps {
  message: ChatMessage;
  showTrustIndicator?: boolean;
  showTimestamp?: boolean;
  className?: string;
}

export function IQEnhancedMessage({ 
  message, 
  showTrustIndicator = true,
  showTimestamp = true,
  className 
}: IQEnhancedMessageProps) {
  const [showFullResponse, setShowFullResponse] = useState(false);
  const { currentResponse } = useIQAgentStore();
  
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isIQAgent = message.metadata?.source === 'iq_agent';

  // Status icon for user messages
  const StatusIcon = () => {
    if (!isUser) return null;

    switch (message.metadata?.status) {
      case 'sending':
        return <Clock className="w-3 h-3 text-muted-foreground animate-pulse" />;
      case 'sent':
        return <Check className="w-3 h-3 text-muted-foreground" />;
      case 'delivered':
        return <CheckCheck className="w-3 h-3 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-3 h-3 text-destructive" />;
      default:
        return null;
    }
  };

  // Avatar component
  const Avatar = () => {
    if (isSystem) return null;

    const avatarClass = cn(
      'w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold flex-shrink-0',
      isUser 
        ? 'bg-gradient-to-br from-purple-500 to-pink-600'
        : isIQAgent
        ? 'bg-gradient-to-br from-blue-500 to-purple-600'
        : 'bg-gradient-to-br from-gray-500 to-gray-600'
    );

    return (
      <div className={avatarClass}>
        {isUser ? (
          <User className="w-4 h-4" />
        ) : isIQAgent ? (
          <Brain className="w-4 h-4" />
        ) : (
          <Settings className="w-4 h-4" />
        )}
      </div>
    );
  };

  return (
    <div className={cn('space-y-3', className)}>
      {/* Standard Message Layout */}
      <div
        className={cn(
          'flex gap-3 group',
          isUser && 'flex-row-reverse',
          isSystem && 'justify-center'
        )}
      >
        <Avatar />

        {/* Message Content */}
        <div
          className={cn(
            'flex flex-col gap-2 max-w-[70%]',
            isUser && 'items-end',
            isSystem && 'max-w-full w-full',
            isIQAgent && 'max-w-full w-full'
          )}
        >
          {/* Trust Indicator for IQ Agent Messages */}
          {showTrustIndicator && isIQAgent && message.metadata?.trust_level && (
            <IQTrustIndicator 
              trustLevel={message.metadata.trust_level}
              confidenceScore={message.metadata.confidence_score || 0}
              variant="compact"
              size="sm"
            />
          )}

          {/* Message Bubble */}
          <div
            className={cn(
              'rounded-lg px-4 py-3 transition-all relative',
              isUser
                ? 'bg-primary text-primary-foreground'
                : isSystem
                ? 'bg-muted text-center italic text-muted-foreground border'
                : isIQAgent
                ? 'bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200'
                : 'bg-muted',
              'group-hover:shadow-md'
            )}
          >
            {/* IQ Agent Header */}
            {isIQAgent && (
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-blue-200">
                <Brain className="w-4 h-4 text-blue-600" />
                <span className="font-medium text-blue-700">IQ Agent Analysis</span>
                {message.metadata?.confidence_score && (
                  <span className="text-xs text-blue-600 ml-auto">
                    {message.metadata.confidence_score}% Confidence
                  </span>
                )}
              </div>
            )}

            {/* Text Content */}
            <div className="whitespace-pre-wrap break-words">
              {message.content}
            </div>

            {/* IQ Agent Response Metrics */}
            {isIQAgent && message.metadata && (
              <div className="mt-3 pt-2 border-t border-blue-200 flex items-center justify-between text-xs text-blue-600">
                <div className="flex items-center gap-4">
                  {message.metadata.evidence_count && (
                    <span>{message.metadata.evidence_count} sources</span>
                  )}
                  {message.metadata.graph_nodes && (
                    <span>{message.metadata.graph_nodes} nodes analyzed</span>
                  )}
                  {message.metadata.response_time && (
                    <span>{message.metadata.response_time}ms</span>
                  )}
                </div>
                
                {currentResponse && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowFullResponse(!showFullResponse)}
                    className="h-auto p-1 text-xs text-blue-600 hover:text-blue-800"
                  >
                    {showFullResponse ? (
                      <>
                        <ChevronUp className="w-3 h-3 mr-1" />
                        Hide Details
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-3 h-3 mr-1" />
                        Show Details
                      </>
                    )}
                  </Button>
                )}
              </div>
            )}
          </div>

          {/* Timestamp and Status */}
          {showTimestamp && (
            <div className={cn(
              'flex items-center gap-1 text-xs text-muted-foreground px-1',
              isUser && 'flex-row-reverse'
            )}>
              <span>{format(new Date(message.created_at), 'HH:mm')}</span>
              <StatusIcon />
            </div>
          )}
        </div>
      </div>

      {/* Full IQ Agent Response Details */}
      {showFullResponse && isIQAgent && currentResponse && (() => {
        // Adapt the IQAgentResponse to ExtendedIQResponse format
        const adaptedResponse: any = {
          success: true,
          data: currentResponse,
          summary: currentResponse.llm_response || 'No summary available',
          trust_level: 'helper',
          confidence_score: 85,
          response_time_ms: 2500,
          evidence: [] // Would need to extract from artifacts if available
        };
        
        // Only add optional properties if they have valid data
        if (currentResponse.artifacts?.action_plan && currentResponse.next_actions?.length) {
          adaptedResponse.action_plan = {
            immediate_actions: currentResponse.next_actions.map(action => ({
              title: action.action,
              description: action.action,
              priority: action.priority,
              estimated_effort: 'Medium'
            }))
          };
        }
        
        if (currentResponse.artifacts?.risk_assessment) {
          adaptedResponse.risk_assessment = {
            overall_risk_level: currentResponse.artifacts.risk_assessment.overall_risk_level || 'medium',
            identified_risks: []
          };
        }
        
        if (currentResponse.graph_context) {
          adaptedResponse.graph_analysis = {
            nodes_accessed: currentResponse.graph_context.nodes_traversed || 0,
            relationships_traversed: 0,
            relevant_frameworks: [],
            confidence_factors: {
              data_completeness: 0.8
            }
          };
        }
        
        return (
          <div className="ml-11 mt-4">
            <IQComplianceResponse 
              response={adaptedResponse}
              className="border-l-2 border-blue-200 pl-4"
            />
          </div>
        );
      })()}
    </div>
  );
}