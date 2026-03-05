'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import {
  Building2,
  Users,
  Shield,
  Globe,
  ChevronRight,
  ChevronLeft,
  Check,
  AlertCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import * as React from 'react';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { H2, H3, Body, Caption } from '@/components/ui/typography';
import { useAppStore } from '@/lib/stores/app.store';
import { useBusinessProfileStore } from '@/lib/stores/business-profile.store';
import { cn } from '@/lib/utils';

import type { BusinessProfileFormData } from '@/types/business-profile';

const steps = [
  { title: 'Company Info', icon: Building2 },
  { title: 'Industry & Size', icon: Users },
  { title: 'Compliance Needs', icon: Shield },
  { title: 'Data Handling', icon: Globe },
];

// Step 1: Company Information
const companyInfoSchema = z.object({
  company_name: z.string().min(2, 'Company name is required'),
  website: z.string().url('Invalid URL').optional().or(z.literal('')),
  founded_year: z.number().min(1800).max(new Date().getFullYear()).optional(),
  description: z.string().max(500, 'Description must be less than 500 characters').optional(),
});

// Step 2: Industry & Size
const industrySchema = z.object({
  industry: z.string().min(1, 'Please select an industry'),
  size: z.string().min(1, 'Please select company size'),
  annual_revenue: z.string().optional(),
  country: z.string().min(1, 'Please select a country'),
});

// Step 3: Compliance Needs
const complianceSchema = z.object({
  compliance_frameworks: z.array(z.string()).min(1, 'Please select at least one framework'),
});

// Step 4: Data Handling
const dataHandlingSchema = z.object({
  data_types_collected: z.array(z.string()).min(1, 'Please select at least one data type'),
  data_storage_locations: z.array(z.string()).min(1, 'Please select at least one location'),
  third_party_sharing: z.boolean(),
});

// Combined schema
const profileWizardSchema = companyInfoSchema
  .merge(industrySchema)
  .merge(complianceSchema)
  .merge(dataHandlingSchema);

type ProfileWizardData = z.infer<typeof profileWizardSchema>;

const industries = [
  { value: 'technology', label: 'Technology' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'finance', label: 'Finance & Banking' },
  { value: 'retail', label: 'Retail & E-commerce' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'education', label: 'Education' },
  { value: 'professional-services', label: 'Professional Services' },
  { value: 'hospitality', label: 'Hospitality & Tourism' },
  { value: 'real-estate', label: 'Real Estate' },
  { value: 'other', label: 'Other' },
];

const companySizes = [
  { value: '1-10', label: '1-10 employees' },
  { value: '11-50', label: '11-50 employees' },
  { value: '51-200', label: '51-200 employees' },
  { value: '201-500', label: '201-500 employees' },
  { value: '501-1000', label: '501-1000 employees' },
  { value: '1000+', label: '1000+ employees' },
];

const revenueRanges = [
  { value: '0-100k', label: '£0 - £100K' },
  { value: '100k-500k', label: '£100K - £500K' },
  { value: '500k-1m', label: '£500K - £1M' },
  { value: '1m-5m', label: '£1M - £5M' },
  { value: '5m-10m', label: '£5M - £10M' },
  { value: '10m+', label: '£10M+' },
];

const countries = [
  { value: 'GB', label: 'United Kingdom' },
  { value: 'US', label: 'United States' },
  { value: 'CA', label: 'Canada' },
  { value: 'AU', label: 'Australia' },
  { value: 'DE', label: 'Germany' },
  { value: 'FR', label: 'France' },
  { value: 'NL', label: 'Netherlands' },
  { value: 'IE', label: 'Ireland' },
];

const complianceFrameworks = [
  { id: 'gdpr', label: 'GDPR', description: 'General Data Protection Regulation' },
  { id: 'iso27001', label: 'ISO 27001', description: 'Information Security Management' },
  { id: 'soc2', label: 'SOC 2', description: 'Service Organization Control 2' },
  { id: 'pci-dss', label: 'PCI DSS', description: 'Payment Card Industry Standards' },
  { id: 'hipaa', label: 'HIPAA', description: 'Health Insurance Portability Act' },
  { id: 'cyber-essentials', label: 'Cyber Essentials', description: 'UK Cyber Security Standard' },
  { id: 'nist', label: 'NIST', description: 'National Institute of Standards' },
];

const dataTypes = [
  { id: 'personal', label: 'Personal Information', description: 'Names, addresses, emails' },
  { id: 'financial', label: 'Financial Data', description: 'Payment info, transactions' },
  { id: 'health', label: 'Health Records', description: 'Medical information' },
  { id: 'biometric', label: 'Biometric Data', description: 'Fingerprints, facial recognition' },
  { id: 'location', label: 'Location Data', description: 'GPS, IP addresses' },
  { id: 'behavioral', label: 'Behavioral Data', description: 'Usage patterns, preferences' },
];

