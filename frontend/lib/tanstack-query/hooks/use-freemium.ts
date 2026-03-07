import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import * as freemiumApi from '../../api/freemium.service';
import { useFreemiumStore } from '../../stores/freemium-store';

// Query keys for freemium functionality
export const freemiumKeys = {
  all: ['freemium'] as const,
  results: (token: string) => [...freemiumKeys.all, 'results', token] as const,
  assessment: (token: string) => [...freemiumKeys.all, 'assessment', token] as const,
};

/**
 * Hook for email capture and session initiation
 */
export const useFreemiumEmailCapture = () => {
  const router = useRouter();
  const { setEmail, setToken, utmSource: _utmSource, utmCampaign: _utmCampaign } = useFreemiumStore();

  return useMutation({
    mutationFn: (data: freemiumApi.FreemiumEmailCaptureRequest) => freemiumApi.captureEmail(data),
    onSuccess: (response, variables) => {
      setEmail(variables.email);
      setToken(response.token || null);
      // Redirect to assessment flow
      router.push(`/freemium/assessment?token=${response.token}`);
    },
    onError: () => {
    },
  });
};

/**
 * Hook for starting assessment session
 */
export const useFreemiumStartAssessment = (token: string | null) => {
  const { markAssessmentStarted, setCurrentQuestion } = useFreemiumStore();

  const query = useQuery({
    queryKey: freemiumKeys.assessment(token || ''),
    queryFn: () => freemiumApi.startAssessment(token!),
    enabled: !!token,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: (failureCount, error: any) => {
      // Don't retry if session expired or not found
      if (error?.message?.includes('expired') || error?.message?.includes('not found')) {
        return false;
      }
      return failureCount < 2;
    },
  });

  // Handle success using useEffect instead of deprecated onSuccess
  React.useEffect(() => {
    if (query.data) {
      markAssessmentStarted();
      setCurrentQuestion(query.data.question_id);
    }
  }, [query.data, markAssessmentStarted, setCurrentQuestion]);

  return query;
};

/**
 * Hook for submitting answers and getting next questions
 */
export const useFreemiumAnswerQuestion = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, setCurrentQuestion, markAssessmentCompleted } =
    useFreemiumStore();

  return useMutation({
    mutationFn: (answerData: freemiumApi.FreemiumAnswerRequest) =>
      freemiumApi.answerQuestion(token!, answerData),
    onSuccess: (response) => {
      // incrementProgress doesn't exist in the store

      if (response.is_complete) {
        markAssessmentCompleted();
        router.push(`/freemium/results?token=${token}`);
      } else if (response.next_question_id) {
        setCurrentQuestion(response.next_question_id);
      }

      // Invalidate assessment query to get fresh data
      queryClient.invalidateQueries({
        queryKey: freemiumKeys.assessment(token || ''),
      });
    },
    onError: (error: any) => {


      // Handle session expiration
      if (error?.message?.includes('expired')) {
        router.push('/freemium?error=session_expired');
      }
    },
  });
};

/**
 * Hook for fetching freemium results
 */
export const useFreemiumResults = (token: string | null) => {
  const { markResultsViewed } = useFreemiumStore();

  const query = useQuery({
    queryKey: freemiumKeys.results(token || ''),
    queryFn: () => freemiumApi.getResults(token!),
    enabled: !!token,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: (failureCount, error: any) => {
      // Don't retry if results not found or expired
      if (error?.message?.includes('not found') || error?.message?.includes('expired')) {
        return false;
      }
      return failureCount < 2;
    },
  });

  // Handle success with useEffect instead of deprecated onSuccess
  React.useEffect(() => {
    if (query.data) {
      markResultsViewed();
    }
  }, [query.data, markResultsViewed]);

  return query;
};

/**
 * Hook for tracking conversion events
 */
export const useFreemiumConversionTracking = () => {
  const { token } = useFreemiumStore();

  return useMutation({
    mutationFn: (trackingData: freemiumApi.ConversionTrackingRequest) =>
      freemiumApi.trackConversion(token!, trackingData),
    onSuccess: (_response, _variables) => {
      // Track locally regardless of API success
      // TODO: trackConversionEvent doesn't exist in the store yet
      // trackConversionEvent(variables.event_type);
    },
    onError: () => {
      // Conversion tracking failures should not break UX
    },
    // Don't show loading states for tracking
    mutationKey: ['freemium-tracking'],
  });
};

/**
 * Combined hook for assessment flow management
 */
export const useFreemiumAssessmentFlow = (token: string | null) => {
  const startAssessmentQuery = useFreemiumStartAssessment(token);
  const answerMutation = useFreemiumAnswerQuestion();

  const currentQuestion = startAssessmentQuery.data;
  const isLoading = startAssessmentQuery.isLoading || answerMutation.isPending;
  const error = startAssessmentQuery.error || answerMutation.error;

  const submitAnswer = (answerData: freemiumApi.FreemiumAnswerRequest) => {
    answerMutation.mutate(answerData);
  };

  return {
    currentQuestion,
    isLoading,
    error,
    submitAnswer,
    isSubmitting: answerMutation.isPending,
  };
};

/**
 * Hook for handling UTM parameter capture
 */
export const useFreemiumUtmCapture = () => {
  const { setUtmParams } = useFreemiumStore();

  const captureUtmParams = () => {
    const { utm_source, utm_campaign } = freemiumApi.extractUtmParams();
    if (utm_source || utm_campaign) {
      const params: Record<string, string> = {};
      if (utm_source) params.utm_source = utm_source;
      if (utm_campaign) params.utm_campaign = utm_campaign;
      setUtmParams(params);
    }
  };

  return { captureUtmParams };
};

/**
 * Hook for freemium assessment reset/restart
 */
export const useFreemiumReset = () => {
  const queryClient = useQueryClient();
  const { reset } = useFreemiumStore();
  const router = useRouter();

  const resetAssessment = () => {
    reset();
    queryClient.removeQueries({ queryKey: freemiumKeys.all });
    router.push('/freemium');
  };

  return { resetAssessment };
};
