import { http, HttpResponse } from 'msw';

const baseURL = 'http://localhost:8000/api';

export const handlers = [
  // Auth endpoints
  http.post(`${baseURL}/v1/auth/login`, () => {
    return HttpResponse.json({
      data: {
        tokens: {
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
        },
        user: {
          id: 'user-123',
          email: 'test@example.com',
          is_active: true,
          permissions: ['read', 'write'],
          role: 'user',
        },
      },
    });
  }),

  http.post(`${baseURL}/v1/auth/register`, () => {
    return HttpResponse.json(
      {
        data: {
          user: { id: 'user-new', email: 'newuser@example.com' },
          tokens: {
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          },
        },
      },
      { status: 201 },
    );
  }),

  http.post(`${baseURL}/v1/auth/logout`, () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
  }),

  http.get(`${baseURL}/v1/auth/me`, () => {
    return HttpResponse.json({
      data: {
        id: 'user-123',
        email: 'test@example.com',
        is_active: true,
        permissions: ['read', 'write'],
        role: 'user',
      },
    });
  }),

  http.post(`${baseURL}/v1/auth/refresh`, () => {
    return HttpResponse.json({
      data: {
        access_token: 'refreshed-access-token',
        refresh_token: 'refreshed-refresh-token',
      },
    });
  }),

  // Assessment endpoints
  http.get(`${baseURL}/assessments`, ({ request }) => {
    const url = new URL(request.url);
    const page = url.searchParams.get('page') || '1';
    const pageSize = url.searchParams.get('page_size') || '20';

    return HttpResponse.json({
      data: {
        items: [
          { id: 'assess-1', name: 'Test Assessment 1', status: 'completed' },
          { id: 'assess-2', name: 'Test Assessment 2', status: 'in_progress' },
        ],
        total: 2,
        page: parseInt(page),
        size: parseInt(pageSize),
      },
    });
  }),

  http.post(`${baseURL}/assessments`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json(
      {
        data: {
          id: 'assess-new',
          ...body,
          status: 'draft',
          created_at: new Date().toISOString(),
        },
      },
      { status: 201 },
    );
  }),

  http.get(`${baseURL}/assessments/:id`, ({ params }) => {
    return HttpResponse.json({
      data: {
        id: params['id'],
        name: 'Test Assessment',
        status: 'completed',
        framework_id: 'gdpr',
        responses: { q1: 'yes', q2: 'no' },
        score: 85,
      },
    });
  }),

  http.put(`${baseURL}/assessments/:id`, async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: params['id'],
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.patch(`${baseURL}/assessments/:id`, async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: params['id'],
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.post(`${baseURL}/assessments/:id/complete`, ({ params }) => {
    return HttpResponse.json({
      data: {
        id: params['id'],
        status: 'completed',
        completed_at: new Date().toISOString(),
      },
    });
  }),

  // Evidence endpoints
  http.get(`${baseURL}/evidence`, ({ request }) => {
    const url = new URL(request.url);
    const framework = url.searchParams.get('framework_id');
    const status = url.searchParams.get('status');

    return HttpResponse.json({
      data: {
        items: [
          {
            id: 'ev-1',
            title: 'Evidence 1',
            framework_id: framework || 'gdpr',
            status: status || 'collected',
            created_at: new Date().toISOString(),
            evidence_type: 'document',
          },
          {
            id: 'ev-2',
            title: 'Evidence 2',
            framework_id: 'iso27001',
            status: 'pending',
            created_at: new Date().toISOString(),
            evidence_type: 'document',
          },
        ],
        total: 2,
      },
    });
  }),

  http.post(`${baseURL}/evidence`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json(
      {
        data: {
          id: 'ev-new',
          ...body,
          status: 'pending',
          created_at: new Date().toISOString(),
        },
      },
      { status: 201 },
    );
  }),

  http.post(`${baseURL}/evidence/upload`, () => {
    return HttpResponse.json(
      {
        data: {
          id: 'ev-new',
          name: 'Uploaded Evidence',
          status: 'uploaded',
          uploaded_at: new Date().toISOString(),
        },
      },
      { status: 201 },
    );
  }),

  http.put(`${baseURL}/evidence/:id`, async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: params['id'],
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.patch(`${baseURL}/evidence/:id`, async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: params['id'],
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.delete(`${baseURL}/evidence/:id`, ({ params }) => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Business Profile endpoints
  http.get(`${baseURL}/business-profiles/me`, () => {
    return HttpResponse.json({
      data: {
        id: 'profile-123',
        company_name: 'Test Company',
        industry: 'Technology',
        employee_count: 50,
        country: 'United Kingdom',
        data_sensitivity: 'Medium',
        handles_personal_data: true,
        required_frameworks: ['gdpr'],
      },
    });
  }),

  http.get(`${baseURL}/business-profiles`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'profile-123',
          company_name: 'Test Company',
          industry: 'Technology',
          employee_count: 50,
        },
      ],
    });
  }),

  http.post(`${baseURL}/business-profiles`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json(
      {
        data: {
          id: 'profile-new',
          ...body,
          created_at: new Date().toISOString(),
        },
      },
      { status: 201 },
    );
  }),

  http.put(`${baseURL}/business-profiles`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: 'profile-123',
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.put(`${baseURL}/business-profiles/:id`, async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        id: params['id'],
        ...body,
        updated_at: new Date().toISOString(),
      },
    });
  }),

  // Framework endpoints
  http.get(`${baseURL}/frameworks`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'gdpr',
          name: 'GDPR',
          description: 'General Data Protection Regulation',
          sections: [],
        },
        {
          id: 'iso27001',
          name: 'ISO 27001',
          description: 'Information Security Management',
          sections: [],
        },
      ],
    });
  }),

  // AI endpoints
  http.post(`${baseURL}/ai/assessments/follow-up-questions`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        follow_up_questions: [
          {
            id: 'ai-q1',
            text: 'Can you provide more details about your data processing activities?',
            type: 'textarea',
            validation: { required: false },
            metadata: {
              source: 'ai',
              reasoning: 'Based on your previous answer, we need more details',
              isAIGenerated: true,
            },
          },
        ],
        reasoning: 'Follow-up needed for compliance assessment',
      },
    });
  }),

  http.post(`${baseURL}/ai/assessments/personalized-recommendations`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        recommendations: [
          {
            id: 'rec-1',
            title: 'Implement Data Protection Policy',
            description:
              'Based on your assessment, you need a comprehensive data protection policy.',
            priority: 'high',
            category: 'Data Protection',
            estimatedEffort: 'Medium',
            timeline: '2-4 weeks',
          },
        ],
        implementation_plan: {
          phases: [],
          total_timeline_weeks: 8,
          resource_requirements: [],
        },
        success_metrics: [],
      },
    });
  }),

  http.post(`${baseURL}/ai/assessments/enhanced-analysis`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        analysis: 'Enhanced AI analysis based on your business profile and assessment context.',
        recommendations: [
          {
            id: 'enhanced-rec-1',
            title: 'Enhanced Data Protection Recommendation',
            description: 'AI-generated recommendation based on comprehensive analysis.',
            priority: 'high',
            category: 'Data Protection',
          },
        ],
        confidence: 0.85,
        sources: ['business_profile', 'assessment_context', 'industry_standards'],
      },
    });
  }),

  http.post(`${baseURL}/ai/assessments/question-help`, async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      data: {
        explanation:
          'This question is asking about your data processing activities to ensure GDPR compliance.',
        examples: [
          'Customer data processing for order fulfillment',
          'Employee data processing for payroll',
          'Marketing data processing for communications',
        ],
        guidance:
          'Please provide specific details about what types of data you process and for what purposes.',
      },
    });
  }),

  // Error simulation endpoints
  http.get(`${baseURL}/error/401`, () => {
    return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
  }),

  http.get(`${baseURL}/error/404`, () => {
    return HttpResponse.json({ detail: 'Resource not found' }, { status: 404 });
  }),

  http.get(`${baseURL}/error/422`, () => {
    return HttpResponse.json(
      {
        detail: [
          { field: 'email', message: 'Invalid email format' },
          { field: 'password', message: 'Password too short' },
        ],
      },
      { status: 422 },
    );
  }),

  http.get(`${baseURL}/error/429`, () => {
    return HttpResponse.json({ detail: 'Rate limit exceeded' }, { status: 429 });
  }),

  http.get(`${baseURL}/error/500`, () => {
    return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }),
];

