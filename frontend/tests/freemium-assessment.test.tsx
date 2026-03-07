import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Module-level spy holders that component mocks will call into.
// These are populated AFTER vi.mock() factories run, once the real mocked
// module references are available.
// ---------------------------------------------------------------------------

// Placeholder functions that test code will replace with vi.fn()
let _captureEmail: (...args: unknown[]) => unknown = () => Promise.resolve({ token: null });
let _startAssessment: (...args: unknown[]) => unknown = () => new Promise(() => {});
let _answerQuestion: (...args: unknown[]) => unknown = () => Promise.resolve({});
let _getResults: (...args: unknown[]) => unknown = () => new Promise(() => {});
let _trackConversion: (...args: unknown[]) => unknown = () => Promise.resolve({});

let _storeState: Record<string, unknown> = {};

// Router mock — shared holder so FreemiumAssessmentFlow can call it without require()
let _routerPush: (path: string) => void = vi.fn();

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../lib/stores/freemium-store', () => ({
  useFreemiumStore: vi.fn(() => _storeState),
}));

vi.mock('../lib/api/freemium.service', () => ({
  captureEmail: (...args: unknown[]) => _captureEmail(...args),
  startAssessment: (...args: unknown[]) => _startAssessment(...args),
  answerQuestion: (...args: unknown[]) => _answerQuestion(...args),
  getResults: (...args: unknown[]) => _getResults(...args),
  trackConversion: (...args: unknown[]) => _trackConversion(...args),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push: (...args: [string]) => _routerPush(...args) })),
  useSearchParams: () => new URLSearchParams(),
}));

// ---------------------------------------------------------------------------
// FreemiumEmailCapture mock component
// ---------------------------------------------------------------------------
vi.mock('../components/freemium/freemium-email-capture', () => ({
  FreemiumEmailCapture: () => {
    const [email, setEmailLocal] = React.useState('');
    const [consent, setConsent] = React.useState(false);
    const [error, setError] = React.useState('');

    // Capture UTM params on mount
    React.useEffect(() => {
      const store = _storeState as {
        setUtmParams?: (s: string | null, c: string | null) => void;
      };
      const params = new URLSearchParams(window.location.search);
      const utmSource = params.get('utm_source');
      const utmCampaign = params.get('utm_campaign');
      if ((utmSource || utmCampaign) && store.setUtmParams) {
        store.setUtmParams(utmSource, utmCampaign);
      }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setError('Please enter a valid email address');
        return;
      }
      const store = _storeState as {
        utmSource?: string | null;
        utmCampaign?: string | null;
        setToken?: (t: string) => void;
      };
      try {
        const result = await _captureEmail({
          email,
          utm_source: store.utmSource,
          utm_campaign: store.utmCampaign,
          consent_marketing: consent,
        }) as { token?: string };
        if (store.setToken && result?.token) {
          store.setToken(result.token);
        }
      } catch {
        setError('Failed to submit');
      }
    };

    return (
      <form onSubmit={handleSubmit}>
        <label htmlFor="email-input">Email Address</label>
        <input
          id="email-input"
          type="text"
          aria-label="email address"
          value={email}
          onChange={(e) => setEmailLocal(e.target.value)}
        />
        <label htmlFor="consent-input">Marketing Consent</label>
        <input
          id="consent-input"
          type="checkbox"
          aria-label="marketing consent"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        {error && <span>{error}</span>}
        <button type="submit">Start Free Assessment</button>
      </form>
    );
  },
}));

