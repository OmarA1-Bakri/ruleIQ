'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  Send,
  Loader2,
  Check,
  ChevronRight,
  Shield,
  ArrowLeft,
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
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import * as React from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { useAppStore } from '@/lib/stores/app.store';
import { useAuthStore } from '@/lib/stores/auth.store';
import { cn } from '@/lib/utils';

// Dynamic Question System
type QuestionType = 'greeting' | 'input' | 'choice' | 'multi-choice' | 'confirm' | 'dynamic';

// User data interface for form responses
interface UserFormData {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  companyName?: string;
  companySize?: string;
  industry?: string;
  businessModel?: string;
  regions?: string[];
  dataTypes?: string[];
  currentFrameworks?: string[];
  topPriority?: string;
  timeline?: string;
  challenge?: string;
  agreeToTerms?: boolean;
  // Industry-specific fields
  healthcareData?: string[];
  financialServices?: string[];
  transactionVolume?: string;
  // Compliance fields
  gdprRelevant?: string;
  usCompliance?: string[];
  paymentHandling?: string;
  hipaaStatus?: string;
  // Business insights
  mainConcerns?: string[];
  hasComplianceTeam?: string;
  maturity?: string;
  customerBase?: string;
  budget?: string;
  [key: string]: unknown; // For dynamic fields
}

// Answer type for question responses
type QuestionAnswer = string | string[] | boolean | undefined;

interface Question {
  id: string;
  type: QuestionType;
  question: string | ((data: UserFormData) => string);
  field?: string;
  validation?: string;
  inputType?: string;
  options?: string[] | ((data: UserFormData) => string[]);
  multiple?: boolean;
  confirmText?: string;
  skipIf?: (data: UserFormData) => boolean;
  nextQuestion?: (data: UserFormData, answer: QuestionAnswer) => string;
  icon?: React.ReactNode;
  priority?: 'high' | 'medium' | 'low';
}