// Error handlers for specific test scenarios
export const errorHandlers = {
  networkError: [
    http.get('*', () => {
      return HttpResponse.error();
    }),
  ],

  timeoutError: [
    http.get('*', async () => {
      await new Promise((resolve) => setTimeout(resolve, 10000));
      return HttpResponse.json({});
    }),
  ],
};

// Enhanced auth response handlers
export const authHandlers = [
  http.post('/api/auth/login', () => {
    return HttpResponse.json({
      access_token: 'mock-access-token',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User'
      }
    }, { status: 200 });
  }),

  http.post('/api/auth/register', () => {
    return HttpResponse.json({
      access_token: 'mock-access-token',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 'user-456',
        email: 'newuser@example.com',
        name: 'New User'
      }
    }, { status: 201 });
  }),

  http.get('/api/auth/me', ({ request }) => {
    const authHeader = request.headers.get('Authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json({ detail: 'No authentication token available' }, { status: 401 });
    }
    
    return HttpResponse.json({
      id: 'user-123',
      email: 'test@example.com',
      name: 'Test User'
    }, { status: 200 });
  }),
  
  // Freemium endpoints
  http.post(`${baseURL}/freemium/capture-email`, async ({ request }) => {
    const body = await request.json() as any;
    
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!body.email || !emailRegex.test(body.email)) {
      return HttpResponse.json(
        { detail: 'Invalid email format' },
        { status: 400 }
      );
    }
    
    // Validate consent
    if (!body.consent) {
      return HttpResponse.json(
        { detail: 'Consent is required' },
        { status: 400 }
      );
    }
    
    return HttpResponse.json({
      success: true,
      token: 'mock-session-token',
      session_id: 'session-123',
    });
  }),
  
  http.post(`${baseURL}/freemium/sessions`, async ({ request }) => {
    const body = await request.json() as any;
    
    // Validate business type
    const validBusinessTypes = ['technology', 'retail', 'healthcare', 'finance', 'other'];
    if (!body.business_type || !validBusinessTypes.includes(body.business_type)) {
      return HttpResponse.json(
        { detail: 'Invalid business type' },
        { status: 400 }
      );
    }
    
    // Validate company size
    const validSizes = ['1-10', '10-50', '50-200', '200-500', '500+'];
    if (!body.company_size || !validSizes.includes(body.company_size)) {
      return HttpResponse.json(
        { detail: 'Invalid company size' },
        { status: 400 }
      );
    }
    
    return HttpResponse.json({
      session_id: 'session-123',
      session_token: 'mock-session-token',
      question_id: 'q1',
      question_text: 'Do you process customer personal data?',
      question_type: 'yes_no',
      progress: {
        current_question: 1,
        total_questions_estimate: 10,
        progress_percentage: 10,
      },
    });
  }),
  
  http.post(`${baseURL}/freemium/answer-question`, async ({ request }) => {
    const body = await request.json() as any;
    
    if (!body.session_token || !body.question_id || !body.answer) {
      return HttpResponse.json(
        { detail: 'Missing required fields' },
        { status: 400 }
      );
    }
    
    return HttpResponse.json({
      next_question: {
        question_id: 'q2',
        question_text: 'What type of data do you collect?',
        question_type: 'multiple_choice',
        options: ['Personal', 'Financial', 'Health', 'Other'],
      },
      progress: {
        current_question: 2,
        total_questions_estimate: 10,
        progress_percentage: 20,
      },
    });
  }),
  
  http.get(`${baseURL}/freemium/results/:token`, ({ params }) => {
    return HttpResponse.json({
      compliance_score: 75,
      risk_score: 25,
      recommendations: [
        'Implement data encryption',
        'Create privacy policy',
        'Set up access controls',
      ],
    });
  }),
];

// Add auth handlers to main handlers array
handlers.push(...authHandlers);
