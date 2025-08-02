'use client';

import * as React from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { FormField } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

export function FormShowcase() {
  const [formData, setFormData] = React.useState({
    email: '',
    password: '',
    confirmPassword: '',
    companyName: '',
    industry: '',
    description: '',
    terms: false,
    newsletter: false,
  });

  const [validationState, setValidationState] = React.useState<{
    [key: string]: { error?: string; success?: string };
  }>({});

  const validateField = (name: string, value: string | boolean) => {
    let error = '';
    let success = '';

    switch (name) {
      case 'email':
        if (!value) {
          error = 'Email is required';
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value as string)) {
          error = 'Please enter a valid email address';
        } else {
          success = 'Valid email address';
        }
        break;
      case 'password':
        if (!value) {
          error = 'Password is required';
        } else if ((value as string).length < 8) {
          error = 'Password must be at least 8 characters';
        } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(value as string)) {
          error = 'Password must contain uppercase, lowercase, and number';
        } else {
          success = 'Strong password';
        }
        break;
      case 'confirmPassword':
        if (!value) {
          error = 'Please confirm your password';
        } else if (value !== formData.password) {
          error = 'Passwords do not match';
        } else {
          success = 'Passwords match';
        }
        break;
      case 'companyName':
        if (!value) {
          error = 'Company name is required';
        } else if ((value as string).length < 2) {
          error = 'Company name must be at least 2 characters';
        } else {
          success = 'Valid company name';
        }
        break;
      case 'industry':
        if (!value) {
          error = 'Please select an industry';
        } else {
          success = 'Industry selected';
        }
        break;
    }

    setValidationState((prev) => ({
      ...prev,
      [name]: { error, success },
    }));
  };

  const handleInputChange = (name: string, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    validateField(name, value);
  };

  return (
    <div className="space-y-8">
      {/* Basic Form Components */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Basic Form Components</CardTitle>
          <CardDescription className="text-neutral-600">
            Individual form components with different states
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Input Fields */}
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="Default Input" description="Standard input field">
              <Input placeholder="Enter text..." />
            </FormField>
            <FormField label="Focused Input" description="Click to see focus state">
              <Input placeholder="Click to focus..." />
            </FormField>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="Error State" error="This field is required">
              <Input placeholder="Error state..." error />
            </FormField>
            <FormField label="Success State" success="Input is valid">
              <Input placeholder="Success state..." success />
            </FormField>
          </div>

          {/* Select Dropdown */}
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="Select Dropdown" description="Choose an option">
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Select an option..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="option1">Option 1</SelectItem>
                  <SelectItem value="option2">Option 2</SelectItem>
                  <SelectItem value="option3">Option 3</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Select with Error" error="Please select an option">
              <Select>
                <SelectTrigger error>
                  <SelectValue placeholder="Select with error..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="option1">Option 1</SelectItem>
                  <SelectItem value="option2">Option 2</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
          </div>

          {/* Textarea */}
          <FormField label="Textarea" description="Multi-line text input">
            <Textarea placeholder="Enter your message..." rows={4} />
          </FormField>

          {/* Checkboxes */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox id="default-checkbox" />
              <Label htmlFor="default-checkbox">Default checkbox</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="error-checkbox" error />
              <Label htmlFor="error-checkbox" variant="error">
                Checkbox with error state
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="success-checkbox" success defaultChecked />
              <Label htmlFor="success-checkbox" variant="success">
                Checkbox with success state
              </Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Complete Form Example */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle style={{ color: '#F0EAD6' }}>Complete Form Example</CardTitle>
          <CardDescription style={{ color: '#6C757D' }}>
            A comprehensive form with validation states and real-time feedback
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-6">
            {/* Personal Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold" style={{ color: '#F0EAD6' }}>
                Account Information
              </h3>

              <FormField
                label="Email Address"
                required
                {...(validationState['email']?.error && { error: validationState['email'].error })}
                {...(validationState['email']?.success && {
                  success: validationState['email'].success,
                })}
                description="We'll use this for your account login"
              >
                <Input
                  type="email"
                  placeholder="john.doe@company.com"
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                />
              </FormField>

              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  label="Password"
                  required
                  {...(validationState['password']?.error && {
                    error: validationState['password'].error,
                  })}
                  {...(validationState['password']?.success && {
                    success: validationState['password'].success,
                  })}
                >
                  <Input
                    type="password"
                    placeholder="Enter password..."
                    value={formData.password}
                    onChange={(e) => handleInputChange('password', e.target.value)}
                  />
                </FormField>

                <FormField
                  label="Confirm Password"
                  required
                  {...(validationState['confirmPassword']?.error && {
                    error: validationState['confirmPassword'].error,
                  })}
                  {...(validationState['confirmPassword']?.success && {
                    success: validationState['confirmPassword'].success,
                  })}
                >
                  <Input
                    type="password"
                    placeholder="Confirm password..."
                    value={formData.confirmPassword}
                    onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                  />
                </FormField>
              </div>
            </div>

            {/* Company Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold" style={{ color: '#F0EAD6' }}>
                Company Information
              </h3>

              <FormField
                label="Company Name"
                required
                {...(validationState['companyName']?.error && {
                  error: validationState['companyName'].error,
                })}
                {...(validationState['companyName']?.success && {
                  success: validationState['companyName'].success,
                })}
              >
                <Input
                  placeholder="Your Company Ltd."
                  value={formData.companyName}
                  onChange={(e) => handleInputChange('companyName', e.target.value)}
                />
              </FormField>

              <FormField
                label="Industry"
                required
                {...(validationState['industry']?.error && {
                  error: validationState['industry'].error,
                })}
                {...(validationState['industry']?.success && {
                  success: validationState['industry'].success,
                })}
                description="Select your primary industry"
              >
                <Select onValueChange={(value) => handleInputChange('industry', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select industry..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="technology">Technology</SelectItem>
                    <SelectItem value="finance">Finance</SelectItem>
                    <SelectItem value="healthcare">Healthcare</SelectItem>
                    <SelectItem value="manufacturing">Manufacturing</SelectItem>
                    <SelectItem value="retail">Retail</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>

              <FormField
                label="Company Description"
                description="Brief description of your company (optional)"
              >
                <Textarea
                  placeholder="Tell us about your company..."
                  rows={4}
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                />
              </FormField>
            </div>

            {/* Agreements */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold" style={{ color: '#F0EAD6' }}>
                Agreements
              </h3>

              <div className="space-y-3">
                <div className="flex items-start space-x-3">
                  <Checkbox
                    id="terms"
                    checked={formData.terms}
                    onCheckedChange={(checked) => handleInputChange('terms', checked as boolean)}
                  />
                  <div className="space-y-1">
                    <Label htmlFor="terms" className="text-sm font-medium">
                      I agree to the Terms of Service and Privacy Policy *
                    </Label>
                    <p className="text-xs" style={{ color: '#6C757D' }}>
                      By checking this box, you agree to our terms and conditions
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <Checkbox
                    id="newsletter"
                    checked={formData.newsletter}
                    onCheckedChange={(checked) =>
                      handleInputChange('newsletter', checked as boolean)
                    }
                  />
                  <div className="space-y-1">
                    <Label htmlFor="newsletter" className="text-sm font-medium">
                      Subscribe to our newsletter
                    </Label>
                    <p className="text-xs" style={{ color: '#6C757D' }}>
                      Get updates about new features and compliance insights
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Form Actions */}
            <div className="flex flex-col gap-3 pt-4 sm:flex-row">
              <Button variant="default" size="lg" className="flex-1">
                Create Account
              </Button>
              <Button variant="secondary" size="lg" className="flex-1">
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Form States Demo */}
      <Card className="ruleiq-card">
        <CardHeader>
          <CardTitle className="text-neutral-900">Form Validation States</CardTitle>
          <CardDescription className="text-neutral-600">
            Examples of different validation states and feedback
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Error Examples */}
            <div className="space-y-4">
              <h4 className="font-semibold text-neutral-900">
                Error States
              </h4>

              <FormField label="Required Field" error="This field is required" required>
                <Input placeholder="Required field..." error />
              </FormField>

              <FormField label="Invalid Email" error="Please enter a valid email address">
                <Input type="email" placeholder="invalid-email" error />
              </FormField>

              <FormField label="Invalid Selection" error="Please select a valid option">
                <Select>
                  <SelectTrigger error>
                    <SelectValue placeholder="Select option..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="option1">Option 1</SelectItem>
                    <SelectItem value="option2">Option 2</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            </div>

            {/* Success Examples */}
            <div className="space-y-4">
              <h4 className="font-semibold text-neutral-900">
                Success States
              </h4>

              <FormField label="Valid Input" success="Input is valid">
                <Input placeholder="Valid input..." success />
              </FormField>

              <FormField label="Valid Email" success="Email format is correct">
                <Input type="email" placeholder="user@example.com" success />
              </FormField>

              <FormField label="Valid Selection" success="Option selected successfully">
                <Select>
                  <SelectTrigger success>
                    <SelectValue placeholder="Option 1" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="option1">Option 1</SelectItem>
                    <SelectItem value="option2">Option 2</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
