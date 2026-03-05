'use client';

import { useState } from 'react';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';
import {
  ExternalLink,
  AlertTriangle,
  CheckCircle,
  Shield,
  Loader2,
  RefreshCw,
  TrendingUp,
  Clock,
  Users,
  ArrowRight,
} from 'lucide-react';
import { useFreemiumStore } from '../../lib/stores/freemium-store';
import {
  getSeverityColor,
  getRiskScoreColor,
  formatRiskScore,
} from '../../lib/api/freemium.service';
import type { ComplianceGap } from '../../types/freemium';

interface FreemiumResultsProps {
  token: string;
  className?: string;
}

export function FreemiumResults({ token: _token, className = '' }: FreemiumResultsProps) {
  const { results, isLoading, error, generateResults, trackEvent } = useFreemiumStore();
  const [hasTrackedView, setHasTrackedView] = useState(false);

  // Track results page view (once)
  if (results && !hasTrackedView) {
    trackEvent('page_view', {
      timestamp: new Date().toISOString(),
      page_url: window.location.href,
      custom_properties: { page: 'results' }
    });
    setHasTrackedView(true);
  }

  const handleConversionClick = (conversionCta: any) => {
    if (!conversionCta) return;

    // Track conversion click
    trackEvent('cta_click', {
      timestamp: new Date().toISOString(),
      page_url: window.location.href,
      custom_properties: {
        cta_text: conversionCta.cta_button_text,
      },
    });

    // For now, redirect to main signup/contact page since we don't have payment_link
    window.open('/signup', '_blank');
  };

  const handleEmailShare = () => {
    if (!results) return;

    const subject = 'My Compliance Assessment Results';
    const body = `I just completed a compliance assessment and found ${results.compliance_gaps.length} gaps with a risk score of ${formatRiskScore(results.risk_score)}.\n\nKey recommendations:\n${results.recommendations
      .slice(0, 3)
      .map((r) => `• ${r.title}`)
      .join('\n')}\n\nGet your free assessment: ${window.location.origin}/freemium`;

    const mailtoLink = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = mailtoLink;

    // Track email share
    trackEvent('email_shared', {
      timestamp: new Date().toISOString(),
      page_url: window.location.href,
      custom_properties: { method: 'mailto' },
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <Card className={`mx-auto w-full max-w-4xl ${className}`}>
        <CardContent className="flex flex-col items-center justify-center space-y-4 py-12">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
            <Shield className="h-6 w-6 animate-pulse text-purple-600" />
          </div>
          <div className="space-y-2 text-center">
            <h3 className="text-lg font-semibold text-gray-900">Analyzing Your Results</h3>
            <p className="text-gray-600">
              AI is processing your responses and generating compliance insights...
            </p>
          </div>
          <Loader2 className="h-6 w-6 animate-spin text-purple-600" />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className={`mx-auto w-full max-w-4xl ${className}`}>
        <CardContent className="space-y-4 py-8">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-base">
              {typeof error === 'string' ? error : 'Unable to load your assessment results.'}
            </AlertDescription>
          </Alert>
          <div className="text-center">
            <Button onClick={() => generateResults()} variant="outline" className="mr-4">
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
            <Button
              onClick={() => (window.location.href = '/freemium')}
              className="bg-purple-600 hover:bg-purple-700"
            >
              Start New Assessment
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!results) {
    return null;
  }

  return (
    <div className={`mx-auto w-full max-w-4xl space-y-6 ${className}`}>
      {/* Results Header */}
      <Card>
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-purple-100">
            <Shield className="h-8 w-8 text-purple-600" />
          </div>
          <div>
            <CardTitle className="text-2xl font-bold text-gray-900">
              Your Compliance Assessment Results
            </CardTitle>
            <p className="mt-2 text-gray-600">AI-powered analysis of your compliance posture</p>
          </div>
        </CardHeader>
      </Card>

      {/* Risk Score Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-purple-600" />
            <span>Overall Risk Score</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`text-4xl font-bold ${getRiskScoreColor(results.risk_score)}`}>
                {formatRiskScore(results.risk_score)}
              </div>
              <div className="space-y-1">
                <p className="font-medium text-gray-900">Risk Level</p>
                <Badge
                  variant={
                    results.risk_score >= 7
                      ? 'destructive'
                      : results.risk_score >= 5
                        ? 'secondary'
                        : 'default'
                  }
                  className="text-xs"
                >
                  {results.risk_score >= 7
                    ? 'High Risk'
                    : results.risk_score >= 5
                      ? 'Medium Risk'
                      : 'Low Risk'}
                </Badge>
              </div>
            </div>
            <div className="space-y-1 text-right">
              <p className="text-sm text-gray-600">Compliance Gaps Found</p>
              <p className="text-2xl font-bold text-gray-900">{results.compliance_gaps.length}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Compliance Gaps */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <AlertTriangle className="h-5 w-5 text-orange-500" />
            <span>Critical Compliance Gaps</span>
          </CardTitle>
          <p className="text-sm text-gray-600">Priority areas that need immediate attention</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {results.compliance_gaps.slice(0, 3).map((gap, index) => (
            <ComplianceGapCard key={index} gap={gap} />
          ))}

          {results.compliance_gaps.length > 3 && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>{results.compliance_gaps.length - 3} additional gaps</strong> identified.
                Get the full analysis with detailed remediation steps.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Key Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <CheckCircle className="h-5 w-5 text-green-500" />
            <span>Priority Recommendations</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {results.recommendations.slice(0, 4).map((recommendation, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-purple-100">
                  <span className="text-xs font-semibold text-purple-600">{index + 1}</span>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-900">{recommendation.title}</p>
                  <p className="text-sm leading-5 text-gray-700">{recommendation.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Conversion CTA */}
      {results.conversion_cta && (
        <ConversionCTA
          conversionCta={results.conversion_cta}
          onCtaClick={() => handleConversionClick(results.conversion_cta)}
          onEmailShare={handleEmailShare}
          gapsCount={results.compliance_gaps.length}
          riskScore={results.risk_score}
        />
      )}
    </div>
  );
}

// Individual compliance gap component
function ComplianceGapCard({ gap }: { gap: ComplianceGap }) {
  const severityClasses = getSeverityColor(gap.severity);

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Badge className={`text-xs ${severityClasses}`}>{gap.severity.toUpperCase()}</Badge>
            <span className="font-medium text-gray-900">{gap.category}</span>
          </div>
          <p className="text-sm leading-5 text-gray-700">{gap.description}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">Effort</p>
          <p className="text-sm font-medium text-gray-900">{gap.estimated_effort}</p>
        </div>
      </div>
    </div>
  );
}

// Conversion CTA component
interface ConversionCTAProps {
  conversionCta: {
    primary_message: string;
    secondary_message: string;
    cta_button_text: string;
    urgency_indicator?: string;
  };
  onCtaClick: () => void;
  onEmailShare: () => void;
  gapsCount: number;
  riskScore: number;
}

function ConversionCTA({
  conversionCta,
  onCtaClick,
  onEmailShare,
  gapsCount: _gapsCount,
  riskScore: _riskScore,
}: ConversionCTAProps) {
  return (
    <Card className="border-purple-200 bg-gradient-to-r from-purple-50 to-purple-100">
      <CardContent className="py-8">
        <div className="space-y-6 text-center">
          <div className="space-y-2">
            <h3 className="text-xl font-bold text-gray-900">{conversionCta.primary_message}</h3>
            <p className="mx-auto max-w-2xl text-gray-600">{conversionCta.secondary_message}</p>
          </div>

          {/* Features Preview */}
          <div className="mx-auto grid max-w-2xl grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2 text-center">
              <Shield className="mx-auto h-8 w-8 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-gray-900">Complete Analysis</p>
                <p className="text-xs text-gray-600">Full gap analysis & remediation</p>
              </div>
            </div>
            <div className="space-y-2 text-center">
              <Clock className="mx-auto h-8 w-8 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-gray-900">Live Monitoring</p>
                <p className="text-xs text-gray-600">Real-time compliance tracking</p>
              </div>
            </div>
            <div className="space-y-2 text-center">
              <Users className="mx-auto h-8 w-8 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-gray-900">Expert Support</p>
                <p className="text-xs text-gray-600">Compliance experts on-demand</p>
              </div>
            </div>
          </div>

          {/* Call to Action */}
          <div className="mx-auto max-w-lg space-y-4 rounded-lg border border-purple-200 bg-white p-6">
            <div className="space-y-2 text-center">
              {conversionCta.urgency_indicator && (
                <Badge className="bg-purple-600 px-3 py-1 text-sm text-white">
                  {conversionCta.urgency_indicator}
                </Badge>
              )}
            </div>

            <Button
              onClick={onCtaClick}
              className="w-full bg-purple-600 py-3 text-base font-semibold text-white hover:bg-purple-700"
              size="lg"
            >
              {conversionCta.cta_button_text}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>

            <p className="text-center text-xs text-gray-500">
              No commitment • Cancel anytime • Secure payment
            </p>
          </div>

          {/* Secondary Actions */}
          <div className="flex flex-col items-center justify-center space-y-2 sm:flex-row sm:space-x-4 sm:space-y-0">
            <Button onClick={onEmailShare} variant="outline" className="text-sm">
              <ExternalLink className="mr-2 h-4 w-4" />
              Email Results to Team
            </Button>
            <Button
              onClick={() => (window.location.href = '/freemium')}
              variant="ghost"
              className="text-sm text-gray-600"
            >
              Take Assessment Again
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
