/**
 * QuestionnaireEngine - Core assessment execution engine with AI follow-up questions
 *
 * Note: There are pre-existing TypeScript errors in other parts of the codebase
 * (primarily in legacy components, auth pages, and test files). These do not affect
 * the assessment engine functionality and are tracked as technical debt.
 */
import { assessmentAIService } from '../api/assessments-ai.service';

import {
  type Question,
  type Answer,
  type AssessmentFramework,
  type AssessmentContext,
  type AssessmentProgress,
  type AssessmentResult,
  type QuestionCondition,
  type QuestionnaireEngineConfig,
  type Gap,
  type Recommendation,
  type AssessmentSection,
} from './types';

import type { BusinessProfile } from '@/types/api';

export class QuestionnaireEngine {
  private framework: AssessmentFramework;
  private context: AssessmentContext;
  private config: QuestionnaireEngineConfig;
  private currentSectionIndex: number = 0;
  private currentQuestionIndex: number = 0;
  private autoSaveTimer?: NodeJS.Timeout;
  private visibleQuestions: Map<string, Question[]> = new Map();
  private aiFollowUpQuestions: Map<string, Question[]> = new Map();
  private pendingAIQuestions: Question[] = [];
  private currentAIQuestionIndex: number = -1;
  private isInAIQuestionMode: boolean = false;
  private sectionAnalysisCache: Map<string, { timestamp: number; result: boolean }> = new Map();
  private AI_TIMEOUT_MS = 10000; // 10 seconds timeout for AI calls
  private aiServiceCache: Map<string, { timestamp: number; data: unknown }> = new Map();
  private readonly AI_CACHE_TTL = 300000; // 5 minutes cache TTL

  constructor(
    framework: AssessmentFramework,
    context: AssessmentContext,
    config: QuestionnaireEngineConfig = {},
  ) {
    this.framework = framework;
    this.context = context;
    this.config = {
      allowSkipping: true,
      autoSave: true,
      autoSaveInterval: 30,
      showProgress: true,
      enableNavigation: true,
      randomizeQuestions: false,
      ...config,
    };
    this.initializeVisibleQuestions();
    this.startAutoSave();
  }

  private initializeVisibleQuestions(): void {
    this.framework.sections.forEach((section) => {
      const visibleQuestions = this.filterVisibleQuestions(section.questions);
      this.visibleQuestions.set(section.id, visibleQuestions);
    });
  }

  private filterVisibleQuestions(questions: Question[]): Question[] {
    return questions.filter((question) => this.isQuestionVisible(question));
  }

  private isQuestionVisible(question: Question): boolean {
    if (!question.conditions || question.conditions.length === 0) {
      return true;
    }

    return this.evaluateConditions(question.conditions);
  }

  private evaluateConditions(conditions: QuestionCondition[]): boolean {
    let result = true;
    let currentOperator: 'AND' | 'OR' = 'AND';

    for (const condition of conditions) {
      const conditionResult = this.evaluateCondition(condition);

      if (currentOperator === 'AND') {
        result = result && conditionResult;
      } else {
        result = result || conditionResult;
      }

      currentOperator = condition.combineWith || 'AND';
    }

    return result;
  }

  private evaluateCondition(condition: QuestionCondition): boolean {
    const answer = this.context.answers.get(condition.questionId);
    if (!answer) return false;

    const { value } = answer;

    switch (condition.operator) {
      case 'equals':
        return value === condition.value;
      case 'not_equals':
        return value !== condition.value;
      case 'contains':
        return Array.isArray(value)
          ? value.includes(condition.value)
          : String(value).includes(String(condition.value));
      case 'greater_than':
        return Number(value) > Number(condition.value);
      case 'less_than':
        return Number(value) < Number(condition.value);
      case 'in':
        return Array.isArray(condition.value) && condition.value.includes(value);
      case 'not_in':
        return Array.isArray(condition.value) && !condition.value.includes(value);
      default:
        return false;
    }
  }

  private startAutoSave(): void {
    if (this.config.autoSave && this.config.autoSaveInterval) {
      this.autoSaveTimer = setInterval(() => {
        this.saveProgress();
      }, this.config.autoSaveInterval * 1000);
    }
  }

  private async saveProgress(): Promise<void> {
    try {
      // Save to localStorage for now, can be extended to save to backend
      const progressData = {
        assessmentId: this.context.assessmentId,
        frameworkId: this.context.frameworkId,
        answers: Array.from(this.context.answers.entries()),
        currentSectionIndex: this.currentSectionIndex,
        currentQuestionIndex: this.currentQuestionIndex,
        // AI-related state
        isInAIQuestionMode: this.isInAIQuestionMode,
        pendingAIQuestions: this.pendingAIQuestions,
        currentAIQuestionIndex: this.currentAIQuestionIndex,
        lastSaved: new Date().toISOString(),
      };

      localStorage.setItem(
        `assessment_progress_${this.context.assessmentId}`,
        JSON.stringify(progressData),
      );

      if (this.config.onProgress) {
        this.config.onProgress(this.getProgress());
      }
    } catch (error) {
      if (this.config.onError) {
        this.config.onError(error as Error);
      }
    }
  }

