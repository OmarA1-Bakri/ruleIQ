/**
 * Hook for managing streaming chat messages
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  ChatMessage,
  StreamingMessagePayload,
  StreamingState,
} from '../websocket/types';

interface UseStreamingChatProps {
  onMessageComplete?: (message: ChatMessage) => void;
  onStreamError?: (error: Error, messageId: string) => void;
}

export function useStreamingChat(props?: UseStreamingChatProps) {
  const { onMessageComplete, onStreamError } = props || {};

  // Map to track in-flight streaming messages
  const streamingMessages = useRef<Map<string, StreamingState>>(new Map());

  // State for all messages
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // State to track if any messages are streaming
  const [isStreaming, setIsStreaming] = useState(false);

  /**
   * Handle incoming streaming chunk
   */
  const handleStreamChunk = useCallback((chunk: StreamingMessagePayload) => {
    const { messageId, delta, isFinal, sequence = 0, trustLevel } = chunk;

    // Get or create streaming state
    let streamState = streamingMessages.current.get(messageId);

    if (!streamState) {
      // New streaming message
      streamState = {
        messageId,
        content: '',
        sequence: 0,
        isComplete: false,
        startTime: Date.now()
      };
      streamingMessages.current.set(messageId, streamState);
      setIsStreaming(true);
    }

    // Update streaming state
    streamState.content += delta;
    streamState.sequence = sequence;

    // Update or create message in the messages array
    setMessages((prevMessages) => {
      const existingIndex = prevMessages.findIndex(m => m.id === messageId);

      if (existingIndex >= 0) {
        // Update existing message
        const updatedMessages = [...prevMessages];
        updatedMessages[existingIndex] = {
          ...updatedMessages[existingIndex],
          content: streamState!.content,
          isStreaming: !isFinal,
          trustLevel: trustLevel || updatedMessages[existingIndex].trustLevel,
          status: isFinal ? 'delivered' : 'sending'
        };
        return updatedMessages;
      } else {
        // Create new message
        const newMessage: ChatMessage = {
          id: messageId,
          content: streamState!.content,
          role: 'agent',
          timestamp: new Date(),
          isStreaming: !isFinal,
          ...(trustLevel && { trustLevel }),
          status: isFinal ? 'delivered' : 'sending'
        };
        return [...prevMessages, newMessage];
      }
    });

    // Handle completion
    if (isFinal) {
      streamState.isComplete = true;
      const completedMessage = messages.find(m => m.id === messageId);
      if (completedMessage && onMessageComplete) {
        onMessageComplete(completedMessage);
      }

      // Clean up streaming state
      streamingMessages.current.delete(messageId);

      // Check if any messages are still streaming
      if (streamingMessages.current.size === 0) {
        setIsStreaming(false);
      }
    }
  }, [messages, onMessageComplete]);

  /**
   * Mark a streaming message as complete
   */
  const handleStreamComplete = useCallback((messageId: string) => {
    const streamState = streamingMessages.current.get(messageId);
    if (!streamState) return;

    streamState.isComplete = true;

    setMessages((prevMessages) => {
      const index = prevMessages.findIndex(m => m.id === messageId);
      if (index >= 0) {
        const updatedMessages = [...prevMessages];
        updatedMessages[index] = {
          ...updatedMessages[index],
          isStreaming: false,
          status: 'delivered'
        };
        return updatedMessages;
      }
      return prevMessages;
    });

    // Clean up
    streamingMessages.current.delete(messageId);
    if (streamingMessages.current.size === 0) {
      setIsStreaming(false);
    }
  }, []);

  /**
   * Handle streaming error
   */
  const handleStreamError = useCallback((error: Error, messageId: string) => {
    console.error('Streaming error for message:', messageId, error);

    const streamState = streamingMessages.current.get(messageId);
    if (!streamState) return;

    // Mark message as failed
    setMessages((prevMessages) => {
      const index = prevMessages.findIndex(m => m.id === messageId);
      if (index >= 0) {
        const updatedMessages = [...prevMessages];
        updatedMessages[index] = {
          ...updatedMessages[index],
          isStreaming: false,
          status: 'failed'
        };
        return updatedMessages;
      }
      return prevMessages;
    });

    // Clean up
    streamingMessages.current.delete(messageId);
    if (streamingMessages.current.size === 0) {
      setIsStreaming(false);
    }

    if (onStreamError) {
      onStreamError(error, messageId);
    }
  }, [onStreamError]);

  /**
   * Add a non-streaming message
   */
  const addMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  /**
   * Update an existing message
   */
  const updateMessage = useCallback((messageId: string, updates: Partial<ChatMessage>) => {
    setMessages((prevMessages) => {
      const index = prevMessages.findIndex(m => m.id === messageId);
      if (index >= 0) {
        const updatedMessages = [...prevMessages];
        updatedMessages[index] = {
          ...updatedMessages[index],
          ...updates
        };
        return updatedMessages;
      }
      return prevMessages;
    });
  }, []);

  /**
   * Clear all messages
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    streamingMessages.current.clear();
    setIsStreaming(false);
  }, []);

  /**
   * Get streaming status for a specific message
   */
  const getMessageStreamingStatus = useCallback((messageId: string): boolean => {
    return streamingMessages.current.has(messageId);
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      streamingMessages.current.clear();
    };
  }, []);

  return {
    messages,
    isStreaming,
    handleStreamChunk,
    handleStreamComplete,
    handleStreamError,
    addMessage,
    updateMessage,
    clearMessages,
    getMessageStreamingStatus
  };
}