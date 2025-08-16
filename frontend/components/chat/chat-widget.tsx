'use client';

import { Bot, MessageSquare, Mic, MicOff, Phone, PhoneOff, Send, X, Minimize2, Maximize2, Volume2, VolumeX } from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { ChatMessage } from './chat-message';
import { TypingIndicator } from './typing-indicator';
import { useChatStore } from '@/lib/stores/chat.store';
import { useVoiceStore } from '@/lib/stores/voice.store';
import type { VoiceState, VoiceCapabilities } from '@/types/voice';

interface ChatWidgetProps {
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
  defaultOpen?: boolean;
  enableVoice?: boolean;
  voiceConfig?: {
    autoStart?: boolean;
    language?: string;
    voiceType?: 'male' | 'female' | 'neutral';
    speechRate?: number;
  };
}

export function ChatWidget({ 
  position = 'bottom-right',
  defaultOpen = false,
  enableVoice = true,
  voiceConfig = {
    autoStart: false,
    language: 'en-US',
    voiceType: 'neutral',
    speechRate: 1.0
  }
}: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [isMinimized, setIsMinimized] = useState(false);
  const [message, setMessage] = useState('');
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isVoiceCall, setIsVoiceCall] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Chat store
  const {
    widgetConversationId,
    messages,
    isConnected,
    typingUsers,
    sendMessage,
    createWidgetConversation,
    loadWidgetConversation,
  } = useChatStore();

  // Voice store (placeholder for future implementation)
  const {
    isSupported: isVoiceSupported,
    isListening,
    isProcessing,
    isSpeaking,
    transcript,
    startListening,
    stopListening,
    startVoiceCall,
    endVoiceCall,
    toggleMute,
    speakResponse,
    voiceCapabilities,
  } = useVoiceStore();

  const widgetMessages = widgetConversationId ? messages[widgetConversationId] || [] : [];

  // Initialize widget conversation on mount
  useEffect(() => {
    if (!widgetConversationId) {
      createWidgetConversation();
    } else {
      loadWidgetConversation();
    }
  }, [widgetConversationId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [widgetMessages]);

  // Voice transcript integration
  useEffect(() => {
    if (transcript && isVoiceActive) {
      setMessage(transcript);
    }
  }, [transcript, isVoiceActive]);

  // Handle send message
  const handleSendMessage = async () => {
    if (message.trim() && isConnected) {
      await sendMessage(message, { source: 'widget', voiceInput: isVoiceActive });
      setMessage('');
      setIsVoiceActive(false);
    }
  };

  // Voice control handlers
  const handleVoiceToggle = useCallback(() => {
    if (!isVoiceSupported) {
      console.log('Voice not supported in this browser');
      return;
    }

    if (isListening) {
      stopListening();
      setIsVoiceActive(false);
    } else {
      startListening(voiceConfig);
      setIsVoiceActive(true);
    }
  }, [isListening, isVoiceSupported, voiceConfig, startListening, stopListening]);

  const handleVoiceCall = useCallback(() => {
    if (!voiceCapabilities?.calling) {
      console.log('Voice calling not yet available');
      return;
    }

    if (isVoiceCall) {
      endVoiceCall();
      setIsVoiceCall(false);
    } else {
      startVoiceCall({
        conversationId: widgetConversationId || undefined,
        ...voiceConfig
      });
      setIsVoiceCall(true);
    }
  }, [isVoiceCall, widgetConversationId, voiceCapabilities, voiceConfig, startVoiceCall, endVoiceCall]);

  const handleMuteToggle = useCallback(() => {
    toggleMute();
    setIsMuted(!isMuted);
  }, [isMuted, toggleMute]);

  // Position classes
  const positionClasses = {
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'top-right': 'top-20 right-4',
    'top-left': 'top-20 left-4'
  };

  return (
    <>
      {/* Floating Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            className={cn('fixed z-50', positionClasses[position])}
          >
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    onClick={() => setIsOpen(true)}
                    size="lg"
                    className="h-14 w-14 rounded-full bg-gold text-navy shadow-lg hover:bg-gold-dark hover:scale-110 transition-all"
                  >
                    <Bot className="h-6 w-6" />
                    {typingUsers.length > 0 && (
                      <span className="absolute -top-1 -right-1 h-3 w-3 bg-green-500 rounded-full animate-pulse" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Chat with IQ Assistant</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat Widget */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ scale: 0.8, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.8, opacity: 0, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className={cn(
              'fixed z-50',
              positionClasses[position],
              isMinimized ? 'w-80' : 'w-96',
              'max-w-[calc(100vw-2rem)]'
            )}
          >
            <Card className="flex flex-col shadow-2xl border-2 border-navy/10 overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between p-3 bg-gradient-to-r from-navy to-navy-dark text-white">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5" />
                  <span className="font-semibold">IQ Assistant</span>
                  {isConnected ? (
                    <Badge variant="secondary" className="bg-green-500/20 text-green-300 text-xs">
                      Online
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="bg-red-500/20 text-red-300 text-xs">
                      Offline
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {/* Voice Call Button (Future) */}
                  {enableVoice && voiceCapabilities?.calling && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-white hover:bg-white/20"
                            onClick={handleVoiceCall}
                          >
                            {isVoiceCall ? (
                              <PhoneOff className="h-4 w-4" />
                            ) : (
                              <Phone className="h-4 w-4" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {isVoiceCall ? 'End voice call' : 'Start voice call'}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}

                  {/* Mute Button (Future) */}
                  {enableVoice && isVoiceCall && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-white hover:bg-white/20"
                            onClick={handleMuteToggle}
                          >
                            {isMuted ? (
                              <VolumeX className="h-4 w-4" />
                            ) : (
                              <Volume2 className="h-4 w-4" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {isMuted ? 'Unmute' : 'Mute'}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}

                  {/* Minimize Button */}
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 w-8 p-0 text-white hover:bg-white/20"
                          onClick={() => setIsMinimized(!isMinimized)}
                        >
                          {isMinimized ? (
                            <Maximize2 className="h-4 w-4" />
                          ) : (
                            <Minimize2 className="h-4 w-4" />
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {isMinimized ? 'Expand' : 'Minimize'}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  {/* Close Button */}
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 w-8 p-0 text-white hover:bg-white/20"
                          onClick={() => setIsOpen(false)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Close chat</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>

              {/* Voice Status Bar (Future) */}
              {isVoiceCall && (
                <div className="flex items-center justify-between px-3 py-2 bg-gold/10 border-b">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-xs text-muted-foreground">Voice call active</span>
                  </div>
                  <span className="text-xs text-muted-foreground">00:00</span>
                </div>
              )}

              {/* Messages */}
              {!isMinimized && (
                <div className="flex-1 h-96 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-background to-muted/20">
                  {widgetMessages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                      <MessageSquare className="h-10 w-10 text-muted-foreground mb-3" />
                      <p className="text-sm text-muted-foreground">
                        Hi! I&apos;m your AI compliance assistant.
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Ask me anything about compliance, policies, or regulations.
                      </p>
                      {enableVoice && isVoiceSupported && (
                        <p className="text-xs text-muted-foreground mt-2">
                          🎤 Voice input available - click the mic to speak
                        </p>
                      )}
                    </div>
                  ) : (
                    <>
                      {widgetMessages.map((msg) => (
                        <ChatMessage key={msg.id} message={msg} />
                      ))}
                      {typingUsers.length > 0 && <TypingIndicator />}
                    </>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}

              {/* Input Area */}
              {!isMinimized && (
                <div className="border-t p-3 bg-background">
                  <div className="flex items-end gap-2">
                    <div className="flex-1 relative">
                      <textarea
                        ref={inputRef}
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage();
                          }
                        }}
                        placeholder={isListening ? "Listening..." : "Type your message..."}
                        className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm min-h-[40px] max-h-[120px] focus:outline-none focus:ring-2 focus:ring-gold"
                        disabled={!isConnected || isProcessing}
                      />
                      {isListening && (
                        <div className="absolute top-2 right-2">
                          <div className="flex gap-1">
                            <span className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
                            <span className="h-2 w-2 bg-red-500 rounded-full animate-pulse delay-75" />
                            <span className="h-2 w-2 bg-red-500 rounded-full animate-pulse delay-150" />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Voice Input Button */}
                    {enableVoice && isVoiceSupported && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="sm"
                              variant={isListening ? "default" : "outline"}
                              className={cn(
                                "h-10 w-10 p-0",
                                isListening && "bg-red-500 hover:bg-red-600"
                              )}
                              onClick={handleVoiceToggle}
                              disabled={!isConnected || isProcessing}
                            >
                              {isListening ? (
                                <MicOff className="h-4 w-4" />
                              ) : (
                                <Mic className="h-4 w-4" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            {isListening ? 'Stop recording' : 'Start voice input'}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}

                    {/* Send Button */}
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            className="h-10 w-10 p-0 bg-gold hover:bg-gold-dark text-navy"
                            onClick={handleSendMessage}
                            disabled={!message.trim() || !isConnected || isProcessing}
                          >
                            <Send className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Send message</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>

                  {/* Voice Processing Indicator */}
                  {isProcessing && (
                    <div className="mt-2 text-xs text-muted-foreground text-center">
                      Processing voice input...
                    </div>
                  )}

                  {/* Voice Speaking Indicator */}
                  {isSpeaking && (
                    <div className="mt-2 text-xs text-muted-foreground text-center flex items-center justify-center gap-2">
                      <Volume2 className="h-3 w-3 animate-pulse" />
                      Speaking response...
                    </div>
                  )}
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}