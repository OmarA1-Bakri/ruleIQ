/**
 * WebSocket client for real-time agent communication
 */

import {
  WSMessage,
  MessageType,
  ConnectionState,
  WSEventHandlers,
  TypingIndicator,
  StreamingMessagePayload
} from './types';
import { categorizeError, logError } from '@/lib/utils/websocket-error-handler';

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay = 30000; // Max 30 seconds
  private messageQueue: WSMessage[] = [];
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private connectionState: ConnectionState = {
    connected: false,
    connecting: false,
    error: null,
    retryCount: 0
  };
  private eventHandlers: WSEventHandlers = {};

  constructor(url: string, handlers?: WSEventHandlers) {
    this.url = url;
    if (handlers) {
      this.eventHandlers = handlers;
    }
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.connectionState.connecting || this.connectionState.connected) {
      console.log('Already connected or connecting');
      return;
    }

    this.connectionState.connecting = true;
    this.connectionState.error = null;

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventListeners();
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
    
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.connectionState = {
      connected: false,
      connecting: false,
      error: null,
      retryCount: 0
    };
  }

  /**
   * Send a message through WebSocket
   */
  send(message: WSMessage): void {
    if (!this.connectionState.connected) {
      // Queue message if not connected
      this.messageQueue.push(message);
      return;
    }

    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(message));
      } else {
        this.messageQueue.push(message);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      this.messageQueue.push(message);
    }
  }

  /**
   * Send a chat message
   */
  sendChatMessage(content: string, metadata?: any): void {
    const message: WSMessage = {
      id: this.generateMessageId(),
      type: MessageType.CHAT,
      timestamp: new Date().toISOString(),
      payload: {
        content,
        metadata
      }
    };
    this.send(message);
  }

  /**
   * Send a chat message with streaming support
   */
  sendChatMessageWithStreaming(content: string, metadata?: any): string {
    const messageId = this.generateMessageId();
    const message: WSMessage = {
      id: messageId,
      type: MessageType.CHAT,
      timestamp: new Date().toISOString(),
      payload: {
        content,
        metadata: {
          ...metadata,
          streaming: true
        }
      }
    };
    this.send(message);
    return messageId;
  }

  /**
   * Send typing indicator
   */
  sendTypingIndicator(isTyping: boolean, sessionId: string, agentId: string): void {
    const message: WSMessage = {
      id: this.generateMessageId(),
      type: MessageType.TYPING,
      timestamp: new Date().toISOString(),
      payload: {
        metadata: {
          agentId,
          sessionId
        },
        content: isTyping ? 'typing' : 'stopped'
      }
    };
    this.send(message);
  }

  /**
   * Get connection state
   */
  getConnectionState(): ConnectionState {
    return { ...this.connectionState };
  }

  /**
   * Update event handlers
   */
  setEventHandlers(handlers: WSEventHandlers): void {
    this.eventHandlers = { ...this.eventHandlers, ...handlers };
  }

  /**
   * Setup WebSocket event listeners
   */
  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.connectionState = {
        connected: true,
        connecting: false,
        error: null,
        retryCount: 0,
        lastConnectedAt: new Date()
      };
      
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      
      // Start heartbeat
      this.startHeartbeat();
      
      // Process queued messages
      this.processMessageQueue();
      
      // Call handler
      if (this.eventHandlers.onOpen) {
        this.eventHandlers.onOpen();
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      const classification = categorizeError(event);
      this.connectionState.connected = false;
      this.connectionState.connecting = false;
      this.connectionState.error = new Error(classification.message);
      logError(classification, { phase: 'onclose', code: event.code });

      // Stop heartbeat
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }

      // Call handler with error information
      if (this.eventHandlers.onClose) {
        this.eventHandlers.onClose(event);
      }

      if (this.eventHandlers.onError) {
        this.eventHandlers.onError(new Error(classification.message));
      }

      // Auto-reconnect if not intentional disconnect
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      const classification = categorizeError(event as Event);
      this.connectionState.error = new Error(classification.message);
      logError(classification, { phase: 'onerror' });

      if (this.eventHandlers.onError) {
        this.eventHandlers.onError(new Error(classification.message));
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);

        // Check if this is a streaming message chunk
        if (message.payload.delta !== undefined) {
          if (this.eventHandlers.onStreamChunk) {
            const streamChunk: StreamingMessagePayload = {
              delta: message.payload.delta,
              isFinal: message.payload.isFinal,
              sequence: message.payload.sequence,
              messageId: message.payload.messageId || message.id,
              trustLevel: message.payload.metadata?.trustLevel,
              sessionId: message.payload.metadata?.sessionId || '',
              agentId: message.payload.metadata?.agentId || ''
            };
            console.log('Received streaming chunk:', streamChunk);
            this.eventHandlers.onStreamChunk(streamChunk);
          }
          return;
        }

        // Handle different message types
        switch (message.type) {
          case MessageType.HEARTBEAT:
            // Respond to heartbeat
            this.sendHeartbeatResponse();
            break;

          case MessageType.TYPING:
            if (this.eventHandlers.onTyping) {
              const indicator: TypingIndicator = {
                agentId: message.payload.metadata?.agentId || '',
                sessionId: message.payload.metadata?.sessionId || '',
                isTyping: message.payload.content === 'typing'
              };
              this.eventHandlers.onTyping(indicator);
            }
            break;

          default:
            if (this.eventHandlers.onMessage) {
              this.eventHandlers.onMessage(message);
            }
        }
      } catch (error) {
        console.error('Failed to parse message:', error);
      }
    };
  }

  /**
   * Handle connection errors
   */
  private handleError(error: Error): void {
    console.error('WebSocket error:', error);
    this.connectionState.error = error;
    this.connectionState.connecting = false;
    
    if (this.eventHandlers.onError) {
      this.eventHandlers.onError(error);
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      if (this.eventHandlers.onReconnect) {
        this.eventHandlers.onReconnect(this.reconnectAttempts);
      }
      this.connect();
    }, delay);
  }

  /**
   * Process queued messages
   */
  private processMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message);
      }
    }
  }

  /**
   * Start heartbeat mechanism
   */
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.connectionState.connected) {
        const heartbeat: WSMessage = {
          id: this.generateMessageId(),
          type: MessageType.HEARTBEAT,
          timestamp: new Date().toISOString(),
          payload: {}
        };
        this.send(heartbeat);
      }
    }, 30000); // Send heartbeat every 30 seconds
  }

  /**
   * Send heartbeat response
   */
  private sendHeartbeatResponse(): void {
    const response: WSMessage = {
      id: this.generateMessageId(),
      type: MessageType.HEARTBEAT,
      timestamp: new Date().toISOString(),
      payload: { content: 'pong' }
    };
    this.send(response);
  }

  /**
   * Generate unique message ID
   */
  private generateMessageId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Export singleton instance
let wsClient: WebSocketClient | null = null;

export function getWebSocketClient(url?: string, handlers?: WSEventHandlers): WebSocketClient {
  if (!wsClient && url) {
    wsClient = new WebSocketClient(url, handlers);
  } else if (wsClient && handlers) {
    // Update handlers on existing client to avoid stale closures
    wsClient.setEventHandlers(handlers);
  }

  if (!wsClient) {
    throw new Error('WebSocket client not initialized. Please provide URL.');
  }

  return wsClient;
}

export function disconnectWebSocket(): void {
  if (wsClient) {
    wsClient.disconnect();
    wsClient = null;
  }
}