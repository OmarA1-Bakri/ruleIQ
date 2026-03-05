'use client';

import { Loader2 } from 'lucide-react';
import { useRouter, useParams } from 'next/navigation';
import React, { useState, useEffect, useCallback } from 'react';

import { AssessmentWizard } from '@/components/assessments/AssessmentWizard';
import { assessmentService } from '@/lib/api/assessments.service';
import {
  type AssessmentFramework,
  type AssessmentResult,
  type AssessmentProgress,
} from '@/lib/assessment-engine';
import { useAppStore } from '@/lib/stores/app.store';
import { useAuthStore } from '@/lib/stores/auth.store';

// Mock framework data - in production this would come from API based on assessment
const mockFramework: AssessmentFramework = {
  id: 'gdpr',
  name: 'GDPR Compliance Assessment',
  description: 'Comprehensive assessment for EU General Data Protection Regulation compliance',
  version: '2.0',
  scoringMethod: 'percentage',
  passingScore: 70,
  estimatedDuration: 45,
  tags: ['Privacy', 'EU', 'Data Rights'],
  sections: [
    {
      id: 'data-processing',
      title: 'Data Processing Activities',
      description: "Assess your organization's data processing practices",
      order: 1,
      questions: [
        {
          id: 'q1',
          type: 'radio',
          text: 'Do you maintain a record of processing activities (ROPA) as required by Article 30 of GDPR?',
          description:
            'This record should detail the purposes of processing, categories of data subjects, and data transfers.',
          options: [
            { value: 'yes', label: 'Yes, fully documented and regularly updated' },
            { value: 'partial', label: 'Partially documented' },
            { value: 'no', label: 'No' },
          ],
          validation: { required: true },
          weight: 3,
        },
        {
          id: 'q2',
          type: 'checkbox',
          text: 'Which lawful bases do you rely on for processing personal data?',
          description: 'Select all that apply to your organization',
          options: [
            { value: 'consent', label: 'Consent' },
            { value: 'contract', label: 'Contract' },
            { value: 'legal_obligation', label: 'Legal Obligation' },
            { value: 'vital_interests', label: 'Vital Interests' },
            { value: 'public_task', label: 'Public Task' },
            { value: 'legitimate_interests', label: 'Legitimate Interests' },
          ],
          validation: { required: true, min: 1 },
          weight: 2,
        },
        {
          id: 'q3',
          type: 'textarea',
          text: 'Describe your data retention policies and how you ensure data is not kept longer than necessary.',
          validation: { required: true, minLength: 50 },
          weight: 2,
        },
      ],
    },
    {
      id: 'data-subject-rights',
      title: 'Data Subject Rights',
      description: 'Evaluate how you handle data subject requests',
      order: 2,
      questions: [
        {
          id: 'q4',
          type: 'radio',
          text: 'Do you have a documented process for handling Data Subject Access Requests (DSARs)?',
          options: [
            { value: 'yes', label: 'Yes, with defined timelines and procedures' },
            { value: 'partial', label: 'Informal process exists' },
            { value: 'no', label: 'No documented process' },
          ],
          validation: { required: true },
          weight: 3,
        },
        {
          id: 'q5',
          type: 'scale',
          text: 'How confident are you in your ability to respond to DSARs within the 30-day deadline?',
          scaleMin: 1,
          scaleMax: 5,
          scaleLabels: { min: 'Not confident', max: 'Very confident' },
          validation: { required: true },
          weight: 2,
        },
      ],
    },
    {
      id: 'security-measures',
      title: 'Security Measures',
      description: 'Review your technical and organizational security measures',
      order: 3,
      questions: [
        {
          id: 'q6',
          type: 'matrix',
          text: 'Rate your implementation of the following security measures:',
          rows: [
            { id: 'encryption', label: 'Data Encryption' },
            { id: 'access_control', label: 'Access Control' },
            { id: 'monitoring', label: 'Security Monitoring' },
            { id: 'incident_response', label: 'Incident Response' },
          ],
          columns: [
            { id: 'not_implemented', label: 'Not Implemented' },
            { id: 'planned', label: 'Planned' },
            { id: 'partial', label: 'Partially Implemented' },
            { id: 'full', label: 'Fully Implemented' },
          ],
          validation: { required: true },
          weight: 4,
        },
      ],
    },
  ],
};

export default function AssessmentPage() {
  const router = useRouter();
  const params = useParams();
  const { addNotification } = useAppStore();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [framework, setFramework] = useState<AssessmentFramework | null>(null);

  const assessmentId = params?.['id'] as string;

  const loadAssessment = useCallback(async () => {
    try {
      // Load assessment details
      await assessmentService.getAssessment(assessmentId);

      // Load framework questions - in production this would be from API
      // For now, use mock data
      setFramework(mockFramework);
      setLoading(false);
    } catch (_error) {
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to load assessment. Please try again.',
        duration: 5000,
      });
      router.push('/assessments');
    }
  }, [assessmentId, addNotification, router]);

  useEffect(() => {
    loadAssessment();
  }, [loadAssessment]);

  const handleComplete = async (result: AssessmentResult) => {
    try {
      // Complete assessment
      await assessmentService.completeAssessment(assessmentId);

      addNotification({
        type: 'success',
        title: 'Assessment Complete!',
        message: `You scored ${result.overallScore}%. View your detailed results and recommendations.`,
        duration: 5000,
      });

      // Navigate to results page
      router.push(`/assessments/${assessmentId}/results`);
    } catch (_error) {
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to submit assessment. Your progress has been saved.',
        duration: 5000,
      });
    }
  };

  const handleSaveProgress = async (_progress: AssessmentProgress) => {
    try {
      // Save progress to backend
      await assessmentService.updateAssessment(assessmentId, {
        status: 'in_progress',
        // Note: AssessmentProgress from assessment-engine doesn't have responses
        // In a real implementation, you'd track responses separately
      });
    } catch (_error) {
      // Log error for debugging - consider using a proper logger in production
    }
  };

  const handleExit = () => {
    router.push('/assessments');
  };

  if (loading || !framework) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading assessment...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-5xl p-6">
      <AssessmentWizard
        framework={framework}
        assessmentId={assessmentId}
        businessProfileId={user?.companyId || 'default'}
        onComplete={handleComplete}
        onSave={handleSaveProgress}
        onExit={handleExit}
      />
    </div>
  );
}