const storageLocations = [
  { id: 'uk', label: 'United Kingdom' },
  { id: 'eu', label: 'European Union' },
  { id: 'us', label: 'United States' },
  { id: 'cloud', label: 'Cloud (Multi-region)' },
  { id: 'on-premise', label: 'On-premise only' },
];

interface ProfileWizardProps {
  onComplete?: () => void;
  initialData?: Partial<ProfileWizardData>;
}

export function ProfileWizard({ onComplete, initialData }: ProfileWizardProps) {
  const router = useRouter();
  const { saveProfile, updateProfile, profile, isLoading, error } = useBusinessProfileStore();
  const { addNotification } = useAppStore();
  const [currentStep, setCurrentStep] = React.useState(0);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    trigger,
    getValues,
  } = useForm<ProfileWizardData>({
    resolver: zodResolver(profileWizardSchema),
    defaultValues: initialData || {
      company_name: '',
      website: '',
      description: '',
      industry: '',
      size: '',
      annual_revenue: '',
      country: 'GB',
      compliance_frameworks: [],
      data_types_collected: [],
      data_storage_locations: [],
      third_party_sharing: false,
    },
  });

  const watchedCompliance = watch('compliance_frameworks') || [];
  const watchedDataTypes = watch('data_types_collected') || [];
  const watchedStorageLocations = watch('data_storage_locations') || [];

  const validateStep = async (step: number) => {
    switch (step) {
      case 0:
        return await trigger(['company_name', 'website', 'founded_year', 'description']);
      case 1:
        return await trigger(['industry', 'size', 'annual_revenue', 'country']);
      case 2:
        return await trigger(['compliance_frameworks']);
      case 3:
        return await trigger([
          'data_types_collected',
          'data_storage_locations',
          'third_party_sharing',
        ]);
      default:
        return false;
    }
  };

  const handleNext = async () => {
    const isValid = await validateStep(currentStep);
    if (isValid && currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const onSubmit = async (data: ProfileWizardData) => {
    try {
      // Map wizard data to BusinessProfile format
      const profileData: Partial<BusinessProfileFormData> = {
        company_name: data.company_name,
        industry: data.industry,
        employee_count: parseInt(data.size.split('-')[0] || '1') || 1, // Convert "1-10" to 1
        annual_revenue: data.annual_revenue || '',
        country: data.country,
        data_sensitivity: 'Moderate' as const, // Default value
        handles_personal_data: data.data_types_collected?.includes('personal') || false,
        processes_payments: data.data_types_collected?.includes('financial') || false,
        stores_health_data: data.data_types_collected?.includes('health') || false,
        provides_financial_services: data.industry === 'finance',
        operates_critical_infrastructure: false, // Default
        has_international_operations:
          data.data_storage_locations?.includes('us') ||
          data.data_storage_locations?.includes('eu') ||
          false,
        cloud_providers:
          data.data_storage_locations?.map((loc) =>
            loc === 'cloud' ? 'AWS' : loc.toUpperCase(),
          ) || [],
        saas_tools: [], // Default empty
        development_tools: [], // Default empty
        existing_frameworks: data.compliance_frameworks || [],
        planned_frameworks: [], // Default empty
        compliance_budget: data.annual_revenue || '',
        compliance_timeline: '6-months',
        assessment_completed: false,
        assessment_data: {},
      };

      if (profile) {
        await updateProfile(profileData as BusinessProfileFormData);
      } else {
        await saveProfile(profileData as BusinessProfileFormData);
      }

      addNotification({
        type: 'success',
        title: 'Profile saved!',
        message: 'Your business profile has been successfully created.',
        duration: 5000,
      });

      if (onComplete) {
        onComplete();
      } else {
        router.push('/dashboard');
      }
    } catch (_error) {
      // Error is handled by the store
    }
  };

  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <Caption>
            Step {currentStep + 1} of {steps.length}
          </Caption>
          <Caption>{Math.round(progress)}% Complete</Caption>
        </div>
        <Progress value={progress} className="h-2" />
      </div>

      {/* Stepper */}
      <div className="flex justify-between">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isActive = index === currentStep;
          const isCompleted = index < currentStep;

          return (
            <div
              key={index}
              className={cn(
                'flex flex-1 items-center',
                index < steps.length - 1 &&
                  "after:mx-3 after:h-0.5 after:w-full after:content-['']",
                isCompleted && 'after:bg-success',
                !isCompleted && 'after:bg-muted',
              )}
            >
              <div className="flex flex-col items-center gap-2">
                <div
                  className={cn(
                    'flex h-12 w-12 items-center justify-center rounded-full border-2 transition-all',
                    isCompleted && 'border-success bg-success text-white',
                    isActive && 'scale-110 border-gold bg-gold text-white',
                    !isCompleted && !isActive && 'border-muted-foreground/30 text-muted-foreground',
                  )}
                >
                  {isCompleted ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                </div>
                <Caption
                  className={cn(
                    'text-center',
                    isActive && 'font-medium text-gold',
                    isCompleted && 'text-success',
                  )}
                >
                  {step.title}
                </Caption>
              </div>
            </div>
          );
        })}
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        <Card>
          <CardContent className="p-6">
            {/* Step 0: Company Information */}
            <div className={cn('space-y-6', currentStep !== 0 && 'hidden')}>
              <div className="space-y-2">
                <H2>Company Information</H2>
                <Body color="muted">Tell us about your company</Body>
              </div>

              <div className="grid gap-6">
                <div className="space-y-2">
                  <Label htmlFor="company_name">Company Name *</Label>
                  <Input
                    id="company_name"
                    placeholder="Acme Corporation"
                    {...register('company_name')}
                    className={errors.company_name && 'border-error'}
                  />
                  {errors.company_name && (
                    <Caption color="error">{errors.company_name.message}</Caption>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="website">Website</Label>
                  <Input
                    id="website"
                    type="url"
                    placeholder="https://example.com"
                    {...register('website')}
                    className={errors.website && 'border-error'}
                  />
                  {errors.website && <Caption color="error">{errors.website.message}</Caption>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="founded_year">Founded Year</Label>
                  <Input
                    id="founded_year"
                    type="number"
                    placeholder="2020"
                    {...register('founded_year', { valueAsNumber: true })}
                    className={errors.founded_year && 'border-error'}
                  />
                  {errors.founded_year && (
                    <Caption color="error">{errors.founded_year.message}</Caption>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Brief description of your company..."
                    rows={4}
                    {...register('description')}
                    className={errors.description && 'border-error'}
                  />
                  {errors.description && (
                    <Caption color="error">{errors.description.message}</Caption>
                  )}
                  <Caption color="muted">
                    {watch('description')?.length || 0}/500 characters
                  </Caption>
                </div>
              </div>
            </div>

            {/* Step 1: Industry & Size */}
            <div className={cn('space-y-6', currentStep !== 1 && 'hidden')}>
              <div className="space-y-2">
                <H2>Industry & Size</H2>
                <Body color="muted">Help us understand your business better</Body>
              </div>

              <div className="grid gap-6">
                <div className="space-y-2">
                  <Label htmlFor="industry">Industry *</Label>
                  <Select
                    onValueChange={(value) => setValue('industry', value)}
                    {...(getValues('industry') && { defaultValue: getValues('industry') })}
                  >
                    <SelectTrigger className={errors.industry && 'border-error'}>
                      <SelectValue placeholder="Select your industry" />
                    </SelectTrigger>
                    <SelectContent>
                      {industries.map((industry) => (
                        <SelectItem key={industry.value} value={industry.value}>
                          {industry.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.industry && <Caption color="error">{errors.industry.message}</Caption>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="size">Company Size *</Label>
                  <Select
                    onValueChange={(value) => setValue('size', value)}
                    {...(getValues('size') && { defaultValue: getValues('size') })}
                  >
                    <SelectTrigger className={errors.size && 'border-error'}>
                      <SelectValue placeholder="Select company size" />
                    </SelectTrigger>
                    <SelectContent>
                      {companySizes.map((size) => (
                        <SelectItem key={size.value} value={size.value}>
                          {size.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.size && <Caption color="error">{errors.size.message}</Caption>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="annual_revenue">Annual Revenue</Label>
                  <Select
                    onValueChange={(value) => setValue('annual_revenue', value)}
                    {...((() => {
                      const value = getValues('annual_revenue');
                      return value && value !== '' ? { defaultValue: value } : {};
                    })())}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select revenue range" />
                    </SelectTrigger>
                    <SelectContent>
                      {revenueRanges.map((range) => (
                        <SelectItem key={range.value} value={range.value}>
                          {range.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="country">Country *</Label>
                  <Select
                    onValueChange={(value) => setValue('country', value)}
                    {...(getValues('country') && { defaultValue: getValues('country') })}
                  >
                    <SelectTrigger className={errors.country && 'border-error'}>
                      <SelectValue placeholder="Select country" />
                    </SelectTrigger>
                    <SelectContent>
                      {countries.map((country) => (
                        <SelectItem key={country.value} value={country.value}>
                          {country.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.country && <Caption color="error">{errors.country.message}</Caption>}
                </div>
              </div>
            </div>

            {/* Step 2: Compliance Needs */}
            <div className={cn('space-y-6', currentStep !== 2 && 'hidden')}>
              <div className="space-y-2">
                <H2>Compliance Requirements</H2>
                <Body color="muted">Select all frameworks that apply to your business</Body>
              </div>

              <div className="space-y-4">
                {complianceFrameworks.map((framework) => (
                  <label
                    key={framework.id}
                    className={cn(
                      'flex cursor-pointer items-start space-x-3 rounded-lg border p-4 transition-all',
                      watchedCompliance.includes(framework.id)
                        ? 'border-gold bg-gold/5'
                        : 'border-border hover:border-gold/50',
                    )}
                  >
                    <Checkbox
                      checked={watchedCompliance.includes(framework.id)}
                      onCheckedChange={(checked) => {
                        const current = getValues('compliance_frameworks') || [];
                        if (checked) {
                          setValue('compliance_frameworks', [...current, framework.id]);
                        } else {
                          setValue(
                            'compliance_frameworks',
                            current.filter((id) => id !== framework.id),
                          );
                        }
                      }}
                      className="mt-0.5"
                    />
                    <div className="flex-1">
                      <H3 className="text-base">{framework.label}</H3>
                      <Caption color="muted">{framework.description}</Caption>
                    </div>
                  </label>
                ))}
                {errors.compliance_frameworks && (
                  <Caption color="error">{errors.compliance_frameworks.message}</Caption>
                )}
              </div>
            </div>

            {/* Step 3: Data Handling */}
            <div className={cn('space-y-6', currentStep !== 3 && 'hidden')}>
              <div className="space-y-2">
                <H2>Data Handling</H2>
                <Body color="muted">Tell us about the data you collect and process</Body>
              </div>

              <div className="space-y-6">
                <div className="space-y-4">
                  <H3>Types of Data Collected *</H3>
                  {dataTypes.map((type) => (
                    <label
                      key={type.id}
                      className={cn(
                        'flex cursor-pointer items-start space-x-3 rounded-lg border p-4 transition-all',
                        watchedDataTypes.includes(type.id)
                          ? 'border-gold bg-gold/5'
                          : 'border-border hover:border-gold/50',
                      )}
                    >
                      <Checkbox
                        checked={watchedDataTypes.includes(type.id)}
                        onCheckedChange={(checked) => {
                          const current = getValues('data_types_collected') || [];
                          if (checked) {
                            setValue('data_types_collected', [...current, type.id]);
                          } else {
                            setValue(
                              'data_types_collected',
                              current.filter((id) => id !== type.id),
                            );
                          }
                        }}
                        className="mt-0.5"
                      />
                      <div className="flex-1">
                        <Body className="font-medium">{type.label}</Body>
                        <Caption color="muted">{type.description}</Caption>
                      </div>
                    </label>
                  ))}
                  {errors.data_types_collected && (
                    <Caption color="error">{errors.data_types_collected.message}</Caption>
                  )}
                </div>

                <div className="space-y-4">
                  <H3>Data Storage Locations *</H3>
                  {storageLocations.map((location) => (
                    <label key={location.id} className="flex items-center space-x-3">
                      <Checkbox
                        checked={watchedStorageLocations.includes(location.id)}
                        onCheckedChange={(checked) => {
                          const current = getValues('data_storage_locations') || [];
                          if (checked) {
                            setValue('data_storage_locations', [...current, location.id]);
                          } else {
                            setValue(
                              'data_storage_locations',
                              current.filter((id) => id !== location.id),
                            );
                          }
                        }}
                      />
                      <Body>{location.label}</Body>
                    </label>
                  ))}
                  {errors.data_storage_locations && (
                    <Caption color="error">{errors.data_storage_locations.message}</Caption>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="flex items-center space-x-3">
                    <Checkbox
                      checked={watch('third_party_sharing')}
                      onCheckedChange={(checked) =>
                        setValue('third_party_sharing', checked as boolean)
                      }
                    />
                    <Body>We share data with third parties</Body>
                  </label>
                  <Caption color="muted" className="ml-7">
                    Select if you share customer data with partners, vendors, or service providers
                  </Caption>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between gap-4">
          <Button
            type="button"
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 0 || isLoading}
            className="gap-2"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </Button>

          {currentStep < steps.length - 1 ? (
            <Button
              type="button"
              variant="secondary"
              onClick={handleNext}
              disabled={isLoading}
              className="gap-2"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" variant="secondary" loading={isLoading} className="gap-2">
              Complete Profile
              <Check className="h-4 w-4" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
