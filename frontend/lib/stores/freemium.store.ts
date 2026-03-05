import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { z } from 'zod';
import { 
  validateApiResponse, 
  safeValidateApiResponse,
  logValidationWarning 
} from '../api/validation';
import {
  LeadResponseSchema,
  FreemiumAssessmentStartResponseSchema,
  AssessmentQuestionResponseSchema,
  AssessmentResultsResponseSchema,
} from '../validation/zod-schemas';
import type {
  LeadResponse,
  FreemiumAssessmentStartResponse,
  AssessmentQuestion,
  AssessmentResultsResponse,
  AssessmentAnswerRequest,
} from '@/types/freemium';
import { freemiumService } from '../api/freemium.service';

// ===========================
// Store Types
// ===========================

interface FreemiumStoreState {
  // Lead Information
  lead: LeadResponse | null;
  leadToken: string | null;
  
  // Session Information
  session: FreemiumAssessmentStartResponse | null;
  sessionToken: string | null;
  
  // Assessment State
  currentQuestion: AssessmentQuestion | null;
  currentQuestionIndex: number;
  totalQuestions: number;
  progressPercentage: number;
  answers: Map<string, AssessmentAnswerRequest>;
  
  // Results
  results: AssessmentResultsResponse | null;
  
  // UI State
  isLoading: boolean;
  error: string | null;
  validationErrors: string[];
  
  // Actions
  captureEmail: (email: string, companyName: string, additionalData?: Partial<LeadResponse>) => Promise<void>;
  startAssessment: (assessmentType?: string) => Promise<void>;
  submitAnswer: (questionId: string, answer: unknown) => Promise<void>;
  getResults: () => Promise<void>;
  resetAssessment: () => void;
  clearError: () => void;
  
  // Session Management
  loadSessionFromStorage: () => void;
  saveSessionToStorage: () => void;
  clearSession: () => void;

  // Consumer compatibility
  token: string | null;
  utmSource: string | null;
  utmCampaign: string | null;
  setEmail: (email: string) => void;
  setToken: (token: string | null) => void;
  setConsent: (type: 'marketing' | 'terms', value: boolean) => void;
  loadSession: (sessionToken: string) => Promise<void>;
  markAssessmentStarted: () => void;
  setCurrentQuestion: (questionId: string | null) => void;
  markAssessmentCompleted: () => void;
  markResultsViewed: () => void;
  reset: () => void;
  generateResults: () => Promise<void>;
  trackEvent: (eventType: string, metadata?: Record<string, unknown>) => void;
  setUtmParams: (params: Record<string, string>) => void;
}

// ===========================
// Store Implementation
// ===========================