  public loadProgress(): boolean {
    try {
      const savedData = localStorage.getItem(`assessment_progress_${this.context.assessmentId}`);

      if (!savedData) return false;

      const progressData = JSON.parse(savedData);

      // Restore answers
      this.context.answers = new Map(progressData.answers);
      this.currentSectionIndex = progressData.currentSectionIndex;
      this.currentQuestionIndex = progressData.currentQuestionIndex;

      // Restore AI state if present
      if (progressData.isInAIQuestionMode !== undefined) {
        this.isInAIQuestionMode = progressData.isInAIQuestionMode;
        this.pendingAIQuestions = progressData.pendingAIQuestions || [];
        this.currentAIQuestionIndex = progressData.currentAIQuestionIndex || -1;
      }

      // Refresh visible questions based on loaded answers
      this.initializeVisibleQuestions();

      return true;
    } catch (error) {
      if (this.config.onError) {
        this.config.onError(error as Error);
      }
      return false;
    }
  }

  public getCurrentSection(): AssessmentSection | null {
    return this.framework.sections[this.currentSectionIndex] || null;
  }

  public getCurrentQuestion(): Question | null {
    // If we're in AI question mode, return the current AI question
    if (this.isInAIQuestionMode && this.currentAIQuestionIndex >= 0) {
      return this.pendingAIQuestions[this.currentAIQuestionIndex] || null;
    }

    const section = this.getCurrentSection();
    if (!section) return null;

    const visibleQuestions = this.visibleQuestions.get(section.id) || [];
    return visibleQuestions[this.currentQuestionIndex] || null;
  }

  public getVisibleQuestionsForSection(sectionId: string): Question[] {
    return this.visibleQuestions.get(sectionId) || [];
  }

  public answerQuestion(questionId: string, value: any): void {
    const currentQuestion = this.getCurrentQuestion();
    const isAIQuestion = this.isInAIQuestionMode && currentQuestion?.metadata?.['isAIGenerated'];

    const answer: Answer = {
      questionId,
      value,
      timestamp: new Date(),
      source: isAIQuestion ? 'ai' : 'framework',
      metadata: isAIQuestion ? { reasoning: currentQuestion?.metadata?.['reasoning'] } : undefined,
    };

    this.context.answers.set(questionId, answer);

    // Invalidate section analysis cache for current section
    const section = this.getCurrentSection();
    if (section) {
      this.sectionAnalysisCache.delete(section.id);
    }

    // Refresh visible questions as answer might affect conditions
    this.initializeVisibleQuestions();

    // Auto-save if enabled
    if (this.config.autoSave) {
      this.saveProgress();
    }
  }

  public async nextQuestion(): Promise<boolean> {
    // If we're in AI question mode, handle AI question navigation
    if (this.isInAIQuestionMode) {
      if (this.currentAIQuestionIndex < this.pendingAIQuestions.length - 1) {
        this.currentAIQuestionIndex++;
        return true;
      } else {
        // Finished AI questions, return to normal flow
        this.exitAIQuestionMode();
        return await this.nextQuestion(); // Continue with normal navigation
      }
    }

    // Check if we should trigger AI follow-up questions
    const currentQuestion = this.getCurrentQuestion();
    if (currentQuestion && this.shouldTriggerAIFollowUp(currentQuestion)) {
      await this.enterAIQuestionMode();
      return this.isInAIQuestionMode; // Only return true if AI mode was successfully entered
    }

    const section = this.getCurrentSection();
    if (!section) return false;

    const visibleQuestions = this.visibleQuestions.get(section.id) || [];

    if (this.currentQuestionIndex < visibleQuestions.length - 1) {
      this.currentQuestionIndex++;
      return true;
    } else if (this.currentSectionIndex < this.framework.sections.length - 1) {
      this.currentSectionIndex++;
      this.currentQuestionIndex = 0;
      return true;
    }

    return false;
  }

  public previousQuestion(): boolean {
    // If we're in AI question mode, handle AI question navigation
    if (this.isInAIQuestionMode) {
      if (this.currentAIQuestionIndex > 0) {
        this.currentAIQuestionIndex--;
        return true;
      } else {
        // Exit AI mode and go back to previous regular question
        this.exitAIQuestionMode();
        return false; // Don't auto-navigate, let user control
      }
    }

    if (this.currentQuestionIndex > 0) {
      this.currentQuestionIndex--;
      return true;
    } else if (this.currentSectionIndex > 0) {
      this.currentSectionIndex--;
      const previousSection = this.framework.sections[this.currentSectionIndex];
      if (previousSection) {
        const visibleQuestions = this.visibleQuestions.get(previousSection.id) || [];
        this.currentQuestionIndex = Math.max(0, visibleQuestions.length - 1);
        return true;
      }
    }

    return false;
  }