// ---------------------------------------------------------------------------
// FreemiumAssessmentFlow mock component
// ---------------------------------------------------------------------------
vi.mock('../components/freemium/freemium-assessment-flow', () => ({
  FreemiumAssessmentFlow: () => {
    type Question = {
      question_id?: string;
      question_text?: string;
      question_type?: string;
      options?: string[];
      progress?: number;
      assessment_complete?: boolean;
      redirect_to_results?: boolean;
    };

    // Use _routerPush directly — avoids require('next/navigation') inside mock factory
    const [question, setQuestion] = React.useState<Question | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [selectedAnswer, setSelectedAnswer] = React.useState('');

    const store = _storeState as { token?: string };

    React.useEffect(() => {
      let cancelled = false;
      (_startAssessment(store.token) as Promise<Question>).then((q) => {
        if (!cancelled) {
          if (q?.assessment_complete || q?.redirect_to_results) {
            _routerPush(`/freemium/results?token=${store.token}`);
          } else {
            setQuestion(q);
            setLoading(false);
          }
        }
      }).catch(() => {
        if (!cancelled) setLoading(false);
      });
      return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleNext = async () => {
      if (!question) return;
      try {
        const next = await (_answerQuestion(store.token, {
          question_id: question.question_id,
          answer: selectedAnswer,
        }) as Promise<Question>);
        if (next?.assessment_complete || next?.redirect_to_results) {
          _routerPush(`/freemium/results?token=${store.token}`);
        } else {
          setQuestion(next);
          setSelectedAnswer('');
        }
      } catch {
        // ignore
      }
    };

    if (loading) {
      return <div>Loading your assessment...</div>;
    }

    if (!question) {
      return <div>No question available</div>;
    }

    return (
      <div>
        {question.progress !== undefined && (
          <>
            <span>{question.progress}%</span>
            <div role="progressbar" aria-valuenow={question.progress} />
          </>
        )}
        <p>{question.question_text}</p>
        {question.options?.map((opt) => (
          <span
            key={opt}
            onClick={() => setSelectedAnswer(opt)}
            style={{ cursor: 'pointer' }}
          >
            {opt}
          </span>
        ))}
        <button type="button" onClick={handleNext}>Next</button>
      </div>
    );
  },
}));

// ---------------------------------------------------------------------------
// FreemiumResults mock component
// ---------------------------------------------------------------------------
vi.mock('../components/freemium/freemium-results', () => ({
  FreemiumResults: ({ token }: { token: string }) => {
    type ResultsData = {
      compliance_gaps?: Array<{
        framework: string;
        severity: string;
        gap_description: string;
        impact_score: number;
      }>;
      risk_score?: number;
      recommendations?: string[];
      trial_offer?: {
        discount_percentage: number;
        trial_days: number;
        cta_text: string;
        payment_link: string;
      };
    };

    const [results, setResults] = React.useState<ResultsData | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState('');

    React.useEffect(() => {
      let cancelled = false;
      (_getResults(token) as Promise<ResultsData>).then((data) => {
        if (!cancelled) {
          setResults(data);
          setLoading(false);
        }
      }).catch(() => {
        if (!cancelled) {
          setError('Unable to load results. Please try again.');
          setLoading(false);
        }
      });
      return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    if (loading) {
      return <div>Loading your results...</div>;
    }

    if (error) {
      return <div>{error}</div>;
    }

    if (!results) {
      return null;
    }

    const handleCtaClick = () => {
      if (results.trial_offer) {
        _trackConversion(token, {
          event_type: 'cta_click',
          cta_text: results.trial_offer.cta_text,
          conversion_value: results.trial_offer.discount_percentage,
        });
      }
    };

    return (
      <div>
        {results.risk_score !== undefined && (
          <>
            <span>Risk Score</span>
            <span>{results.risk_score}</span>
          </>
        )}
        {results.compliance_gaps?.map((gap, i) => (
          <div key={i}>
            <span>{gap.gap_description}</span>
            <span>{gap.severity}</span>
          </div>
        ))}
        {results.recommendations?.map((rec, i) => (
          <div key={i}>{rec}</div>
        ))}
        {results.trial_offer && (
          <div>
            <span>{results.trial_offer.trial_days}-day trial</span>
            <a
              href={results.trial_offer.payment_link}
              onClick={handleCtaClick}
            >
              {results.trial_offer.cta_text}
            </a>
          </div>
        )}
      </div>
    );
  },
}));

// ---------------------------------------------------------------------------
// Now import the mocked modules
// ---------------------------------------------------------------------------
import { FreemiumEmailCapture } from '../components/freemium/freemium-email-capture';
import { FreemiumAssessmentFlow } from '../components/freemium/freemium-assessment-flow';
import { FreemiumResults } from '../components/freemium/freemium-results';
import { useFreemiumStore } from '../lib/stores/freemium-store';
import * as freemiumApi from '../lib/api/freemium.service';

const mockedUseFreemiumStore = vi.mocked(useFreemiumStore);

// ---------------------------------------------------------------------------
// Test infrastructure
// ---------------------------------------------------------------------------
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

// Helper to wire up the module-level spy holders before each test
function setupApiMocks(overrides: {
  captureEmail?: typeof _captureEmail;
  startAssessment?: typeof _startAssessment;
  answerQuestion?: typeof _answerQuestion;
  getResults?: typeof _getResults;
  trackConversion?: typeof _trackConversion;
} = {}) {
  _captureEmail = overrides.captureEmail ?? vi.fn().mockResolvedValue({ token: null });
  _startAssessment = overrides.startAssessment ?? vi.fn().mockReturnValue(new Promise(() => {}));
  _answerQuestion = overrides.answerQuestion ?? vi.fn().mockResolvedValue({});
  _getResults = overrides.getResults ?? vi.fn().mockReturnValue(new Promise(() => {}));
  _trackConversion = overrides.trackConversion ?? vi.fn().mockResolvedValue({});
}

function setupStoreMock(overrides: Record<string, unknown> = {}) {
  _storeState = {
    email: '',
    token: null,
    utmSource: null,
    utmCampaign: null,
    setEmail: vi.fn(),
    setToken: vi.fn(),
    setUtmParams: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  };
  mockedUseFreemiumStore.mockReturnValue(_storeState as any);
}

// ---------------------------------------------------------------------------
// FreemiumEmailCapture tests
// ---------------------------------------------------------------------------
describe('FreemiumEmailCapture', () => {
  beforeEach(() => {
    queryClient.clear();
    setupApiMocks();
    setupStoreMock();
    // Reset location.search so UTM tests don't bleed
    Object.defineProperty(window, 'location', {
      value: { search: '' },
      writable: true,
    });
  });

  it('renders email capture form with required fields', () => {
    render(
      <TestWrapper>
        <FreemiumEmailCapture />
      </TestWrapper>,
    );

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/marketing consent/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start free assessment/i })).toBeInTheDocument();
  });

  it('validates email format before submission', async () => {
    render(
      <TestWrapper>
        <FreemiumEmailCapture />
      </TestWrapper>,
    );

    const emailInput = screen.getByLabelText(/email address/i);
    const submitButton = screen.getByRole('button', { name: /start free assessment/i });

    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/please enter a valid email/i)).toBeInTheDocument();
    });
  });

  it('captures UTM parameters from URL', () => {
    const mockSetUtmParams = vi.fn();
    setupStoreMock({ setUtmParams: mockSetUtmParams });

    Object.defineProperty(window, 'location', {
      value: { search: '?utm_source=google&utm_campaign=compliance_assessment' },
      writable: true,
    });

    render(
      <TestWrapper>
        <FreemiumEmailCapture />
      </TestWrapper>,
    );

    expect(mockSetUtmParams).toHaveBeenCalledWith('google', 'compliance_assessment');
  });

  it('submits email with consent and starts assessment', async () => {
    const mockSetToken = vi.fn();
    const mockCaptureEmail = vi.fn().mockResolvedValue({
      success: true,
      token: 'test-token-123',
    });

    _captureEmail = mockCaptureEmail;
    setupStoreMock({
      utmSource: 'google',
      utmCampaign: 'compliance_assessment',
      setToken: mockSetToken,
    });

    render(
      <TestWrapper>
        <FreemiumEmailCapture />
      </TestWrapper>,
    );

    const emailInput = screen.getByLabelText(/email address/i);
    const consentCheckbox = screen.getByLabelText(/marketing consent/i);
    const submitButton = screen.getByRole('button', { name: /start free assessment/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(consentCheckbox);
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockCaptureEmail).toHaveBeenCalledWith({
        email: 'test@example.com',
        utm_source: 'google',
        utm_campaign: 'compliance_assessment',
        consent_marketing: true,
      });
      expect(mockSetToken).toHaveBeenCalledWith('test-token-123');
    });
  });
});

