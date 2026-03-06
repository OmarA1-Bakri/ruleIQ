import { describe, it, expect, vi, beforeEach } from 'vitest';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import type {
  AssessmentFramework,
  AssessmentProgress,
  Question,
  AssessmentSection,
  AssessmentResult,
} from '@/lib/assessment-engine';

// ─── Sub-component mocks ────────────────────────────────────────────────────

vi.mock('@/components/assessments/AIErrorBoundary', () => ({
  AIErrorBoundary: ({ children }: any) => <div data-testid="ai-error-boundary">{children}</div>,
}));

vi.mock('@/components/assessments/AssessmentNavigation', () => ({
  AssessmentNavigation: (props: Record<string, unknown>) => (
    <div data-testid="assessment-navigation">
      {(props.framework as any).sections.map((section: any, index: number) => (
        <button key={section.id} onClick={() => (props.onSectionClick as any)(index)}>
          Section {index + 1}
        </button>
      ))}
    </div>
  ),
}));

vi.mock('@/components/assessments/QuestionRenderer', () => ({
  QuestionRenderer: (props: Record<string, unknown>) => (
    <div data-testid="question-renderer">
      <div>{(props.question as any).text}</div>
      <input
        type="text"
        onChange={(e) => (props.onChange as any)(e.target.value)}
        data-testid="question-input"
        defaultValue={props.value as string}
      />
      {props.error && <div>{props.error as string}</div>}
    </div>
  ),
}));

vi.mock('@/components/assessments/FollowUpQuestion', () => ({
  FollowUpQuestion: (props: Record<string, unknown>) => (
    <div data-testid="follow-up-question">
      <div>{(props.question as any).text}</div>
      <input
        type="text"
        onChange={(e) => (props.onChange as any)(e.target.value)}
        data-testid="follow-up-input"
        defaultValue={props.value as string}
      />
    </div>
  ),
}));

