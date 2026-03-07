'use client';

import React from 'react';
import { ChatMessage } from '@/lib/websocket/types';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { Check, CheckCheck, Clock, AlertCircle } from 'lucide-react';
import { TrustIndicator } from './TrustIndicator';
import { StreamingMessageIndicator } from './StreamingMessageIndicator';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';

interface MessageProps {
  message: ChatMessage;
  showTrustIndicator?: boolean;
}

export function Message({ message, showTrustIndicator = false }: MessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isStreaming = message.isStreaming || false;

  // Process code blocks
  React.useEffect(() => {
    if (message.codeBlocks?.length && !isStreaming) {
      Prism.highlightAll();
    }
  }, [message.codeBlocks, isStreaming]);

  // Status icon
  const StatusIcon = () => {
    // Show streaming indicator for agent messages
    if (!isUser && isStreaming) {
      return <StreamingMessageIndicator />;
    }

    if (!isUser) return null;

    switch (message.status) {
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

  return (
    <div
      className={cn(
        'flex gap-3 group',
        isUser && 'flex-row-reverse',
        isSystem && 'justify-center'
      )}
    >
      {/* Avatar */}
      {!isSystem && (
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold flex-shrink-0',
            isUser
              ? 'bg-gradient-to-br from-purple-500 to-pink-600'
              : 'bg-gradient-to-br from-blue-500 to-purple-600'
          )}
        >
          {isUser ? 'U' : 'A'}
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          'flex flex-col gap-1 max-w-[70%]',
          isUser && 'items-end',
          isSystem && 'max-w-full w-full'
        )}
      >
        {/* Trust Indicator for Agent Messages */}
        {showTrustIndicator && !isUser && !isSystem && message.trustLevel !== undefined && (
          <div className="mb-1">
            <TrustIndicator trustLevel={message.trustLevel} size="sm" />
          </div>
        )}

        {/* Message Bubble */}
        <div
          className={cn(
            'rounded-lg px-4 py-2 transition-all relative',
            isUser
              ? 'bg-primary text-primary-foreground'
              : isSystem
              ? 'bg-muted text-center italic text-muted-foreground border'
              : 'bg-muted',
            isStreaming && !isUser && 'border-l-2 border-blue-500 animate-pulse-subtle',
            'group-hover:shadow-md'
          )}
        >
          {/* Text Content */}
          <div className={cn(
            'whitespace-pre-wrap break-words',
            isStreaming && 'opacity-90'
          )}>
            {message.content}
            {isStreaming && !message.content && (
              <span className="text-muted-foreground italic">Thinking...</span>
            )}
          </div>

          {/* Code Blocks */}
          {message.codeBlocks?.map((block, index) => (
            <div key={index} className="mt-2">
              {block.filename && (
                <div className="text-xs text-muted-foreground mb-1">
                  {block.filename}
                </div>
              )}
              <pre className="!bg-zinc-900 rounded-md p-3 overflow-x-auto">
                <code className={`language-${block.language}`}>
                  {block.code}
                </code>
              </pre>
            </div>
          ))}

          {/* Attachments */}
          {message.attachments?.map((attachment) => (
            <div
              key={attachment.id}
              className="mt-2 flex items-center gap-2 text-sm"
            >
              <div className="w-8 h-8 bg-background rounded flex items-center justify-center">
                📎
              </div>
              <div className="flex-1">
                <div className="font-medium">{attachment.name}</div>
                <div className="text-xs text-muted-foreground">
                  {(attachment.size / 1024).toFixed(1)} KB
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Timestamp and Status */}
        <div className={cn(
          'flex items-center gap-1 text-xs text-muted-foreground px-1',
          isUser && 'flex-row-reverse'
        )}>
          <span>{format(new Date(message.timestamp), 'HH:mm')}</span>
          <StatusIcon />
        </div>
      </div>
    </div>
  );
}