'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Label } from '../ui/label';
import { Alert, AlertDescription } from '../ui/alert';
import { Loader2, Mail, Shield, Zap } from 'lucide-react';
import {
  useFreemiumEmailCapture,
  useFreemiumUtmCapture,
} from '../../lib/tanstack-query/hooks/use-freemium';
import { isValidEmail } from '../../lib/api/freemium.service';
import { useFreemiumStore } from '../../lib/stores/freemium-store';

interface FreemiumEmailCaptureProps {
  title?: string;
  description?: string;
  className?: string;
}

export function FreemiumEmailCapture({
  title = 'Get Your Free Compliance Assessment',
  description = 'Discover your compliance gaps in under 5 minutes with our AI-powered assessment tool.',
  className = '',
}: FreemiumEmailCaptureProps) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [consentMarketing, setConsentMarketing] = useState(false);
  const [consentTerms, setConsentTerms] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [termsError, setTermsError] = useState('');

  const emailCaptureMutation = useFreemiumEmailCapture();
  const { captureUtmParams } = useFreemiumUtmCapture();
  const { setEmail: setStoreEmail, setToken, setConsent } = useFreemiumStore();

  // Capture UTM parameters on component mount
  useEffect(() => {
    captureUtmParams();
  }, [captureUtmParams]);

  const handleEmailChange = (value: string) => {
    setEmail(value);
    setStoreEmail(value); // Update store
    // Clear error when user starts typing
    if (emailError) {
      setEmailError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Clear previous errors
    setEmailError('');
    setTermsError('');

    // Validate email
    if (!email.trim()) {
      setEmailError('Email address is required');
      return;
    }

    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    // Validate terms consent
    if (!consentTerms) {
      setTermsError('You must agree to the Terms of Service');
      return;
    }

    // Extract UTM parameters from current URL
    const urlParams = new URLSearchParams(window.location.search);
    const utm_source = urlParams.get('utm_source') || undefined;
    const utm_campaign = urlParams.get('utm_campaign') || undefined;

    try {
      const payload: any = {
        email: email.trim(),
        marketing_consent: consentMarketing,
      };
      
      // Only include UTM parameters if they exist
      if (utm_source) payload.utm_source = utm_source;
      if (utm_campaign) payload.utm_campaign = utm_campaign;
      
      const response = await emailCaptureMutation.mutateAsync(payload);
      // Update store with token if returned
      if (response?.token) {
        setToken(response.token);
      }
      // Navigate to assessment on success
      router.push('/freemium/assessment');
    } catch (error: unknown) {
      setEmailError(error instanceof Error ? error.message : 'Failed to start assessment. Please try again.');
    }
  };

  return (
    <Card className={`mx-auto w-full max-w-lg ${className}`}>
      <CardHeader className="space-y-2 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
          <Shield className="h-6 w-6 text-purple-600" />
        </div>
        <CardTitle className="text-2xl font-bold text-gray-900">{title}</CardTitle>
        <CardDescription className="text-base text-gray-600">{description}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Benefits List */}
        <div className="space-y-3">
          <div className="flex items-center space-x-3 text-sm text-gray-600">
            <Zap className="h-4 w-4 flex-shrink-0 text-purple-500" />
            <span>AI-powered assessment tailored to your business</span>
          </div>
          <div className="flex items-center space-x-3 text-sm text-gray-600">
            <Shield className="h-4 w-4 flex-shrink-0 text-purple-500" />
            <span>Identify critical compliance gaps instantly</span>
          </div>
          <div className="flex items-center space-x-3 text-sm text-gray-600">
            <Mail className="h-4 w-4 flex-shrink-0 text-purple-500" />
            <span>Get personalized recommendations via email</span>
          </div>
        </div>

        {/* Email Form */}
        <form onSubmit={handleSubmit} className="space-y-4" role="form">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm font-medium text-gray-700">
              Email Address
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="Enter your email address"
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              className={`w-full ${emailError ? 'border-red-300 focus:border-red-500' : ''}`}
              disabled={emailCaptureMutation.isPending}
              autoComplete="email"
              data-testid="email-input"
              required
              aria-invalid={!!emailError}
            />
            {emailError && (
              <p className="text-sm text-red-600" role="alert">
                {emailError}
              </p>
            )}
          </div>

          {/* Terms Consent */}
          <div className="flex items-start space-x-3">
            <Checkbox
              id="terms-consent"
              checked={consentTerms}
              onCheckedChange={(checked) => {
                setConsentTerms(!!checked);
                setConsent('terms', !!checked);
                if (checked && termsError) setTermsError('');
              }}
              className="mt-0.5"
              disabled={emailCaptureMutation.isPending}
              data-testid="terms-consent"
            />
            <Label
              htmlFor="terms-consent"
              className="cursor-pointer text-sm leading-5 text-gray-600"
            >
              I agree to the Terms of Service
            </Label>
          </div>
          {termsError && (
            <p className="text-sm text-red-600" role="alert">
              {termsError}
            </p>
          )}

          {/* Marketing Consent */}
          <div className="flex items-start space-x-3">
            <Checkbox
              id="marketing-consent"
              checked={consentMarketing}
              onCheckedChange={(checked) => {
                setConsentMarketing(!!checked);
                setConsent('marketing', !!checked);
              }}
              className="mt-0.5"
              disabled={emailCaptureMutation.isPending}
              data-testid="marketing-consent"
            />
            <Label
              htmlFor="marketing-consent"
              className="cursor-pointer text-sm leading-5 text-gray-600"
            >
              I agree to receive marketing emails about compliance best practices and RuleIQ product
              news. You can unsubscribe at any time.
            </Label>
          </div>

          {/* Error Display */}
          {emailCaptureMutation.isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {emailCaptureMutation.error?.message ||
                  'Failed to start assessment. Please try again.'}
              </AlertDescription>
            </Alert>
          )}

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full bg-purple-600 py-3 font-medium text-white hover:bg-purple-700"
            disabled={emailCaptureMutation.isPending || !email.trim()}
            data-testid="start-assessment-button"
          >
            {emailCaptureMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting your assessment...
              </>
            ) : (
              'Start Free Assessment'
            )}
          </Button>
        </form>

        {/* Trust Indicators */}
        <div className="border-t border-gray-100 pt-4">
          <div className="flex items-center justify-center space-x-4 text-xs text-gray-500">
            <div className="flex items-center space-x-1">
              <Shield className="h-3 w-3" />
              <span>Secure & Private</span>
            </div>
            <div className="h-1 w-1 rounded-full bg-gray-300"></div>
            <div className="flex items-center space-x-1">
              <Zap className="h-3 w-3" />
              <span>5 Min Assessment</span>
            </div>
            <div className="h-1 w-1 rounded-full bg-gray-300"></div>
            <div className="flex items-center space-x-1">
              <Mail className="h-3 w-3" />
              <span>No Spam</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Lightweight version for embedding in other components
