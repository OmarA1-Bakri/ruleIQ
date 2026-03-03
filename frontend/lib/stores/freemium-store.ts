/**
 * Freemium Store Facade - Backward Compatibility Layer
 *
 * This file is a facade that re-exports the freemium store implementation.
 * The planned modular refactoring into frontend/lib/stores/freemium/ was
 * never completed, so this now re-exports from the actual store file.
 *
 * Legacy imports like:
 *     import { useFreemiumStore } from '@/lib/stores/freemium-store'
 *
 * Will continue to work and resolve to freemium.store.ts.
 *
 * Migration Status: FACADE ACTIVE (Jan 2025)
 */

// Re-export everything from the actual store implementation
export {
  useFreemiumStore,
  useFreemiumLead,
  useFreemiumSession,
  useFreemiumProgress,
  useFreemiumQuestion,
  useFreemiumResults,
  useFreemiumLoading,
  useFreemiumError,
} from './freemium.store';
