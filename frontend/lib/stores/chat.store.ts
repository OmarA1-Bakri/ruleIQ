import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { chatService, type ChatWebSocketMessage } from '@/lib/api/chat.service';

import { useAuthStore } from './auth.store';

import type { ChatConversation, ChatMessage } from '@/types/api';

interface ChatState {
  // Conversations
  conversations: ChatConversation[];
  activeConversationId: string | null;
  
  // Widget-specific conversation
  widgetConversationId: string | null;

  // Messages
  messages: Record<string, ChatMessage[]>; // conversationId -> messages

  // WebSocket state
  isConnected: boolean;
  isTyping: boolean;
  typingUsers: string[];

  // Loading states
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;
  isSendingMessage: boolean;

  // Error handling
  error: string | null;

  // WebSocket cleanup handlers
  cleanupHandlers: Map<string, () => void>;

  // Actions
  loadConversations: () => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  createConversation: (title?: string, initialMessage?: string) => Promise<void>;
  setActiveConversation: (conversationId: string | null) => void;
  sendMessage: (message: string, metadata?: Record<string, any>) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  
  // Widget-specific actions
  createWidgetConversation: () => Promise<void>;
  loadWidgetConversation: () => Promise<void>;

  // WebSocket actions
  connectWebSocket: (conversationId: string) => void;
  disconnectWebSocket: () => void;

  // Utility actions
  clearError: () => void;
  reset: () => void;
}

