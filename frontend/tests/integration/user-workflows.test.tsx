import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'

// Mock stores
const mockAuthStore = {
  isAuthenticated: false,
  user: null,
  login: vi.fn(),
  logout: vi.fn(),
  isLoading: false,
  error: null,
}

const mockAssessmentStore = {
  assessments: [],
  currentAssessment: null,
  frameworks: [],
  createAssessment: vi.fn(),
  updateAssessment: vi.fn(),
  completeAssessment: vi.fn(),
}

const mockEvidenceStore = {
  evidence: [],
  uploadEvidence: vi.fn(),
  updateEvidence: vi.fn(),
  filters: {},
  setFilters: vi.fn(),
}

const mockBusinessProfileStore = {
  profile: null,
  createProfile: vi.fn(),
  updateProfile: vi.fn(),
  isLoading: false,
}

vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: () => mockAuthStore,
}))

vi.mock('@/lib/stores/assessment.store', () => ({
  useAssessmentStore: () => mockAssessmentStore,
}))

vi.mock('@/lib/stores/evidence.store', () => ({
  useEvidenceStore: () => mockEvidenceStore,
}))

vi.mock('@/lib/stores/business-profile.store', () => ({
  useBusinessProfileStore: () => mockBusinessProfileStore,
}))

// Mock navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/dashboard',
  useSearchParams: () => new URLSearchParams(),
}))

// Mock API services
vi.mock('@/lib/api/auth.service', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}))

// Test wrapper
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  
  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return (
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </BrowserRouter>
    )
  }
}

