'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { ArrowLeft, Brain, Clock, AlertCircle } from 'lucide-react';
import { AssessmentWizard } from '@/components/assessments/AssessmentWizard';
import { freemiumService } from '@/lib/api/freemium.service';
import { frameworkService } from '@/lib/api/frameworks.service';
import type { AssessmentFramework, AssessmentResult, AssessmentProgress } from '@/lib/assessment-engine/types';
import type { FreemiumAssessmentStartResponse } from '@/types/freemium';

export default function AssessmentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams?.get('token') ?? null;

  const [sessionData, setSessionData] = useState<FreemiumAssessmentStartResponse | null>(null);
  const [framework, setFramework] = useState<AssessmentFramework | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uiProgress, setUiProgress] = useState<{ answered: number; total: number; percentage: number } | null>(null);
  const [sessionExpiryMinutes, setSessionExpiryMinutes] = useState<number>(60);

  useEffect(() => {
    let mounted = true;

    if (!token) {
      router.push('/');
      return;
    }

    const loadData = async () => {
      if (!token || !mounted) return;

      try {
        setLoading(true);
        setError(null);

        // Load session data and framework in parallel
        const [session, defaultFramework] = await Promise.all([
          freemiumService.getSessionProgress(token),
          Promise.resolve(frameworkService.getDefaultFramework())
        ]);

        // Check if component is still mounted before updating state
        if (!mounted) return;

        setSessionData(session);
        setFramework(defaultFramework);

        // Initialize UI progress from session data
        if (session?.progress) {
          setUiProgress({
            answered: session.progress.current_question ?? 0,
            total: session.progress.total_questions_estimate ?? 0,
            percentage: session.progress.progress_percentage ?? 0
          });
        }

        // Calculate initial expiry
        if (session?.expires_at) {
          const expiryMs = new Date(session.expires_at).getTime() - Date.now();
          setSessionExpiryMinutes(Math.max(0, Math.ceil(expiryMs / (1000 * 60))));
        }
      } catch (err) {
        // Check if component is still mounted before updating error state
        if (!mounted) return;

        setError(err instanceof Error ? err.message : 'Failed to load assessment session');
        setLoading(false);
      } finally {
        // Check if component is still mounted before updating loading state
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [token, router]);

  // Update session expiry timer
  useEffect(() => {
    if (!sessionData?.expires_at) return;

    const updateExpiry = () => {
      const expiryMs = new Date(sessionData.expires_at).getTime() - Date.now();
      const minutes = Math.max(0, Math.ceil(expiryMs / (1000 * 60)));
      setSessionExpiryMinutes(minutes);

      // Redirect if expired
      if (minutes <= 0) {
        setError('Your session has expired. Please start a new assessment.');
        setTimeout(() => router.push('/'), 3000);
      }
    };

    // Update immediately
    updateExpiry();

    // Update every 60 seconds
    const interval = setInterval(updateExpiry, 60000);

    return () => clearInterval(interval);
  }, [sessionData?.expires_at, router]);

  const loadSessionAndFramework = async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);

      // Load session data and framework in parallel
      const [session, defaultFramework] = await Promise.all([
        freemiumService.getSessionProgress(token),
        Promise.resolve(frameworkService.getDefaultFramework())
      ]);

      setSessionData(session);
      setFramework(defaultFramework);

      // Initialize UI progress from session data
      if (session?.progress) {
        setUiProgress({
          answered: session.progress.current_question ?? 0,
          total: session.progress.total_questions_estimate ?? 0,
          percentage: session.progress.progress_percentage ?? 0
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load assessment session');
    } finally {
      setLoading(false);
    }
  };

  const handleAssessmentComplete = async (result: AssessmentResult) => {
    if (!token) return;

    try {
      // Persist the assessment results before redirecting
      await freemiumService.completeAssessment(token, result);

      // Also store in sessionStorage as backup
      sessionStorage.setItem(`assessment_result_${token}`, JSON.stringify(result));

      // Optionally refresh the cache if using assessment-results.service
      // await assessmentResultsService.refreshCache(token);

      router.push(`/assessment/results/${token}`);
    } catch (error) {
      console.error('Failed to save assessment results:', error);

      // Store in sessionStorage for fallback persistence
      sessionStorage.setItem(`assessment_result_${token}`, JSON.stringify(result));

      // Show error but still redirect - results will be available from sessionStorage
      setError('Failed to save results to server. Showing a local preview.');

      // Redirect after showing error message
      setTimeout(() => {
        router.push(`/assessment/results/${token}`);
      }, 2000);
    }
  };


  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-purple-50 via-white to-neutral-50">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <Brain className="mx-auto mb-4 h-12 w-12 animate-pulse text-purple-600" />
            <h2 className="mb-2 text-xl font-semibold">Loading Your Assessment</h2>
            <p className="text-muted-foreground">
              Preparing your personalized AI-driven assessment...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-purple-50 via-white to-neutral-50">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive" />
            <h2 className="mb-2 text-xl font-semibold">Assessment Unavailable</h2>
            <p className="mb-6 text-muted-foreground">{error}</p>
            <div className="flex justify-center gap-2">
              <Button variant="outline" onClick={() => router.push('/')}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Home
              </Button>
              <Button onClick={loadSessionAndFramework}>Try Again</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!sessionData || !framework) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-purple-50 via-white to-neutral-50">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-amber-500" />
            <h2 className="mb-2 text-xl font-semibold">
              {!sessionData ? 'Session Not Found' : 'Framework Not Available'}
            </h2>
            <p className="mb-6 text-muted-foreground">
              {!sessionData 
                ? 'The assessment session could not be found or has expired.'
                : 'The assessment framework could not be loaded. Please try again.'
              }
            </p>
            <Button onClick={() => router.push('/')}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Start New Assessment
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-neutral-50">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={() => router.push('/')}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-purple-700">ruleIQ</h1>
                <p className="text-sm text-muted-foreground">AI Compliance Assessment</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-sm text-muted-foreground">
                <Clock className="mr-1 inline h-4 w-4" />
                Session expires in {sessionExpiryMinutes} min
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Progress Bar - only show when total questions count is positive */}
      {((uiProgress?.total || 0) > 0 || (sessionData.progress?.total_questions_estimate || 0) > 0) && (
        <div className="border-b bg-white/80 backdrop-blur-sm">
          <div className="container mx-auto px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">Assessment Progress</span>
              <span className="text-sm text-muted-foreground">
                {uiProgress ? uiProgress.answered : (sessionData.progress?.current_question ?? 0)} of {uiProgress ? uiProgress.total : (sessionData.progress?.total_questions_estimate ?? 0)} questions
              </span>
            </div>
            <Progress value={uiProgress ? uiProgress.percentage : (sessionData.progress?.progress_percentage ?? 0)} className="h-2" />
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="mx-auto max-w-4xl">
          <AssessmentWizard
            framework={framework}
            assessmentId={token!}  // Pass the token as assessmentId for proper API calls - token is guaranteed to exist due to early return
            businessProfileId={sessionData.session_id}  // Note: freemium start response has no lead_id; trend linking uses lead_id at results time.
            enableIncrementalSubmissions={false}  // Disable for freemium unless mapping layer is provided
            onComplete={handleAssessmentComplete}
            onSave={(progress: AssessmentProgress) => {
              // Update UI progress
              setUiProgress({
                answered: progress.answeredQuestions,
                total: progress.totalQuestions,
                percentage: progress.percentComplete
              });
              // Optional: Save progress to freemium service
              console.log('Assessment progress:', progress);
            }}
            onExit={() => router.push('/')}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t bg-white/50">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4" />
              <span>Powered by ruleIQ AI</span>
            </div>
            <div className="flex gap-4">
              <a href="/privacy" className="transition-colors hover:text-foreground">
                Privacy Policy
              </a>
              <a href="/terms" className="transition-colors hover:text-foreground">
                Terms of Service
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