  public jumpToSection(sectionIndex: number): boolean {
    if (sectionIndex >= 0 && sectionIndex < this.framework.sections.length) {
      this.currentSectionIndex = sectionIndex;
      this.currentQuestionIndex = 0;
      return true;
    }
    return false;
  }

  public jumpToQuestion(sectionIndex: number, questionIndex: number): boolean {
    if (this.jumpToSection(sectionIndex)) {
      const section = this.framework.sections[sectionIndex];
      if (section) {
        const visibleQuestions = this.visibleQuestions.get(section.id) || [];

        if (questionIndex >= 0 && questionIndex < visibleQuestions.length) {
          this.currentQuestionIndex = questionIndex;
          return true;
        }
      }
    }
    return false;
  }

  public getProgress(): AssessmentProgress {
    let totalQuestions = 0;
    let answeredQuestions = 0;

    this.framework.sections.forEach((section) => {
      const visibleQuestions = this.visibleQuestions.get(section.id) || [];
      totalQuestions += visibleQuestions.length;

      visibleQuestions.forEach((question) => {
        if (this.context.answers.has(question.id)) {
          answeredQuestions++;
        }
      });
    });

    const percentComplete =
      totalQuestions > 0 ? Math.round((answeredQuestions / totalQuestions) * 100) : 0;

    const currentSection = this.getCurrentSection();
    const currentQuestion = this.getCurrentQuestion();

    return {
      totalQuestions,
      answeredQuestions,
      currentSection: currentSection?.id || '',
      currentQuestion: currentQuestion?.id || '',
      percentComplete,
      lastSaved: new Date(),
    };
  }

  public async calculateResults(): Promise<AssessmentResult> {
    const sectionScores: Record<string, number> = {};
    const gaps: Gap[] = [];
    let totalScore = 0;
    let totalWeight = 0;

    this.framework.sections.forEach((section) => {
      const visibleQuestions = this.visibleQuestions.get(section.id) || [];
      let sectionScore = 0;
      let sectionWeight = 0;

      visibleQuestions.forEach((question) => {
        const answer = this.context.answers.get(question.id);
        const weight = question.weight || 1;
        sectionWeight += weight;

        if (answer) {
          const score = this.calculateQuestionScore(question, answer);
          sectionScore += score * weight;

          // Identify gaps
          if (score < 0.7) {
            // Less than 70% is considered a gap
            gaps.push(this.createGap(question, answer, score));
          }
        } else if (question.validation?.required) {
          // Required question not answered is a critical gap
          gaps.push(this.createGap(question, null, 0));
        }
      });

      const normalizedSectionScore = sectionWeight > 0 ? (sectionScore / sectionWeight) * 100 : 0;

      sectionScores[section.id] = Math.round(normalizedSectionScore);
      totalScore += sectionScore;
      totalWeight += sectionWeight;
    });

    const overallScore = totalWeight > 0 ? Math.round((totalScore / totalWeight) * 100) : 0;

    const maturityLevel = this.calculateMaturityLevel(overallScore);
    const recommendations = await this.generateRecommendations(gaps);

    return {
      assessmentId: this.context.assessmentId,
      frameworkId: this.context.frameworkId,
      overallScore,
      sectionScores,
      maturityLevel,
      gaps,
      recommendations,
      completedAt: new Date(),
      answers: Array.from(this.context.answers.values()),
    };
  }

  private calculateQuestionScore(question: Question, answer: Answer): number {
    // This is a simplified scoring logic - can be customized based on question type
    switch (question.type) {
      case 'radio':
      case 'select':
        // Assume options have values like 'yes', 'no', 'partial'
        if (answer.value === 'yes' || answer.value === 'fully_compliant') return 1;
        if (answer.value === 'partial' || answer.value === 'partially_compliant') return 0.5;
        return 0;

      case 'checkbox':
        // Score based on percentage of positive selections
        const selectedCount = Array.isArray(answer.value) ? answer.value.length : 0;
        const totalOptions = question.options?.length || 1;
        return selectedCount / totalOptions;

      case 'scale':
        // Normalize scale to 0-1
        const scaleMin = question.scaleMin || 1;
        const scaleMax = question.scaleMax || 5;
        return (answer.value - scaleMin) / (scaleMax - scaleMin);

      default:
        // For text, textarea, etc., assume answered = compliant
        return answer.value ? 1 : 0;
    }
  }

  private calculateMaturityLevel(score: number): AssessmentResult['maturityLevel'] {
    if (score >= 90) return 'optimized';
    if (score >= 75) return 'managed';
    if (score >= 60) return 'defined';
    if (score >= 40) return 'developing';
    return 'initial';
  }

