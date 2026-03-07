'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Loader2, ThumbsUp, ThumbsDown, Copy, ExternalLink, X, Lightbulb } from 'lucide-react';
import { useState, useEffect } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';
import { assessmentAIService, type AIHelpResponse } from '@/lib/api/assessments-ai.service';
import { type Question } from '@/lib/assessment-engine/types';
import { cn } from '@/lib/utils';
import { type UserContext } from '@/types/ai';

interface AIHelpTooltipProps {
  question: Question;
  frameworkId: string;
  sectionId?: string;
  userContext?: UserContext;
  className?: string;
}

export function AIHelpTooltip({
  question,
  frameworkId,
  sectionId,
  userContext,
  className,
}: AIHelpTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<AIHelpResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const { toast } = useToast();

  // Suppress TypeScript unused variable warning
  void requestId;

  const handleGetHelp = async () => {
    if (aiResponse && !loading) {
      setIsOpen(!isOpen);
      return;
    }

    // Prevent multiple concurrent requests
    const currentRequestId = Date.now().toString();
    setRequestId(currentRequestId);
    setLoading(true);
    setError(null);
    setIsOpen(true);

    try {
      const helpRequest = {
        question_id: question.id,
        question_text: question.text,
        framework_id: frameworkId,
        ...(sectionId && { section_id: sectionId }),
        ...(userContext && { user_context: userContext }),
      };

      const response = await assessmentAIService.getQuestionHelp(helpRequest);

      // Check if this request is still valid
      setRequestId((latestRequestId) => {
        if (currentRequestId === latestRequestId) {
          setAiResponse(response);
          setLoading(false);
        }
        return latestRequestId;
      });
    } catch (err) {
      setRequestId((latestRequestId) => {
        if (currentRequestId === latestRequestId) {
          setError(err instanceof Error ? err.message : 'Failed to get AI help');
          setLoading(false);
        }
        return latestRequestId;
      });
    }
  };

  const handleCopyResponse = () => {
    if (aiResponse?.guidance) {
      navigator.clipboard.writeText(aiResponse.guidance);
      toast({
        title: 'Copied to clipboard',
        description: 'AI guidance has been copied to your clipboard.',
        duration: 2000,
      });
    }
  };

  const handleFeedback = async (helpful: boolean) => {
    try {
      await assessmentAIService.submitFeedback(`${question.id}_${Date.now()}`, {
        helpful,
        rating: helpful ? 5 : 2,
      });

      toast({
        title: 'Feedback submitted',
        description: 'Thank you for helping us improve AI assistance.',
        duration: 2000,
      });
    } catch (_err) {
      // intentionally empty - non-blocking feedback submission
    }
  };

  // Add keyboard shortcut listener with proper cleanup
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'h') {
        event.preventDefault();
        handleGetHelp();
      }
    };

    document.addEventListener('keydown', handleKeyPress);
    return () => document.removeEventListener('keydown', handleKeyPress);
  }, []);

  return (
    <TooltipProvider>
      <div className={cn('relative', className)}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={handleGetHelp}
              disabled={loading}
              className={cn(
                'gap-2 border-primary/20 text-primary hover:bg-primary/5',
                loading && 'cursor-wait',
              )}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              <span className="hidden sm:inline">AI Help</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Get AI assistance (Ctrl+H)</p>
          </TooltipContent>
        </Tooltip>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="absolute left-0 top-12 z-50 w-80 sm:w-96"
            >
              <Card className="border-2 border-primary/10 shadow-lg">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-sm font-medium">
                      <Bot className="h-4 w-4 text-primary" />
                      AI Compliance Assistant
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsOpen(false)}
                      className="h-6 w-6 p-0"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {loading && (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-center">
                        <Loader2 className="mx-auto mb-2 h-8 w-8 animate-spin text-primary" />
                        <p className="text-sm text-muted-foreground">
                          Analyzing question and generating guidance...
                        </p>
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="py-4 text-center">
                      <p className="mb-2 text-sm text-destructive">{error}</p>
                      <Button variant="outline" size="sm" onClick={handleGetHelp}>
                        Try Again
                      </Button>
                    </div>
                  )}

                  {aiResponse && (
                    <div className="space-y-4">
                      {/* Confidence Score */}
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={aiResponse.confidence_score > 0.8 ? 'success' : 'secondary'}
                          className="text-xs"
                        >
                          {Math.round(aiResponse.confidence_score * 100)}% Confidence
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleCopyResponse}
                          className="h-6 w-6 p-0"
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>

                      {/* AI Guidance */}
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-sm leading-relaxed">{aiResponse.guidance}</p>
                      </div>

                      {/* Related Topics */}
                      {aiResponse.related_topics && aiResponse.related_topics.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
                            Related Topics
                          </h4>
                          <div className="flex flex-wrap gap-1">
                            {aiResponse.related_topics.map((topic, index) => (
                              <Badge
                                key={`tooltip-topic-${index}-${topic.substring(0, 15)}`}
                                variant="outline"
                                className="text-xs"
                              >
                                {topic}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Follow-up Suggestions */}
                      {aiResponse.follow_up_suggestions &&
                        aiResponse.follow_up_suggestions.length > 0 && (
                          <div>
                            <h4 className="mb-2 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                              <Lightbulb className="h-3 w-3" />
                              Suggestions
                            </h4>
                            <ul className="space-y-1">
                              {aiResponse.follow_up_suggestions.map((suggestion, index) => (
                                <li
                                  key={`tooltip-suggestion-${index}-${suggestion.substring(0, 20)}`}
                                  className="flex items-start gap-2 text-xs text-muted-foreground"
                                >
                                  <span className="text-primary">•</span>
                                  <span>{suggestion}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                      {/* Source References */}
                      {aiResponse.source_references && aiResponse.source_references.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
                            References
                          </h4>
                          <div className="space-y-1">
                            {aiResponse.source_references.map((ref, index) => (
                              <div
                                key={`tooltip-ref-${index}-${ref.substring(0, 20)}`}
                                className="flex items-center gap-2"
                              >
                                <ExternalLink className="h-3 w-3 text-muted-foreground" />
                                <span className="text-xs text-muted-foreground">{ref}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <Separator />

                      {/* Feedback */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Was this helpful?</span>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleFeedback(true)}
                            className="h-6 w-6 p-0 hover:text-green-600"
                          >
                            <ThumbsUp className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleFeedback(false)}
                            className="h-6 w-6 p-0 hover:text-red-600"
                          >
                            <ThumbsDown className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </TooltipProvider>
  );
}