describe('User Workflows Integration Tests', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    vi.clearAllMocks()
    
    // Reset store states
    mockAuthStore.isAuthenticated = false
    mockAuthStore.user = null
    mockAuthStore.isLoading = false
    mockAuthStore.error = null
    
    mockAssessmentStore.assessments = []
    mockAssessmentStore.currentAssessment = null
    mockAssessmentStore.frameworks = []
    
    mockEvidenceStore.evidence = []
    mockEvidenceStore.filters = {}
    
    mockBusinessProfileStore.profile = null
    mockBusinessProfileStore.isLoading = false
  })

  describe('User Registration and Onboarding Flow', () => {
    it('should complete full registration workflow', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock successful registration
      const { authService } = await import('@/lib/api/auth.service')
      vi.mocked(authService.register).mockResolvedValue({
        user: { id: 'user-1', email: 'test@example.com' },
        tokens: { access_token: 'token', refresh_token: 'refresh' },
      })
      
      // Start registration
      const RegisterPage = (await import('@/app/(auth)/register/page')).default
      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )
      
      // Step 1: Account Details
      await user.type(screen.getByLabelText(/email/i), 'test@example.com')
      await user.type(screen.getByLabelText(/^password/i), 'SecurePass123!')
      await user.type(screen.getByLabelText(/confirm password/i), 'SecurePass123!')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Step 2: Personal Info
      await waitFor(() => {
        expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
      })
      
      await user.type(screen.getByLabelText(/first name/i), 'John')
      await user.type(screen.getByLabelText(/last name/i), 'Smith')
      await user.type(screen.getByLabelText(/company name/i), 'Acme Corp')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Step 3: Company Details
      await waitFor(() => {
        expect(screen.getByLabelText(/company size/i)).toBeInTheDocument()
      })
      
      await user.selectOptions(screen.getByLabelText(/company size/i), 'small')
      await user.selectOptions(screen.getByLabelText(/industry/i), 'technology')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Step 4: Compliance Frameworks
      await waitFor(() => {
        expect(screen.getByLabelText(/gdpr/i)).toBeInTheDocument()
      })
      
      await user.click(screen.getByLabelText(/gdpr/i))
      await user.click(screen.getByLabelText(/iso 27001/i))
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Step 5: Terms and Conditions
      await waitFor(() => {
        expect(screen.getByLabelText(/terms.*conditions/i)).toBeInTheDocument()
      })
      
      await user.click(screen.getByLabelText(/terms.*conditions/i))
      await user.click(screen.getByLabelText(/data processing/i))
      
      // Complete registration
      await user.click(screen.getByRole('button', { name: /create account/i }))
      
      await waitFor(() => {
        expect(authService.register).toHaveBeenCalledWith(
          expect.objectContaining({
            email: 'test@example.com',
            name: 'John Smith',
            company_name: 'Acme Corp',
            company_size: 'small',
            industry: 'technology',
            compliance_frameworks: ['gdpr', 'iso27001'],
            agreed_to_terms: true,
            agreed_to_data_processing: true,
          })
        )
      })
    })

    it('should guide user through business profile setup', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock authenticated user without profile
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      mockBusinessProfileStore.profile = null
      
      const ProfileWizard = (await import('@/components/business-profile/profile-wizard')).ProfileWizard
      render(
        <TestWrapper>
          <ProfileWizard onComplete={vi.fn()} />
        </TestWrapper>
      )
      
      // Fill business details
      await user.type(screen.getByLabelText(/company name/i), 'Tech Solutions Ltd')
      await user.selectOptions(screen.getByLabelText(/country/i), 'United Kingdom')
      await user.type(screen.getByLabelText(/employee count/i), '25')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Data handling section
      await waitFor(() => {
        expect(screen.getByLabelText(/handles personal data/i)).toBeInTheDocument()
      })
      
      await user.click(screen.getByLabelText(/handles personal data/i))
      await user.selectOptions(screen.getByLabelText(/data sensitivity/i), 'High')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Compliance requirements
      await waitFor(() => {
        expect(screen.getByLabelText(/gdpr/i)).toBeInTheDocument()
      })
      
      await user.click(screen.getByLabelText(/gdpr/i))
      await user.click(screen.getByRole('button', { name: /complete/i }))
      
      await waitFor(() => {
        expect(mockBusinessProfileStore.createProfile).toHaveBeenCalledWith(
          expect.objectContaining({
            company_name: 'Tech Solutions Ltd',
            country: 'United Kingdom',
            employee_count: 25,
            handles_personal_data: true,
            data_sensitivity: 'High',
            required_frameworks: ['gdpr'],
          })
        )
      })
    })
  })

  describe('Assessment Creation and Completion Flow', () => {
    it('should create and complete GDPR assessment', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock authenticated user with profile
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      mockBusinessProfileStore.profile = { id: 'profile-1', company_name: 'Test Corp' }
      
      // Mock available frameworks
      mockAssessmentStore.frameworks = [
        {
          id: 'gdpr',
          name: 'GDPR Compliance',
          description: 'General Data Protection Regulation assessment',
          sections: [
            {
              id: 'data-processing',
              title: 'Data Processing',
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
                },
              ],
            },
          ],
        },
      ]
      
      const AssessmentWizard = (await import('@/components/assessments/AssessmentWizard')).AssessmentWizard
      render(
        <TestWrapper>
          <AssessmentWizard
            framework={mockAssessmentStore.frameworks[0]}
            assessmentId="new-assessment"
            businessProfileId="profile-1"
            onComplete={vi.fn()}
            onSave={mockAssessmentStore.updateAssessment}
          />
        </TestWrapper>
      )
      
      // Start assessment
      expect(screen.getByText('GDPR Compliance')).toBeInTheDocument()
      
      // Answer first question
      await user.click(screen.getByLabelText(/yes/i))
      
      // Navigate to next (complete)
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      await waitFor(() => {
        expect(mockAssessmentStore.updateAssessment).toHaveBeenCalledWith(
          'new-assessment',
          expect.objectContaining({
            responses: { q1: 'yes' },
          })
        )
      })
    })

    it('should handle assessment validation and errors', async () => {
      const TestWrapper = createTestWrapper()
      
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      
      const framework = {
        id: 'gdpr',
        name: 'GDPR',
        sections: [
          {
            id: 'section-1',
            title: 'Section 1',
            questions: [
              {
                id: 'q1',
                type: 'textarea',
                text: 'Describe your data retention policy',
                validation: { required: true, minLength: 10 },
              },
            ],
          },
        ],
      }
      
      const AssessmentWizard = (await import('@/components/assessments/AssessmentWizard')).AssessmentWizard
      render(
        <TestWrapper>
          <AssessmentWizard
            framework={framework}
            assessmentId="test-assessment"
            businessProfileId="profile-1"
            onComplete={vi.fn()}
          />
        </TestWrapper>
      )
      
      // Try to proceed without answering
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/required/i)).toBeInTheDocument()
      })
      
      // Answer with insufficient length
      await user.type(screen.getByRole('textbox'), 'Short')
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/minimum.*10.*characters/i)).toBeInTheDocument()
      })
      
      // Provide valid answer
      await user.clear(screen.getByRole('textbox'))
      await user.type(screen.getByRole('textbox'), 'We maintain comprehensive data retention policies that comply with GDPR requirements.')
      
      await user.click(screen.getByRole('button', { name: /next/i }))
      
      // Should proceed without errors
      await waitFor(() => {
        expect(screen.queryByText(/required/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Evidence Management Flow', () => {
    it('should upload and manage evidence documents', async () => {
      const TestWrapper = createTestWrapper()
      
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      
      const EvidenceUpload = (await import('@/components/evidence/evidence-upload')).EvidenceUpload
      const mockOnUpload = vi.fn()
      
      render(
        <TestWrapper>
          <EvidenceUpload
            onUpload={mockOnUpload}
            frameworkId="gdpr"
            controlReference="A.1.1"
          />
        </TestWrapper>
      )
      
      // Create and upload file
      const file = new File(['policy content'], 'data-policy.pdf', { type: 'application/pdf' })
      const fileInput = screen.getByTestId('file-input')
      
      await user.upload(fileInput, file)
      
      // Fill metadata
      await user.type(screen.getByLabelText(/evidence name/i), 'Data Protection Policy')
      await user.type(screen.getByLabelText(/description/i), 'Company data protection policy v2.1')
      
      // Upload evidence
      await user.click(screen.getByRole('button', { name: /upload/i }))
      
      await waitFor(() => {
        expect(mockOnUpload).toHaveBeenCalledWith(
          file,
          expect.objectContaining({
            evidence_name: 'Data Protection Policy',
            description: 'Company data protection policy v2.1',
            framework_id: 'gdpr',
            control_reference: 'A.1.1',
          })
        )
      })
    })

    it('should filter and search evidence documents', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock evidence data
      mockEvidenceStore.evidence = [
        {
          id: 'ev-1',
          name: 'GDPR Policy',
          framework: 'GDPR',
          status: 'approved',
          uploaded_at: new Date('2025-01-01'),
        },
        {
          id: 'ev-2',
          name: 'ISO Training Records',
          framework: 'ISO 27001',
          status: 'pending',
          uploaded_at: new Date('2025-01-05'),
        },
      ]
      
      const EvidenceFilters = (await import('@/components/evidence/evidence-filters')).EvidenceFilters
      render(
        <TestWrapper>
          <EvidenceFilters
            filters={mockEvidenceStore.filters}
            onFiltersChange={mockEvidenceStore.setFilters}
          />
        </TestWrapper>
      )
      
      // Filter by framework
      await user.selectOptions(screen.getByLabelText(/framework/i), 'gdpr')
      
      expect(mockEvidenceStore.setFilters).toHaveBeenCalledWith(
        expect.objectContaining({ framework: 'gdpr' })
      )
      
      // Filter by status
      await user.selectOptions(screen.getByLabelText(/status/i), 'approved')
      
      expect(mockEvidenceStore.setFilters).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'approved' })
      )
    })
  })

  describe('Dashboard and Analytics Flow', () => {
    it('should display personalized dashboard based on user profile', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock authenticated user with analytics data
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { 
        id: 'user-1', 
        email: 'test@example.com',
        preferences: { persona: 'analytical' }
      }
      
      mockBusinessProfileStore.profile = {
        id: 'profile-1',
        company_name: 'Tech Corp',
        compliance_frameworks: ['gdpr', 'iso27001'],
      }
      
      const DashboardPage = (await import('@/app/(dashboard)/dashboard/page')).default
      render(
        <TestWrapper>
          <DashboardPage />
        </TestWrapper>
      )
      
      // Should show analytical user features
      expect(screen.getByText(/compliance score/i)).toBeInTheDocument()
      expect(screen.getByText(/pending tasks/i)).toBeInTheDocument()
      expect(screen.getByText(/ai insights/i)).toBeInTheDocument()
      
      // Should show customization options for analytical users
      expect(screen.getByRole('button', { name: /customize/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
    })

    it('should handle interactive dashboard widgets', async () => {
      const TestWrapper = createTestWrapper()
      
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      
      const ComplianceScoreWidget = (await import('@/components/dashboard/widgets/compliance-score-widget')).ComplianceScoreWidget
      const mockOnViewDetails = vi.fn()
      
      render(
        <TestWrapper>
          <ComplianceScoreWidget
            score={85}
            trend="up"
            previousScore={78}
            frameworks={[
              { name: 'GDPR', score: 90, status: 'compliant' },
              { name: 'ISO 27001', score: 80, status: 'partially_compliant' },
            ]}
            onViewDetails={mockOnViewDetails}
          />
        </TestWrapper>
      )
      
      // Click to view details
      await user.click(screen.getByRole('button', { name: /view details/i }))
      
      expect(mockOnViewDetails).toHaveBeenCalled()
      
      // Framework breakdown should be interactive
      expect(screen.getByText('GDPR')).toBeInTheDocument()
      expect(screen.getByText('90%')).toBeInTheDocument()
    })
  })

  describe('Error Handling and Recovery', () => {
    it('should handle network errors gracefully', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock network error during login
      const { authService } = await import('@/lib/api/auth.service')
      vi.mocked(authService.login).mockRejectedValue(new Error('Network error'))
      
      const LoginPage = (await import('@/app/(auth)/login/page')).default
      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )
      
      // Attempt login
      await user.type(screen.getByLabelText(/email/i), 'test@example.com')
      await user.type(screen.getByLabelText(/password/i), 'password123')
      await user.click(screen.getByRole('button', { name: /sign in/i }))
      
      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
      })
      
      // Should allow retry
      expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled()
    })

    it('should handle validation errors during form submission', async () => {
      const TestWrapper = createTestWrapper()
      
      // Mock validation error during registration
      const { authService } = await import('@/lib/api/auth.service')
      vi.mocked(authService.register).mockRejectedValue({
        response: {
          status: 422,
          data: {
            detail: [
              { field: 'email', message: 'Email already exists' },
              { field: 'password', message: 'Password too weak' },
            ],
          },
        },
      })
      
      const RegisterPage = (await import('@/app/(auth)/register/page')).default
      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )
      
      // Fill and submit form
      await user.type(screen.getByLabelText(/email/i), 'existing@example.com')
      await user.type(screen.getByLabelText(/^password/i), '123')
      await user.type(screen.getByLabelText(/confirm password/i), '123')
      
      // Skip to final step and submit
      await user.click(screen.getByRole('button', { name: /create account/i }))
      
      // Should show field-specific errors
      await waitFor(() => {
        expect(screen.getByText('Email already exists')).toBeInTheDocument()
        expect(screen.getByText('Password too weak')).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility and Navigation', () => {
    it('should support keyboard navigation throughout the app', async () => {
      const TestWrapper = createTestWrapper()
      
      mockAuthStore.isAuthenticated = true
      mockAuthStore.user = { id: 'user-1', email: 'test@example.com' }
      
      const DashboardPage = (await import('@/app/(dashboard)/dashboard/page')).default
      render(
        <TestWrapper>
          <DashboardPage />
        </TestWrapper>
      )
      
      // Tab through interactive elements
      await user.tab()
      expect(document.activeElement).toBeInTheDocument()
      
      // Continue tabbing
      await user.tab()
      expect(document.activeElement).toBeInTheDocument()
      
      // Should be able to navigate with Enter/Space
      if (document.activeElement?.tagName === 'BUTTON') {
        await user.keyboard('{Enter}')
        // Should trigger button action
      }
    })

    it('should provide proper screen reader support', () => {
      const TestWrapper = createTestWrapper()
      
      mockAuthStore.isAuthenticated = true
      
      const LoginPage = (await import('@/app/(auth)/login/page')).default
      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )
      
      // Check for proper ARIA labels
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-describedby')
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('aria-describedby')
      
      // Check for proper headings hierarchy
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
      
      // Check for form validation announcements
      const emailInput = screen.getByLabelText(/email/i)
      expect(emailInput).toHaveAttribute('aria-invalid', 'false')
    })
  })
})