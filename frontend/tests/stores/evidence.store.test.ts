import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the evidence service before importing the store
vi.mock('@/lib/api/evidence.service', () => ({
  evidenceService: {
    getEvidence: vi.fn(),
    getEvidenceItem: vi.fn(),
    createEvidence: vi.fn(),
    updateEvidence: vi.fn(),
    deleteEvidence: vi.fn(),
    bulkUpdateEvidence: vi.fn(),
    uploadEvidenceFile: vi.fn(),
    configureEvidenceAutomation: vi.fn(),
    getEvidenceDashboard: vi.fn(),
    getEvidenceRequirements: vi.fn(),
    classifyEvidence: vi.fn(),
    getEvidenceQualityAnalysis: vi.fn(),
    searchEvidence: vi.fn(),
  },
}));

describe('Evidence Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');
    const store = useEvidenceStore.getState();

    expect(store.evidence).toEqual([]);
    expect(store.currentEvidence).toBeNull();
    expect(store.evidenceRequirements).toBeNull();
    expect(store.evidenceDashboard).toBeNull();
    expect(store.selectedItems).toEqual([]);
    expect(store.isLoading).toBe(false);
    expect(store.isUploading).toBe(false);
    expect(store.isBulkUpdating).toBe(false);
    expect(store.uploadProgress).toBe(0);
    expect(store.error).toBeNull();
    expect(store.total).toBe(0);
    expect(store.currentPage).toBe(1);
    expect(store.pageSize).toBe(20);
    expect(store.searchQuery).toBe('');
  });

  it('should select an item', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().selectItem('ev-1');
    expect(useEvidenceStore.getState().selectedItems).toContain('ev-1');

    useEvidenceStore.getState().selectItem('ev-2');
    expect(useEvidenceStore.getState().selectedItems).toEqual(['ev-1', 'ev-2']);
  });

  it('should deselect an item', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().selectItem('ev-1');
    useEvidenceStore.getState().selectItem('ev-2');

    useEvidenceStore.getState().deselectItem('ev-1');
    expect(useEvidenceStore.getState().selectedItems).toEqual(['ev-2']);
  });

  it('should select all items', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    const mockEvidence = [
      { id: 'ev-1', title: 'Evidence 1' },
      { id: 'ev-2', title: 'Evidence 2' },
      { id: 'ev-3', title: 'Evidence 3' },
    ];

    useEvidenceStore.getState().setEvidence(mockEvidence as any);
    useEvidenceStore.getState().selectAll();

    expect(useEvidenceStore.getState().selectedItems).toEqual(['ev-1', 'ev-2', 'ev-3']);
  });

  it('should clear selection', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().selectItem('ev-1');
    useEvidenceStore.getState().selectItem('ev-2');
    useEvidenceStore.getState().clearSelection();

    expect(useEvidenceStore.getState().selectedItems).toEqual([]);
  });

  it('should set filters and reset page', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().setPage(5);
    expect(useEvidenceStore.getState().currentPage).toBe(5);

    useEvidenceStore.getState().setFilters({ framework_id: 'gdpr', status: 'collected' } as any);

    expect(useEvidenceStore.getState().filters).toEqual({
      framework_id: 'gdpr',
      status: 'collected',
    });
    // Filters reset page to 1
    expect(useEvidenceStore.getState().currentPage).toBe(1);
  });

  it('should set page', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().setPage(3);
    expect(useEvidenceStore.getState().currentPage).toBe(3);
  });

  it('should set search query', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().setSearchQuery('GDPR evidence');
    expect(useEvidenceStore.getState().searchQuery).toBe('GDPR evidence');
  });

  it('should set evidence', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    const mockEvidence = [
      { id: 'ev-1', title: 'Evidence 1', status: 'collected' },
      { id: 'ev-2', title: 'Evidence 2', status: 'pending' },
    ];

    useEvidenceStore.getState().setEvidence(mockEvidence as any);
    expect(useEvidenceStore.getState().evidence).toEqual(mockEvidence);
  });

  it('should set loading state', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    useEvidenceStore.getState().setLoading(true);
    expect(useEvidenceStore.getState().isLoading).toBe(true);

    useEvidenceStore.getState().setLoading(false);
    expect(useEvidenceStore.getState().isLoading).toBe(false);
  });

  it('should clear error', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    // Manually simulate error state by setting via internal access
    useEvidenceStore.setState({ error: 'Something went wrong' });
    expect(useEvidenceStore.getState().error).toBe('Something went wrong');

    useEvidenceStore.getState().clearError();
    expect(useEvidenceStore.getState().error).toBeNull();
  });

  it('should reset to initial state', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');

    // Modify state
    useEvidenceStore.getState().selectItem('ev-1');
    useEvidenceStore.getState().setSearchQuery('test');
    useEvidenceStore.getState().setPage(3);

    // Reset
    useEvidenceStore.getState().reset();

    const state = useEvidenceStore.getState();
    expect(state.selectedItems).toEqual([]);
    expect(state.searchQuery).toBe('');
    expect(state.currentPage).toBe(1);
    expect(state.evidence).toEqual([]);
  });

  it('should provide selector hooks', async () => {
    const mod = await import('@/lib/stores/evidence.store');

    expect(typeof mod.useEvidence).toBe('function');
    expect(typeof mod.useCurrentEvidence).toBe('function');
    expect(typeof mod.useSelectedEvidence).toBe('function');
    expect(typeof mod.useEvidenceDashboard).toBe('function');
    expect(typeof mod.useEvidenceRequirements).toBe('function');
    expect(typeof mod.useEvidenceLoading).toBe('function');
    expect(typeof mod.useEvidenceStats).toBe('function');
  });

  it('should provide all expected action methods', async () => {
    const { useEvidenceStore } = await import('@/lib/stores/evidence.store');
    const store = useEvidenceStore.getState();

    expect(typeof store.loadEvidence).toBe('function');
    expect(typeof store.loadEvidenceItem).toBe('function');
    expect(typeof store.createEvidence).toBe('function');
    expect(typeof store.updateEvidence).toBe('function');
    expect(typeof store.deleteEvidence).toBe('function');
    expect(typeof store.bulkUpdateEvidence).toBe('function');
    expect(typeof store.uploadFile).toBe('function');
    expect(typeof store.configureAutomation).toBe('function');
    expect(typeof store.loadEvidenceDashboard).toBe('function');
    expect(typeof store.loadEvidenceRequirements).toBe('function');
    expect(typeof store.classifyEvidence).toBe('function');
    expect(typeof store.analyzeEvidenceQuality).toBe('function');
    expect(typeof store.searchEvidence).toBe('function');
  });
});
