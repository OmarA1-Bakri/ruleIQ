'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ChatMessage,
  Agent,
  Session,
  ConnectionState,
  StreamingMessagePayload
} from '@/lib/websocket/types';
import { getWebSocketClient, disconnectWebSocket } from '@/lib/websocket/client';
import { categorizeError, getUserMessage, getRecoverySuggestion } from '@/lib/utils/websocket-error-handler';
import { useStreamingChat } from '@/lib/hooks/use-streaming-chat';
import { useTypingIndicator } from '@/lib/hooks/use-typing-indicator';
import { Message } from './Message';
import { TrustIndicator } from './TrustIndicator';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { ConnectionStatusIndicator } from './ConnectionStatusIndicator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

interface ChatContainerProps {
  agent: Agent;
  session: Session;
  onSessionEnd?: () => void;
}

export function ChatContainer({ agent, session, onSessionEnd: _onSessionEnd }: ChatContainerProps) {
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    connected: false,
    connecting: false,
    error: null,
    retryCount: 0
  });
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [agentTyping, setAgentTyping] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsClientRef = useRef<ReturnType<typeof getWebSocketClient> | null>(null);
  const { toast } = useToast();

  // Initialize streaming chat hook
  const {
    messages,
    isStreaming,
    handleStreamChunk,
    handleStreamComplete: _handleStreamComplete,
    handleStreamError: _handleStreamError,
    addMessage,
    updateMessage,
    clearMessages: _clearMessages
  } = useStreamingChat({
    onMessageComplete: (message) => {
      console.log('Message streaming complete:', message.id);
    },
    onStreamError: (error, _messageId) => {
      toast({
        title: 'Streaming Error',
        description: `Failed to receive message: ${error.message}`,
        variant: 'destructive',
      });
    }
  });

  // Initialize typing indicator hook with WebSocket client support
  const { handleTypingStart: _handleTypingStart, handleTypingStop } = useTypingIndicator({
    sessionId: session.id,
    agentId: agent.id,
    useWebSocketClient: true
  });

  // Initialize WebSocket connection
  useEffect(() => {
    // Get auth token from the same source as chat service
    const getAuthToken = () => {
      try {
        // Import useAuthStore dynamically to avoid dependency issues
        const authStore = require('@/lib/stores/auth.store').useAuthStore;
        return authStore.getState().getToken();
      } catch (error) {
        console.warn('Unable to get auth token:', error);
        return null;
      }
    };

    const baseWsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
    const authToken = getAuthToken();

    // Append auth token to WebSocket URL if available
    const wsUrl = authToken ? `${baseWsUrl}?token=${encodeURIComponent(authToken)}` : baseWsUrl;

    const wsClient = getWebSocketClient(wsUrl, {
      onOpen: () => {
        setConnectionState({
          connected: true,
          connecting: false,
          error: null,
          retryCount: 0,
          lastConnectedAt: new Date()
        });
        setConnectionError(null);
        toast({
          title: 'Connected',
          description: 'Connected to agent service',
        });
      },
      onClose: (event) => {
        setConnectionState(prev => ({
          ...prev,
          connected: false,
          connecting: false
        }));

        // Only show toast for unexpected disconnections
        if (event.code !== 1000) {
          const classification = categorizeError(event);
          toast({
            title: 'Connection Error',
            description: `${getUserMessage(classification)} ${getRecoverySuggestion(classification)}`,
            variant: 'destructive',
          });
        }
      },
      onError: (error) => {
        console.error('WebSocket error:', error);
        const classification = categorizeError(error as any);
        setConnectionError(classification.message);
        setConnectionState(prev => ({
          ...prev,
          error,
          connecting: false
        }));
        toast({
          title: 'Connection Error',
          description: `${getUserMessage(classification)} ${getRecoverySuggestion(classification)}`,
          variant: 'destructive',
        });
      },
      onReconnect: (attempt) => {
        setConnectionState(prev => ({
          ...prev,
          connecting: true,
          retryCount: attempt
        }));
      },
      onStreamChunk: (chunk: StreamingMessagePayload) => {
        // Filter streaming messages by session and agent to prevent cross-session leakage
        if (chunk.sessionId !== session.id || chunk.agentId !== agent.id) {
          console.debug('Ignoring stream chunk from different session/agent:', chunk.sessionId, chunk.agentId);
          return;
        }

        // Handle streaming message chunks
        handleStreamChunk(chunk);

        // Show typing indicator while streaming
        if (!chunk.isFinal) {
          setAgentTyping(true);
        } else {
          setAgentTyping(false);
        }
      },
      onMessage: (wsMessage) => {
        // Filter messages by session to prevent cross-session leakage
        if (wsMessage.payload.metadata?.sessionId && wsMessage.payload.metadata.sessionId !== session.id) {
          console.debug('Ignoring message from different session:', wsMessage.payload.metadata.sessionId);
          return;
        }

        // Handle non-streaming messages
        if (!wsMessage.payload.delta) {
          const chatMessage: ChatMessage = {
            id: wsMessage.id,
            content: wsMessage.payload.content || '',
            role: wsMessage.payload.metadata?.role || 'agent',
            timestamp: new Date(wsMessage.timestamp),
            status: 'delivered',
            isStreaming: false
          };
          
          // Only add optional properties if they have defined values
          if (wsMessage.payload.metadata?.agentId) {
            chatMessage.agentId = wsMessage.payload.metadata.agentId;
          }
          if (wsMessage.payload.metadata?.sessionId) {
            chatMessage.sessionId = wsMessage.payload.metadata.sessionId;
          }
          if (wsMessage.payload.metadata?.trustLevel !== undefined) {
            chatMessage.trustLevel = wsMessage.payload.metadata.trustLevel;
          }

          addMessage(chatMessage);
        }
      },
      onTyping: (indicator) => {
        // Filter typing indicators by session
        if (indicator.sessionId === session.id && indicator.agentId === agent.id) {
          setAgentTyping(indicator.isTyping);
        }
      }
    });

    wsClientRef.current = wsClient;
    setConnectionState(prev => ({ ...prev, connecting: true }));
    wsClient.connect();

    // Load initial messages
    if (session.messages && session.messages.length > 0) {
      session.messages.forEach(msg => addMessage(msg));
    }

    return () => {
      wsClientRef.current = null;
      disconnectWebSocket();
    };
  }, [session.id, agent.id, toast, handleStreamChunk, addMessage]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle sending messages
  const handleSendMessage = useCallback((content: string, _attachments?: File[]) => {
    if (!wsClientRef.current || !connectionState.connected) {
      toast({
        title: 'Not Connected',
        description: 'Please wait for connection to be established',
        variant: 'destructive',
      });
      return;
    }

    const messageId = `${Date.now()}-${Math.random()}`;
    const newMessage: ChatMessage = {
      id: messageId,
      content,
      role: 'user',
      timestamp: new Date(),
      sessionId: session.id,
      status: 'sending',
      isStreaming: false
    };

    // Optimistically add message to UI
    addMessage(newMessage);

    // Send through WebSocket with streaming support
    const _sentMessageId = wsClientRef.current.sendChatMessageWithStreaming(content, {
      agentId: agent.id,
      sessionId: session.id,
      userId: session.userId,
      role: 'user'
    });

    // Update message status after a delay
    setTimeout(() => {
      updateMessage(messageId, { status: 'sent' });
    }, 500);

    // Stop typing indicator when message is sent
    handleTypingStop();
  }, [
    agent.id,
    session.id,
    session.userId,
    connectionState.connected,
    toast,
    addMessage,
    updateMessage,
    handleTypingStop
  ]);

  return (
    <Card className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold">
            {agent.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 className="font-semibold">{agent.name}</h3>
            <p className="text-sm text-muted-foreground">{agent.personaType}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrustIndicator trustLevel={session.trustLevel} />
          <ConnectionStatusIndicator
            connectionState={connectionState}
            onRetry={() => {
              setConnectionState((s) => ({ ...s, connecting: true }));
              wsClientRef.current?.connect();
              toast({
                title: 'Reconnecting...',
                description: 'Attempting to restore connection'
              });
            }}
          />
        </div>
      </div>

      {/* Connection Error Alert */}
      {connectionError && (
        <Alert variant="destructive" className="m-4 mb-0">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{connectionError}</AlertDescription>
        </Alert>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              <p>Start a conversation with {agent.name}</p>
              <p className="text-sm mt-2">Messages will be streamed in real-time</p>
            </div>
          )}
          {messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              showTrustIndicator={message.role === 'agent'}
            />
          ))}
          {(agentTyping || isStreaming) && (
            <TypingIndicator agentName={agent.name} />
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-4">
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={!connectionState.connected}
          placeholder={
            connectionState.connected
              ? `Message ${agent.name}...`
              : connectionState.connecting
              ? 'Connecting...'
              : 'Connection lost. Reconnecting...'
          }
        />
      </div>
    </Card>
  );
}