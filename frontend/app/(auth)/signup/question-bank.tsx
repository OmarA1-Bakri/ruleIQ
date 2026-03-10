import {
  Bot,
  Shield,
  AlertTriangle,
  TrendingUp,
  Users,
  FileCheck,
  Lock,
  Globe,
  CreditCard,
  Heart,
  Building2,
} from 'lucide-react';

import type { Question, QuestionAnswer, UserFormData } from './signup-types';

// Question Bank - Smart, Dynamic Questions
export const questionBank: Record<string, Question> = {
  // Initial Greeting
  greeting: {
    id: 'greeting',
    type: 'greeting',
    question:
      "👋 Hello! I'm ruleIQ's AI compliance advisor. I'll help create a personalized compliance roadmap for your business. This will take about 5 minutes. Ready?",
    options: ["Let's start!", 'Tell me more'],
    icon: <Bot className="h-5 w-5" />,
  },

  // Basic Information
  fullName: {
    id: 'fullName',
    type: 'input',
    question: "Great! Let's start with your name. What should I call you?",
    field: 'fullName',
    validation: 'name',
  },

  email: {
    id: 'email',
    type: 'input',
    question: (data) => `Nice to meet you, ${data.fullName}! What's your business email?`,
    field: 'email',
    validation: 'email',
  },

  password: {
    id: 'password',
    type: 'input',
    question: "Let's secure your account. Please create a strong password:",
    field: 'password',
    validation: 'password',
    inputType: 'password',
  },

  confirmPassword: {
    id: 'confirmPassword',
    type: 'input',
    question: 'Please confirm your password:',
    field: 'confirmPassword',
    validation: 'confirmPassword',
    inputType: 'password',
  },

  // Company Information
  companyName: {
    id: 'companyName',
    type: 'input',
    question: "What's your company name?",
    field: 'companyName',
    validation: 'companyName',
    icon: <Building2 className="h-5 w-5" />,
  },

  companySize: {
    id: 'companySize',
    type: 'choice',
    question: (data) => `How many people work at ${data.companyName}?`,
    field: 'companySize',
    options: ['Just me', '2-10', '11-50', '51-200', '201-500', '500+'],
    icon: <Users className="h-5 w-5" />,
    nextQuestion: (_data, answer) => {
      if (answer === 'Just me' || answer === '2-10') return 'smallBusinessConcerns';
      if (typeof answer === 'string' && answer && answer.includes('-')) {
        const firstNumber = parseInt(answer.split('-')[0]!);
        if (!isNaN(firstNumber) && firstNumber > 50) return 'hasComplianceTeam';
      }
      return 'industry';
    },
  },

  // Dynamic questions based on company size
  smallBusinessConcerns: {
    id: 'smallBusinessConcerns',
    type: 'multi-choice',
    question: 'As a small business, what are your main concerns? (Select all that apply)',
    field: 'mainConcerns',
    options: [
      'Cost of compliance',
      'Time constraints',
      'Lack of expertise',
      'Understanding requirements',
      'Getting certified quickly',
    ],
    multiple: true,
    priority: 'high',
  },

  hasComplianceTeam: {
    id: 'hasComplianceTeam',
    type: 'choice',
    question: 'Do you have a dedicated compliance or legal team?',
    field: 'hasComplianceTeam',
    options: ['Yes, full team', 'Yes, part-time', 'No, but planning to', 'No dedicated team'],
    nextQuestion: (_data, answer) => {
      if (typeof answer === 'string' && answer?.includes('Yes')) return 'complianceMaturity';
      return 'industry';
    },
  },

  complianceMaturity: {
    id: 'complianceMaturity',
    type: 'choice',
    question: 'How would you rate your current compliance maturity?',
    field: 'maturity',
    options: ['Just starting', 'Basic processes', 'Well-established', 'Industry-leading'],
    icon: <TrendingUp className="h-5 w-5" />,
  },

  // Industry & Operations
  industry: {
    id: 'industry',
    type: 'choice',
    question: (data) => `Which industry is ${data.companyName} in?`,
    field: 'industry',
    options: [
      'Technology/SaaS',
      'Healthcare',
      'Financial Services',
      'E-commerce/Retail',
      'Manufacturing',
      'Education',
      'Professional Services',
      'Other',
    ],
    nextQuestion: (_data, answer) => {
      if (answer === 'Healthcare') return 'healthcareSpecific';
      if (answer === 'Financial Services') return 'financialSpecific';
      if (answer === 'E-commerce/Retail') return 'ecommerceSpecific';
      return 'businessModel';
    },
  },

  // Industry-specific questions
  healthcareSpecific: {
    id: 'healthcareSpecific',
    type: 'multi-choice',
    question: 'Which healthcare data do you handle?',
    field: 'healthcareData',
    options: [
      'Patient records',
      'Medical imaging',
      'Billing information',
      'Research data',
      'Genetic information',
    ],
    multiple: true,
    icon: <Heart className="h-5 w-5" />,
    priority: 'high',
  },

  financialSpecific: {
    id: 'financialSpecific',
    type: 'multi-choice',
    question: 'Which financial services do you provide?',
    field: 'financialServices',
    options: [
      'Payment processing',
      'Investment advice',
      'Banking services',
      'Insurance',
      'Cryptocurrency',
      'Lending',
    ],
    multiple: true,
    icon: <CreditCard className="h-5 w-5" />,
    priority: 'high',
  },

  ecommerceSpecific: {
    id: 'ecommerceSpecific',
    type: 'choice',
    question: 'How many transactions do you process monthly?',
    field: 'transactionVolume',
    options: ['Under 100', '100-1,000', '1,000-10,000', '10,000-100,000', 'Over 100,000'],
    priority: 'high',
  },

  // Business Model & Data
  businessModel: {
    id: 'businessModel',
    type: 'choice',
    question: (data) => `Is ${data.companyName} B2B or B2C?`,
    field: 'businessModel',
    options: ['B2B only', 'B2C only', 'Both B2B and B2C', 'B2G (Government)', 'Non-profit'],
    nextQuestion: (_data, answer) =>
      typeof answer === 'string' && (answer.includes('B2C') || answer === 'Both B2B and B2C')
        ? 'customerBase'
        : 'regions',
  },

  customerBase: {
    id: 'customerBase',
    type: 'choice',
    question: 'How many customers/users do you have?',
    field: 'customerBase',
    options: ['Under 100', '100-1,000', '1,000-10,000', '10,000-100,000', 'Over 100,000'],
    priority: 'medium',
  },

  regions: {
    id: 'regions',
    type: 'multi-choice',
    question: (data) => `Where does ${data.companyName} operate? (Select all)`,
    field: 'regions',
    options: ['UK', 'EU', 'USA', 'Canada', 'Asia-Pacific', 'Global'],
    multiple: true,
    icon: <Globe className="h-5 w-5" />,
    nextQuestion: (_data, answer) => {
      if (Array.isArray(answer) && (answer.includes('EU') || answer.includes('UK')))
        return 'gdprRelevant';
      if (Array.isArray(answer) && answer.includes('USA')) return 'usCompliance';
      return 'dataTypes';
    },
  },

  // Compliance-specific
  gdprRelevant: {
    id: 'gdprRelevant',
    type: 'choice',
    question: 'Do you process personal data of EU/UK residents?',
    field: 'gdprRelevant',
    options: ['Yes, extensively', 'Yes, some', 'Planning to', 'No'],
    icon: <Lock className="h-5 w-5" />,
    priority: 'high',
  },

  usCompliance: {
    id: 'usCompliance',
    type: 'multi-choice',
    question: 'Which US compliance requirements might apply?',
    field: 'usCompliance',
    options: ['CCPA (California)', 'HIPAA', 'SOX', 'FERPA', 'State privacy laws', 'Not sure'],
    multiple: true,
    priority: 'medium',
  },

  // Data Handling
  dataTypes: {
    id: 'dataTypes',
    type: 'multi-choice',
    question: 'What types of data does your business handle?',
    field: 'dataTypes',
    options: [
      'Customer personal info',
      'Payment/financial',
      'Health records',
      'Employee data',
      'Sensitive/confidential',
      "Children's data",
    ],
    multiple: true,
    icon: <FileCheck className="h-5 w-5" />,
    priority: 'high',
    nextQuestion: (_data, answer) => {
      if (Array.isArray(answer) && answer.includes('Payment/financial')) return 'pciDssRelevant';
      if (Array.isArray(answer) && answer.includes('Health records')) return 'hipaaRelevant';
      return 'currentCompliance';
    },
  },

  pciDssRelevant: {
    id: 'pciDssRelevant',
    type: 'choice',
    question: 'How do you handle payment card data?',
    field: 'paymentHandling',
    options: [
      'We store card details',
      "We process but don't store",
      'Third-party handles it',
      "We don't handle cards",
    ],
    priority: 'high',
  },

  hipaaRelevant: {
    id: 'hipaaRelevant',
    type: 'choice',
    question: 'Are you a covered entity or business associate under HIPAA?',
    field: 'hipaaStatus',
    options: ['Covered entity', 'Business associate', 'Both', 'Not sure', 'Not applicable'],
    priority: 'high',
  },

  // Current State
  currentCompliance: {
    id: 'currentCompliance',
    type: 'multi-choice',
    question: 'Which frameworks are you currently following? (Select all)',
    field: 'currentFrameworks',
    options: (data) => {
      const base = ['None yet', 'ISO 27001', 'SOC 2', 'Cyber Essentials'];
      if (data.gdprRelevant === 'Yes, extensively') base.push('GDPR');
      if (data.paymentHandling && data.paymentHandling !== "We don't handle cards")
        base.push('PCI DSS');
      if (data.hipaaStatus && data.hipaaStatus !== 'Not applicable') base.push('HIPAA');
      return base;
    },
    multiple: true,
  },

  // Priorities & Timeline
  compliancePriorities: {
    id: 'compliancePriorities',
    type: 'choice',
    question: "What's your #1 compliance priority?",
    field: 'topPriority',
    options: (data) => {
      const priorities = [];
      if (data.gdprRelevant === 'Yes, extensively') priorities.push('GDPR compliance');
      if (
        data.customerBase &&
        typeof data.customerBase === 'string' &&
        data.customerBase &&
        data.customerBase.includes('-')
      ) {
        const firstNumber = parseInt(data.customerBase.split('-')[0]!);
        if (!isNaN(firstNumber) && firstNumber > 1000) priorities.push('SOC 2 certification');
      }
      priorities.push(
        'ISO 27001',
        'Build security policies',
        'Risk assessment',
        'Employee training',
      );
      return priorities;
    },
    icon: <AlertTriangle className="h-5 w-5" />,
    priority: 'high',
  },

  timeline: {
    id: 'timeline',
    type: 'choice',
    question: (data) => `When do you need to achieve ${data.topPriority || 'compliance'}?`,
    field: 'timeline',
    options: [
      'ASAP (< 1 month)',
      'Within 3 months',
      'Within 6 months',
      'Within a year',
      'Just planning ahead',
    ],
    priority: 'high',
  },

  // Budget & Resources
  budget: {
    id: 'budget',
    type: 'choice',
    question: "What's your annual compliance budget?",
    field: 'budget',
    options: ['Under £10k', '£10k-50k', '£50k-100k', 'Over £100k', 'Not yet defined'],
    skipIf: (data) => data.companySize === 'Just me',
  },

  // Final Questions
  biggestChallenge: {
    id: 'biggestChallenge',
    type: 'choice',
    question: "What's your biggest compliance challenge?",
    field: 'challenge',
    options: (data) => {
      const challenges = ["Don't know where to start", 'Too time consuming', 'Lack of expertise'];
      if (data.companySize === 'Just me' || data.companySize === '2-10') {
        challenges.push('Limited budget', 'No dedicated staff');
      } else {
        challenges.push('Keeping up with changes', 'Managing multiple frameworks');
      }
      challenges.push('Documentation burden');
      return challenges;
    },
  },

  agreeToTerms: {
    id: 'agreeToTerms',
    type: 'confirm',
    question: (data) => {
      const frameworks = [];
      if (data.gdprRelevant === 'Yes, extensively') frameworks.push('GDPR');
      if (data.topPriority) frameworks.push(data.topPriority);

      return `Excellent, ${data.fullName}! Based on your answers, I'll create a personalized compliance roadmap focusing on ${frameworks.join(' and ')}. Ready to get started?`;
    },
    field: 'agreeToTerms',
    confirmText: 'I agree to the Terms of Service and Privacy Policy',
  },
};

