'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { FreemiumResults } from '../../../../components/freemium/freemium-results';
import { Card, CardContent } from '../../../../components/ui/card';
import { Button } from '../../../../components/ui/button';
import { useFreemiumStore, useFreemiumSession } from '../../../../lib/stores/freemium-store';
import { AlertTriangle, Loader2, ArrowLeft, Share2, Download, Shield, Mail, Rocket } from 'lucide-react';

function ResultsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { loadSession } = useFreemiumStore();
  const { hasSession, sessionData, canViewResults } = useFreemiumSession();
  const [hasSharedResults, setHasSharedResults] = useState(false);

  const tokenFromUrl = searchParams?.get('token');
  const errorFromUrl = searchParams?.get('error');

  // Load session from URL if provided and not already in store
  useEffect(() => {
    if (tokenFromUrl && tokenFromUrl !== sessionData.sessionToken) {
      loadSession(tokenFromUrl).catch(console.error);
    }
  }, [tokenFromUrl, sessionData.sessionToken, loadSession]);

  // Handle error states
  if (errorFromUrl === 'expired') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardContent className="space-y-4 py-8 text-center">
            <AlertTriangle className="mx-auto h-12 w-12 text-orange-500" />
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-gray-900">Results Expired</h2>
              <p className="text-gray-600">
                Your assessment results have expired. Please take the assessment again to get fresh
                results.
              </p>
            </div>
            <Button
              onClick={() => router.push('/freemium')}
              className="bg-purple-600 hover:bg-purple-700"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Take New Assessment
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Redirect to assessment if no session or assessment not complete
  if (!hasSession || !canViewResults) {
    if (tokenFromUrl) {
      // If token is provided but assessment not complete, redirect to assessment
      router.push(`/freemium/assessment?token=${tokenFromUrl}`);
    } else {
      // No token, redirect to landing page
      router.push('/freemium');
    }

    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="space-y-4 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600" />
          <p className="text-gray-600">Redirecting to assessment...</p>
        </div>
      </div>
    );
  }

  const currentToken = tokenFromUrl || sessionData.sessionToken;

  const handleShareResults = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'My Compliance Assessment Results - RuleIQ',
          text: 'I just completed a compliance assessment and discovered important gaps in my business. Check out RuleIQ for your free assessment!',
          url: `${window.location.origin}/freemium`,
        });
        setHasSharedResults(true);
      } catch (_error) {
        // User cancelled or share failed, fallback to copy
        await navigator.clipboard.writeText(`${window.location.origin}/freemium`);
        setHasSharedResults(true);
      }
    } else {
      // Fallback for browsers without Web Share API
      await navigator.clipboard.writeText(`${window.location.origin}/freemium`);
      setHasSharedResults(true);
    }
  };

  const handleDownloadResults = () => {
    // This would typically generate a PDF report
    // For now, we'll just track the event
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button
                onClick={() => router.push('/freemium')}
                variant="ghost"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Take Another Assessment
              </Button>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">
                  Your Compliance Assessment Results
                </h1>
                <p className="text-sm text-gray-600">
                  Personalized insights for {sessionData.email}
                </p>
              </div>
            </div>

            {/* Action buttons for desktop */}
            <div className="hidden items-center space-x-2 md:flex">
              <Button
                onClick={handleShareResults}
                variant="outline"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
              >
                <Share2 className="mr-2 h-4 w-4" />
                {hasSharedResults ? 'Shared!' : 'Share Results'}
              </Button>
              <Button
                onClick={handleDownloadResults}
                variant="outline"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
              >
                <Download className="mr-2 h-4 w-4" />
                Download Report
              </Button>
            </div>
          </div>

          {/* Action buttons for mobile */}
          <div className="mt-4 flex space-x-2 md:hidden">
            <Button
              onClick={handleShareResults}
              variant="outline"
              size="sm"
              className="flex-1 text-gray-600 hover:text-gray-900"
            >
              <Share2 className="mr-2 h-4 w-4" />
              {hasSharedResults ? 'Shared!' : 'Share'}
            </Button>
            <Button
              onClick={handleDownloadResults}
              variant="outline"
              size="sm"
              className="flex-1 text-gray-600 hover:text-gray-900"
            >
              <Download className="mr-2 h-4 w-4" />
              Download
            </Button>
          </div>
        </div>
      </div>

      {/* Results Content */}
      <div className="container mx-auto px-4 py-8">
        <FreemiumResults token={currentToken!} />
      </div>

      {/* Footer */}
      <div className="border-t border-gray-200 bg-white py-6">
        <div className="container mx-auto px-4">
          <div className="space-y-4 text-center">
            <div className="flex flex-col items-center justify-center space-y-2 text-sm text-gray-500 sm:flex-row sm:space-x-6 sm:space-y-0">
              <span><Shield className="inline h-4 w-4 mr-1" />Your data is secure and never shared</span>
              <span><Mail className="inline h-4 w-4 mr-1" />Results saved to {sessionData.email}</span>
              <span><Rocket className="inline h-4 w-4 mr-1" />Powered by RuleIQ AI</span>
            </div>

            {/* Call to action for additional assessments */}
            <div className="border-t border-gray-100 pt-4">
              <p className="mb-3 text-sm text-gray-600">
                Want to assess another business unit or framework?
              </p>
              <Button
                onClick={() => router.push('/freemium')}
                variant="outline"
                className="border-purple-200 text-purple-600 hover:bg-purple-50"
              >
                Start Another Assessment
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function FreemiumResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          <div className="space-y-4 text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-600" />
            <p className="text-gray-600">Loading your results...</p>
          </div>
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}
