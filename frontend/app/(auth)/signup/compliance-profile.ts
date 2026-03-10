import type { UserFormData } from './signup-types';

export const generateComplianceProfile = (data: UserFormData) => {
  const priorities = [];
  const risks = [];
  const recommendations = [];

  // Analyze answers to create intelligent profile
  if (data.gdprRelevant === 'Yes, extensively') {
    priorities.push('GDPR Compliance');
    risks.push('Data protection violations');
  }

  if (data.paymentHandling && data.paymentHandling !== "We don't handle cards") {
    priorities.push('PCI DSS');
    risks.push('Payment security');
  }

  if (data.companySize === 'Just me' || data.companySize === '2-10') {
    recommendations.push('Start with essential policies');
    recommendations.push('Use automated compliance tools');
  }

  if (data.timeline === 'ASAP (< 1 month)') {
    recommendations.push('Fast-track certification program');
  }

  return {
    priorities,
    risks,
    recommendations,
    maturityLevel: data.currentFrameworks?.includes('None yet') ? 'beginner' : 'intermediate',
    estimatedTimeToCompliance: getTimeEstimate(data),
    suggestedFrameworks: getSuggestedFrameworks(data),
  };
};

export const getTimeEstimate = (data: UserFormData): string => {
  if (data.currentFrameworks?.includes('None yet')) {
    return '3-6 months';
  }
  if (data.hasComplianceTeam === 'Yes, full team') {
    return '1-3 months';
  }
  return '2-4 months';
};

export const getSuggestedFrameworks = (data: UserFormData): string[] => {
  const frameworks = [];

  if (data.regions?.includes('UK') || data.regions?.includes('EU')) {
    frameworks.push('GDPR');
  }

  if (
    data.customerBase &&
    typeof data.customerBase === 'string' &&
    data.customerBase &&
    data.customerBase.includes('-')
  ) {
    const firstNumber = parseInt(data.customerBase.split('-')[0]!);
    if (!isNaN(firstNumber) && firstNumber > 1000) {
      frameworks.push('SOC 2');
    }
  }

  if (data.industry === 'Healthcare') {
    frameworks.push('HIPAA');
  }

  return frameworks;
};
