'use client';

import { ArrowLeft, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';

import { FrameworkSelector, type Framework } from '@/components/assessments/FrameworkSelector';
import { Button } from '@/components/ui/button';
import { assessmentService } from '@/lib/api/assessments.service';
import { useAppStore } from '@/lib/stores/app.store';
import { useAuthStore } from '@/lib/stores/auth.store';

// Mock frameworks data - in production this would come from API
const mockFrameworks: Framework[] = [
  {
    id: 'gdpr',
    name: 'GDPR Compliance',
    description: 'Comprehensive assessment for EU General Data Protection Regulation compliance',
    category: 'data-protection',
    tags: ['Privacy', 'EU', 'Data Rights'],
    estimatedDuration: 45,
    questionCount: 120,
    coverageAreas: [
      'Data Processing',
      'Subject Rights',
      'Security Measures',
      'Data Breaches',
      'Third-Party Risk',
    ],
    difficulty: 'intermediate',
    popularity: 95,
    lastUpdated: '2024-01-15',
  },
  {
    id: 'iso27001',
    name: 'ISO 27001',
    description: 'Information Security Management System (ISMS) assessment based on ISO 27001:2022',
    category: 'security',
    tags: ['Security', 'International', 'ISMS'],
    estimatedDuration: 60,
    questionCount: 150,
    coverageAreas: [
      'Risk Management',
      'Access Control',
      'Incident Management',
      'Business Continuity',
      'Compliance',
    ],
    difficulty: 'advanced',
    popularity: 88,
    lastUpdated: '2024-01-10',
  },
  {
    id: 'cyber-essentials',
    name: 'Cyber Essentials',
    description: 'UK government-backed scheme for basic cyber security',
    category: 'security',
    tags: ['UK', 'Cybersecurity', 'Government'],
    estimatedDuration: 30,
    questionCount: 80,
    coverageAreas: [
      'Firewalls',
      'Secure Configuration',
      'User Access',
      'Malware Protection',
      'Patch Management',
    ],
    difficulty: 'beginner',
    popularity: 92,
    lastUpdated: '2024-01-20',
  },
  {
    id: 'pci-dss',
    name: 'PCI DSS v4.0',
    description:
      'Payment Card Industry Data Security Standard for organizations handling card payments',
    category: 'financial',
    tags: ['Payments', 'Financial', 'Cards'],
    estimatedDuration: 50,
    questionCount: 130,
    coverageAreas: [
      'Network Security',
      'Data Protection',
      'Access Management',
      'Monitoring',
      'Security Testing',
    ],
    difficulty: 'advanced',
    popularity: 78,
    lastUpdated: '2024-01-05',
  },
  {
    id: 'soc2',
    name: 'SOC 2 Type II',
    description: 'Service Organization Control 2 assessment for service providers',
    category: 'security',
    tags: ['Trust', 'Service Providers', 'Controls'],
    estimatedDuration: 55,
    questionCount: 140,
    coverageAreas: [
      'Security',
      'Availability',
      'Processing Integrity',
      'Confidentiality',
      'Privacy',
    ],
    difficulty: 'intermediate',
    popularity: 85,
    lastUpdated: '2024-01-12',
  },
  {
    id: 'uk-gdpr',
    name: 'UK GDPR',
    description: 'UK-specific GDPR requirements post-Brexit',
    category: 'data-protection',
    tags: ['Privacy', 'UK', 'Post-Brexit'],
    estimatedDuration: 40,
    questionCount: 110,
    coverageAreas: [
      'UK-specific Requirements',
      'ICO Guidance',
      'Data Transfers',
      'Brexit Changes',
      'Accountability',
    ],
    difficulty: 'intermediate',
    popularity: 90,
    lastUpdated: '2024-01-18',
  },
];

export default function NewAssessmentPage() {
  const router = useRouter();
  const { addNotification } = useAppStore();
  const { user } = useAuthStore();
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    // Simulate loading frameworks from API
    setTimeout(() => {
      setFrameworks(mockFrameworks);
      setLoading(false);
    }, 1000);
  }, []);

  const handleFrameworkSelect = async (frameworkId: string, mode: 'quick' | 'comprehensive') => {
    setCreating(true);

    try {
      // Create assessment via API
      const assessment = await assessmentService.createAssessment({
        business_profile_id: user?.companyId || 'default', // Get from user's business profile
        framework_id: frameworkId,
        assessment_type: mode,
      });

      addNotification({
        type: 'success',
        title: 'Assessment Created',
        message: "Your assessment has been created. Let's get started!",
        duration: 3000,
      });

      // Navigate to assessment wizard
      router.push(`/assessments/${assessment.id}`);
    } catch (_error) {
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to create assessment. Please try again.',
        duration: 5000,
      });
      setCreating(false);
    }
  };

  const handleCancel = () => {
    router.push('/assessments');
  };

  if (loading) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading compliance frameworks...</p>
        </div>
      </div>
    );
  }

  if (creating) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
          <p className="text-muted-foreground">Creating your assessment...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl p-6">
      {/* Back Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push('/assessments')}
        className="mb-6"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Assessments
      </Button>

      <FrameworkSelector
        frameworks={frameworks}
        onSelect={handleFrameworkSelect}
        onCancel={handleCancel}
      />
    </div>
  );
}
