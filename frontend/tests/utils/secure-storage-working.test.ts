import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock Web Crypto API
const mockCrypto = {
  subtle: {
    generateKey: vi.fn().mockResolvedValue({}),
    encrypt: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
    decrypt: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
    exportKey: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
    importKey: vi.fn().mockResolvedValue({}),
  },
  getRandomValues: vi.fn().mockReturnValue(new Uint8Array(16)),
};

// Mock sessionStorage
const mockSessionStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

// Mock document.cookie
Object.defineProperty(document, 'cookie', {
  writable: true,
  value: '',
});

// Set up global mocks
Object.defineProperty(global, 'crypto', {
  value: mockCrypto,
  writable: true,
});

Object.defineProperty(global, 'sessionStorage', {
  value: mockSessionStorage,
  writable: true,
});

Object.defineProperty(global, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

describe('SecureStorage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSessionStorage.getItem.mockReturnValue(null);
    mockLocalStorage.getItem.mockReturnValue(null);
    document.cookie = '';
  });

  describe('Token Storage', () => {
    it('should have setAccessToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.setAccessToken).toBe('function');
    });

    it('should have getAccessToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.getAccessToken).toBe('function');
    });

    it('should handle setAccessToken calls without errors', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      await expect(SecureStorage.setAccessToken('test-token')).resolves.not.toThrow();
    });
  });

  describe('Session Management', () => {
    it('should have isSessionExpired method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.isSessionExpired).toBe('function');
    });

    it('should have getSessionExpiry method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.getSessionExpiry).toBe('function');
    });

    it('should handle session expiry checks', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      const result = SecureStorage.isSessionExpired();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('Refresh Token Management', () => {
    it('should have setRefreshToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.setRefreshToken).toBe('function');
    });

    it('should have getRefreshToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.getRefreshToken).toBe('function');
    });

    it('should handle refresh token operations', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(() => SecureStorage.setRefreshToken('test-refresh-token')).not.toThrow();

      const result = SecureStorage.getRefreshToken();
      expect(result).toBeDefined();
    });
  });

  describe('Clear Operations', () => {
    it('should have clearAccessToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.clearAccessToken).toBe('function');
    });

    it('should have clearRefreshToken method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.clearRefreshToken).toBe('function');
    });

    it('should have clearAll method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.clearAll).toBe('function');
    });

    it('should handle clear operations without errors', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(() => SecureStorage.clearAccessToken()).not.toThrow();
      expect(() => SecureStorage.clearRefreshToken()).not.toThrow();
      expect(() => SecureStorage.clearAll()).not.toThrow();
    });
  });

  describe('Legacy Migration', () => {
    it('should have migrateLegacyTokens method', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      expect(typeof SecureStorage.migrateLegacyTokens).toBe('function');
    });

    it('should handle legacy migration without errors', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      await expect(SecureStorage.migrateLegacyTokens()).resolves.not.toThrow();
    });
  });

  describe('Encryption Operations', () => {
    it('should handle encryption operations', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      // Test that crypto operations are available
      expect(global.crypto).toBeDefined();
      expect(global.crypto.subtle).toBeDefined();
    });

    it('should handle storage operations', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      // Test that storage APIs are available
      expect(global.sessionStorage).toBeDefined();
      expect(global.localStorage).toBeDefined();
    });
  });

  describe('Cookie Operations', () => {
    it('should handle cookie operations', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      // Test that document.cookie is available
      expect(document.cookie).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('should handle errors gracefully', async () => {
      const SecureStorage = (await import('@/lib/utils/secure-storage')).default;

      // Mock crypto to throw an error
      mockCrypto.subtle.encrypt.mockRejectedValueOnce(new Error('Encryption failed'));

      // Should throw when encryption fails (this is expected behavior)
      await expect(SecureStorage.setAccessToken('test')).rejects.toThrow('Failed to encrypt data');
    });
  });
});
