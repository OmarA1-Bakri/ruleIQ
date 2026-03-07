import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock external dependencies before importing the hook
vi.mock('@/lib/api/chat.service', () => ({
  chatService: {
    sendWebSocketMessage: vi.fn(),
  },
}));

vi.mock('@/lib/stores/chat.store', () => ({
  useChatStore: vi.fn(() => ({
    activeConversationId: 'conv-123',
    isConnected: true,
  })),
}));

vi.mock('@/lib/websocket/client', () => ({
  getWebSocketClient: vi.fn(() => ({
    getConnectionState: vi.fn(() => ({ connected: true })),
    sendTypingIndicator: vi.fn(),
  })),
}));

import { useTypingIndicator } from '@/lib/hooks/use-typing-indicator';
import { chatService } from '@/lib/api/chat.service';
import { useChatStore } from '@/lib/stores/chat.store';
import { getWebSocketClient } from '@/lib/websocket/client';

describe('useTypingIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();

    // Reset store mock to default (connected)
    vi.mocked(useChatStore).mockReturnValue({
      activeConversationId: 'conv-123',
      isConnected: true,
    } as any);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns handleTypingStart and handleTypingStop functions', () => {
    const { result } = renderHook(() => useTypingIndicator());
    expect(typeof result.current.handleTypingStart).toBe('function');
    expect(typeof result.current.handleTypingStop).toBe('function');
  });

  it('does not send typing start for empty message', () => {
    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('');
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: 'typing', data: expect.objectContaining({ action: 'start' }) })
    );
  });

  it('does not send typing start for whitespace-only message', () => {
    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('   ');
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ action: 'start' }) })
    );
  });

  it('sends typing start after debounce delay (500ms) for non-empty message', () => {
    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('Hello');
    });

    // Not yet sent
    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(chatService.sendWebSocketMessage).toHaveBeenCalledWith({
      type: 'typing',
      data: { action: 'start', conversation_id: 'conv-123' },
    });
  });

  it('handleTypingStop sends stop indicator immediately', () => {
    const { result } = renderHook(() => useTypingIndicator());

    // First start typing to set the ref
    act(() => {
      result.current.handleTypingStart('Hello');
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Now stop
    act(() => {
      result.current.handleTypingStop();
    });

    expect(chatService.sendWebSocketMessage).toHaveBeenCalledWith({
      type: 'typing',
      data: { action: 'stop', conversation_id: 'conv-123' },
    });
  });

  it('stops typing automatically after 3 seconds of inactivity', () => {
    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('Hello');
    });
    act(() => {
      vi.advanceTimersByTime(500); // debounce — sends start
    });

    const startCallCount = vi.mocked(chatService.sendWebSocketMessage).mock.calls.length;

    act(() => {
      vi.advanceTimersByTime(3000); // auto-stop timeout
    });

    const stopCall = vi.mocked(chatService.sendWebSocketMessage).mock.calls.find(
      (call) => call[0]?.data?.action === 'stop'
    );
    expect(stopCall).toBeDefined();
    expect(vi.mocked(chatService.sendWebSocketMessage).mock.calls.length).toBeGreaterThan(startCallCount);
  });

  it('does not send if not connected', () => {
    vi.mocked(useChatStore).mockReturnValue({
      activeConversationId: 'conv-123',
      isConnected: false,
    } as any);

    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('Hello');
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalled();
  });

  it('does not send if no active conversation', () => {
    vi.mocked(useChatStore).mockReturnValue({
      activeConversationId: null,
      isConnected: true,
    } as any);

    const { result } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('Hello');
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalled();
  });

  it('uses WebSocketClient when useWebSocketClient=true', () => {
    const mockWsClient = {
      getConnectionState: vi.fn(() => ({ connected: true })),
      sendTypingIndicator: vi.fn(),
    };
    vi.mocked(getWebSocketClient).mockReturnValue(mockWsClient as any);

    const { result } = renderHook(() =>
      useTypingIndicator({ useWebSocketClient: true, sessionId: 'sess-1', agentId: 'agent-1' })
    );

    act(() => {
      result.current.handleTypingStart('Hello');
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(mockWsClient.sendTypingIndicator).toHaveBeenCalledWith(true, 'sess-1', 'agent-1');
  });

  it('cleanup on unmount cancels pending timeouts', () => {
    const { result, unmount } = renderHook(() => useTypingIndicator());

    act(() => {
      result.current.handleTypingStart('Hello');
    });

    // Unmount before debounce fires
    unmount();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Should not have sent start because it was cancelled on unmount
    expect(chatService.sendWebSocketMessage).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ action: 'start' }) })
    );
  });
});
