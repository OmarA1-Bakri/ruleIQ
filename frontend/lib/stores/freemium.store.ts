import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
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
  AssessmentQuestionSchema,
} from '../validation/zod-schemas';
import type {
  LeadResponse,
  FreemiumAssessmentStartResponse,
  AssessmentQuestion,
  AssessmentQuestionResponse,
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
            leadToken: (validatedResponse as any).token ?? validatedResponse.lead_id ?? null,
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
            lead_token: leadToken,
          } as any);

          // Validate response - cast to expected type after validation
          const validatedResponse = validateApiResponse(
            response,
            FreemiumAssessmentStartResponseSchema
          ) as unknown as FreemiumAssessmentStartResponse;

          // Validate current question if available
          const rawQuestion = (validatedResponse as any).current_question ?? validatedResponse;
          const validatedQuestion = validateApiResponse(
            rawQuestion,
            AssessmentQuestionSchema
          ) as unknown as AssessmentQuestion;

          set({
            session: validatedResponse,
            sessionToken: validatedResponse.session_id ?? (validatedResponse as any).session_token,
            currentQuestion: validatedQuestion,
            currentQuestionIndex: (validatedResponse as any).current_question_index ?? 0,
            totalQuestions: (validatedResponse as any).total_questions ?? 0,
            progressPercentage: (validatedResponse as any).progress_percentage ?? 0,
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
            session_id: sessionToken,
            question_id: questionId,
            answer: answer as string | number | boolean | string[],
            time_spent: 0, // Track this if needed
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
          
          if (!validatedResponse.is_last_question) {
            // Validate next question
            const validatedQuestion = validateApiResponse(
              validatedResponse.question,
              AssessmentQuestionSchema
            );
            
            set({
              currentQuestion: validatedQuestion,
              currentQuestionIndex: validatedResponse.next_question_index || get().currentQuestionIndex + 1,
              progressPercentage: validatedResponse.progress_percentage,
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
            results: validatedResponse,
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
            results: resultsValidation.success ? resultsValidation.data : null,
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
export const useFreemiumSession = () => useFreemiumStore((state) => state.session);
export const useFreemiumQuestion = () => useFreemiumStore((state) => state.currentQuestion);
export const useFreemiumProgress = () => useFreemiumStore((state) => ({
  current: state.currentQuestionIndex,
  total: state.totalQuestions,
  percentage: state.progressPercentage,
}));
export const useFreemiumResults = () => useFreemiumStore((state) => state.results);
export const useFreemiumLoading = () => useFreemiumStore((state) => state.isLoading);
export const useFreemiumError = () => useFreemiumStore((state) => state.error);