import type { UserFormData, Question, QuestionAnswer } from './signup-types';
import { getQuestionFlow } from './question-bank';

export const processQuestion = (question: Question, data: UserFormData): string => {
  if (typeof question.question === 'function') {
    return question.question(data);
  }
  return question.question;
};

export const getOptions = (question: Question, data: UserFormData): string[] | undefined => {
  if (!question.options) return undefined;
  if (typeof question.options === 'function') {
    return question.options(data);
  }
  return question.options;
};

export const validateInput = (
  value: string,
  validation: string,
  password?: string,
): boolean => {
  switch (validation) {
    case 'email':
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    case 'password':
      return (
        value.length >= 8 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /[0-9]/.test(value)
      );
    case 'confirmPassword':
      return value === password;
    case 'name':
    case 'companyName':
      return value.length >= 2;
    default:
      return true;
  }
};

export const getValidationError = (validation: string): string => {
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

export const parseFullName = (fullName: string): { firstName: string; lastName: string } => {
  if (!fullName || typeof fullName !== 'string') {
    return { firstName: '', lastName: '' };
  }

  const trimmed = fullName.trim();
  const parts = trimmed.split(/\s+/);

  if (parts.length === 0) {
    return { firstName: '', lastName: '' };
  } else if (parts.length === 1) {
    return { firstName: parts[0] || '', lastName: '' };
  } else if (parts.length === 2) {
    return { firstName: parts[0] || '', lastName: parts[1] || '' };
  } else {
    return {
      firstName: parts[0] || '',
      lastName: parts.slice(1).join(' '),
    };
  }
};

export const calculateTotalQuestions = (
  formData: UserFormData,
  questionsAnswered: number,
): number => {
  const baseFlow = getQuestionFlow();
  let total = baseFlow.length;

  if (formData.industry === 'Healthcare') total += 1;
  if (formData.industry === 'Financial Services') total += 1;
  if (formData.industry === 'E-commerce/Retail') total += 1;
  if (formData.companySize === 'Just me' || formData.companySize === '2-10') total += 1;
  if (formData.companySize && formData.companySize !== 'Just me' && formData.companySize !== '2-10')
    total += 2;
  if (formData.regions?.includes('EU') || formData.regions?.includes('UK')) total += 1;
  if (formData.regions?.includes('USA')) total += 1;
  if (formData.dataTypes?.includes('Payment/financial')) total += 1;
  if (formData.dataTypes?.includes('Health records')) total += 1;

  return Math.max(total, questionsAnswered + 1);
};