  private createGap(question: Question, answer: Answer | null, score: number): Gap {
    const section = this.framework.sections.find((s) =>
      s.questions.some((q) => q.id === question.id),
    );

    const gap: Gap = {
      id: `gap_${question.id}`,
      questionId: question.id,
      questionText: question.text,
      section: section?.title || 'Unknown',
      category: question.category || 'General',
      severity: score === 0 ? 'critical' : score < 0.5 ? 'high' : 'medium',
      description: question.text,
      impact: this.assessImpact(question, score),
      currentState: answer ? `Score: ${Math.round(score * 100)}%` : 'Not answered',
      targetState: '100% compliance',
      expectedAnswer: this.getExpectedAnswer(question),
    };
    
    // Only set actualAnswer if we have a value to avoid exactOptionalPropertyTypes issues
    if (answer?.value) {
      gap.actualAnswer = String(answer.value);
    }
    
    return gap;
  }

  private getExpectedAnswer(question: Question): string {
    // For boolean questions, the expected answer is typically the highest-scoring option
    if (question.type === 'radio') return 'Yes';
    if (question.type === 'select') {
      // Return the option with the highest value as expected
      const bestOption = question.options?.[question.options.length - 1];
      return bestOption?.label || 'Best practice option';
    }
    return 'Full compliance';
  }

  private assessImpact(question: Question, score: number): string {
    // This can be enhanced with more sophisticated impact analysis
    const weight = question.weight || 1;
    if (weight > 3 && score < 0.5) {
      return 'High impact - Critical compliance requirement';
    } else if (weight > 2) {
      return 'Medium impact - Important for compliance';
    }
    return 'Low impact - Best practice recommendation';
  }

  private async generateRecommendations(gaps: Gap[]): Promise<Recommendation[]> {
    // If no gaps, return empty array
    if (gaps.length === 0) {
      return [];
    }

    // Create cache key for this recommendation request
    const cacheKey = `rec_${this.context.frameworkId}_${gaps.map((g) => g.id).join('_')}`;

    // Check cache first
    const cached = this.getCachedAIResponse(cacheKey);
    if (cached) {
      return cached;
    }

    try {
      // Use AI service if enabled, otherwise fall back to mock generation
      if (this.config.enableAI !== false) {
        const recommendations = await this.callAIServiceWithTimeout(
          () =>
            assessmentAIService.getPersonalizedRecommendations({
              gaps,
              business_profile: this.getBusinessProfileFromContext(),
              existing_policies: this.getExistingPoliciesFromAnswers(),
              industry_context: this.getIndustryContextFromAnswers(),
              timeline_preferences: this.getTimelinePreferenceFromAnswers(),
            }),
          'AI recommendation service',
        );

        // Transform AI response to our recommendation format
        const transformedRecs = recommendations.recommendations.map((rec, index) => {
          const relatedGap = gaps[index];
          if (!relatedGap) {
            throw new Error(`No gap found for recommendation at index ${index}`);
          }
          return {
            ...rec,
            id: rec.id || `ai_rec_${Date.now()}_${index}`,
            gapId: relatedGap.id,
            estimatedEffort: (rec as any).estimatedTime || this.estimateEffort(relatedGap),
            resources: rec.resources || this.suggestResources(relatedGap),
          };
        });

        // Cache the result
        this.setCachedAIResponse(cacheKey, transformedRecs);
        return transformedRecs;
      } else {
        // Fall back to mock recommendations
        return this.generateMockRecommendations(gaps);
      }
    } catch (_error) {
      // Log error but don't break the assessment


      // Use mock recommendations as fallback
      if (this.config.useMockAIOnError) {
        return this.generateMockRecommendations(gaps);
      }

      // Call error handler if provided
      if (this.config.onError) {
        this.config.onError(new Error('Failed to generate AI recommendations'));
      }

      // Return basic fallback recommendations
      return this.generateMockRecommendations(gaps);
    }
  }

  private generateMockRecommendations(gaps: Gap[]): Recommendation[] {
    // Sort gaps by severity for prioritization (original logic)
    const sortedGaps = [...gaps].sort((a, b) => {
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return severityOrder[a.severity] - severityOrder[b.severity];
    });

    return sortedGaps.slice(0, 10).map((gap, index) => ({
      id: `rec_${gap.id}`,
      gapId: gap.id,
      priority: index < 3 ? 'immediate' : index < 6 ? 'short_term' : 'medium_term',
      title: `Address: ${gap.description.substring(0, 50)}...`,
      description: this.generateRecommendationText(gap),
      estimatedEffort: this.estimateEffort(gap),
      resources: this.suggestResources(gap),
      category: gap.category,
      impact: gap.impact,
      effort: this.estimateEffort(gap),
      estimatedTime: this.estimateTime(gap),
    }));
  }

  private generateRecommendationText(gap: Gap): string {
    // This can be enhanced with AI or template-based recommendations
    return `To achieve compliance for "${gap.description}", implement controls and processes to move from ${gap.currentState} to ${gap.targetState}.`;
  }