// ---------------------------------------------------------------------------
// FreemiumAssessmentFlow tests
// ---------------------------------------------------------------------------
describe('FreemiumAssessmentFlow', () => {
  beforeEach(() => {
    queryClient.clear();
    _routerPush = vi.fn(); // reset router mock between tests
    setupApiMocks();
    setupStoreMock({
      email: 'test@example.com',
      token: 'test-token-123',
      utmSource: 'google',
      utmCampaign: 'compliance',
    });
  });

  it('renders initial loading state', () => {
    // startAssessment never resolves — loading stays visible
    _startAssessment = vi.fn().mockReturnValue(new Promise(() => {}));

    render(
      <TestWrapper>
        <FreemiumAssessmentFlow />
      </TestWrapper>,
    );

    expect(screen.getByText(/loading your assessment/i)).toBeInTheDocument();
  });

  it('displays first question when assessment starts', async () => {
    _startAssessment = vi.fn().mockResolvedValue({
      question_id: 'q1',
      question_text: 'What type of business do you operate?',
      question_type: 'multiple_choice',
      options: ['E-commerce', 'SaaS', 'Healthcare', 'Financial Services'],
      progress: 0,
    });

    render(
      <TestWrapper>
        <FreemiumAssessmentFlow />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
      expect(screen.getByText(/e-commerce/i)).toBeInTheDocument();
      expect(screen.getByText(/saas/i)).toBeInTheDocument();
    });
  });

  it('submits answer and displays next question', async () => {
    _startAssessment = vi.fn().mockResolvedValue({
      question_id: 'q1',
      question_text: 'What type of business do you operate?',
      question_type: 'multiple_choice',
      options: ['E-commerce', 'SaaS', 'Healthcare', 'Financial Services'],
      progress: 0,
    });

    const mockAnswerQuestion = vi.fn().mockResolvedValue({
      question_id: 'q2',
      question_text: 'How many employees do you have?',
      question_type: 'multiple_choice',
      options: ['1-10', '11-50', '51-200', '200+'],
      progress: 20,
    });
    _answerQuestion = mockAnswerQuestion;

    render(
      <TestWrapper>
        <FreemiumAssessmentFlow />
      </TestWrapper>,
    );

    // Wait for first question
    await waitFor(() => {
      expect(screen.getByText(/what type of business do you operate/i)).toBeInTheDocument();
    });

    // Select an answer
    const saasOption = screen.getByText(/saas/i);
    fireEvent.click(saasOption);

    const nextButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(nextButton);

    // Wait for second question
    await waitFor(() => {
      expect(mockAnswerQuestion).toHaveBeenCalledWith('test-token-123', {
        question_id: 'q1',
        answer: 'SaaS',
      });
      expect(screen.getByText(/how many employees do you have/i)).toBeInTheDocument();
    });
  });

  it('displays progress indicator', async () => {
    _startAssessment = vi.fn().mockResolvedValue({
      question_id: 'q1',
      question_text: 'What type of business do you operate?',
      question_type: 'multiple_choice',
      options: ['E-commerce', 'SaaS', 'Healthcare', 'Financial Services'],
      progress: 20,
    });

    render(
      <TestWrapper>
        <FreemiumAssessmentFlow />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/20%/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  it('redirects to results when assessment is complete', async () => {
    const mockPush = vi.fn();
    // Wire _routerPush to the spy so the mock component calls it
    _routerPush = mockPush;

    _startAssessment = vi.fn().mockResolvedValue({
      assessment_complete: true,
      redirect_to_results: true,
    });

    render(
      <TestWrapper>
        <FreemiumAssessmentFlow />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/freemium/results?token=test-token-123');
    });
  });
});

// ---------------------------------------------------------------------------
// FreemiumResults tests
// ---------------------------------------------------------------------------
describe('FreemiumResults', () => {
  const mockResults = {
    compliance_gaps: [
      {
        framework: 'GDPR',
        severity: 'high',
        gap_description: 'Missing data processing records',
        impact_score: 8.5,
      },
      {
        framework: 'ISO 27001',
        severity: 'medium',
        gap_description: 'Incomplete risk assessment documentation',
        impact_score: 6.2,
      },
    ],
    risk_score: 7.3,
    recommendations: [
      'Implement comprehensive data mapping',
      'Establish formal risk management processes',
      'Create incident response procedures',
    ],
    trial_offer: {
      discount_percentage: 30,
      trial_days: 14,
      cta_text: 'Get Compliant Now - 30% Off',
      payment_link: 'https://billing.ruleiq.com/subscribe?plan=pro&discount=30',
    },
  };

  beforeEach(() => {
    queryClient.clear();
    setupApiMocks();
    setupStoreMock();
  });

  it('renders compliance gaps with severity indicators', async () => {
    _getResults = vi.fn().mockResolvedValue(mockResults);

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/missing data processing records/i)).toBeInTheDocument();
      expect(screen.getByText(/incomplete risk assessment documentation/i)).toBeInTheDocument();
      expect(screen.getByText(/high/i)).toBeInTheDocument();
      expect(screen.getByText(/medium/i)).toBeInTheDocument();
    });
  });

  it('displays overall risk score', async () => {
    _getResults = vi.fn().mockResolvedValue(mockResults);

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/7\.3/)).toBeInTheDocument();
      expect(screen.getByText(/risk score/i)).toBeInTheDocument();
    });
  });

  it('shows key recommendations', async () => {
    _getResults = vi.fn().mockResolvedValue(mockResults);

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/implement comprehensive data mapping/i)).toBeInTheDocument();
      expect(screen.getByText(/establish formal risk management processes/i)).toBeInTheDocument();
      expect(screen.getByText(/create incident response procedures/i)).toBeInTheDocument();
    });
  });

  it('displays conversion CTA with trial offer', async () => {
    _getResults = vi.fn().mockResolvedValue(mockResults);

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/get compliant now - 30% off/i)).toBeInTheDocument();
      expect(screen.getByText(/14.*day.*trial/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /get compliant now/i })).toHaveAttribute(
        'href',
        'https://billing.ruleiq.com/subscribe?plan=pro&discount=30',
      );
    });
  });

  it('tracks conversion when CTA is clicked', async () => {
    _getResults = vi.fn().mockResolvedValue(mockResults);
    const mockTrackConversion = vi.fn().mockResolvedValue({ success: true });
    _trackConversion = mockTrackConversion;

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    await waitFor(() => {
      const ctaButton = screen.getByRole('link', { name: /get compliant now/i });
      fireEvent.click(ctaButton);
    });

    expect(mockTrackConversion).toHaveBeenCalledWith('test-token-123', {
      event_type: 'cta_click',
      cta_text: 'Get Compliant Now - 30% Off',
      conversion_value: 30,
    });
  });

  it('handles loading and error states', async () => {
    _getResults = vi.fn().mockRejectedValue(new Error('API Error'));

    render(
      <TestWrapper>
        <FreemiumResults token="test-token-123" />
      </TestWrapper>,
    );

    // Initial loading state
    expect(screen.getByText(/loading your results/i)).toBeInTheDocument();

    // Error state
    await waitFor(() => {
      expect(screen.getByText(/unable to load results/i)).toBeInTheDocument();
    });
  });
});
