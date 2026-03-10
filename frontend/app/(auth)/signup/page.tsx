'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Send, Loader2, Check, ChevronRight, Shield, ArrowLeft } from 'lucide-react';
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

import { generateComplianceProfile } from './compliance-profile';
import { questionBank, getNextQuestion } from './question-bank';
import type { UserFormData, QuestionAnswer, Message } from './signup-types';
import {
  processQuestion,
  getOptions,
  validateInput,
  getValidationError,
  parseFullName,
  calculateTotalQuestions,
} from './signup-utils';

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

  const handleNext = async (answer?: QuestionAnswer) => {
    const currentQuestion = questionBank[currentQuestionId];
    if (!currentQuestion) return;

    const actualAnswer = answer || userInput;

    if (currentQuestion.type === 'input' && !answer) {
      if (!validateInput(userInput, currentQuestion.validation || '', formData.password)) {
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

  const totalQuestions = calculateTotalQuestions(formData, questionsAnswered);
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
