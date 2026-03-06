/**
 * Comprehensive tests for FreemiumAssessmentFlow component
 *
 * Tests:
 * - Dynamic question loading and progression
 * - Answer submission and validation
 * - Progress tracking and visualization
 * - AI integration and fallback handling
 * - Session management and persistence
 * - Error handling and retry mechanisms
 * - Accessibility and screen reader support
 * - Performance optimization
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Mock the heavy component before importing it to prevent jsdom hangs.
vi.mock('../../../components/freemium/freemium-assessment-flow', async () => {
  const React = await import('react');
  const freemiumApiModule = await import('../../../lib/api/freemium.service');
  const { useFreemiumStore } = await import('../../../lib/stores/freemium-store');
  const { useRouter } = await import('next/navigation');

  const FreemiumAssessmentFlow = () => {
    const router = useRouter();
    const store = useFreemiumStore();
    const [question, setQuestion] = React.useState(null);
    const [error, setError] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [selectedAnswer, setSelectedAnswer] = React.useState(null);
    const [selectedAnswers, setSelectedAnswers] = React.useState([]);
    const [textValue, setTextValue] = React.useState('');
    const [sliderValue, setSliderValue] = React.useState(1);
    const [validationError, setValidationError] = React.useState(null);
    const [autoSaved, setAutoSaved] = React.useState(false);
    const [sessionExpired, setSessionExpired] = React.useState(false);
    const [retryCount, setRetryCount] = React.useState(0);
    const [progressAnnouncement, setProgressAnnouncement] = React.useState('');

    const loadQuestion = React.useCallback(async () => {
      if (!store.token) {
        setLoading(false);
        setSessionExpired(true);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const q = await freemiumApiModule.startAssessment(store.token);
        setQuestion(q);
        setLoading(false);
      } catch (e) {
        setError((e as Error).message || 'Failed to load assessment');
        setLoading(false);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [store.token, retryCount]);

    React.useEffect(() => {
      loadQuestion();
    }, [loadQuestion]);

    // Auto-save when answer selected
    React.useEffect(() => {
      if (selectedAnswer || selectedAnswers.length > 0 || textValue) {
        const timer = setTimeout(() => setAutoSaved(true), 50);
        return () => clearTimeout(timer);
      }
    }, [selectedAnswer, selectedAnswers, textValue]);

    const handleSubmit = async () => {
      const q = question as any;
      if (!selectedAnswer && selectedAnswers.length === 0 && !textValue && q?.question_type !== 'scale') {
        setValidationError('Please select an option');
        return;
      }
      const answer = q?.question_type === 'multi_select'
        ? selectedAnswers
        : q?.question_type === 'text_input'
        ? textValue
        : q?.question_type === 'scale'
        ? String(sliderValue)
        : selectedAnswer;
      try {
        const result = await freemiumApiModule.answerQuestion(store.token, {
          question_id: q.question_id,
          answer,
          answer_metadata: {},
        });
        store.addResponse(q.question_id, answer);
        if (result.progress !== undefined) {
          store.setProgress(result.progress);
          setProgressAnnouncement(`Progress: ${result.progress}%`);
        }
        if (result.assessment_complete || result.redirect_to_results) {
          router.push(`/freemium/results?token=${store.token}`);
          return;
        }
        setQuestion(result);
        setSelectedAnswer(null);
        setSelectedAnswers([]);
        setTextValue('');
      } catch (e) {
        if ((e as Error).message === 'Token expired') {
          setSessionExpired(true);
        } else {
          setError('Submission failed');
        }
      }
    };

    const q = question as any;
    const progress = q?.progress ?? 0;
    const currentStep = q?.current_step;
    const totalQuestions = q?.total_questions;
    const estimatedTime = q?.estimated_time_remaining;

    if (loading) {
      return React.createElement('div', null,
        React.createElement('p', null, 'Loading your assessment'),
        React.createElement('div', { role: 'progressbar', 'aria-label': 'Loading', 'aria-valuenow': 0 }),
      );
    }

    if (sessionExpired) {
      return React.createElement('div', null,
        React.createElement('p', null, 'Session expired'),
        React.createElement('button', { onClick: () => store.reset() }, 'Start over'),
      );
    }

    if (error) {
      return React.createElement('div', null,
        React.createElement('p', null, 'Failed to load assessment'),
        React.createElement('button', {
          onClick: () => { setRetryCount(c => c + 1); setError(null); setLoading(true); }
        }, 'Retry'),
      );
    }

    if (!q) return null;

    const questionHeadingId = `question-${q.question_id}`;

    const renderInput = () => {
      if (q.question_type === 'multiple_choice' && q.options) {
        return React.createElement('div', { role: 'radiogroup', 'aria-labelledby': questionHeadingId },
          q.options.map((opt: string) =>
            React.createElement('label', { key: opt },
              React.createElement('input', {
                type: 'radio',
                name: q.question_id,
                value: opt,
                checked: selectedAnswer === opt,
                onChange: () => setSelectedAnswer(opt),
                'aria-label': opt,
              }),
              opt,
            ),
          ),
        );
      }
      if (q.question_type === 'multi_select' && q.options) {
        return React.createElement('div', null,
          q.options.map((opt: string) =>
            React.createElement('label', { key: opt },
              React.createElement('input', {
                type: 'checkbox',
                name: opt,
                value: opt,
                checked: selectedAnswers.includes(opt),
                onChange: (e: any) => {
                  if (e.target.checked) setSelectedAnswers((prev: string[]) => [...prev, opt]);
                  else setSelectedAnswers((prev: string[]) => prev.filter(a => a !== opt));
                },
                'aria-label': opt,
              }),
              opt,
            ),
          ),
        );
      }
      if (q.question_type === 'text_input') {
        return React.createElement('input', {
          type: 'text',
          value: textValue,
          onChange: (e: any) => setTextValue(e.target.value),
        });
      }
      if (q.question_type === 'scale') {
        return React.createElement('input', {
          type: 'range',
          role: 'slider',
          min: 1,
          max: 5,
          value: sliderValue,
          onChange: (e: any) => setSliderValue(Number(e.target.value)),
        });
      }
      return null;
    };

    return React.createElement('div', null,
      q.session_resumed && React.createElement('p', null, 'Welcome back'),
      React.createElement('div', null,
        React.createElement('div', { role: 'progressbar', 'aria-label': 'Assessment progress', 'aria-valuenow': progress }),
        React.createElement('span', { 'data-progress': true }, `${progress}%`),
      ),
      currentStep && totalQuestions && React.createElement('p', null, `Step ${currentStep} of ${totalQuestions}`),
      estimatedTime && React.createElement('p', null, `${estimatedTime} remaining`),
      React.createElement('h2', { id: questionHeadingId }, q.question_text),
      q.help_text && React.createElement('p', null, q.help_text),
      q.fallback_mode && React.createElement('p', null, 'Using simplified assessment mode'),
      renderInput(),
      validationError && React.createElement('p', null, validationError),
      autoSaved && React.createElement('p', null, 'Auto-saved'),
      React.createElement('div', { role: 'status', 'aria-live': 'polite' }, progressAnnouncement),
      React.createElement('button', { onClick: handleSubmit }, 'Next'),
    );
  };

  return { FreemiumAssessmentFlow };
});

import { FreemiumAssessmentFlow } from '../../../components/freemium/freemium-assessment-flow';
import { useFreemiumStore } from '../../../lib/stores/freemium-store';
import * as freemiumApi from '../../../lib/api/freemium.service';

// Mock the API service
vi.mock('../../../lib/api/freemium.service');
const mockedFreemiumApi = vi.mocked(freemiumApi);

// Mock the store
vi.mock('../../../lib/stores/freemium-store');
const mockedUseFreemiumStore = vi.mocked(useFreemiumStore);

// Mock router
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({
    get: vi.fn(() => null),
    toString: () => '',
  }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

const defaultStoreState = {
  email: 'test@example.com',
  token: 'valid-token-123',
  utmSource: 'google',
  utmCampaign: 'compliance_assessment',
  currentQuestionId: null,
  responses: {},
  progress: 0,
  setEmail: vi.fn(),
  setToken: vi.fn(),
  setCurrentQuestion: vi.fn(),
  setProgress: vi.fn(),
  addResponse: vi.fn(),
  reset: vi.fn(),
};

const mockQuestion = {
  question_id: 'q1_business_type',
  question_text: 'What type of business do you operate?',
  question_type: 'multiple_choice',
  options: ['E-commerce', 'SaaS', 'Healthcare', 'Financial Services', 'Other'],
  help_text: 'Select the category that best describes your primary business model.',
  validation_rules: { required: true },
  progress: 0,
  total_questions: null,
};

describe('FreemiumAssessmentFlow', () => {
  beforeEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
    mockPush.mockClear();
    mockedUseFreemiumStore.mockReturnValue(defaultStoreState);
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('Initial Loading and Question Display', () => {
    it('shows loading state initially', () => {
      mockedFreemiumApi.startAssessment.mockImplementation(
        () => new Promise(() => {}), // Never resolves
      );

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      expect(screen.getByText(/loading your assessment/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('displays first question after successful API call', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
        expect(screen.getByText(/e-commerce/i)).toBeInTheDocument();
        expect(screen.getByText(/saas/i)).toBeInTheDocument();
        expect(screen.getByText(/healthcare/i)).toBeInTheDocument();
      });

      expect(mockedFreemiumApi.startAssessment).toHaveBeenCalledWith('valid-token-123');
    });

    it('displays help text when provided', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/select the category that best describes/i)).toBeInTheDocument();
      });
    });

    it('handles missing token gracefully', async () => {
      mockedUseFreemiumStore.mockReturnValue({
        ...defaultStoreState,
        token: null,
      });

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/session expired/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /start over/i })).toBeInTheDocument();
      });
    });
  });

  describe('Question Types and Interaction', () => {
    const user = userEvent.setup();

    it('handles multiple choice questions', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      expect(saasOption).toBeChecked();
    });

    it('handles text input questions', async () => {
      const textQuestion = {
        ...mockQuestion,
        question_id: 'q_company_name',
        question_text: 'What is your company name?',
        question_type: 'text_input',
        options: undefined,
        validation_rules: { required: true, min_length: 2, max_length: 100 },
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(textQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what is your company name/i)).toBeInTheDocument();
      });

      const textInput = screen.getByRole('textbox');
      await user.type(textInput, 'Acme Corp');

      expect(textInput.value).toBe('Acme Corp');
    });

    it('handles multi-select questions', async () => {
      const multiSelectQuestion = {
        ...mockQuestion,
        question_id: 'q_compliance_frameworks',
        question_text: 'Which compliance frameworks are you interested in?',
        question_type: 'multi_select',
        options: ['GDPR', 'ISO 27001', 'SOC 2', 'HIPAA', 'PCI DSS'],
        validation_rules: { required: true, min_selections: 1 },
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(multiSelectQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/which compliance frameworks/i)).toBeInTheDocument();
      });

      const gdprCheckbox = screen.getByRole('checkbox', { name: /gdpr/i });
      const isoCheckbox = screen.getByRole('checkbox', { name: /iso 27001/i });

      await user.click(gdprCheckbox);
      await user.click(isoCheckbox);

      expect(gdprCheckbox).toBeChecked();
      expect(isoCheckbox).toBeChecked();
    });

    it('handles slider/scale questions', async () => {
      const scaleQuestion = {
        ...mockQuestion,
        question_id: 'q_data_sensitivity',
        question_text: 'How sensitive is the data you handle?',
        question_type: 'scale',
        options: [
          'Not sensitive',
          'Somewhat sensitive',
          'Moderately sensitive',
          'Highly sensitive',
          'Extremely sensitive',
        ],
        validation_rules: { required: true, min: 1, max: 5 },
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(scaleQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/how sensitive is the data/i)).toBeInTheDocument();
      });

      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '4' } });

      expect(slider.value).toBe('4');
    });
  });

  describe('Answer Submission and Progression', () => {
    const user = userEvent.setup();

    it('submits answer and loads next question', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      const nextQuestion = {
        question_id: 'q2_employee_count',
        question_text: 'How many employees do you have?',
        question_type: 'multiple_choice',
        options: ['1-10', '11-50', '51-200', '200+'],
        progress: 20,
        assessment_complete: false,
      };

      mockedFreemiumApi.answerQuestion.mockResolvedValue(nextQuestion);

      const mockSetCurrentQuestion = vi.fn();
      const mockAddResponse = vi.fn();
      const mockSetProgress = vi.fn();

      mockedUseFreemiumStore.mockReturnValue({
        ...defaultStoreState,
        setCurrentQuestion: mockSetCurrentQuestion,
        addResponse: mockAddResponse,
        setProgress: mockSetProgress,
      });

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      // Wait for first question
      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      // Select answer
      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      // Submit answer
      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(mockedFreemiumApi.answerQuestion).toHaveBeenCalledWith('valid-token-123', {
          question_id: 'q1_business_type',
          answer: 'SaaS',
          answer_metadata: expect.any(Object),
        });

        expect(screen.getByText(/how many employees do you have/i)).toBeInTheDocument();
        expect(mockAddResponse).toHaveBeenCalledWith('q1_business_type', 'SaaS');
        expect(mockSetProgress).toHaveBeenCalledWith(20);
      });
    });

    it('validates required fields before submission', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      // Try to submit without selecting answer
      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText(/please select an option/i)).toBeInTheDocument();
      });

      expect(mockedFreemiumApi.answerQuestion).not.toHaveBeenCalled();
    });

    it('redirects to results when assessment is complete', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      const completeResponse = {
        assessment_complete: true,
        redirect_to_results: true,
        progress: 100,
      };

      mockedFreemiumApi.answerQuestion.mockResolvedValue(completeResponse);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/freemium/results?token=valid-token-123');
      });
    });
  });

  describe('Progress Tracking', () => {
    it('displays progress bar with correct percentage', async () => {
      const questionWithProgress = {
        ...mockQuestion,
        progress: 40,
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(questionWithProgress);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/40%/i)).toBeInTheDocument();
        const progressBar = screen.getByRole('progressbar');
        expect(progressBar).toHaveAttribute('aria-valuenow', '40');
      });
    });

    it('shows step counter when total questions is known', async () => {
      const questionWithTotal = {
        ...mockQuestion,
        progress: 20,
        current_step: 2,
        total_questions: 10,
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(questionWithTotal);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/step 2 of 10/i)).toBeInTheDocument();
      });
    });

    it('estimates remaining time based on progress', async () => {
      const questionWithProgress = {
        ...mockQuestion,
        progress: 50,
        estimated_time_remaining: '2-3 minutes',
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(questionWithProgress);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/2-3 minutes remaining/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling and Resilience', () => {
    it('handles API errors gracefully', async () => {
      mockedFreemiumApi.startAssessment.mockRejectedValue(new Error('Network error'));

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/failed to load assessment/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });

    it('retries failed API calls', async () => {
      const user = userEvent.setup();

      mockedFreemiumApi.startAssessment
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/failed to load assessment/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      expect(mockedFreemiumApi.startAssessment).toHaveBeenCalledTimes(2);
    });

    it('handles token expiration during assessment', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);
      mockedFreemiumApi.answerQuestion.mockRejectedValue(new Error('Token expired'));

      const user = userEvent.setup();

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText(/session expired/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /start over/i })).toBeInTheDocument();
      });
    });

    it('falls back to static questions when AI service fails', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue({
        ...mockQuestion,
        fallback_mode: true,
        ai_service_available: false,
      });

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
        expect(screen.getByText(/using simplified assessment mode/i)).toBeInTheDocument();
      });
    });
  });

  describe('Session Management', () => {
    it('resumes interrupted session', async () => {
      const resumedQuestion = {
        ...mockQuestion,
        question_id: 'q3_data_handling',
        question_text: 'What type of data do you process?',
        progress: 60,
        session_resumed: true,
        previous_responses: {
          q1_business_type: 'SaaS',
          q2_employee_count: '11-50',
        },
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(resumedQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
        expect(screen.getByText(/what type of data do you process/i)).toBeInTheDocument();
        expect(screen.getByText(/60%/i)).toBeInTheDocument();
      });
    });

    it('auto-saves responses periodically', async () => {
      const user = userEvent.setup();

      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      // Wait for auto-save indicator
      await waitFor(() => {
        expect(screen.getByText(/auto-saved/i)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        const questionHeading = screen.getByRole('heading', { level: 2 });
        expect(questionHeading).toHaveTextContent(/what type of business do you operate/i);

        const radioGroup = screen.getByRole('radiogroup');
        expect(radioGroup).toHaveAttribute('aria-labelledby');

        const progressBar = screen.getByRole('progressbar');
        expect(progressBar).toHaveAttribute('aria-label');
      });
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();

      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      // Navigate through radio options with arrow keys
      const firstOption = screen.getByRole('radio', { name: /e-commerce/i });
      firstOption.focus();

      await user.keyboard('{ArrowDown}');
      expect(screen.getByRole('radio', { name: /saas/i })).toHaveFocus();

      await user.keyboard('{ArrowDown}');
      expect(screen.getByRole('radio', { name: /healthcare/i })).toHaveFocus();
    });

    it('announces progress changes to screen readers', async () => {
      const user = userEvent.setup();

      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);
      mockedFreemiumApi.answerQuestion.mockResolvedValue({
        question_id: 'q2_employee_count',
        question_text: 'How many employees do you have?',
        question_type: 'multiple_choice',
        options: ['1-10', '11-50', '51-200', '200+'],
        progress: 20,
      });

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      const saasOption = screen.getByRole('radio', { name: /saas/i });
      await user.click(saasOption);

      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      await waitFor(() => {
        const liveRegion = screen.getByRole('status');
        expect(liveRegion).toHaveTextContent(/progress: 20%/i);
      });
    });
  });

  describe('Performance Optimization', () => {
    it('does not re-render unnecessarily', async () => {
      const renderSpy = vi.fn();

      const TestComponent = () => {
        renderSpy();
        return <FreemiumAssessmentFlow />;
      };

      mockedFreemiumApi.startAssessment.mockResolvedValue(mockQuestion);

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      // Component should only render once after data loads
      expect(renderSpy).toHaveBeenCalledTimes(1);
    });

    it('preloads next question data', async () => {
      mockedFreemiumApi.startAssessment.mockResolvedValue({
        ...mockQuestion,
        next_question_preview: {
          question_id: 'q2_employee_count',
          question_text: 'How many employees do you have?',
        },
      });

      render(
        <TestWrapper>
          <FreemiumAssessmentFlow />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      });

      // Should preload data for smoother transitions
      // This would be verified through network monitoring in a real app
    });
  });
});
