import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Voice Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');
    const store = useVoiceStore.getState();

    expect(store.isSupported).toBe(false);
    expect(store.isEnabled).toBe(false);
    expect(store.isListening).toBe(false);
    expect(store.isProcessing).toBe(false);
    expect(store.isSpeaking).toBe(false);
    expect(store.isInCall).toBe(false);
    expect(store.callDuration).toBe(0);
    expect(store.volume).toBe(1.0);
    expect(store.isMuted).toBe(false);
    expect(store.transcript).toBe('');
    expect(store.interimTranscript).toBe('');
    expect(store.confidence).toBe(0);
    expect(store.language).toBe('en-US');
    expect(store.error).toBeNull();
  });

  it('should have default config', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');
    const config = useVoiceStore.getState().config;

    expect(config.language).toBe('en-US');
    expect(config.continuous).toBe(true);
    expect(config.interimResults).toBe(true);
    expect(config.confidenceThreshold).toBe(0.7);
    expect(config.voiceType).toBe('neutral');
    expect(config.speechRate).toBe(1.0);
    expect(config.pitch).toBe(1.0);
    expect(config.volume).toBe(1.0);
    expect(config.noiseSuppression).toBe(true);
    expect(config.echoCancellation).toBe(true);
  });

  it('should stop listening', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    // Manually set listening state
    useVoiceStore.setState({ isListening: true, isProcessing: true });

    useVoiceStore.getState().stopListening();

    expect(useVoiceStore.getState().isListening).toBe(false);
    expect(useVoiceStore.getState().isProcessing).toBe(false);
  });

  it('should pause and resume listening', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.setState({ isListening: true });

    useVoiceStore.getState().pauseListening();
    expect(useVoiceStore.getState().isListening).toBe(false);

    useVoiceStore.getState().resumeListening();
    expect(useVoiceStore.getState().isListening).toBe(true);
  });

  it('should stop speaking', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.setState({ isSpeaking: true });

    useVoiceStore.getState().stopSpeaking();
    expect(useVoiceStore.getState().isSpeaking).toBe(false);
  });

  it('should end voice call', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.setState({ isInCall: true, callDuration: 120, callParticipants: ['user-1'] });

    useVoiceStore.getState().endVoiceCall();

    expect(useVoiceStore.getState().isInCall).toBe(false);
    expect(useVoiceStore.getState().callDuration).toBe(0);
    expect(useVoiceStore.getState().callParticipants).toEqual([]);
  });

  it('should toggle mute', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    expect(useVoiceStore.getState().isMuted).toBe(false);

    useVoiceStore.getState().toggleMute();
    expect(useVoiceStore.getState().isMuted).toBe(true);

    useVoiceStore.getState().toggleMute();
    expect(useVoiceStore.getState().isMuted).toBe(false);
  });

  it('should adjust volume within bounds', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.getState().adjustVolume(0.5);
    expect(useVoiceStore.getState().volume).toBe(0.5);

    // Should clamp to max 1
    useVoiceStore.getState().adjustVolume(1.5);
    expect(useVoiceStore.getState().volume).toBe(1.0);

    // Should clamp to min 0
    useVoiceStore.getState().adjustVolume(-0.5);
    expect(useVoiceStore.getState().volume).toBe(0);
  });

  it('should set language', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.getState().setLanguage('fr-FR');
    expect(useVoiceStore.getState().language).toBe('fr-FR');
    expect(useVoiceStore.getState().config.language).toBe('fr-FR');
  });

  it('should set voice type', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.getState().setVoiceType('female');
    expect(useVoiceStore.getState().config.voiceType).toBe('female');

    useVoiceStore.getState().setVoiceType('male');
    expect(useVoiceStore.getState().config.voiceType).toBe('male');
  });

  it('should update config partially', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    // First capture current language (may be mutated by previous test due to persist)
    const currentLanguage = useVoiceStore.getState().config.language;

    useVoiceStore.getState().updateConfig({
      speechRate: 1.5,
      pitch: 0.8,
    });

    const config = useVoiceStore.getState().config;
    expect(config.speechRate).toBe(1.5);
    expect(config.pitch).toBe(0.8);
    // Language should remain whatever it was before
    expect(config.language).toBe(currentLanguage);
    expect(config.volume).toBe(1.0);
  });

  it('should clear transcript', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    useVoiceStore.setState({
      transcript: 'Hello world',
      interimTranscript: 'Hello',
      confidence: 0.95,
    });

    useVoiceStore.getState().clearTranscript();

    expect(useVoiceStore.getState().transcript).toBe('');
    expect(useVoiceStore.getState().interimTranscript).toBe('');
    expect(useVoiceStore.getState().confidence).toBe(0);
  });

  it('should check capabilities', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    const capabilities = await useVoiceStore.getState().checkCapabilities();

    expect(capabilities).toBeDefined();
    expect(typeof capabilities.speechRecognition).toBe('boolean');
    expect(typeof capabilities.speechSynthesis).toBe('boolean');
    expect(typeof capabilities.calling).toBe('boolean');

    // Store should be updated
    expect(useVoiceStore.getState().voiceCapabilities).toBeDefined();
  });

  it('should reset state', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');

    // Modify state
    useVoiceStore.setState({
      isListening: true,
      transcript: 'test',
      volume: 0.5,
    });

    useVoiceStore.getState().reset();

    const state = useVoiceStore.getState();
    expect(state.isListening).toBe(false);
    expect(state.transcript).toBe('');
    expect(state.volume).toBe(1.0);
  });

  it('should provide all expected methods', async () => {
    const { useVoiceStore } = await import('@/lib/stores/voice.store');
    const store = useVoiceStore.getState();

    expect(typeof store.startListening).toBe('function');
    expect(typeof store.stopListening).toBe('function');
    expect(typeof store.pauseListening).toBe('function');
    expect(typeof store.resumeListening).toBe('function');
    expect(typeof store.speakResponse).toBe('function');
    expect(typeof store.stopSpeaking).toBe('function');
    expect(typeof store.startVoiceCall).toBe('function');
    expect(typeof store.endVoiceCall).toBe('function');
    expect(typeof store.toggleMute).toBe('function');
    expect(typeof store.adjustVolume).toBe('function');
    expect(typeof store.setLanguage).toBe('function');
    expect(typeof store.setVoiceType).toBe('function');
    expect(typeof store.updateConfig).toBe('function');
    expect(typeof store.checkCapabilities).toBe('function');
    expect(typeof store.requestPermissions).toBe('function');
    expect(typeof store.testMicrophone).toBe('function');
    expect(typeof store.clearTranscript).toBe('function');
    expect(typeof store.reset).toBe('function');
  });
});