  private getBusinessProfileFromContext(): Partial<BusinessProfile> {
    // Extract business profile information from context metadata
    // This would be populated when the assessment is initialized with business profile data
    const businessProfile = this.context.metadata['businessProfile'] as
      | Partial<BusinessProfile>
      | undefined;
    return (
      businessProfile || {
        id: this.context.businessProfileId,
        // Add any other available profile information from context
      }
    );
  }

  private getExistingPoliciesFromAnswers(): string[] {
    // Extract policy information from answers with enhanced logic
    const policies: string[] = [];
    const policyKeywords = ['policy', 'procedure', 'standard', 'guideline', 'protocol', 'process'];
    const positiveIndicators = [
      'yes',
      'implemented',
      'exists',
      'established',
      'documented',
      'formal',
    ];

    for (const [questionId, answer] of this.context.answers) {
      const question = this.framework.sections
        .flatMap((s) => s.questions)
        .find((q) => q.id === questionId);

      if (!question) continue;

      // Check if question is policy-related
      const questionText = question.text.toLowerCase();
      const isPolicyRelated = policyKeywords.some(
        (keyword) => questionId.toLowerCase().includes(keyword) || questionText.includes(keyword),
      );

      if (isPolicyRelated && answer.value) {
        const answerText = String(answer.value).toLowerCase();
        const hasPositiveIndicator = positiveIndicators.some((indicator) =>
          answerText.includes(indicator),
        );

        if (hasPositiveIndicator) {
          // Extract policy name from question text
          const policyName = question.text
            .replace(/^(Do you have|Does your organization have|Is there)\s*/i, '')
            .replace(/\?$/, '')
            .trim();
          policies.push(policyName);
        }
      }
    }

    return policies;
  }

  private getIndustryContextFromAnswers(): string {
    // Try to determine industry context from business profile or answers
    const businessProfile = this.getBusinessProfileFromContext();

    // First, check business profile
    if (businessProfile.industry) {
      return businessProfile.industry as string;
    }

    // Look for industry-specific indicators in answers
    const industryKeywords = {
      Healthcare: ['medical', 'patient', 'healthcare', 'clinical', 'hospital', 'hipaa'],
      'Financial Services': [
        'financial',
        'banking',
        'payment',
        'transaction',
        'pci',
        'gdpr financial',
      ],
      Technology: ['software', 'saas', 'technology', 'cloud', 'api', 'data processing'],
      Education: ['student', 'education', 'school', 'university', 'ferpa'],
      'E-commerce': ['e-commerce', 'online retail', 'customer data', 'online payments'],
      Manufacturing: ['manufacturing', 'industrial', 'supply chain', 'production'],
      Legal: ['legal', 'law firm', 'attorney', 'privileged information'],
      Government: ['government', 'public sector', 'municipal', 'federal', 'state'],
    };

    for (const [questionId, answer] of this.context.answers) {
      if (!answer.value) continue;

      const answerText = String(answer.value).toLowerCase();
      const question = this.framework.sections
        .flatMap((s) => s.questions)
        .find((q) => q.id === questionId);

      const combinedText = `${questionId} ${question?.text || ''} ${answerText}`.toLowerCase();

      for (const [industry, keywords] of Object.entries(industryKeywords)) {
        if (keywords.some((keyword) => combinedText.includes(keyword))) {
          return industry;
        }
      }
    }

    return 'General Business';
  }

  private getTimelinePreferenceFromAnswers(): 'urgent' | 'standard' | 'gradual' {
    // Look for timeline-related answers and risk indicators
    const timelineKeywords = {
      urgent: ['immediate', 'asap', 'urgent', 'critical', 'emergency', '1 month', 'soon'],
      standard: ['3 months', '6 months', 'quarterly', 'standard', 'normal'],
      gradual: ['1 year', 'annual', 'long-term', 'gradual', 'phased', 'when possible'],
    };

    const riskKeywords = [
      'breach',
      'violation',
      'non-compliant',
      'failing',
      'audit finding',
      'penalty',
    ];

    let urgencyScore = 0;
    let hasHighRisk = false;

    // Check for explicit timeline preferences in answers
    for (const [questionId, answer] of this.context.answers) {
      if (!answer.value) continue;

      const answerText = String(answer.value).toLowerCase();
      const question = this.framework.sections
        .flatMap((s) => s.questions)
        .find((q) => q.id === questionId);

      const combinedText = `${questionId} ${question?.text || ''} ${answerText}`.toLowerCase();

      // Check for timeline indicators
      if (timelineKeywords.urgent.some((keyword) => combinedText.includes(keyword))) {
        urgencyScore += 3;
      } else if (timelineKeywords.standard.some((keyword) => combinedText.includes(keyword))) {
        urgencyScore += 1;
      } else if (timelineKeywords.gradual.some((keyword) => combinedText.includes(keyword))) {
        urgencyScore -= 1;
      }

      // Check for risk indicators
      if (riskKeywords.some((keyword) => combinedText.includes(keyword))) {
        hasHighRisk = true;
        urgencyScore += 2;
      }

      // Check for negative compliance answers that indicate urgency
      if (
        answerText.includes('no') ||
        answerText.includes('not implemented') ||
        answerText.includes('non-compliant')
      ) {
        urgencyScore += 1;
      }
    }

    // Factor in current progress
    const currentProgress = this.getProgress();
    if (currentProgress.percentComplete < 40) {
      urgencyScore += 2;
    } else if (currentProgress.percentComplete < 70) {
      urgencyScore += 1;
    }

    // Determine timeline preference
    if (hasHighRisk || urgencyScore >= 5) {
      return 'urgent';
    } else if (urgencyScore >= 2) {
      return 'standard';
    } else {
      return 'gradual';
    }
  }

