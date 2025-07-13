import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EvidenceUpload } from '@/components/evidence/evidence-upload'
import { EvidenceList } from '@/components/evidence/evidence-list'
import { EvidenceViewer } from '@/components/evidence/evidence-viewer'
import { EvidenceFilters } from '@/components/evidence/evidence-filters'

// Mock file API
Object.defineProperty(window, 'File', {
  value: class MockFile {
    constructor(public bits: any[], public name: string, public options: any = {}) {
      this.type = options.type || ''
      this.size = bits.reduce((acc, bit) => acc + (bit.length || 0), 0)
    }
    type: string
    size: number
  },
})

// Mock drag and drop API
Object.defineProperty(window, 'DataTransfer', {
  value: class MockDataTransfer {
    files: File[] = []
    items: any[] = []
    types: string[] = []
  },
})

// Mock react-dropzone
vi.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop, accept, maxSize }: any) => ({
    getRootProps: () => ({
      'data-testid': 'dropzone',
      onClick: () => {},
    }),
    getInputProps: () => ({
      'data-testid': 'file-input',
    }),
    isDragActive: false,
    isDragReject: false,
    acceptedFiles: [],
    rejectedFiles: [],
  }),
}))

// Mock toast
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

describe('Evidence Management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('EvidenceUpload', () => {
    const mockProps = {
      onUpload: vi.fn(),
      frameworkId: 'gdpr',
      controlReference: 'A.1.1',
      maxFileSize: 10 * 1024 * 1024, // 10MB
      acceptedFileTypes: ['pdf', 'docx', 'xlsx'],
    }

    it('should render upload dropzone', () => {
      render(<EvidenceUpload {...mockProps} />)
      
      expect(screen.getByTestId('dropzone')).toBeInTheDocument()
      expect(screen.getByText(/drag.*drop.*files/i)).toBeInTheDocument()
    })

    it('should display accepted file types', () => {
      render(<EvidenceUpload {...mockProps} />)
      
      expect(screen.getByText(/pdf.*docx.*xlsx/i)).toBeInTheDocument()
    })

    it('should show file size limit', () => {
      render(<EvidenceUpload {...mockProps} />)
      
      expect(screen.getByText(/10 MB/i)).toBeInTheDocument()
    })

    it('should handle file selection', async () => {
      render(<EvidenceUpload {...mockProps} />)
      
      const fileInput = screen.getByTestId('file-input')
      const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      
      fireEvent.change(fileInput, { target: { files: [file] } })
      
      await waitFor(() => {
        expect(screen.getByText('test.pdf')).toBeInTheDocument()
      })
    })

    it('should validate file types', async () => {
      render(<EvidenceUpload {...mockProps} />)
      
      const fileInput = screen.getByTestId('file-input')
      const invalidFile = new File(['test'], 'test.txt', { type: 'text/plain' })
      
      fireEvent.change(fileInput, { target: { files: [invalidFile] } })
      
      await waitFor(() => {
        expect(screen.getByText(/file type not supported/i)).toBeInTheDocument()
      })
    })

    it('should validate file size', async () => {
      const file = new File(['x'.repeat(15 * 1024 * 1024)], 'large.pdf', { type: 'application/pdf' })
      render(<EvidenceUpload {...mockProps} />)
      
      const fileInput = screen.getByTestId('file-input')
      fireEvent.change(fileInput, { target: { files: [file] } })
      
      await waitFor(() => {
        expect(screen.getByText(/file too large/i)).toBeInTheDocument()
      })
    })

    it('should handle upload with metadata', async () => {
      render(<EvidenceUpload {...mockProps} />)
      
      // Add file
      const fileInput = screen.getByTestId('file-input')
      const file = new File(['content'], 'policy.pdf', { type: 'application/pdf' })
      fireEvent.change(fileInput, { target: { files: [file] } })
      
      // Fill metadata
      const nameInput = screen.getByLabelText(/evidence name/i)
      const descInput = screen.getByLabelText(/description/i)
      
      fireEvent.change(nameInput, { target: { value: 'Data Protection Policy' } })
      fireEvent.change(descInput, { target: { value: 'Company data protection policy v2.1' } })
      
      // Upload
      const uploadButton = screen.getByRole('button', { name: /upload/i })
      fireEvent.click(uploadButton)
      
      await waitFor(() => {
        expect(mockProps.onUpload).toHaveBeenCalledWith(
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

    it('should show upload progress', async () => {
      render(<EvidenceUpload {...mockProps} isUploading={true} uploadProgress={45} />)
      
      expect(screen.getByText('Uploading...')).toBeInTheDocument()
      expect(screen.getByText('45%')).toBeInTheDocument()
    })

    it('should handle multiple file uploads', async () => {
      render(<EvidenceUpload {...mockProps} allowMultiple={true} />)
      
      const fileInput = screen.getByTestId('file-input')
      const files = [
        new File(['content1'], 'file1.pdf', { type: 'application/pdf' }),
        new File(['content2'], 'file2.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }),
      ]
      
      fireEvent.change(fileInput, { target: { files } })
      
      await waitFor(() => {
        expect(screen.getByText('file1.pdf')).toBeInTheDocument()
        expect(screen.getByText('file2.docx')).toBeInTheDocument()
      })
    })
  })

  describe('EvidenceList', () => {
    const mockEvidence = [
      {
        id: 'ev-1',
        name: 'Data Protection Policy',
        filename: 'dp-policy.pdf',
        status: 'approved' as const,
        framework: 'GDPR',
        control_reference: 'A.1.1',
        uploaded_at: new Date('2025-01-01'),
        file_size: 2048000,
        file_type: 'application/pdf',
      },
      {
        id: 'ev-2',
        name: 'Security Training Records',
        filename: 'training.xlsx',
        status: 'pending' as const,
        framework: 'ISO 27001',
        control_reference: 'A.7.2.2',
        uploaded_at: new Date('2025-01-05'),
        file_size: 1024000,
        file_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      },
    ]

    it('should render evidence list', () => {
      render(<EvidenceList evidence={mockEvidence} />)
      
      expect(screen.getByText('Data Protection Policy')).toBeInTheDocument()
      expect(screen.getByText('Security Training Records')).toBeInTheDocument()
    })

    it('should show evidence status', () => {
      render(<EvidenceList evidence={mockEvidence} />)
      
      expect(screen.getByText('Approved')).toBeInTheDocument()
      expect(screen.getByText('Pending')).toBeInTheDocument()
    })

    it('should display file information', () => {
      render(<EvidenceList evidence={mockEvidence} />)
      
      expect(screen.getByText('dp-policy.pdf')).toBeInTheDocument()
      expect(screen.getByText('2.0 MB')).toBeInTheDocument()
    })

    it('should show framework and control reference', () => {
      render(<EvidenceList evidence={mockEvidence} />)
      
      expect(screen.getByText('GDPR')).toBeInTheDocument()
      expect(screen.getByText('A.1.1')).toBeInTheDocument()
      expect(screen.getByText('ISO 27001')).toBeInTheDocument()
      expect(screen.getByText('A.7.2.2')).toBeInTheDocument()
    })

    it('should handle evidence actions', () => {
      const onView = vi.fn()
      const onDownload = vi.fn()
      const onDelete = vi.fn()
      
      render(
        <EvidenceList 
          evidence={mockEvidence} 
          onView={onView}
          onDownload={onDownload}
          onDelete={onDelete}
        />
      )
      
      const viewButtons = screen.getAllByRole('button', { name: /view/i })
      fireEvent.click(viewButtons[0])
      expect(onView).toHaveBeenCalledWith('ev-1')
      
      const downloadButtons = screen.getAllByRole('button', { name: /download/i })
      fireEvent.click(downloadButtons[0])
      expect(onDownload).toHaveBeenCalledWith('ev-1')
    })

    it('should sort evidence by upload date', () => {
      render(<EvidenceList evidence={mockEvidence} sortBy="uploaded_at" sortOrder="desc" />)
      
      const evidenceItems = screen.getAllByRole('row')
      // First item should be the more recent one (ev-2)
      expect(evidenceItems[1]).toHaveTextContent('Security Training Records')
    })

    it('should handle empty evidence list', () => {
      render(<EvidenceList evidence={[]} />)
      
      expect(screen.getByText('No evidence found')).toBeInTheDocument()
      expect(screen.getByText(/upload.*first.*evidence/i)).toBeInTheDocument()
    })

    it('should show loading state', () => {
      render(<EvidenceList evidence={[]} isLoading={true} />)
      
      expect(screen.getByText(/loading/i)).toBeInTheDocument()
    })
  })

  describe('EvidenceViewer', () => {
    const mockEvidence = {
      id: 'ev-1',
      name: 'Data Protection Policy',
      filename: 'dp-policy.pdf',
      status: 'approved' as const,
      framework: 'GDPR',
      control_reference: 'A.1.1',
      uploaded_at: new Date('2025-01-01'),
      file_size: 2048000,
      file_type: 'application/pdf',
      download_url: 'https://example.com/files/dp-policy.pdf',
      description: 'Company data protection policy document',
      version: '2.1',
    }

    it('should render evidence details', () => {
      render(<EvidenceViewer evidence={mockEvidence} />)
      
      expect(screen.getByText('Data Protection Policy')).toBeInTheDocument()
      expect(screen.getByText('dp-policy.pdf')).toBeInTheDocument()
      expect(screen.getByText('Company data protection policy document')).toBeInTheDocument()
    })

    it('should show evidence metadata', () => {
      render(<EvidenceViewer evidence={mockEvidence} />)
      
      expect(screen.getByText('GDPR')).toBeInTheDocument()
      expect(screen.getByText('A.1.1')).toBeInTheDocument()
      expect(screen.getByText('v2.1')).toBeInTheDocument()
      expect(screen.getByText('Approved')).toBeInTheDocument()
    })

    it('should handle PDF preview', () => {
      render(<EvidenceViewer evidence={mockEvidence} showPreview={true} />)
      
      expect(screen.getByTestId('pdf-viewer')).toBeInTheDocument()
    })

    it('should handle download action', () => {
      const onDownload = vi.fn()
      render(<EvidenceViewer evidence={mockEvidence} onDownload={onDownload} />)
      
      const downloadButton = screen.getByRole('button', { name: /download/i })
      fireEvent.click(downloadButton)
      
      expect(onDownload).toHaveBeenCalledWith(mockEvidence.id)
    })

    it('should handle evidence approval workflow', () => {
      const onApprove = vi.fn()
      const onReject = vi.fn()
      const pendingEvidence = { ...mockEvidence, status: 'pending' as const }
      
      render(
        <EvidenceViewer 
          evidence={pendingEvidence} 
          onApprove={onApprove}
          onReject={onReject}
          canApprove={true}
        />
      )
      
      const approveButton = screen.getByRole('button', { name: /approve/i })
      const rejectButton = screen.getByRole('button', { name: /reject/i })
      
      fireEvent.click(approveButton)
      expect(onApprove).toHaveBeenCalledWith(pendingEvidence.id)
      
      fireEvent.click(rejectButton)
      expect(onReject).toHaveBeenCalledWith(pendingEvidence.id)
    })

    it('should show file type icon', () => {
      render(<EvidenceViewer evidence={mockEvidence} />)
      
      expect(screen.getByTestId('file-icon')).toBeInTheDocument()
    })
  })

  describe('EvidenceFilters', () => {
    const mockFilters = {
      status: '',
      framework: '',
      dateRange: { from: undefined, to: undefined },
      fileType: '',
    }

    const mockOnFiltersChange = vi.fn()

    it('should render filter controls', () => {
      render(<EvidenceFilters filters={mockFilters} onFiltersChange={mockOnFiltersChange} />)
      
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/framework/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/file type/i)).toBeInTheDocument()
    })

    it('should handle status filter change', () => {
      render(<EvidenceFilters filters={mockFilters} onFiltersChange={mockOnFiltersChange} />)
      
      const statusSelect = screen.getByLabelText(/status/i)
      fireEvent.change(statusSelect, { target: { value: 'approved' } })
      
      expect(mockOnFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'approved' })
      )
    })

    it('should handle framework filter change', () => {
      render(<EvidenceFilters filters={mockFilters} onFiltersChange={mockOnFiltersChange} />)
      
      const frameworkSelect = screen.getByLabelText(/framework/i)
      fireEvent.change(frameworkSelect, { target: { value: 'gdpr' } })
      
      expect(mockOnFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({ framework: 'gdpr' })
      )
    })

    it('should handle date range selection', () => {
      render(<EvidenceFilters filters={mockFilters} onFiltersChange={mockOnFiltersChange} />)
      
      const fromDate = screen.getByLabelText(/from date/i)
      fireEvent.change(fromDate, { target: { value: '2025-01-01' } })
      
      expect(mockOnFiltersChange).toHaveBeenCalledWith(
        expect.objectContaining({
          dateRange: expect.objectContaining({
            from: expect.any(Date)
          })
        })
      )
    })

    it('should clear all filters', () => {
      const activeFilters = {
        status: 'approved',
        framework: 'gdpr',
        dateRange: { from: new Date(), to: new Date() },
        fileType: 'pdf',
      }
      
      render(<EvidenceFilters filters={activeFilters} onFiltersChange={mockOnFiltersChange} />)
      
      const clearButton = screen.getByRole('button', { name: /clear.*filters/i })
      fireEvent.click(clearButton)
      
      expect(mockOnFiltersChange).toHaveBeenCalledWith({
        status: '',
        framework: '',
        dateRange: { from: undefined, to: undefined },
        fileType: '',
      })
    })

    it('should show active filter count', () => {
      const activeFilters = {
        status: 'approved',
        framework: 'gdpr',
        dateRange: { from: undefined, to: undefined },
        fileType: '',
      }
      
      render(<EvidenceFilters filters={activeFilters} onFiltersChange={mockOnFiltersChange} />)
      
      expect(screen.getByText('2 filters active')).toBeInTheDocument()
    })
  })

  describe('Evidence Management Accessibility', () => {
    it('should have proper ARIA labels for upload', () => {
      const mockProps = {
        onUpload: vi.fn(),
        frameworkId: 'gdpr',
        controlReference: 'A.1.1',
      }
      
      render(<EvidenceUpload {...mockProps} />)
      
      expect(screen.getByLabelText(/evidence name/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument()
    })

    it('should support keyboard navigation in evidence list', () => {
      const mockEvidence = [
        {
          id: 'ev-1',
          name: 'Test Evidence',
          filename: 'test.pdf',
          status: 'approved' as const,
          framework: 'GDPR',
          control_reference: 'A.1.1',
          uploaded_at: new Date(),
          file_size: 1024,
          file_type: 'application/pdf',
        },
      ]
      
      render(<EvidenceList evidence={mockEvidence} />)
      
      const actionButtons = screen.getAllByRole('button')
      actionButtons.forEach(button => {
        expect(button).toHaveAttribute('tabIndex')
      })
    })
  })
})