const initialState = {
  conversations: [],
  activeConversationId: null,
  widgetConversationId: null,
  messages: {},
  isConnected: false,
  isTyping: false,
  typingUsers: [],
  isLoadingConversations: false,
  isLoadingMessages: false,
  isSendingMessage: false,
  error: null,
  cleanupHandlers: new Map(),
};

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      ...initialState,

      loadConversations: async () => {
        set({ isLoadingConversations: true, error: null });
        try {
          const response = await chatService.getConversations();
          set({ conversations: response.items, isLoadingConversations: false });
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load conversations',
            isLoadingConversations: false,
          });
        }
      },

      loadConversation: async (conversationId: string) => {
        set({ isLoadingMessages: true, error: null });
        try {
          const response = await chatService.getConversation(conversationId);
          set((state) => ({
            messages: {
              ...state.messages,
              [conversationId]: response.messages,
            },
            isLoadingMessages: false,
          }));

          // Connect WebSocket for real-time updates
          get().connectWebSocket(conversationId);
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load conversation',
            isLoadingMessages: false,
          });
        }
      },

      createConversation: async (title?: string, initialMessage?: string) => {
        set({ error: null });
        try {
          const response = await chatService.createConversation({
            title,
            initial_message: initialMessage,
          });

          set((state) => ({
            conversations: [response.conversation, ...state.conversations],
            messages: {
              ...state.messages,
              [response.conversation.id]: response.messages,
            },
            activeConversationId: response.conversation.id,
          }));

          // Connect WebSocket for the new conversation
          get().connectWebSocket(response.conversation.id);
        } catch (error: any) {
          set({ error: error.message || 'Failed to create conversation' });
        }
      },

      setActiveConversation: (conversationId: string | null) => {
        const state = get();

        // Disconnect from previous conversation
        if (state.activeConversationId && state.activeConversationId !== conversationId) {
          state.disconnectWebSocket();
        }

        set({ activeConversationId: conversationId });

        // Load conversation if not already loaded
        if (conversationId && !state.messages[conversationId]) {
          state.loadConversation(conversationId);
        } else if (conversationId) {
          // Connect WebSocket if switching to existing conversation
          state.connectWebSocket(conversationId);
        }
      },

      sendMessage: async (message: string, metadata?: Record<string, any>) => {
        const state = get();
        const conversationId = metadata?.source === 'widget' 
          ? state.widgetConversationId 
          : state.activeConversationId;
        
        if (!conversationId) return;

        set({ isSendingMessage: true, error: null });

        // Get current user info
        const { user: _user } = useAuthStore.getState();

        // Optimistically add message to UI
        const tempMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          conversation_id: conversationId,
          role: 'user',
          content: message,
          sequence_number: (state.messages[conversationId]?.length || 0) + 1,
          created_at: new Date().toISOString(),
        };

        set((state) => ({
          messages: {
            ...state.messages,
            [conversationId]: [
              ...(state.messages[conversationId] || []),
              tempMessage,
            ],
          },
        }));

        try {
          // Send via WebSocket if connected, otherwise use REST API
          if (state.isConnected) {
            chatService.sendWebSocketMessage({
              type: 'message',
              data: { content: message, metadata },
            });
          } else {
            const response = await chatService.sendMessage(conversationId, {
              content: message,
            });

            // Replace temp message with real one
            set((state) => ({
              messages: {
                ...state.messages,
                [conversationId]: state.messages[conversationId]?.map((msg) => 
                  msg.id === tempMessage.id ? response : msg
                ) || [],
              },
            }));
          }

          set({ isSendingMessage: false });
        } catch (error: any) {
          // Remove temp message on error
          set((state) => ({
            messages: {
              ...state.messages,
              [conversationId]: state.messages[conversationId]?.filter((msg) => 
                msg.id !== tempMessage.id
              ) || [],
            },
            error: error.message || 'Failed to send message',
            isSendingMessage: false,
          }));
        }
      },

      deleteConversation: async (conversationId: string) => {
        set({ error: null });
        try {
          await chatService.deleteConversation(conversationId);

          set((state) => {
            const newState: Partial<ChatState> = {
              conversations: state.conversations.filter((c) => c.id !== conversationId),
            };

            // Clean up messages
            const newMessages = { ...state.messages };
            delete newMessages[conversationId];
            newState.messages = newMessages;

            // Reset active conversation if it was deleted
            if (state.activeConversationId === conversationId) {
              newState.activeConversationId = null;
              state.disconnectWebSocket();
            }

            return newState;
          });
        } catch (error: any) {
          set({ error: error.message || 'Failed to delete conversation' });
        }
      },

      connectWebSocket: (conversationId: string) => {
        const state = get();
        const authToken = useAuthStore.getState().getToken();

        if (!authToken) {
          set({ error: 'Authentication required for chat' });
          return;
        }

        // Clean up any existing handler for this conversation
        const existingCleanup = state.cleanupHandlers.get(conversationId);
        if (existingCleanup) {
          existingCleanup();
        }

        // Set up message handler
        const cleanup = chatService.addMessageHandler((message: ChatWebSocketMessage) => {
          switch (message.type) {
            case 'connection':
              set({ isConnected: message.data.status === 'connected' });
              break;

            case 'message':
              // Add received message to the conversation
              if (message.data.conversation_id === conversationId) {
                set((state) => ({
                  messages: {
                    ...state.messages,
                    [conversationId]: [...(state.messages[conversationId] || []), message.data],
                  },
                }));
              }
              break;

            case 'typing':
              // Handle typing indicators
              if (message.data.action === 'start') {
                set((state) => ({
                  typingUsers: [...state.typingUsers, message.data.user],
                }));
              } else if (message.data.action === 'stop') {
                set((state) => ({
                  typingUsers: state.typingUsers.filter((u) => u !== message.data.user),
                }));
              }
              break;

            case 'error':
              set({ error: message.data.message || 'WebSocket error occurred' });
              break;
          }
        });

        // Store cleanup function
        set((state) => {
          const newHandlers = new Map(state.cleanupHandlers);
          newHandlers.set(conversationId, cleanup);
          return { cleanupHandlers: newHandlers };
        });

        // Connect to WebSocket with auth token
        const wsUrl = `${chatService.getWebSocketUrl(conversationId)}?token=${authToken}`;
        chatService.connectWebSocketWithUrl(wsUrl);
      },

      disconnectWebSocket: () => {
        const state = get();

        // Clean up all message handlers
        state.cleanupHandlers.forEach((cleanup) => cleanup());

        set({
          cleanupHandlers: new Map(),
          isConnected: false,
          typingUsers: [],
        });

        chatService.disconnectWebSocket();
      },

      createWidgetConversation: async () => {
        set({ error: null });
        try {
          const response = await chatService.createConversation({
            title: 'Chat Support',
            initial_message: 'Chat widget conversation',
          });

          set((state) => ({
            widgetConversationId: response.conversation.id,
            messages: {
              ...state.messages,
              [response.conversation.id]: response.messages || [],
            },
          }));

          // Connect WebSocket for the widget conversation
          get().connectWebSocket(response.conversation.id);
        } catch (error: any) {
          set({ error: error.message || 'Failed to create widget conversation' });
        }
      },

      loadWidgetConversation: async () => {
        const state = get();
        if (!state.widgetConversationId) return;

        set({ isLoadingMessages: true, error: null });
        try {
          const response = await chatService.getConversation(state.widgetConversationId);
          set((state) => ({
            messages: {
              ...state.messages,
              [state.widgetConversationId!]: response.messages,
            },
            isLoadingMessages: false,
          }));

          // Connect WebSocket for real-time updates
          get().connectWebSocket(state.widgetConversationId);
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load widget conversation',
            isLoadingMessages: false,
          });
        }
      },

      clearError: () => set({ error: null }),

      reset: () => {
        get().disconnectWebSocket();
        set(initialState);
      },
    }),
    {
      name: 'chat-store',
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
        widgetConversationId: state.widgetConversationId,
        messages: state.messages,
      }),
    },
  ),
);
