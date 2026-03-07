import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock crypto.randomUUID
vi.stubGlobal('crypto', {
  randomUUID: () => 'test-uuid-' + Math.random().toString(36).substring(7),
});

describe('App Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');
    const store = useAppStore.getState();

    expect(store.sidebarOpen).toBe(true);
    expect(store.sidebarCollapsed).toBe(false);
    expect(store.theme).toBe('dark');
    expect(store.globalLoading).toBe(false);
    expect(store.loadingMessage).toBeNull();
    expect(store.notifications).toEqual([]);
  });

  it('should toggle sidebar', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    expect(useAppStore.getState().sidebarOpen).toBe(true);

    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarOpen).toBe(false);

    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarOpen).toBe(true);
  });

  it('should set sidebar open state', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().setSidebarOpen(false);
    expect(useAppStore.getState().sidebarOpen).toBe(false);

    useAppStore.getState().setSidebarOpen(true);
    expect(useAppStore.getState().sidebarOpen).toBe(true);
  });

  it('should set sidebar collapsed state', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().setSidebarCollapsed(true);
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);

    useAppStore.getState().setSidebarCollapsed(false);
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });

  it('should set theme', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().setTheme('light');
    expect(useAppStore.getState().theme).toBe('light');

    useAppStore.getState().setTheme('dark');
    expect(useAppStore.getState().theme).toBe('dark');

    useAppStore.getState().setTheme('system');
    expect(useAppStore.getState().theme).toBe('system');
  });

  it('should set global loading with optional message', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().setGlobalLoading(true, 'Loading data...');
    expect(useAppStore.getState().globalLoading).toBe(true);
    expect(useAppStore.getState().loadingMessage).toBe('Loading data...');

    useAppStore.getState().setGlobalLoading(false);
    expect(useAppStore.getState().globalLoading).toBe(false);
    expect(useAppStore.getState().loadingMessage).toBeNull();
  });

  it('should add a notification', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().addNotification({
      type: 'success',
      title: 'Test notification',
      message: 'This is a test',
    });

    const notifications = useAppStore.getState().notifications;
    expect(notifications.length).toBe(1);
    expect(notifications[0].type).toBe('success');
    expect(notifications[0].title).toBe('Test notification');
    expect(notifications[0].message).toBe('This is a test');
    expect(notifications[0].id).toBeDefined();
    expect(notifications[0].timestamp).toBeInstanceOf(Date);
  });

  it('should add multiple notifications', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().addNotification({
      type: 'success',
      title: 'First',
    });
    useAppStore.getState().addNotification({
      type: 'error',
      title: 'Second',
    });
    useAppStore.getState().addNotification({
      type: 'warning',
      title: 'Third',
    });

    expect(useAppStore.getState().notifications.length).toBe(3);
  });

  it('should remove a notification by id', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().addNotification({
      type: 'info',
      title: 'To be removed',
    });

    const notification = useAppStore.getState().notifications[0];
    useAppStore.getState().removeNotification(notification.id);

    expect(useAppStore.getState().notifications.length).toBe(0);
  });

  it('should clear all notifications', async () => {
    const { useAppStore } = await import('@/lib/stores/app.store');

    useAppStore.getState().addNotification({ type: 'success', title: 'A' });
    useAppStore.getState().addNotification({ type: 'error', title: 'B' });
    useAppStore.getState().addNotification({ type: 'warning', title: 'C' });

    expect(useAppStore.getState().notifications.length).toBe(3);

    useAppStore.getState().clearNotifications();
    expect(useAppStore.getState().notifications.length).toBe(0);
  });

  it('should export selectors', async () => {
    const {
      selectSidebarOpen,
      selectTheme,
      selectNotifications,
      selectGlobalLoading,
    } = await import('@/lib/stores/app.store');

    expect(typeof selectSidebarOpen).toBe('function');
    expect(typeof selectTheme).toBe('function');
    expect(typeof selectNotifications).toBe('function');
    expect(typeof selectGlobalLoading).toBe('function');
  });

  it('should have correct selector return values', async () => {
    const {
      useAppStore,
      selectSidebarOpen,
      selectTheme,
      selectNotifications,
      selectGlobalLoading,
    } = await import('@/lib/stores/app.store');

    const state = useAppStore.getState();

    expect(selectSidebarOpen(state)).toBe(true);
    expect(selectTheme(state)).toBe('dark');
    expect(selectNotifications(state)).toEqual([]);
    expect(selectGlobalLoading(state)).toBe(false);
  });
});