export const useFreemiumStore = create<FreemiumStoreState>()(
  devtools(
    (set, get) => ({
      // Initial State
      lead: null,
      leadToken: null,
      session: null,
      sessionToken: null,
      currentQuestion: null,
      currentQuestionIndex: 0,
      totalQuestions: 0,
      progressPercentage: 0,
      answers: new Map(),
      results: null,
      isLoading: false,
      error: null,
      validationErrors: [],
      token: null,
      utmSource: null,
      utmCampaign: null,

      // Capture Email Action
      captureEmail: async (email: string, companyName: string, additionalData = {}) => {
        set({ isLoading: true, error: null, validationErrors: [] });
        
        try {
          const response = await freemiumService.captureEmail({
            email,
            company_name: companyName,
            ...additionalData,
          });

          // Validate response
          const validatedResponse = validateApiResponse(response, LeadResponseSchema) as LeadResponse;

          set({
            lead: validatedResponse,
            leadToken: validatedResponse.lead_id ?? null,
            token: validatedResponse.lead_id ?? null,
            isLoading: false,
          });
          
          // Save to localStorage
          get().saveSessionToStorage();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to capture email';
          set({ error: errorMessage, isLoading: false });
          throw error;
        }
      },

      // Start Assessment Action
      startAssessment: async (assessmentType = 'gdpr_basic') => {
        const { leadToken } = get();
        
        if (!leadToken) {
          set({ error: 'No lead token available. Please capture email first.' });
          return;
        }
        
        set({ isLoading: true, error: null, validationErrors: [] });
        
        try {
          const response = await freemiumService.startAssessment({
            lead_id: leadToken,
            business_type: assessmentType,
          });

          // Validate response
          const validatedResponse = validateApiResponse(
            response,
            FreemiumAssessmentStartResponseSchema
          ) as z.infer<typeof FreemiumAssessmentStartResponseSchema>;

          // Build question from the start response fields
          const validatedQuestion: AssessmentQuestion = {
            question_id: validatedResponse.question_id ?? '',
            question_text: validatedResponse.question_text ?? '',
            question_type: validatedResponse.question_type,
            question_context: validatedResponse.question_context ?? '',
            answer_options: validatedResponse.answer_options ?? [],
            is_required: validatedResponse.is_required ?? false,
          };

          set({
            session: validatedResponse,
            sessionToken: validatedResponse.session_id,
            currentQuestion: validatedQuestion,
            currentQuestionIndex: validatedResponse.progress?.current_question ?? 0,
            totalQuestions: validatedResponse.progress?.total_questions_estimate ?? 0,
            progressPercentage: validatedResponse.progress?.progress_percentage ?? 0,
            isLoading: false,
          });
          
          // Save to localStorage
          get().saveSessionToStorage();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to start assessment';
          set({ error: errorMessage, isLoading: false });
          throw error;
        }
      },

      // Submit Answer Action
      submitAnswer: async (questionId: string, answer: unknown) => {
        const { sessionToken, answers } = get();
        
        if (!sessionToken) {
          set({ error: 'No active session. Please start assessment first.' });
          return;
        }
        
        set({ isLoading: true, error: null, validationErrors: [] });
        
        try {
          const answerData: AssessmentAnswerRequest = {
            session_token: sessionToken,
            question_id: questionId,
            answer: answer as string | number | boolean | string[],
            time_spent_seconds: 0,
          };
          
          // Store answer locally
          const newAnswers = new Map(answers);
          newAnswers.set(questionId, answerData);
          
          const response = await freemiumService.submitAnswer(sessionToken, answerData);

          // Validate response
          const validatedResponse = validateApiResponse(
            response,
            AssessmentQuestionResponseSchema
          );
          
          if (!validatedResponse.is_complete) {
            // Build next question from response fields
            const nextQuestion: AssessmentQuestion = {
              question_id: validatedResponse.next_question_id ?? '',
              question_text: validatedResponse.next_question_text ?? '',
              question_type: validatedResponse.next_question_type ?? 'text',
              question_context: validatedResponse.next_question_context ?? '',
              answer_options: validatedResponse.next_answer_options ?? [],
              is_required: true,
            };

            set({
              currentQuestion: nextQuestion,
              currentQuestionIndex: validatedResponse.progress?.current_question ?? get().currentQuestionIndex + 1,
              progressPercentage: validatedResponse.progress?.progress_percentage ?? get().progressPercentage,
              answers: newAnswers,
              isLoading: false,
            });
          } else {
            // Assessment complete
            set({
              currentQuestion: null,
              progressPercentage: 100,
              answers: newAnswers,
              isLoading: false,
            });
            
            // Automatically fetch results
            await get().getResults();
          }
          
          // Save to localStorage
          get().saveSessionToStorage();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to submit answer';
          set({ error: errorMessage, isLoading: false });
          throw error;
        }
      },

      // Get Results Action
      getResults: async () => {
        const { sessionToken } = get();
        
        if (!sessionToken) {
          set({ error: 'No session token available.' });
          return;
        }
        
        set({ isLoading: true, error: null });
        
        try {
          const response = await freemiumService.getResults(sessionToken);

          // Validate response
          const validatedResponse = validateApiResponse(
            response,
            AssessmentResultsResponseSchema
          );
          
          set({
            results: validatedResponse as unknown as AssessmentResultsResponse,
            isLoading: false,
          });
          
          // Save to localStorage
          get().saveSessionToStorage();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to get results';
          set({ error: errorMessage, isLoading: false });
          throw error;
        }
      },

      // Reset Assessment
      resetAssessment: () => {
        set({
          session: null,
          sessionToken: null,
          currentQuestion: null,
          currentQuestionIndex: 0,
          totalQuestions: 0,
          progressPercentage: 0,
          answers: new Map(),
          results: null,
          error: null,
          validationErrors: [],
        });
        
        // Clear from localStorage
        if (typeof window !== 'undefined') {
          localStorage.removeItem('freemium_session');
        }
      },

      // Clear Error
      clearError: () => {
        set({ error: null, validationErrors: [] });
      },

      // Load Session from Storage
      loadSessionFromStorage: () => {
        if (typeof window === 'undefined') return;
        
        try {
          const storedSession = localStorage.getItem('freemium_session');
          if (!storedSession) return;
          
          const parsed = JSON.parse(storedSession);
          
          // Validate stored data
          const leadValidation = safeValidateApiResponse(parsed.lead, LeadResponseSchema);
          const sessionValidation = parsed.session 
            ? safeValidateApiResponse(parsed.session, FreemiumAssessmentStartResponseSchema)
            : { success: true, data: null };
          const resultsValidation = parsed.results
            ? safeValidateApiResponse(parsed.results, AssessmentResultsResponseSchema)
            : { success: true, data: null };
          
          if (!leadValidation.success) {
            logValidationWarning('Stored lead data validation', leadValidation.error);
            return;
          }
          
          set({
            lead: leadValidation.success ? leadValidation.data : null,
            leadToken: parsed.leadToken,
            session: sessionValidation.success ? sessionValidation.data : null,
            sessionToken: parsed.sessionToken,
            currentQuestion: parsed.currentQuestion,
            currentQuestionIndex: parsed.currentQuestionIndex || 0,
            totalQuestions: parsed.totalQuestions || 0,
            progressPercentage: parsed.progressPercentage || 0,
            answers: new Map(parsed.answers || []),
            results: resultsValidation.success ? (resultsValidation.data as unknown as AssessmentResultsResponse) : null,
          });
        } catch (error) {
          console.error('Failed to load session from storage:', error);
        }
      },

      // Save Session to Storage
      saveSessionToStorage: () => {
        if (typeof window === 'undefined') return;
        
        const state = get();
        
        try {
          const sessionData = {
            lead: state.lead,
            leadToken: state.leadToken,
            session: state.session,
            sessionToken: state.sessionToken,
            currentQuestion: state.currentQuestion,
            currentQuestionIndex: state.currentQuestionIndex,
            totalQuestions: state.totalQuestions,
            progressPercentage: state.progressPercentage,
            answers: Array.from(state.answers.entries()),
            results: state.results,
          };
          
          localStorage.setItem('freemium_session', JSON.stringify(sessionData));
        } catch (error) {
          console.error('Failed to save session to storage:', error);
        }
      },

      // Clear Session
      clearSession: () => {
        set({
          lead: null,
          leadToken: null,
          session: null,
          sessionToken: null,
          currentQuestion: null,
          currentQuestionIndex: 0,
          totalQuestions: 0,
          progressPercentage: 0,
          answers: new Map(),
          results: null,
          error: null,
          validationErrors: [],
        });
        
        // Clear from localStorage
        if (typeof window !== 'undefined') {
          localStorage.removeItem('freemium_session');
        }
      },

      // Consumer compatibility stubs
      setEmail: (email: string) => {
        const lead = get().lead;
        if (lead) {
          set({ lead: { ...lead, email } });
        }
      },

      setToken: (token: string | null) => {
        set({ token, leadToken: token });
      },

      setConsent: (_type: 'marketing' | 'terms', _value: boolean) => {
        // Consent state tracked by component; stub for store compatibility
      },

      loadSession: async (sessionToken: string) => {
        set({ sessionToken, token: sessionToken });
        get().loadSessionFromStorage();
      },

      markAssessmentStarted: () => {
        // Assessment already started via startAssessment
      },

      setCurrentQuestion: (questionId: string | null) => {
        if (questionId && get().currentQuestion) {
          set({ currentQuestion: { ...get().currentQuestion!, question_id: questionId } });
        } else if (!questionId) {
          set({ currentQuestion: null });
        }
      },

      markAssessmentCompleted: () => {
        set({ currentQuestion: null, progressPercentage: 100 });
      },

      markResultsViewed: () => {
        // Analytics marker - no-op
      },

      reset: () => {
        get().resetAssessment();
      },

      generateResults: async () => {
        await get().getResults();
      },

      trackEvent: (_eventType: string, _metadata?: Record<string, unknown>) => {
        // Analytics stub
      },

      setUtmParams: (params: Record<string, string>) => {
        set({
          utmSource: params.utm_source || null,
          utmCampaign: params.utm_campaign || null,
        });
      },
    }),
    {
      name: 'freemium-store',
    }
  )
);

// ===========================
// Selectors
// ===========================

export const useFreemiumLead = () => useFreemiumStore((state) => state.lead);
export const useFreemiumSession = () => useFreemiumStore((state) => ({
  hasSession: state.session !== null || state.sessionToken !== null,
  sessionData: {
    sessionToken: state.sessionToken,
    email: state.lead?.email ?? null,
  },
  canViewResults: state.results !== null,
}));
export const useFreemiumQuestion = () => useFreemiumStore((state) => state.currentQuestion);
export const useFreemiumProgress = () => useFreemiumStore((state) => ({
  current: state.currentQuestionIndex,
  total: state.totalQuestions,
  percentage: state.progressPercentage,
}));
export const useFreemiumResults = () => useFreemiumStore((state) => state.results);
export const useFreemiumLoading = () => useFreemiumStore((state) => state.isLoading);
export const useFreemiumError = () => useFreemiumStore((state) => state.error);