  private estimateEffort(gap: Gap): string {
    switch (gap.severity) {
      case 'critical':
        return '1-2 weeks';
      case 'high':
        return '2-4 weeks';
      case 'medium':
        return '1-2 months';
      default:
        return '2-3 months';
    }
  }

  private estimateTime(gap: Gap): string {
    // Similar to estimateEffort but could have different logic if needed
    switch (gap.severity) {
      case 'critical':
        return '1-2 weeks';
      case 'high':
        return '2-4 weeks';
      case 'medium':
        return '1-2 months';
      default:
        return '2-3 months';
    }
  }

  private suggestResources(_gap: Gap): string[] {
    // This can be enhanced with actual resource mapping
    return ['Implementation guide', 'Policy templates', 'Training materials'];
  }

  // AI Follow-up Question Methods
  public addAIFollowUpQuestions(triggerQuestionId: string, questions: Question[]): void {
    this.aiFollowUpQuestions.set(triggerQuestionId, questions);
  }

  public isInAIMode(): boolean {
    return this.isInAIQuestionMode;
  }

  public getCurrentAIQuestion(): Question | null {
    if (this.isInAIQuestionMode && this.currentAIQuestionIndex >= 0) {
      return this.pendingAIQuestions[this.currentAIQuestionIndex] || null;
    }
    return null;
  }

  public hasAIQuestionsRemaining(): boolean {
    return (
      this.isInAIQuestionMode && this.currentAIQuestionIndex < this.pendingAIQuestions.length - 1
    );
  }

  public getAIQuestionProgress(): { current: number; total: number } {
    return {
      current: this.currentAIQuestionIndex + 1,
      total: this.pendingAIQuestions.length,
    };
  }

  public getAnswers(): Map<string, Answer> {
    return this.context.answers;
  }

  public getContext(): AssessmentContext {
    return this.context;
  }

  private shouldTriggerAIFollowUp(question: Question): boolean {
    // Check if this question has AI follow-ups and if the answer indicates need for follow-up
    const answer = this.context.answers.get(question.id);
    if (!answer || answer.value === null || answer.value === undefined) return false;

    // Don't trigger AI for AI-generated questions
    if (answer.source === 'ai') return false;

    // Check question-specific AI trigger configuration
    if (question.metadata && question.metadata['aiTrigger'] === false) return false;

    // Check if question explicitly triggers AI (for test compatibility)
    if (question.metadata && question.metadata['triggers_ai'] === true) return true;

    // Enhanced logic considering multiple factors
    const { value } = answer;
    const section = this.getCurrentSection();

    // Use cached section analysis if available and recent (within 30 seconds)
    let sectionNeedsAttention = false;
    if (section) {
      const cacheKey = section.id;
      const cached = this.sectionAnalysisCache.get(cacheKey);
      const now = Date.now();

      if (cached && now - cached.timestamp < 30000) {
        sectionNeedsAttention = cached.result;
      } else {
        // Remove expired entry
        if (cached) {
          this.sectionAnalysisCache.delete(cacheKey);
        }
        // Calculate section score to determine if this area needs more investigation
        const sectionAnswers =
          section.questions.map((q) => this.context.answers.get(q.id)).filter(Boolean) || [];

        const negativeAnswers = sectionAnswers.filter(
          (a) => a && this.isNegativeAnswer(a.value, a.questionId),
        ).length;

        sectionNeedsAttention = negativeAnswers > sectionAnswers.length * 0.3;

        // Cache the result
        this.sectionAnalysisCache.set(cacheKey, {
          timestamp: now,
          result: sectionNeedsAttention,
        });
      }
    }

    // Trigger AI follow-up for:
    // 1. 'No' or negative compliance answers
    // 2. Low scale ratings (< 60% of max)
    // 3. Partial compliance answers
    // 4. High-weight questions with concerning answers
    // 5. Sections with multiple negative answers
    if (typeof value === 'string') {
      const lowConfidenceAnswers = [
        'no',
        'never',
        'not_implemented',
        'non_compliant',
        'partial',
        'unsure',
        'unknown',
      ];
      if (lowConfidenceAnswers.some((pattern) => value.toLowerCase().includes(pattern))) {
        return true;
      }
    }

    if (typeof value === 'number' && question.type === 'scale') {
      const scaleMax = question.scaleMax || 5;
      if (value < scaleMax * 0.6) {
        // Less than 60% of scale
        return true;
      }
    }

    // High-weight questions with negative answers
    if ((question.weight || 1) >= 3 && this.isNegativeAnswer(value, question.id)) {
      return true;
    }

    // Section-level analysis
    if (sectionNeedsAttention && this.isNegativeAnswer(value, question.id)) {
      return true;
    }

    return false;
  }