// Question Flow Logic
export const getQuestionFlow = (): string[] => {
  return [
    'greeting',
    'fullName',
    'email',
    'password',
    'confirmPassword',
    'companyName',
    'companySize',
    'industry',
    'businessModel',
    'regions',
    'dataTypes',
    'currentCompliance',
    'compliancePriorities',
    'timeline',
    'biggestChallenge',
    'agreeToTerms',
  ];
};

export const getNextQuestion = (
  currentId: string,
  data: UserFormData,
  answer?: QuestionAnswer,
): string | null => {
  const current = questionBank[currentId];

  // Check if current question exists and has custom next logic
  if (current?.nextQuestion && answer !== undefined) {
    try {
      const nextId = current.nextQuestion(data, answer);
      // Validate that the returned question ID exists and is different from current
      if (nextId && questionBank[nextId] && nextId !== currentId) {
        return nextId;
      }
    } catch (_error) {
      // Error in nextQuestion logic
    }
  }

  // Get base flow
  const flow = getQuestionFlow();
  const currentIndex = flow.findIndex((id) => id === currentId);

  // If current question not in flow, return null
  if (currentIndex === -1) {
    return null;
  }

  // Find next unskipped question
  for (let i = currentIndex + 1; i < flow.length; i++) {
    const nextId = flow[i];
    if (!nextId) continue;

    const nextQuestion = questionBank[nextId];
    if (!nextQuestion) continue;

    if (!nextQuestion.skipIf || !nextQuestion.skipIf(data)) {
      return nextId;
    }
  }

  return null;
};
