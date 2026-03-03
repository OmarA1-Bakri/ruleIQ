'use client';

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

import { iqAgentService } from '@/lib/api/iq-agent.service';
import type {
  IQAgentResponse,
  IQComplianceQueryRequest,
  IQHealthCheckResponse,
  IQAgentError,
  TrustGradientStatus,
} from '@/types/iq-agent';

// ===========================
// Store Types
// ===========================

interface IQAgentState {
  // Current response data
  currentResponse: IQAgentResponse | null;

  // Health status
  healthStatus: IQHealthCheckResponse | null;

  // Trust gradient
  trustStatus: TrustGradientStatus | null;

  // UI state
  isQuerying: boolean;
  isInitializing: boolean;
  error: IQAgentError | null;

  // Query history
  queryHistory: Array<{
    query: string;
    timestamp: string;
    success: boolean;
  }>;

  // Actions
  queryCompliance: (
    query: string,
    options?: {
      context?: IQComplianceQueryRequest['context'];
      include_graph_analysis?: boolean;
      include_recommendations?: boolean;
    }
  ) => Promise<void>;

  checkHealth: () => Promise<void>;

  clearError: () => void;
  reportError: (error: {
    error_type: string;
    message: string;
    correlation_id?: string;
    details?: Record<string, any>;
    retry_after?: number;
  }) => void;

  clearResponse: () => void;
  reset: () => void;
}

// ===========================
// Initial State
// ===========================

const initialState = {
  currentResponse: null,
  healthStatus: null,
  trustStatus: null,
  isQuerying: false,
  isInitializing: false,
  error: null,
  queryHistory: [],
};

// ===========================
// Store Implementation
// ===========================

export const useIQAgentStore = create<IQAgentState>()(
  devtools(
    (set, get) => ({
      ...initialState,

      queryCompliance: async (query, options) => {
        set({ isQuerying: true, error: null }, false, 'queryCompliance/start');

        try {
          const queryOpts: { include_graph_analysis?: boolean; include_recommendations?: boolean } = {};
          if (options?.include_graph_analysis !== undefined) {
            queryOpts.include_graph_analysis = options.include_graph_analysis;
          }
          if (options?.include_recommendations !== undefined) {
            queryOpts.include_recommendations = options.include_recommendations;
          }
          const response = await iqAgentService.queryCompliance(
            query,
            options?.context,
            queryOpts
          );

          set(
            (state) => ({
              currentResponse: response.data,
              isQuerying: false,
              queryHistory: [
                ...state.queryHistory,
                {
                  query,
                  timestamp: new Date().toISOString(),
                  success: true,
                },
              ],
            }),
            false,
            'queryCompliance/success'
          );
        } catch (error: unknown) {
          const errorMessage =
            error && typeof error === 'object' && 'message' in error
              ? (error as { message: string }).message
              : 'Failed to query IQ Agent';

          set(
            (state) => ({
              isQuerying: false,
              error: {
                error_type: 'processing',
                message: errorMessage,
                correlation_id: `query-${Date.now()}`,
              },
              queryHistory: [
                ...state.queryHistory,
                {
                  query,
                  timestamp: new Date().toISOString(),
                  success: false,
                },
              ],
            }),
            false,
            'queryCompliance/error'
          );
        }
      },

      checkHealth: async () => {
        try {
          const health = await iqAgentService.getHealth();
          set({ healthStatus: health }, false, 'checkHealth/success');
        } catch (error: unknown) {
          const errorMessage =
            error && typeof error === 'object' && 'message' in error
              ? (error as { message: string }).message
              : 'Health check failed';

          set(
            {
              error: {
                error_type: 'service_unavailable',
                message: errorMessage,
              },
            },
            false,
            'checkHealth/error'
          );
        }
      },

      clearError: () => {
        set({ error: null }, false, 'clearError');
      },

      reportError: (errorData) => {
        const errorObj: IQAgentError = {
          error_type: errorData.error_type as IQAgentError['error_type'],
          message: errorData.message,
        };
        if (errorData.correlation_id !== undefined) errorObj.correlation_id = errorData.correlation_id;
        if (errorData.details !== undefined) errorObj.details = errorData.details;
        if (errorData.retry_after !== undefined) errorObj.retry_after = errorData.retry_after;
        set(
          { error: errorObj },
          false,
          'reportError'
        );
      },

      clearResponse: () => {
        set({ currentResponse: null }, false, 'clearResponse');
      },

      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'iq-agent-store',
    }
  )
);

// ===========================
// Selectors
// ===========================

export const useIQCurrentResponse = () =>
  useIQAgentStore((state) => state.currentResponse);
export const useIQHealthStatus = () =>
  useIQAgentStore((state) => state.healthStatus);
export const useIQIsQuerying = () =>
  useIQAgentStore((state) => state.isQuerying);
export const useIQError = () =>
  useIQAgentStore((state) => state.error);
export const useIQQueryHistory = () =>
  useIQAgentStore((state) => state.queryHistory);