export function FreemiumEmailCaptureInline({ className = '' }: { className?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [consentMarketing, setConsentMarketing] = useState(false);
  const [emailError, setEmailError] = useState('');

  const emailCaptureMutation = useFreemiumEmailCapture();
  const { captureUtmParams } = useFreemiumUtmCapture();
  const { setEmail: _setStoreEmail, setToken, setConsent: _setConsent } = useFreemiumStore();

  useEffect(() => {
    captureUtmParams();
  }, [captureUtmParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      setEmailError('Email is required');
      return;
    }

    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const utm_source = urlParams.get('utm_source') || undefined;
    const utm_campaign = urlParams.get('utm_campaign') || undefined;

    try {
      const response = await emailCaptureMutation.mutateAsync({
        email: email.trim(),
        ...(utm_source && { utm_source }),
        ...(utm_campaign && { utm_campaign }),
        marketing_consent: consentMarketing,
      });
      // Update store with token if returned
      if (response?.token) {
        setToken(response.token);
      }
      // Navigate on success
      router.push('/freemium/assessment');
    } catch (error: unknown) {
      setEmailError(error instanceof Error ? error.message : 'Failed to start assessment');
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex space-x-2">
          <Input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={`flex-1 ${emailError ? 'border-red-300' : ''}`}
            disabled={emailCaptureMutation.isPending}
          />
          <Button
            type="submit"
            className="bg-purple-600 px-6 text-white hover:bg-purple-700"
            disabled={emailCaptureMutation.isPending || !email.trim()}
          >
            {emailCaptureMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              'Start Assessment'
            )}
          </Button>
        </div>

        <div className="flex items-start space-x-2">
          <Checkbox
            id="inline-consent"
            checked={consentMarketing}
            onCheckedChange={(checked) => setConsentMarketing(!!checked)}
            className="mt-0.5"
            disabled={emailCaptureMutation.isPending}
          />
          <Label htmlFor="inline-consent" className="text-xs leading-4 text-gray-600">
            I agree to receive email updates. Unsubscribe anytime.
          </Label>
        </div>

        {emailError && (
          <p className="text-sm text-red-600" role="alert">
            {emailError}
          </p>
        )}
      </form>
    </div>
  );
}
