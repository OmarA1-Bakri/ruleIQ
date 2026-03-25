'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, ChevronRight, Building, Shield, Users, Target, ArrowRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import { businessProfileService } from '@/lib/api/business-profiles.service';
import { cn } from '@/lib/utils';
import type { BusinessProfileFormData } from '@/types/business-profile';

const steps = [
  { id: 1, title: 'Company Details', icon: Building },
  { id: 2, title: 'Compliance Needs', icon: Shield },
  { id: 3, title: 'Team Setup', icon: Users },
  { id: 4, title: 'Goals', icon: Target },
];

const frameworks = [
  { id: 'gdpr', name: 'GDPR', description: 'EU Data Protection' },
  { id: 'iso27001', name: 'ISO 27001', description: 'Information Security' },
  { id: 'soc2', name: 'SOC 2', description: 'Service Organization Control' },
  { id: 'hipaa', name: 'HIPAA', description: 'Healthcare Compliance' },
  { id: 'pci-dss', name: 'PCI DSS', description: 'Payment Card Security' },
];

const frameworkNameMap: Record<string, string> = {
  gdpr: 'GDPR',
  iso27001: 'ISO 27001',
  soc2: 'SOC 2',
  hipaa: 'HIPAA',
  'pci-dss': 'PCI DSS',
};

const companySizeEmployeeCount: Record<string, number> = {
  '1-10': 10,
  '11-50': 50,
  '51-200': 200,
  '201+': 500,
};

const timelineMap: Record<string, string> = {
  asap: '3 months',
  '3months': '3 months',
  '6months': '6 months',
  year: '12 months',
};

const complianceSensitivityMap: Record<string, BusinessProfileFormData['data_sensitivity']> = {
  none: 'Low',
  basic: 'Moderate',
  advanced: 'High',
};

