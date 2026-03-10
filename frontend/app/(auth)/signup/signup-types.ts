import type React from 'react';

// Dynamic Question System
export type QuestionType = 'greeting' | 'input' | 'choice' | 'multi-choice' | 'confirm' | 'dynamic';

// User data interface for form responses
export interface UserFormData {
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
export type QuestionAnswer = string | string[] | boolean | undefined;

export interface Question {
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

export type Message = {
  id: number;
  type: 'bot' | 'user';
  content: string;
  options?: string[];
  isTyping?: boolean;
  icon?: React.ReactNode;
};
