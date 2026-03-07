// Freemium Assessment Components
export { FreemiumEmailCapture, FreemiumEmailCaptureInline } from './freemium-email-capture';
export { FreemiumAssessmentFlow, FreemiumAssessmentProgress } from './freemium-assessment-flow';
export { FreemiumResults } from './freemium-results';

// Re-export API types for convenience
export type {
  FreemiumEmailCaptureRequest,
  FreemiumEmailCaptureResponse,
  FreemiumAssessmentStartResponse,
  FreemiumAnswerRequest,
  FreemiumAnswerResponse,
  ComplianceGap,
  TrialOffer,
  FreemiumResultsResponse,
  ConversionTrackingRequest,
  ConversionTrackingResponse,
} from '../../lib/api/freemium.service';

// Re-export hooks for convenience
export {
  useFreemiumEmailCapture,
  useFreemiumStartAssessment,
  useFreemiumAnswerQuestion,
  useFreemiumResults,
  useFreemiumConversionTracking,
  useFreemiumAssessmentFlow,
  useFreemiumUtmCapture,
  useFreemiumReset,
} from '../../lib/tanstack-query/hooks/use-freemium';

// Re-export store for convenience
export {
  useFreemiumStore,
  useFreemiumSession,
  useFreemiumProgress,
} from '../../lib/stores/freemium-store';
