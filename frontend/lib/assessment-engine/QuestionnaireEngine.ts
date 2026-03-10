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
import * as scoring from './scoring';
import * as gapAnalysis from './gap-analysis';
import * as contextExtraction from './context-extraction';
import * as conditionEval from './condition-evaluator';
import * as aiQuestionsModule from './ai-questions';

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
    return conditionEval.evaluateConditions(conditions, this.context.answers);
  }

  private evaluateCondition(condition: QuestionCondition): boolean {
    return conditionEval.evaluateCondition(condition, this.context.answers);
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
    return scoring.calculateQuestionScore(question, answer);
  }

  private calculateMaturityLevel(score: number): AssessmentResult['maturityLevel'] {
    return scoring.calculateMaturityLevel(score);
  }

  private createGap(question: Question, answer: Answer | null, score: number): Gap {
    return gapAnalysis.createGap(question, answer, score, this.framework);
  }

  private getExpectedAnswer(question: Question): string {
    return gapAnalysis.getExpectedAnswer(question);
  }

  private assessImpact(question: Question, score: number): string {
    return gapAnalysis.assessImpact(question, score);
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
              business_profile: contextExtraction.getBusinessProfileFromContext(this.context),
              existing_policies: contextExtraction.getExistingPoliciesFromAnswers(this.context, this.framework),
              industry_context: contextExtraction.getIndustryContextFromAnswers(this.context, this.framework),
              timeline_preferences: contextExtraction.getTimelinePreferenceFromAnswers(this.context, this.framework, this.getProgress()),
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
            estimatedEffort: (rec as any).estimatedTime || gapAnalysis.estimateEffort(relatedGap),
            resources: rec.resources || gapAnalysis.suggestResources(relatedGap),
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
    return gapAnalysis.generateMockRecommendations(gaps);
  }

  private generateRecommendationText(gap: Gap): string {
    return gapAnalysis.generateRecommendationText(gap);
  }

  private getBusinessProfileFromContext(): Partial<BusinessProfile> {
    return contextExtraction.getBusinessProfileFromContext(this.context);
  }

  private getExistingPoliciesFromAnswers(): string[] {
    return contextExtraction.getExistingPoliciesFromAnswers(this.context, this.framework);
  }

  private getIndustryContextFromAnswers(): string {
    return contextExtraction.getIndustryContextFromAnswers(this.context, this.framework);
  }

  private getTimelinePreferenceFromAnswers(): 'urgent' | 'standard' | 'gradual' {
    return contextExtraction.getTimelinePreferenceFromAnswers(this.context, this.framework, this.getProgress());
  }

  private estimateEffort(gap: Gap): string {
    return gapAnalysis.estimateEffort(gap);
  }

  private estimateTime(gap: Gap): string {
    return gapAnalysis.estimateTime(gap);
  }

  private suggestResources(_gap: Gap): string[] {
    return gapAnalysis.suggestResources(_gap);
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
    return aiQuestionsModule.shouldTriggerAIFollowUp(
      question,
      this.context.answers,
      this.getCurrentSection(),
      this.config,
      this.framework,
      this.sectionAnalysisCache,
    );
  }

  private isNegativeAnswer(value: any, questionId: string): boolean {
    return aiQuestionsModule.isNegativeAnswer(value, questionId, this.framework);
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
    return aiQuestionsModule.generateMockAIQuestions(currentQuestion, answer || null, this.getCurrentSection());
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
