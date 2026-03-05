import { useEffect, useCallback, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLayoutStore } from '@/lib/stores/layout.store';
import { layoutsService } from '@/lib/api/layouts.service';
import { DashboardLayout } from '@/types/layout';
import { toast } from '@/hooks/use-toast';
import { useAuth } from '@/lib/auth';

interface UseLayoutPersistenceOptions {
  autoSave?: boolean;
  autoSaveInterval?: number;
  loadOnMount?: boolean;
  enableConflictResolution?: boolean;
  onSaveSuccess?: (layout: DashboardLayout) => void;
  onSaveError?: (error: Error) => void;
  onLoadSuccess?: (layout: DashboardLayout | null) => void;
  onLoadError?: (error: Error) => void;
}

export const useLayoutPersistence = (options: UseLayoutPersistenceOptions = {}) => {
  const {
    autoSave = true,
    autoSaveInterval = 500,
    loadOnMount = true,
    enableConflictResolution = true,
    onSaveSuccess,
    onSaveError,
    onLoadSuccess,
    onLoadError,
  } = options;

  const queryClient = useQueryClient();
  const { user } = useAuth();
  const userId = user?.id || 'default';

  const {
    currentLayout,
    isDirty,
    isSaving: _isSaving,
    saveError,
    loadLayout,
    saveLayout: _updateLayoutInStore,
    markClean,
    setSaveError,
    preferences: _preferences,
  } = useLayoutStore();

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [lastSyncedVersion, setLastSyncedVersion] = useState<number>(0);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const _conflictResolverRef = useRef<((layout: DashboardLayout) => void) | null>(null);

  // Query for loading layout
  const {
    data: serverLayout,
    isLoading: isLoadingLayout,
    error: loadError,
    refetch: refetchLayout,
  } = useQuery({
    queryKey: ['layout', userId],
    queryFn: () => layoutsService.getLayout(userId),
    enabled: loadOnMount && !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  // Mutation for saving layout
  const saveMutation = useMutation({
    mutationFn: (layout: DashboardLayout) => layoutsService.saveLayout(userId, layout),
    onMutate: async (layout) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['layout', userId] });

      // Snapshot previous value
      const previousLayout = queryClient.getQueryData<DashboardLayout>(['layout', userId]);

      // Optimistically update
      queryClient.setQueryData(['layout', userId], layout);

      return { previousLayout };
    },
    onError: (error, layout, context) => {
      // Rollback on error
      if (context?.previousLayout) {
        queryClient.setQueryData(['layout', userId], context.previousLayout);
      }

      setSaveError(error.message);
      setHasUnsavedChanges(true);

      toast({
        title: 'Failed to save layout',
        description: error.message,
        variant: 'destructive',
      });

      onSaveError?.(error as Error);
    },
    onSuccess: (_, layout) => {
      markClean();
      setHasUnsavedChanges(false);
      setLastSyncedVersion(layout.metadata.version);

      toast({
        title: 'Layout saved',
        description: 'Your dashboard layout has been saved successfully.',
        variant: 'default',
      });

      onSaveSuccess?.(layout);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: ['layout', userId] });
    },
  });

  // Load initial layout
  useEffect(() => {
    if (serverLayout && !currentLayout && loadOnMount) {
      loadLayout(serverLayout);
      setLastSyncedVersion(serverLayout.metadata.version);
      onLoadSuccess?.(serverLayout);
    } else if (loadError && loadOnMount) {
      onLoadError?.(loadError as Error);
    }
  }, [serverLayout, currentLayout, loadLayout, loadOnMount, onLoadSuccess, loadError, onLoadError]);

  // Auto-save functionality
  const debouncedSave = useCallback(() => {
    if (!currentLayout || !isDirty || !autoSave) return;

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(() => {
      saveMutation.mutate(currentLayout);
    }, autoSaveInterval);
  }, [currentLayout, isDirty, autoSave, autoSaveInterval, saveMutation]);

  useEffect(() => {
    if (isDirty && autoSave) {
      setHasUnsavedChanges(true);
      debouncedSave();
    }

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [isDirty, autoSave, debouncedSave]);

  // Handle browser beforeunload event
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        const message = 'You have unsaved changes. Are you sure you want to leave?';
        e.preventDefault();
        e.returnValue = message;
        return message;
      }
      return undefined;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Manual save
  const saveNow = useCallback(async () => {
    if (!currentLayout) return;

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    await saveMutation.mutateAsync(currentLayout);
  }, [currentLayout, saveMutation]);

  // Reset to server state
  const resetToServer = useCallback(async () => {
    const layout = await refetchLayout();
    if (layout.data) {
      loadLayout(layout.data);
      setHasUnsavedChanges(false);
      toast({
        title: 'Layout reset',
        description: 'Your layout has been reset to the last saved version.',
      });
    }
  }, [refetchLayout, loadLayout]);

  // Check for conflicts
  const checkForConflicts = useCallback(async (): Promise<boolean> => {
    if (!enableConflictResolution || !currentLayout) return false;

    try {
      const serverVersion = await layoutsService.getLayout(userId);
      if (!serverVersion) return false;

      if (serverVersion.metadata.version > lastSyncedVersion) {
        // Conflict detected
        return true;
      }
    } catch (error) {
      console.error('Error checking for conflicts:', error);
    }

    return false;
  }, [enableConflictResolution, currentLayout, userId, lastSyncedVersion]);

  // Resolve conflicts
  const resolveConflict = useCallback(
    async (strategy: 'local' | 'remote' | 'merge') => {
      if (!currentLayout) return;

      const serverVersion = await layoutsService.getLayout(userId);
      if (!serverVersion) return;

      let resolvedLayout: DashboardLayout;

      switch (strategy) {
        case 'local':
          // Keep local changes
          resolvedLayout = currentLayout;
          break;
        case 'remote':
          // Use server version
          resolvedLayout = serverVersion;
          loadLayout(serverVersion);
          break;
        case 'merge':
          // Attempt to merge changes
          resolvedLayout = {
            ...serverVersion,
            widgets: [...currentLayout.widgets],
            ruleOrder: [...currentLayout.ruleOrder],
            metadata: {
              ...serverVersion.metadata,
              version: serverVersion.metadata.version + 1,
            },
          };
          loadLayout(resolvedLayout);
          break;
      }

      await saveMutation.mutateAsync(resolvedLayout);
      toast({
        title: 'Conflict resolved',
        description: `Layout conflict resolved using ${strategy} strategy.`,
      });
    },
    [currentLayout, userId, loadLayout, saveMutation]
  );

  // Migration support
  const migrateLayout = useCallback(
    async (fromVersion: number, toVersion: number) => {
      if (!currentLayout) return;

      // Implement version-specific migrations
      let migratedLayout = { ...currentLayout };

      // Example migration logic
      if (fromVersion < 2 && toVersion >= 2) {
        // Add new fields introduced in v2
        migratedLayout.metadata = {
          ...migratedLayout.metadata,
          version: toVersion,
        };
      }

      loadLayout(migratedLayout);
      await saveMutation.mutateAsync(migratedLayout);

      toast({
        title: 'Layout migrated',
        description: `Your layout has been migrated from v${fromVersion} to v${toVersion}.`,
      });
    },
    [currentLayout, loadLayout, saveMutation]
  );

  // Snapshot management
  const createSnapshot = useCallback(
    async (name: string, description?: string) => {
      if (!currentLayout) return;

      const snapshot = await layoutsService.saveSnapshot(userId, {
        name,
        ...(description && { description }),
        layout: currentLayout,
      });

      queryClient.invalidateQueries({ queryKey: ['snapshots', userId] });

      toast({
        title: 'Snapshot created',
        description: `Snapshot "${name}" has been created successfully.`,
      });

      return snapshot;
    },
    [currentLayout, userId, queryClient]
  );

  const restoreSnapshot = useCallback(
    async (snapshotId: string) => {
      const snapshots = await layoutsService.getSnapshots(userId);
      const snapshot = snapshots.find((s) => s.id === snapshotId);

      if (!snapshot) {
        throw new Error('Snapshot not found');
      }

      loadLayout(snapshot.layout);
      await saveMutation.mutateAsync(snapshot.layout);

      toast({
        title: 'Snapshot restored',
        description: `Layout has been restored from snapshot "${snapshot.name}".`,
      });
    },
    [userId, loadLayout, saveMutation]
  );

  // Template management
  const applyTemplate = useCallback(
    async (templateId: string) => {
      const layout = await layoutsService.applyTemplate(userId, templateId);
      loadLayout(layout);
      await saveMutation.mutateAsync(layout);

      toast({
        title: 'Template applied',
        description: 'The selected template has been applied to your dashboard.',
      });
    },
    [userId, loadLayout, saveMutation]
  );

  // Export/Import
  const exportLayout = useCallback(
    async (format: 'json' | 'yaml' | 'csv' = 'json') => {
      if (!currentLayout) return;

      const blob = await layoutsService.exportLayout(userId, currentLayout.id, {
        format,
        includeMetadata: true,
        includeHistory: false,
        compress: false,
      });

      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dashboard-layout-${Date.now()}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: 'Layout exported',
        description: `Your layout has been exported as ${format.toUpperCase()}.`,
      });
    },
    [currentLayout, userId]
  );

  const importLayout = useCallback(
    async (file: File, replace = true) => {
      const result = await layoutsService.importLayout(userId, file, {
        replace,
        validate: true,
      });

      if (result.success && result.layout) {
        loadLayout(result.layout);
        await saveMutation.mutateAsync(result.layout);

        toast({
          title: 'Layout imported',
          description: 'Your layout has been imported successfully.',
        });
      } else {
        toast({
          title: 'Import failed',
          description: result.errors?.join(', ') || 'Failed to import layout.',
          variant: 'destructive',
        });
      }

      return result;
    },
    [userId, loadLayout, saveMutation]
  );

  return {
    // State
    isLoading: isLoadingLayout || saveMutation.isPending,
    isSaving: saveMutation.isPending,
    hasUnsavedChanges,
    saveError: saveMutation.error?.message || saveError,
    loadError: loadError?.message,

    // Actions
    saveNow,
    resetToServer,
    checkForConflicts,
    resolveConflict,
    migrateLayout,

    // Snapshot management
    createSnapshot,
    restoreSnapshot,

    // Template management
    applyTemplate,

    // Export/Import
    exportLayout,
    importLayout,

    // Query helpers
    refetch: refetchLayout,
    invalidate: () => queryClient.invalidateQueries({ queryKey: ['layout', userId] }),
  };
};