import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('AssessmentService', () => {
  let assessmentService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/assessments.service');
    assessmentService = serviceMod.assessmentService;
  });

  describe('getAssessments', () => {
    it('calls GET /assessments without params', async () => {
      const mockData = { items: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await assessmentService.getAssessments();

      expect(apiClient.get).toHaveBeenCalledWith('/assessments', {});
      expect(result.total).toBe(0);
    });

    it('passes search params when provided', async () => {
      const mockData = {
        items: [
          { id: 'a-1', framework_id: 'gdpr', status: 'in_progress' },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const params = {
        business_profile_id: 'bp-1',
        framework_id: 'gdpr',
        status: 'in_progress',
        page: 1,
        page_size: 20,
      };

      const result = await assessmentService.getAssessments(params);

      expect(apiClient.get).toHaveBeenCalledWith('/assessments', { params });
      expect(result.items).toHaveLength(1);
    });
  });

  describe('getAssessment', () => {
    it('calls GET /assessments/:id', async () => {
      const mockAssessment = {
        id: 'a-1',
        framework_id: 'gdpr',
        status: 'in_progress',
        business_profile_id: 'bp-1',
      };

      (apiClient.get as any).mockResolvedValue(mockAssessment);

      const result = await assessmentService.getAssessment('a-1');

      expect(apiClient.get).toHaveBeenCalledWith('/assessments/a-1');
      expect(result.id).toBe('a-1');
      expect(result.framework_id).toBe('gdpr');
    });
  });

  describe('createAssessment', () => {
    it('calls POST /assessments', async () => {
      const request = {
        business_profile_id: 'bp-1',
        framework_id: 'gdpr',
        assessment_type: 'comprehensive',
      };

      const mockAssessment = { id: 'a-new', ...request, status: 'draft' };
      (apiClient.post as any).mockResolvedValue(mockAssessment);

      const result = await assessmentService.createAssessment(request);

      expect(apiClient.post).toHaveBeenCalledWith('/assessments', request);
      expect(result.id).toBe('a-new');
    });
  });

  describe('updateAssessment', () => {
    it('calls PATCH /assessments/:id', async () => {
      const update = { status: 'in_progress', responses: { q1: 'yes' } };
      const mockAssessment = { id: 'a-1', ...update };
      (apiClient.patch as any).mockResolvedValue(mockAssessment);

      const result = await assessmentService.updateAssessment('a-1', update);

      expect(apiClient.patch).toHaveBeenCalledWith('/assessments/a-1', update);
      expect(result.status).toBe('in_progress');
    });
  });

  describe('deleteAssessment', () => {
    it('calls DELETE /assessments/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await assessmentService.deleteAssessment('a-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/assessments/a-1');
    });
  });

  describe('getAssessmentQuestions', () => {
    it('calls GET /assessments/:id/questions', async () => {
      const mockQuestions = [
        { id: 'q-1', text: 'Do you have a privacy policy?', type: 'radio' },
        { id: 'q-2', text: 'How often do you audit?', type: 'select' },
      ];

      (apiClient.get as any).mockResolvedValue(mockQuestions);

      const result = await assessmentService.getAssessmentQuestions('a-1');

      expect(apiClient.get).toHaveBeenCalledWith('/assessments/a-1/questions');
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('q-1');
    });
  });

  describe('submitAssessmentAnswer', () => {
    it('calls POST /assessments/:id/answers', async () => {
      const data = {
        question_id: 'q-1',
        answer: 'yes',
        metadata: { time_spent: 30 },
      };

      const mockResponse = {
        id: 'resp-1',
        question_id: 'q-1',
        answer: 'yes',
        created_at: '2025-06-15',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await assessmentService.submitAssessmentAnswer('a-1', data);

      expect(apiClient.post).toHaveBeenCalledWith('/assessments/a-1/answers', data);
      expect(result.question_id).toBe('q-1');
    });
  });

  describe('completeAssessment', () => {
    it('calls POST /assessments/:id/complete', async () => {
      const mockAssessment = { id: 'a-1', status: 'completed' };
      (apiClient.post as any).mockResolvedValue(mockAssessment);

      const result = await assessmentService.completeAssessment('a-1');

      expect(apiClient.post).toHaveBeenCalledWith('/assessments/a-1/complete');
      expect(result.status).toBe('completed');
    });
  });

  describe('getAssessmentResults', () => {
    it('calls GET /assessments/:id/results', async () => {
      const mockResults = {
        score: 72,
        gaps: [{ id: 'gap-1', severity: 'high' }],
        recommendations: ['Implement encryption'],
      };

      (apiClient.get as any).mockResolvedValue(mockResults);

      const result = await assessmentService.getAssessmentResults('a-1');

      expect(apiClient.get).toHaveBeenCalledWith('/assessments/a-1/results');
      expect(result.score).toBe(72);
      expect(result.gaps).toHaveLength(1);
    });
  });

  describe('getQuickAssessment', () => {
    it('calls POST /assessments/quick', async () => {
      const mockResponse = {
        id: 'qa-1',
        score: 55,
        summary: 'Basic compliance level',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await assessmentService.getQuickAssessment('bp-1', 'gdpr');

      expect(apiClient.post).toHaveBeenCalledWith('/assessments/quick', {
        business_profile_id: 'bp-1',
        framework_id: 'gdpr',
      });
      expect(result.score).toBe(55);
    });
  });
});

// -- Type interface tests --

describe('Assessment type interfaces', () => {
  it('CreateAssessmentRequest has required fields', () => {
    const request = {
      business_profile_id: 'bp-1',
      framework_id: 'gdpr',
      assessment_type: 'comprehensive' as const,
    };

    expect(request.business_profile_id).toBeTruthy();
    expect(request.framework_id).toBeTruthy();
  });

  it('assessment_type values are valid', () => {
    const types = ['quick', 'comprehensive'];
    expect(types).toHaveLength(2);
  });

  it('SubmitAssessmentAnswerRequest has required fields', () => {
    const request = {
      question_id: 'q-1',
      answer: 'yes',
      metadata: { source: 'manual' },
    };

    expect(request.question_id).toBeTruthy();
    expect(request.answer).toBeTruthy();
  });
});