export default function OnboardingPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const [formData, setFormData] = useState({
    // Step 1
    companyName: '',
    companySize: '',
    industry: '',
    location: '',
    // Step 2
    frameworks: [] as string[],
    complianceLevel: '',
    // Step 3
    teamSize: '',
    inviteEmails: '',
    // Step 4
    primaryGoal: '',
    timeline: '',
  });

  const handleNext = () => {
    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const isCurrentStepValid = () => {
    switch (currentStep) {
      case 1:
        return Boolean(
          formData.companyName.trim() &&
            formData.companySize &&
            formData.industry.trim() &&
            formData.location.trim(),
        );
      case 2:
        return formData.frameworks.length > 0 && Boolean(formData.complianceLevel);
      case 3:
        return Boolean(formData.teamSize);
      case 4:
        return Boolean(formData.primaryGoal && formData.timeline);
      default:
        return false;
    }
  };

  const handleComplete = async () => {
    setIsLoading(true);

    try {
      const selectedFrameworks = formData.frameworks.map(
        (frameworkId) => frameworkNameMap[frameworkId] || frameworkId,
      );

      const dataTypes = Array.from(
        new Set([
          'Operational Data',
          ...(formData.frameworks.includes('gdpr') ? ['Personal Data'] : []),
          ...(formData.frameworks.includes('pci-dss') ? ['Payment Data'] : []),
          ...(formData.frameworks.includes('hipaa') ? ['Health Data'] : []),
        ]),
      );

      const profilePayload: BusinessProfileFormData = {
        company_name: formData.companyName.trim(),
        industry: formData.industry.trim(),
        employee_count: companySizeEmployeeCount[formData.companySize] || 10,
        annual_revenue: undefined,
        country: formData.location.trim(),
        data_sensitivity: complianceSensitivityMap[formData.complianceLevel] || 'Moderate',
        data_types: dataTypes,
        handles_personal_data:
          formData.frameworks.includes('gdpr') || formData.frameworks.includes('hipaa'),
        processes_payments: formData.frameworks.includes('pci-dss'),
        stores_health_data: formData.frameworks.includes('hipaa'),
        provides_financial_services: /finance|bank|fintech|insurance/i.test(formData.industry),
        operates_critical_infrastructure: false,
        has_international_operations: /global|international|multi/i.test(formData.location),
        cloud_providers: [],
        saas_tools: [],
        development_tools: [],
        existing_frameworks:
          formData.complianceLevel === 'none' ? [] : selectedFrameworks,
        planned_frameworks:
          formData.complianceLevel === 'advanced' ? [] : selectedFrameworks,
        compliance_budget: undefined,
        compliance_timeline: timelineMap[formData.timeline],
        assessment_completed: false,
        assessment_data: {
          current_step: steps.length,
          completed_steps: steps.map((step) => step.title),
          progress_percentage: 100,
          completion_status: 'completed',
          answers: {
            company_size: formData.companySize,
            team_size: formData.teamSize,
            compliance_level: formData.complianceLevel,
            primary_goal: formData.primaryGoal,
            timeline: formData.timeline,
            frameworks: selectedFrameworks,
            invite_emails: formData.inviteEmails,
          },
        },
      };

      await businessProfileService.saveProfile(profilePayload);

      toast({
        title: 'Welcome to RuleIQ!',
        description: 'Your account setup is complete.',
      });

      router.push('/dashboard');
    } catch (_error) {
      toast({
        title: 'Setup failed',
        description: 'Please try again or contact support.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="companyName">Company Name</Label>
              <Input
                id="companyName"
                placeholder="e.g., Acme Security Ltd"
                value={formData.companyName}
                onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="companySize">Company Size</Label>
              <RadioGroup
                value={formData.companySize}
                onValueChange={(value) => setFormData({ ...formData, companySize: value })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="1-10" id="size-1" />
                  <Label htmlFor="size-1" className="font-normal">1-10 employees</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="11-50" id="size-2" />
                  <Label htmlFor="size-2" className="font-normal">11-50 employees</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="51-200" id="size-3" />
                  <Label htmlFor="size-3" className="font-normal">51-200 employees</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="201+" id="size-4" />
                  <Label htmlFor="size-4" className="font-normal">201+ employees</Label>
                </div>
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <Input
                id="industry"
                placeholder="e.g., Technology, Healthcare, Finance"
                value={formData.industry}
                onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="location">Primary Location</Label>
              <Input
                id="location"
                placeholder="e.g., United Kingdom, United States"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              />
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-6">
            <div className="space-y-3">
              <Label>Select Compliance Frameworks</Label>
              <div className="space-y-3">
                {frameworks.map((framework) => (
                  <div key={framework.id} className="flex items-center space-x-3">
                    <Checkbox
                      id={framework.id}
                      checked={formData.frameworks.includes(framework.id)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setFormData({
                            ...formData,
                            frameworks: [...formData.frameworks, framework.id],
                          });
                        } else {
                          setFormData({
                            ...formData,
                            frameworks: formData.frameworks.filter((f) => f !== framework.id),
                          });
                        }
                      }}
                    />
                    <Label htmlFor={framework.id} className="flex-1 font-normal">
                      <span className="font-medium">{framework.name}</span> - {framework.description}
                    </Label>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Current Compliance Level</Label>
              <RadioGroup
                value={formData.complianceLevel}
                onValueChange={(value) => setFormData({ ...formData, complianceLevel: value })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="none" id="level-1" />
                  <Label htmlFor="level-1" className="font-normal">Just starting out</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="basic" id="level-2" />
                  <Label htmlFor="level-2" className="font-normal">Some policies in place</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="advanced" id="level-3" />
                  <Label htmlFor="level-3" className="font-normal">Well-established program</Label>
                </div>
              </RadioGroup>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="teamSize">Compliance Team Size</Label>
              <RadioGroup
                value={formData.teamSize}
                onValueChange={(value) => setFormData({ ...formData, teamSize: value })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="solo" id="team-1" />
                  <Label htmlFor="team-1" className="font-normal">Just me</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="small" id="team-2" />
                  <Label htmlFor="team-2" className="font-normal">2-5 people</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="medium" id="team-3" />
                  <Label htmlFor="team-3" className="font-normal">6-10 people</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="large" id="team-4" />
                  <Label htmlFor="team-4" className="font-normal">10+ people</Label>
                </div>
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label htmlFor="inviteEmails">Invite Team Members (Optional)</Label>
              <Input
                id="inviteEmails"
                placeholder="Enter email addresses separated by commas"
                value={formData.inviteEmails}
                onChange={(e) => setFormData({ ...formData, inviteEmails: e.target.value })}
              />
              <p className="text-sm text-muted-foreground">
                You can always invite team members later from Settings
              </p>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Primary Goal</Label>
              <RadioGroup
                value={formData.primaryGoal}
                onValueChange={(value) => setFormData({ ...formData, primaryGoal: value })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="certification" id="goal-1" />
                  <Label htmlFor="goal-1" className="font-normal">Achieve certification</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="audit" id="goal-2" />
                  <Label htmlFor="goal-2" className="font-normal">Pass an audit</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="improve" id="goal-3" />
                  <Label htmlFor="goal-3" className="font-normal">Improve compliance posture</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="maintain" id="goal-4" />
                  <Label htmlFor="goal-4" className="font-normal">Maintain existing compliance</Label>
                </div>
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label>Timeline</Label>
              <RadioGroup
                value={formData.timeline}
                onValueChange={(value) => setFormData({ ...formData, timeline: value })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="asap" id="time-1" />
                  <Label htmlFor="time-1" className="font-normal">ASAP</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="3months" id="time-2" />
                  <Label htmlFor="time-2" className="font-normal">Within 3 months</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="6months" id="time-3" />
                  <Label htmlFor="time-3" className="font-normal">Within 6 months</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="year" id="time-4" />
                  <Label htmlFor="time-4" className="font-normal">Within a year</Label>
                </div>
              </RadioGroup>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-primary/10 via-white to-brand-tertiary/10">
      <Card className="w-full max-w-2xl border-brand-primary/20 shadow-xl">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Welcome to RuleIQ</CardTitle>
          <CardDescription>Let's get your compliance journey started</CardDescription>
          <Progress value={(currentStep / steps.length) * 100} className="mt-4" />
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Step Indicators */}
          <div className="flex justify-between">
            {steps.map((step) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.id}
                  className={cn(
                    'flex flex-col items-center space-y-2',
                    currentStep >= step.id ? 'text-brand-primary' : 'text-muted-foreground'
                  )}
                >
                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-full border-2',
                      currentStep >= step.id
                        ? 'border-brand-primary bg-brand-primary/10'
                        : 'border-muted-foreground/30'
                    )}
                  >
                    {currentStep > step.id ? (
                      <Check className="h-5 w-5" />
                    ) : (
                      <Icon className="h-5 w-5" />
                    )}
                  </div>
                  <span className="text-xs font-medium">{step.title}</span>
                </div>
              );
            })}
          </div>

          {/* Step Content */}
          {renderStepContent()}

          {/* Navigation */}
          <div className="flex justify-between pt-6">
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 1}
              className={currentStep === 1 ? 'invisible' : ''}
            >
              Back
            </Button>
            <Button
              onClick={handleNext}
              disabled={isLoading || !isCurrentStepValid()}
              className="bg-brand-primary hover:bg-brand-dark"
            >
              {currentStep === steps.length ? (
                <>
                  {isLoading ? 'Setting up...' : 'Complete Setup'}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              ) : (
                <>
                  Next
                  <ChevronRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