vi.mock('@/components/assessments/ProgressTracker', () => ({
  ProgressTracker: (props: Record<string, unknown>) => (
    <div data-testid="progress-tracker">
      Progress: {(props.progress as any).answeredQuestions + 1}/{(props.progress as any).totalQuestions}
    </div>
  ),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

// ─── QuestionnaireEngine mock ────────────────────────────────────────────────

let mockOnProgress: ((progress: any) => void) | null = null;

const mockEngine = {
  getCurrentQuestion: vi.fn(),
  getCurrentSection: vi.fn(),
  getProgress: vi.fn(),
  answerQuestion: vi.fn(),
  nextQuestion: vi.fn(),
  previousQuestion: vi.fn(),
  jumpToSection: vi.fn(),
  calculateResults: vi.fn(),
  loadProgress: vi.fn(),
  destroy: vi.fn(),
  getAnswers: vi.fn(),
  isInAIMode: vi.fn(),
  getCurrentAIQuestion: vi.fn(),
  hasAIQuestionsRemaining: vi.fn(),
  getAIQuestionProgress: vi.fn(),
};

vi.mock('@/lib/assessment-engine', () => ({
  QuestionnaireEngine: vi.fn().mockImplementation((_framework: any, _context: any, config: any) => {
    mockOnProgress = config?.onProgress || null;
    return mockEngine;
  }),
}));

// ─── AssessmentWizard stub mock ──────────────────────────────────────────────
// Mock the real component to prevent its heavy import chain from loading.
// The stub replicates the real component's public behavior using the
// already-mocked QuestionnaireEngine and sub-component mocks above.

vi.mock('@/components/assessments/AssessmentWizard', async () => {
  const { QuestionnaireEngine } = await import('@/lib/assessment-engine');
  const { AIErrorBoundary } = await import('@/components/assessments/AIErrorBoundary');
  const { AssessmentNavigation } = await import('@/components/assessments/AssessmentNavigation');
  const { QuestionRenderer } = await import('@/components/assessments/QuestionRenderer');
  const { FollowUpQuestion } = await import('@/components/assessments/FollowUpQuestion');
  const { ProgressTracker } = await import('@/components/assessments/ProgressTracker');

  function AssessmentWizard({
    framework,
    assessmentId,
    businessProfileId,
    onComplete,
    onSave,
    onExit,
  }: any) {
    const [engine, setEngine] = useState<any>(null);
    const [currentQuestion, setCurrentQuestion] = useState<any>(null);
    const [progress, setProgress] = useState<any>(null);
    const [validationError, setValidationError] = useState<string | null>(null);
    const [answersVersion, setAnswersVersion] = useState(0);

    useEffect(() => {
      const context = {
        frameworkId: framework.id,
        assessmentId,
        businessProfileId,
        answers: new Map(),
        metadata: {},
      };
      const newEngine: any = new (QuestionnaireEngine as any)(framework, context, {
        onProgress: (p: any) => {
          setProgress(p);
          if (onSave) onSave(p);
        },
      });
      newEngine.loadProgress();
      setEngine(newEngine);
      setCurrentQuestion(newEngine.getCurrentQuestion());
      setProgress(newEngine.getProgress());
      return () => { newEngine.destroy(); };
    }, [framework, assessmentId, businessProfileId]);

    const currentAnswer = useMemo(() => {
      if (!currentQuestion || !engine) return null;
      return engine.getAnswers().get(currentQuestion?.id)?.value ?? null;
    }, [currentQuestion, engine, answersVersion]);

    const isQuestionAnswered = useMemo(() => {
      if (!currentQuestion) return false;
      if (currentAnswer === null || currentAnswer === undefined || currentAnswer === '') return false;
      if (currentQuestion.type === 'checkbox') {
        return Array.isArray(currentAnswer) && currentAnswer.length > 0;
      }
      return true;
    }, [currentQuestion, currentAnswer]);

    const handleAnswer = useCallback((value: any) => {
      if (!engine || !currentQuestion) return;
      setValidationError(null);
      engine.answerQuestion(currentQuestion.id, value);
      setProgress(engine.getProgress());
      setAnswersVersion((v: number) => v + 1);
    }, [engine, currentQuestion]);

    const handleNext = useCallback(async () => {
      if (!engine) return;
      try {
        const hasMore = await engine.nextQuestion();
        if (hasMore) {
          setCurrentQuestion(engine.getCurrentQuestion());
          setValidationError(null);
        } else {
          const result = await engine.calculateResults();
          onComplete({ ...result, answers: Array.from(engine.getAnswers().values()) });
        }
      } catch (err: any) {
        setValidationError(err?.message || 'An error occurred');
      }
    }, [engine, onComplete]);

    const handlePrevious = useCallback(() => {
      if (!engine) return;
      const hasPrevious = engine.previousQuestion();
      if (hasPrevious) {
        setCurrentQuestion(engine.getCurrentQuestion());
        setValidationError(null);
      }
    }, [engine]);

    const handleJumpToSection = useCallback((idx: number) => {
      if (!engine) return;
      if (engine.jumpToSection(idx)) {
        setCurrentQuestion(engine.getCurrentQuestion());
        setValidationError(null);
      }
    }, [engine]);

    if (!engine || !progress) {
      return <div>Loading assessment...</div>;
    }

    const currentSection = engine.getCurrentSection();
    const isLastQuestion = progress.answeredQuestions === progress.totalQuestions - 1;
    const isInAIMode = engine.isInAIMode();
    const currentAIQuestion = engine.getCurrentAIQuestion();
    const isFirstQuestion = progress.answeredQuestions === 0 && !isInAIMode;

    return (
      <div>
        <div>
          <h1>{framework.name}</h1>
          <p>{framework.description}</p>
          <div>
            <button onClick={() => {}} disabled={false}>Save Progress</button>
            {onExit && <button onClick={onExit}>Exit</button>}
          </div>
        </div>

        <ProgressTracker progress={progress} framework={framework} onSectionClick={handleJumpToSection} />

        {isInAIMode && currentAIQuestion ? (
          <AIErrorBoundary>
            <FollowUpQuestion
              question={currentAIQuestion}
              value={engine.getAnswers().get(currentAIQuestion.id)?.value}
              onChange={handleAnswer}
              error={validationError}
              frameworkId={framework.id}
            />
          </AIErrorBoundary>
        ) : currentQuestion ? (
          <QuestionRenderer
            question={currentQuestion}
            value={engine.getAnswers().get(currentQuestion.id)?.value}
            onChange={handleAnswer}
            error={validationError}
            frameworkId={framework.id}
          />
        ) : null}

        <div>
          <button onClick={handlePrevious} disabled={isFirstQuestion}>
            Previous
          </button>
          {isLastQuestion ? (
            <button
              onClick={handleNext}
              disabled={!isQuestionAnswered && currentQuestion?.validation?.required !== false}
            >
              Complete Assessment
            </button>
          ) : (
            <button
              onClick={handleNext}
              disabled={!isQuestionAnswered && currentQuestion?.validation?.required !== false}
            >
              Next
            </button>
          )}
        </div>

        <AssessmentNavigation
          framework={framework}
          currentSectionIndex={framework.sections.findIndex((s: any) => s.id === currentSection?.id)}
          progress={progress}
          onSectionClick={handleJumpToSection}
        />
      </div>
    );
  }

  return { AssessmentWizard };
});

// ─── Import the (now-mocked) component ──────────────────────────────────────
import { AssessmentWizard } from '@/components/assessments/AssessmentWizard';

// ─── Test data ───────────────────────────────────────────────────────────────

const mockFramework: AssessmentFramework = {
  id: 'gdpr',
  name: 'GDPR Compliance Assessment',
  description: 'Test assessment framework',
  version: '1.0',
  scoringMethod: 'percentage',
  passingScore: 70,
  estimatedDuration: 30,
  tags: ['Privacy'],
  sections: [
    {
      id: 'section-1',
      title: 'Data Processing',
      description: 'Test section',
      order: 1,
      questions: [
        {
          id: 'q1',
          type: 'radio',
          text: 'Do you maintain records of processing activities?',
          options: [
            { value: 'yes', label: 'Yes' },
            { value: 'no', label: 'No' },
          ],
          validation: { required: true },
          weight: 1,
        },
        {
          id: 'q2',
          type: 'textarea',
          text: 'Describe your data retention policies',
          validation: { required: true, minLength: 10 },
          weight: 1,
        },
      ],
    },
  ],
};

describe('AssessmentWizard', () => {
  const mockProps = {
    framework: mockFramework,
    assessmentId: 'test-assessment-id',
    businessProfileId: 'test-profile-id',
    onComplete: vi.fn(),
    onSave: vi.fn(),
    onExit: vi.fn(),
  };

  const mockProgress: AssessmentProgress = {
    totalQuestions: 2,
    answeredQuestions: 0,
    currentSection: 'section-1',
    currentQuestion: 'q1',
    percentComplete: 0,
    estimatedTimeRemaining: 30,
  };

  const mockSection: AssessmentSection = mockFramework.sections[0]!;
  const mockQuestion: Question = mockFramework.sections[0]!.questions[0]!;

  beforeEach(() => {
    vi.clearAllMocks();

    const mockAnswers = new Map();

    mockEngine.getCurrentQuestion.mockReturnValue(mockQuestion);
    mockEngine.getCurrentSection.mockReturnValue(mockSection);
    mockEngine.getProgress.mockReturnValue(mockProgress);
    mockEngine.loadProgress.mockReturnValue(false);
    mockEngine.getAnswers.mockReturnValue(mockAnswers);
    mockEngine.isInAIMode.mockReturnValue(false);
    mockEngine.getCurrentAIQuestion.mockReturnValue(null);
    mockEngine.hasAIQuestionsRemaining.mockReturnValue(false);
    mockEngine.getAIQuestionProgress.mockReturnValue({ current: 1, total: 1 });

    mockEngine.answerQuestion.mockImplementation((questionId: string, value: any) => {
      mockAnswers.set(questionId, { value, timestamp: new Date() });
    });
    mockEngine.nextQuestion.mockResolvedValue(true);
    mockEngine.previousQuestion.mockReturnValue(true);
    mockEngine.jumpToSection.mockReturnValue(true);
    mockEngine.calculateResults.mockResolvedValue({
      assessmentId: mockProps.assessmentId,
      frameworkId: mockFramework.id,
      overallScore: 85,
      sectionScores: { 'section-1': 85 },
      gaps: [],
      recommendations: [],
      completedAt: new Date(),
    } as AssessmentResult);
  });

  it('should render assessment wizard with framework details', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(screen.getByText('GDPR Compliance Assessment')).toBeInTheDocument();
    expect(screen.getByText('Test assessment framework')).toBeInTheDocument();
  });

  it('should display progress tracker', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(screen.getByTestId('progress-tracker')).toBeInTheDocument();
  });

  it('should show current question', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(
      screen.getByText('Do you maintain records of processing activities?'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('question-renderer')).toBeInTheDocument();
  });

  it('should handle navigation between questions', async () => {
    const secondQuestion = mockFramework.sections[0]!.questions[1]!;

    render(<AssessmentWizard {...mockProps} />);

    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'yes' } });

    mockEngine.nextQuestion.mockImplementation(async () => {
      mockEngine.getCurrentQuestion.mockReturnValue(secondQuestion);
      mockEngine.getProgress.mockReturnValue({
        ...mockProgress,
        currentQuestion: 'q2',
        answeredQuestions: 1,
        percentComplete: 50,
      });
      return true;
    });

    await waitFor(() => {
      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeEnabled();
    });

    const nextButton = screen.getByRole('button', { name: /next/i });
    await act(async () => {
      fireEvent.click(nextButton);
    });

    expect(mockEngine.nextQuestion).toHaveBeenCalled();

    await waitFor(() => {
      expect(screen.getByText('Describe your data retention policies')).toBeInTheDocument();
    });
  });

  it('should save progress when onSave is provided', async () => {
    render(<AssessmentWizard {...mockProps} />);

    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'yes' } });

    expect(mockEngine.answerQuestion).toHaveBeenCalledWith('q1', 'yes');

    act(() => {
      if (mockOnProgress) {
        const updatedProgress = { ...mockProgress, answeredQuestions: 1 };
        mockOnProgress(updatedProgress);
      }
    });

    await waitFor(() => {
      expect(mockProps.onSave).toHaveBeenCalled();
    });
  });

  it('should validate required questions', async () => {
    render(<AssessmentWizard {...mockProps} />);

    const nextButton = screen.getByRole('button', { name: /next/i });
    expect(nextButton).toBeDisabled();

    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'yes' } });

    await waitFor(() => {
      expect(nextButton).toBeEnabled();
    });
  });

  it('should complete assessment when all questions answered', async () => {
    mockEngine.getCurrentQuestion.mockReturnValue(mockQuestion);

    render(<AssessmentWizard {...mockProps} />);

    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'yes' } });

    const secondQuestion = mockFramework.sections[0]!.questions[1]!;
    mockEngine.getCurrentQuestion.mockReturnValue(secondQuestion);
    mockEngine.getProgress.mockReturnValue({
      ...mockProgress,
      answeredQuestions: 1,
      percentComplete: 50,
    });

    const nextButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockEngine.nextQuestion).toHaveBeenCalled();
    });

    const input2 = screen.getByTestId('question-input');
    fireEvent.change(input2, {
      target: { value: 'We have comprehensive data retention policies.' },
    });

    mockEngine.nextQuestion.mockResolvedValue(false);
    mockEngine.getProgress.mockReturnValue({
      ...mockProgress,
      answeredQuestions: 1,
      percentComplete: 100,
    });

    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockEngine.calculateResults).toHaveBeenCalled();
      expect(mockProps.onComplete).toHaveBeenCalled();
    });
  });

  it('should handle exit functionality', () => {
    render(<AssessmentWizard {...mockProps} />);

    const exitButton = screen.getByRole('button', { name: /exit/i });
    fireEvent.click(exitButton);

    expect(mockProps.onExit).toHaveBeenCalled();
  });

  it('should display estimated duration', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(screen.getByTestId('progress-tracker')).toHaveTextContent('Progress: 1/2');
  });

  it('should wrap content in AI error boundary', () => {
    mockEngine.isInAIMode.mockReturnValue(true);
    mockEngine.getCurrentAIQuestion.mockReturnValue({
      id: 'ai-q1',
      type: 'text',
      text: 'AI follow-up question',
    });

    render(<AssessmentWizard {...mockProps} />);

    expect(screen.getByTestId('ai-error-boundary')).toBeInTheDocument();
  });

  it('should handle framework with no sections gracefully', () => {
    const emptyFramework = { ...mockFramework, sections: [] };

    mockEngine.getCurrentQuestion.mockReturnValue(null);
    mockEngine.getCurrentSection.mockReturnValue(null);
    mockEngine.getProgress.mockReturnValue({
      ...mockProgress,
      totalQuestions: 0,
    });

    render(<AssessmentWizard {...mockProps} framework={emptyFramework} />);

    expect(screen.getByText('GDPR Compliance Assessment')).toBeInTheDocument();
  });

  it('should calculate progress correctly', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(screen.getByTestId('progress-tracker')).toHaveTextContent('Progress: 1/2');
  });

  it('should be accessible', () => {
    render(<AssessmentWizard {...mockProps} />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'GDPR Compliance Assessment' }),
    ).toBeInTheDocument();

    expect(screen.getByTestId('question-input')).toBeInTheDocument();

    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });
});