  private isNegativeAnswer(value: any, questionId: string): boolean {
    const question = this.framework.sections
      .flatMap((s) => s.questions)
      .find((q) => q.id === questionId);

    if (!question) return false;

    if (typeof value === 'string') {
      const negativePatterns = [
        'no',
        'never',
        'not',
        'none',
        'unable',
        'cannot',
        "don't",
        "haven't",
      ];
      return negativePatterns.some((pattern) => value.toLowerCase().includes(pattern));
    }

    if (typeof value === 'number' && question.type === 'scale') {
      const scaleMax = question.scaleMax || 5;
      return value < scaleMax * 0.5;
    }

    return false;
  }

  private async enterAIQuestionMode(): Promise<void> {
    try {
      const currentQuestion = this.getCurrentQuestion();
      if (!currentQuestion) return;

      const answer = this.context.answers.get(currentQuestion.id);
      if (!answer) return;

      // Use real AI service if enabled, otherwise fall back to mock
      if (this.config.enableAI !== false) {
        const response = await this.callAIServiceWithTimeout(
          () =>
            assessmentAIService.getFollowUpQuestions({
              question_id: currentQuestion.id,
              question_text: currentQuestion.text,
              user_answer: answer.value,
              assessment_context: {
                framework_id: this.framework.id,
                ...(this.getCurrentSection()?.id && { section_id: this.getCurrentSection()!.id }),
                current_answers: Object.fromEntries(this.context.answers),
                ...(this.context.businessProfileId && {
                  business_profile_id: this.context.businessProfileId,
                }),
              },
            }),
          'AI follow-up questions service',
        );

        if (response.follow_up_questions && response.follow_up_questions.length > 0) {
          this.pendingAIQuestions = response.follow_up_questions.map((q) => ({
            ...q,
            metadata: {
              ...(q.metadata || {}),
              isAIGenerated: true,
              reasoning: response.reasoning || 'AI-generated follow-up question',
            },
          }));
          this.currentAIQuestionIndex = 0;
          this.isInAIQuestionMode = true;
        }
      } else {
        // Fall back to mock questions for testing
        this.pendingAIQuestions = this.generateMockAIQuestions();
        this.currentAIQuestionIndex = 0;
        this.isInAIQuestionMode = true;
      }
    } catch (_error) {
      // Log error but don't break the assessment


      // Optionally use mock questions as fallback
      if (this.config.useMockAIOnError) {
        this.pendingAIQuestions = this.generateMockAIQuestions();
        this.currentAIQuestionIndex = 0;
        this.isInAIQuestionMode = true;
      }

      // Call error handler if provided
      if (this.config.onError) {
        this.config.onError(new Error('Failed to generate AI follow-up questions'));
      }
    }
  }

  private exitAIQuestionMode(): void {
    this.pendingAIQuestions = [];
    this.currentAIQuestionIndex = -1;
    this.isInAIQuestionMode = false;
  }