// Question Bank - Smart, Dynamic Questions
const questionBank: Record<string, Question> = {
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
const getQuestionFlow = (): string[] => {
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

const getNextQuestion = (
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
      // If invalid ID or same as current, fall through to default flow
      if (nextId === currentId) {
        // Question trying to loop to itself
      } else {
        // Invalid question ID returned
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
    // Current question not found in flow
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

type Message = {
  id: number;
  type: 'bot' | 'user';
  content: string;
  options?: string[];
  isTyping?: boolean;
  icon?: React.ReactNode;
};

export default function AIGuidedSignupPage() {
  const router = useRouter();
  const { register: registerUser } = useAuthStore();
  const { addNotification } = useAppStore();

  const [currentQuestionId, setCurrentQuestionId] = React.useState('greeting');
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [userInput, setUserInput] = React.useState('');
  const [isTyping, setIsTyping] = React.useState(false);
  const [formData, setFormData] = React.useState<UserFormData>({});
  const [isLoading, setIsLoading] = React.useState(false);
  const [questionsAnswered, setQuestionsAnswered] = React.useState(0);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const messageIdCounter = React.useRef(Date.now());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages]);

  React.useEffect(() => {
    // Start with greeting
    const greetingQuestion = questionBank['greeting'];
    if (greetingQuestion) {
      messageIdCounter.current = 1;
      setMessages([
        {
          id: messageIdCounter.current,
          type: 'bot',
          content: greetingQuestion.question as string,
          options: greetingQuestion.options as string[],
          icon: greetingQuestion.icon,
        },
      ]);
    }
  }, []);

  const processQuestion = (question: Question, data: UserFormData): string => {
    if (typeof question.question === 'function') {
      return question.question(data);
    }
    return question.question;
  };

  const getOptions = (question: Question, data: UserFormData): string[] | undefined => {
    if (!question.options) return undefined;
    if (typeof question.options === 'function') {
      return question.options(data);
    }
    return question.options;
  };

  const addBotMessage = (content: string, options?: string[], icon?: React.ReactNode) => {
    messageIdCounter.current += 1;
    const newMessage: Message = {
      id: messageIdCounter.current,
      type: 'bot',
      content,
      ...(options && { options }),
      isTyping: true,
      ...(icon && { icon }),
    };

    setMessages((prev) => [...prev, newMessage]);
    setIsTyping(true);

    // Simulate typing delay
    setTimeout(
      () => {
        setMessages((prev) =>
          prev.map((msg) => (msg.id === newMessage.id ? { ...msg, isTyping: false } : msg)),
        );
        setIsTyping(false);
      },
      Math.min(content.length * 20, 1500),
    );
  };

  const addUserMessage = (content: string) => {
    messageIdCounter.current += 1;
    setMessages((prev) => [
      ...prev,
      {
        id: messageIdCounter.current,
        type: 'user',
        content,
      },
    ]);
  };

  const validateInput = (value: string, validation: string): boolean => {
    switch (validation) {
      case 'email':
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
      case 'password':
        return (
          value.length >= 8 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /[0-9]/.test(value)
        );
      case 'confirmPassword':
        return value === formData.password;
      case 'name':
      case 'companyName':
        return value.length >= 2;
      default:
        return true;
    }
  };

  const getValidationError = (validation: string): string => {
    switch (validation) {
      case 'email':
        return 'Please enter a valid email address';
      case 'password':
        return 'Password must be at least 8 characters with uppercase, lowercase, and numbers';
      case 'confirmPassword':
        return "Passwords don't match";
      case 'name':
      case 'companyName':
        return 'Please enter at least 2 characters';
      default:
        return 'Invalid input';
    }
  };

  const handleNext = async (answer?: QuestionAnswer) => {
    const currentQuestion = questionBank[currentQuestionId];
    if (!currentQuestion) return;

    const actualAnswer = answer || userInput;

    if (currentQuestion.type === 'input' && !answer) {
      if (!validateInput(userInput, currentQuestion.validation || '')) {
        addBotMessage(getValidationError(currentQuestion.validation || ''));
        return;
      }

      addUserMessage(userInput);
      setFormData({ ...formData, [currentQuestion.field!]: userInput });
      setUserInput('');
    } else if (currentQuestion.field && answer) {
      setFormData({ ...formData, [currentQuestion.field]: answer });
    }

    setQuestionsAnswered((prev) => prev + 1);

    // Get next question
    const nextQuestionId = getNextQuestion(currentQuestionId, formData, actualAnswer);

    if (nextQuestionId) {
      const nextQuestion = questionBank[nextQuestionId];
      if (!nextQuestion) return;

      setCurrentQuestionId(nextQuestionId);

      setTimeout(() => {
        addBotMessage(
          processQuestion(nextQuestion, { ...formData, [currentQuestion.field!]: actualAnswer }),
          getOptions(nextQuestion, { ...formData, [currentQuestion.field!]: actualAnswer }),
          nextQuestion.icon,
        );
      }, 500);
    } else {
      // Complete signup
      await completeSignup();
    }
  };

  const handleChoice = (choice: string) => {
    const currentQuestion = questionBank[currentQuestionId];

    addUserMessage(choice);

    // Handle email already exists choices
    if (choice === 'Take me to login') {
      addBotMessage("I'll redirect you to the login page now.");
      setTimeout(() => {
        router.push('/login');
      }, 1000);
      return;
    } else if (choice === 'Try different email') {
      addBotMessage("Let's try with a different email address. What's your email?");
      setCurrentQuestionId('email');
      setFormData({ ...formData, email: '' });
      return;
    }

    if (!currentQuestion) return;

    if (currentQuestion.type === 'choice') {
      handleNext(choice);
    } else if (currentQuestion.type === 'multi-choice') {
      const current = Array.isArray(formData[currentQuestion.field!])
        ? formData[currentQuestion.field!]
        : [];
      setFormData({
        ...formData,
        [currentQuestion.field!]: [...(current as string[]), choice],
      });
    } else if (currentQuestion.type === 'greeting') {
      if (choice === 'Tell me more') {
        addBotMessage(
          "ruleIQ uses AI to understand your unique compliance needs and creates a personalized roadmap. I'll ask about your business, data handling, and compliance goals to prioritize what matters most for you. This ensures you focus on the right frameworks and avoid wasting time on irrelevant requirements. Ready to start?",
          ["Let's start!"],
        );
        return;
      }
      handleNext();
    }
  };

  // Helper function to parse full name into first and last name
  const parseFullName = (fullName: string): { firstName: string; lastName: string } => {
    if (!fullName || typeof fullName !== 'string') {
      return { firstName: '', lastName: '' };
    }

    const trimmed = fullName.trim();
    const parts = trimmed.split(/\s+/); // Split by any whitespace

    if (parts.length === 0) {
      return { firstName: '', lastName: '' };
    } else if (parts.length === 1) {
      // Single name - use as first name
      return { firstName: parts[0] || '', lastName: '' };
    } else if (parts.length === 2) {
      // Standard first and last name
      return { firstName: parts[0] || '', lastName: parts[1] || '' };
    } else {
      // Multiple parts - assume first part is first name, rest is last name
      return {
        firstName: parts[0] || '',
        lastName: parts.slice(1).join(' '),
      };
    }
  };

  const completeSignup = async () => {
    setIsLoading(true);

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      addBotMessage("Passwords don't match. Please go back and re-enter your password.");
      setIsLoading(false);
      return;
    }

    // Generate compliance profile based on answers
    const complianceProfile = generateComplianceProfile(formData);

    addBotMessage(
      `Creating your personalized dashboard with focus on: ${complianceProfile.priorities.join(', ')}...`,
    );

    try {
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Parse the full name
      const { firstName, lastName } = parseFullName(formData.fullName || '');

      // Register user with auth store (only email, password, fullName supported)
      const fullName = `${firstName} ${lastName}`.trim() || 'User';
      await registerUser(formData.email || '', formData.password || '', fullName);

      // Store compliance profile in local storage for dashboard to use (with error handling)
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          localStorage.setItem('ruleiq_compliance_profile', JSON.stringify(complianceProfile));
          localStorage.setItem('ruleiq_onboarding_data', JSON.stringify(formData));
        }
      } catch (_error) {
        // Unable to save to localStorage
        // Continue anyway - the app will work without personalization
      }

      addNotification({
        type: 'success',
        title: 'Welcome to ruleIQ!',
        message: `Your compliance journey starts now. We've prioritized ${complianceProfile.priorities[0] || 'compliance'} based on your needs.`,
        duration: 5000,
      });

      router.push('/dashboard');
    } catch (error: unknown) {
      // Registration error occurred

      let errorMessage = 'There was an error creating your account. Please try again.';

      if (error && typeof error === 'object') {
        if ('detail' in error && typeof error.detail === 'string') {
          errorMessage = error.detail;
        } else if ('message' in error && typeof error.message === 'string') {
          errorMessage = error.message;
        }
      } else if (typeof error === 'string') {
        errorMessage = error;
      }

      // Handle specific email already exists case
      if (
        errorMessage.toLowerCase().includes('email') &&
        (errorMessage.toLowerCase().includes('already') ||
          errorMessage.toLowerCase().includes('exists') ||
          errorMessage.toLowerCase().includes('taken'))
      ) {
        addBotMessage(
          `It looks like ${formData.email} is already registered. Would you like to try logging in instead?`,
          ['Take me to login', 'Try different email'],
        );
      } else {
        addBotMessage(errorMessage);
      }

      setIsLoading(false);
    }
  };

  const generateComplianceProfile = (data: UserFormData) => {
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

  const getTimeEstimate = (data: UserFormData): string => {
    if (data.currentFrameworks?.includes('None yet')) {
      return '3-6 months';
    }
    if (data.hasComplianceTeam === 'Yes, full team') {
      return '1-3 months';
    }
    return '2-4 months';
  };

  const getSuggestedFrameworks = (data: UserFormData): string[] => {
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

  // Dynamic calculation of total questions based on current flow
  const calculateTotalQuestions = (): number => {
    const baseFlow = getQuestionFlow();
    let total = baseFlow.length;

    // Add dynamic questions based on current data
    if (formData.industry === 'Healthcare') total += 1;
    if (formData.industry === 'Financial Services') total += 1;
    if (formData.industry === 'E-commerce/Retail') total += 1;
    if (formData.companySize === 'Just me' || formData.companySize === '2-10') total += 1;
    if (
      formData.companySize &&
      formData.companySize !== 'Just me' &&
      formData.companySize !== '2-10'
    )
      total += 2;
    if (formData.regions?.includes('EU') || formData.regions?.includes('UK')) total += 1;
    if (formData.regions?.includes('USA')) total += 1;
    if (formData.dataTypes?.includes('Payment/financial')) total += 1;
    if (formData.dataTypes?.includes('Health records')) total += 1;

    return Math.max(total, questionsAnswered + 1); // Ensure progress never exceeds 100%
  };

  const totalQuestions = calculateTotalQuestions();
  const progress = Math.min((questionsAnswered / totalQuestions) * 100, 100);
  const currentQuestion = questionBank[currentQuestionId];

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base p-4">
      <div className="mesh-gradient absolute inset-0 opacity-20"></div>
      <Card className="glass-card relative w-full max-w-3xl border-0 bg-surface-primary/80 shadow-2xl backdrop-blur-xl">
        <CardHeader className="space-y-4 pb-6 text-center">
          <div className="flex items-center justify-center gap-2">
            <Shield className="h-8 w-8 text-primary" />
            <span className="text-3xl font-bold">
              <span className="gradient-text">ruleIQ</span>
            </span>
          </div>

          <div>
            <CardTitle className="gradient-text text-2xl font-bold">
              Smart Compliance Setup
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              AI-powered onboarding tailored to your business
            </CardDescription>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="text-muted-foreground">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-2 bg-surface-secondary" />
            <p className="text-xs text-muted-foreground">
              Estimated time: {Math.max(1, 5 - Math.floor(questionsAnswered / 3))} minutes remaining
            </p>
          </div>

          {/* Dynamic badges based on progress */}
          <div className="flex flex-wrap justify-center gap-2">
            {formData.industry && (
              <Badge
                variant="secondary"
                className="border-glass-border bg-surface-secondary/50 text-foreground"
              >
                {formData.industry}
              </Badge>
            )}
            {formData.companySize && (
              <Badge
                variant="secondary"
                className="border-glass-border bg-surface-secondary/50 text-foreground"
              >
                {formData.companySize} employees
              </Badge>
            )}
            {formData.topPriority && (
              <Badge className="border-primary/50 bg-primary/20 text-primary-foreground">
                {formData.topPriority}
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Chat Messages */}
          <div className="border-glass-border h-[400px] space-y-4 overflow-y-auto rounded-lg border bg-surface-secondary/30 p-4">
            <AnimatePresence>
              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className={cn('flex gap-3', message.type === 'user' && 'justify-end')}
                >
                  {message.type === 'bot' && (
                    <div className="flex-shrink-0">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20">
                        {message.icon || <Bot className="h-5 w-5 text-primary" />}
                      </div>
                    </div>
                  )}

                  <div
                    className={cn(
                      'max-w-[80%] rounded-lg p-3',
                      message.type === 'bot'
                        ? 'glass-card'
                        : 'bg-gradient-to-r from-primary to-primary text-primary-foreground',
                    )}
                  >
                    {message.isTyping ? (
                      <div className="flex gap-1">
                        <span className="animate-bounce">•</span>
                        <span className="animate-bounce delay-100">•</span>
                        <span className="animate-bounce delay-200">•</span>
                      </div>
                    ) : (
                      <>
                        <p className="whitespace-pre-line text-sm">{message.content}</p>

                        {message.options && message.type === 'bot' && currentQuestion && (
                          <div className="mt-3 space-y-2">
                            {currentQuestion.type === 'multi-choice' ? (
                              <div className="space-y-2">
                                {message.options.map((option, optionIndex) => (
                                  <label
                                    key={`msg-${message.id}-option-${optionIndex}`}
                                    className="flex cursor-pointer items-center space-x-2"
                                  >
                                    <Checkbox
                                      checked={
                                        Array.isArray(formData[currentQuestion.field!])
                                          ? (formData[currentQuestion.field!] as string[]).includes(
                                              option,
                                            )
                                          : false
                                      }
                                      onCheckedChange={(checked) => {
                                        if (checked) {
                                          handleChoice(option);
                                        } else {
                                          const current = Array.isArray(
                                            formData[currentQuestion.field!],
                                          )
                                            ? (formData[currentQuestion.field!] as string[])
                                            : [];
                                          setFormData({
                                            ...formData,
                                            [currentQuestion.field!]: current.filter(
                                              (item: string) => item !== option,
                                            ),
                                          });
                                        }
                                      }}
                                      className="border-glass-border data-[state=checked]:border-primary data-[state=checked]:bg-primary"
                                    />
                                    <span className="text-sm">{option}</span>
                                  </label>
                                ))}
                                <div className="mt-3 flex gap-2">
                                  {Array.isArray(formData[currentQuestion.field!]) &&
                                  (formData[currentQuestion.field!] as string[]).length > 0 ? (
                                    <Button
                                      size="sm"
                                      onClick={() =>
                                        handleNext(
                                          formData[currentQuestion.field!] as QuestionAnswer,
                                        )
                                      }
                                      className="btn-gradient flex-1"
                                    >
                                      Continue (
                                      {Array.isArray(formData[currentQuestion.field!])
                                        ? (formData[currentQuestion.field!] as string[]).length
                                        : 0}{' '}
                                      selected)
                                      <ChevronRight className="ml-1 h-3 w-3" />
                                    </Button>
                                  ) : (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => handleNext([])}
                                      className="border-glass-border hover:border-glass-border-hover flex-1 bg-surface-secondary/50 hover:bg-surface-secondary/70"
                                    >
                                      Skip this question
                                      <ChevronRight className="ml-1 h-3 w-3" />
                                    </Button>
                                  )}
                                </div>
                              </div>
                            ) : currentQuestion.type === 'confirm' ? (
                              <div className="space-y-3">
                                <label className="flex items-start space-x-2">
                                  <Checkbox
                                    checked={formData.agreeToTerms || false}
                                    onCheckedChange={(checked) =>
                                      setFormData({ ...formData, agreeToTerms: checked === true })
                                    }
                                    className="border-glass-border data-[state=checked]:border-primary data-[state=checked]:bg-primary"
                                  />
                                  <span className="text-sm text-muted-foreground">
                                    {currentQuestion.confirmText}
                                  </span>
                                </label>
                                <Button
                                  size="sm"
                                  onClick={completeSignup}
                                  disabled={!formData.agreeToTerms || isLoading}
                                  className="btn-gradient w-full"
                                >
                                  {isLoading ? (
                                    <>
                                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                      Creating your compliance roadmap...
                                    </>
                                  ) : (
                                    <>
                                      Start My Compliance Journey
                                      <Check className="ml-2 h-4 w-4" />
                                    </>
                                  )}
                                </Button>
                              </div>
                            ) : (
                              message.options.map((option, optionIndex) => (
                                <Button
                                  key={`msg-${message.id}-button-option-${optionIndex}`}
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleChoice(option)}
                                  className="border-glass-border hover:border-glass-border-hover block w-full bg-surface-secondary/50 text-left transition-colors hover:bg-surface-secondary/70 hover:text-primary"
                                  disabled={isTyping}
                                >
                                  {option}
                                </Button>
                              ))
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          {currentQuestion && currentQuestion.type === 'input' && !isTyping && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleNext();
              }}
              className="flex gap-2"
            >
              <Input
                type={currentQuestion.inputType || 'text'}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="Type your answer..."
                className="border-glass-border flex-1 bg-surface-secondary/50 focus:border-primary"
                disabled={isLoading}
              />
              <Button
                type="submit"
                disabled={!userInput.trim() || isLoading}
                className="btn-gradient"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          )}

          {/* Alternative signup option */}
          <div className="border-glass-border border-t pt-4 text-center">
            <Link
              href="/signup-traditional"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-primary"
            >
              <ArrowLeft className="h-3 w-3" />
              Prefer traditional signup?
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
