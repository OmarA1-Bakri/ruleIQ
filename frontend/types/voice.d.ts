/**
 * Voice Interface Types for Future Voice Integration
 * 
 * This file defines the types and interfaces for voice functionality
 * that will be implemented in future versions of the application.
 * The structure is designed to support:
 * - Speech-to-text (STT)
 * - Text-to-speech (TTS)
 * - Voice calling
 * - Real-time transcription
 * - Multi-language support
 */

export interface VoiceState {
  // Core state
  isSupported: boolean;
  isEnabled: boolean;
  isListening: boolean;
  isProcessing: boolean;
  isSpeaking: boolean;
  
  // Call state
  isInCall: boolean;
  callDuration: number;
  callParticipants: VoiceParticipant[];
  
  // Audio state
  volume: number;
  isMuted: boolean;
  noiseSuppressionEnabled: boolean;
  echoCancellationEnabled: boolean;
  
  // Recognition state
  transcript: string;
  interimTranscript: string;
  confidence: number;
  language: string;
  
  // Error state
  error: VoiceError | null;
  lastErrorTime: Date | null;
}

export interface VoiceCapabilities {
  // Browser capabilities
  speechRecognition: boolean;
  speechSynthesis: boolean;
  mediaDevices: boolean;
  webRTC: boolean;
  
  // Feature capabilities
  continuousRecognition: boolean;
  interimResults: boolean;
  multiLanguage: boolean;
  calling: boolean;
  voiceCommands: boolean;
  wakeWord: boolean;
  
  // Audio processing
  noiseSuppression: boolean;
  echoCancellation: boolean;
  automaticGainControl: boolean;
}

export interface VoiceConfig {
  // Recognition settings
  language: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  confidenceThreshold: number;
  
  // Synthesis settings
  voiceType: 'male' | 'female' | 'neutral';
  speechRate: number;
  pitch: number;
  volume: number;
  
  // Audio processing
  noiseSuppression: boolean;
  echoCancellation: boolean;
  automaticGainControl: boolean;
  
  // Advanced features
  wakeWord?: string;
  voiceCommands?: VoiceCommand[];
  autoStart?: boolean;
  autoPunctuation?: boolean;
}

export interface VoiceCommand {
  trigger: string | RegExp;
  action: string;
  description?: string;
  parameters?: Record<string, any>;
  requiresConfirmation?: boolean;
}

export interface VoiceParticipant {
  id: string;
  name: string;
  isMuted: boolean;
  isSpeaking: boolean;
  volume: number;
  connectionQuality: 'excellent' | 'good' | 'fair' | 'poor';
}

export interface VoiceCallConfig {
  conversationId?: string;
  participantIds?: string[];
  enableVideo?: boolean;
  audioConstraints?: MediaTrackConstraints;
  videoConstraints?: MediaTrackConstraints;
}

export interface VoiceTranscript {
  id: string;
  text: string;
  timestamp: Date;
  speaker?: string;
  confidence: number;
  language: string;
  alternatives?: string[];
  isFinal: boolean;
}

export interface VoiceError {
  code: VoiceErrorCode;
  message: string;
  details?: any;
  recoverable: boolean;
}

export enum VoiceErrorCode {
  // Permission errors
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  MICROPHONE_NOT_FOUND = 'MICROPHONE_NOT_FOUND',
  
  // Recognition errors
  RECOGNITION_FAILED = 'RECOGNITION_FAILED',
  LANGUAGE_NOT_SUPPORTED = 'LANGUAGE_NOT_SUPPORTED',
  NO_SPEECH_DETECTED = 'NO_SPEECH_DETECTED',
  
  // Synthesis errors
  SYNTHESIS_FAILED = 'SYNTHESIS_FAILED',
  VOICE_NOT_AVAILABLE = 'VOICE_NOT_AVAILABLE',
  
  // Connection errors
  NETWORK_ERROR = 'NETWORK_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  TIMEOUT = 'TIMEOUT',
  
  // Call errors
  CALL_FAILED = 'CALL_FAILED',
  PEER_CONNECTION_FAILED = 'PEER_CONNECTION_FAILED',
  
  // General errors
  NOT_SUPPORTED = 'NOT_SUPPORTED',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

export interface VoiceAnalytics {
  // Usage metrics
  totalTranscriptions: number;
  totalSynthesisRequests: number;
  totalCallMinutes: number;
  
  // Quality metrics
  averageConfidence: number;
  recognitionAccuracy: number;
  
  // Performance metrics
  averageLatency: number;
  processingTime: number;
  
  // User preferences
  preferredLanguage: string;
  preferredVoice: string;
  averageSessionDuration: number;
}

export interface VoiceWebSocketMessage {
  type: 'audio' | 'transcript' | 'command' | 'control' | 'error';
  data: any;
  timestamp: Date;
  sessionId: string;
}

export interface VoiceSession {
  id: string;
  startTime: Date;
  endTime?: Date;
  transcripts: VoiceTranscript[];
  commands: VoiceCommand[];
  errors: VoiceError[];
  analytics: VoiceAnalytics;
}