  private generateMockAIQuestions(): Question[] {
    const currentQuestion = this.getCurrentQuestion();
    const answer = currentQuestion ? this.context.answers.get(currentQuestion.id) : null;
    const section = this.getCurrentSection();

    if (!currentQuestion || !answer) {
      return [];
    }

    const timestamp = Date.now();
    const questions: Question[] = [];

    // Generate context-aware questions based on the trigger question type and answer
    if (currentQuestion.type === 'radio' || currentQuestion.type === 'select') {
      const answerValue = String(answer.value).toLowerCase();

      if (answerValue.includes('no') || answerValue.includes('not')) {
        questions.push({
          id: `ai_followup_${timestamp}_barriers`,
          type: 'checkbox',
          text: 'What are the main barriers preventing you from implementing this requirement?',
          options: [
            { value: 'budget', label: 'Budget constraints' },
            { value: 'expertise', label: 'Lack of technical expertise' },
            { value: 'time', label: 'Time constraints' },
            { value: 'priority', label: 'Other priorities' },
            { value: 'compliance', label: 'Unclear compliance requirements' },
            { value: 'tools', label: 'Lack of appropriate tools/systems' },
          ],
          validation: { required: false },
          metadata: {
            isAIGenerated: true,
            reasoning: `Based on your "${answer.value}" response, we want to understand implementation barriers.`,
          },
        });
      } else if (answerValue.includes('partial') || answerValue.includes('some')) {
        questions.push({
          id: `ai_followup_${timestamp}_completion`,
          type: 'scale',
          text: `On a scale of 1-10, how would you rate the completeness of your current implementation?`,
          scaleMin: 1,
          scaleMax: 10,
          scaleLabels: { min: 'Very incomplete', max: 'Fully complete' },
          validation: { required: false },
          metadata: {
            isAIGenerated: true,
            reasoning: `Your "${answer.value}" response suggests partial implementation - we need to understand the extent.`,
          },
        });
      }
    }

    if (currentQuestion.type === 'scale') {
      const scaleValue = Number(answer.value);
      const scaleMax = currentQuestion.scaleMax || 5;

      if (scaleValue < scaleMax * 0.6) {
        questions.push({
          id: `ai_followup_${timestamp}_improvement`,
          type: 'textarea',
          text: `You rated this area as ${scaleValue}/${scaleMax}. What specific improvements would have the highest impact?`,
          description:
            'Please describe 2-3 key areas where improvements would make the biggest difference.',
          validation: { required: false, minLength: 10 },
          metadata: {
            isAIGenerated: true,
            reasoning: `Your low rating (${scaleValue}/${scaleMax}) suggests room for improvement.`,
          },
        });
      }
    }

    // Add a general context question if no specific questions were generated
    if (questions.length === 0) {
      questions.push({
        id: `ai_followup_${timestamp}_context`,
        type: 'textarea',
        text: `Can you provide more context about your ${section?.title.toLowerCase() || 'current'} practices?`,
        description: 'Additional details will help us provide more targeted recommendations.',
        validation: { required: false },
        metadata: {
          isAIGenerated: true,
          reasoning: 'We need more context to provide better compliance guidance.',
        },
      });
    }

    // Limit to maximum 2 AI questions to avoid overwhelming users
    const maxQuestions = 2;
    if (questions.length > maxQuestions) {
      questions.splice(maxQuestions);
    }

    // Add priority question if we have room (either no questions or room for one more)
    if (questions.length < maxQuestions) {
      questions.push({
        id: `ai_followup_${timestamp}_priority`,
        type: 'radio',
        text: 'What is your timeline for addressing improvements in this area?',
        options: [
          { value: 'immediate', label: 'Immediate (within 1 month)' },
          { value: 'short_term', label: 'Short-term (1-3 months)' },
          { value: 'medium_term', label: 'Medium-term (3-6 months)' },
          { value: 'long_term', label: 'Long-term (6+ months)' },
          { value: 'no_timeline', label: 'No specific timeline' },
        ],
        validation: { required: false },
        metadata: {
          isAIGenerated: true,
          reasoning: 'Understanding your timeline helps prioritize recommendations.',
        },
      });
    }

    return questions;
  }

  // AI Service Helper Methods
  private async callAIServiceWithTimeout<T>(
    serviceCall: () => Promise<T>,
    serviceName: string,
  ): Promise<T> {
    let timeoutId: NodeJS.Timeout | undefined;

    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => {
        reject(new Error(`${serviceName} timeout after ${this.AI_TIMEOUT_MS}ms`));
      }, this.AI_TIMEOUT_MS);
    });

    try {
      const result = await Promise.race([serviceCall(), timeoutPromise]);

      // Clear timeout on successful completion
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = undefined;
      }

      return result;
    } catch (error) {
      // Ensure timeout is cleared on error
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = undefined;
      }
      throw error;
    }
  }

  private getCachedAIResponse(key: string): any | null {
    const cached = this.aiServiceCache.get(key);
    if (!cached) return null;

    const now = Date.now();
    if (now - cached.timestamp > this.AI_CACHE_TTL) {
      // Cache expired, remove it
      this.aiServiceCache.delete(key);
      return null;
    }

    return cached.data;
  }

  private setCachedAIResponse(key: string, data: unknown): void {
    this.aiServiceCache.set(key, {
      timestamp: Date.now(),
      data,
    });

    // Clean up expired cache entries periodically
    if (this.aiServiceCache.size > 50) {
      this.cleanupExpiredCache();
    }
  }

  private cleanupExpiredCache(): void {
    const now = Date.now();
    for (const [key, cached] of this.aiServiceCache.entries()) {
      if (now - cached.timestamp > this.AI_CACHE_TTL) {
        this.aiServiceCache.delete(key);
      }
    }
  }

  public destroy(): void {
    if (this.autoSaveTimer) {
      clearInterval(this.autoSaveTimer);
    }

    // Clear caches
    this.aiServiceCache.clear();
    this.sectionAnalysisCache.clear();

    this.saveProgress();
  }
}
