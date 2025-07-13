/**
 * Secure storage utility for sensitive data like authentication tokens
 * Uses Web Crypto API for encryption and httpOnly cookies for refresh tokens
 */

interface StorageOptions {
  useHttpOnlyCookie?: boolean;
  expiry?: number; // in milliseconds
}

class SecureStorage {
  private static readonly ENCRYPTION_KEY_NAME = 'ruleiq_encryption_key';
  private static readonly ACCESS_TOKEN_KEY = 'ruleiq_access_token';
  private static readonly SESSION_EXPIRY_KEY = 'ruleiq_session_expiry';
  private static readonly REFRESH_TOKEN_COOKIE = 'ruleiq_refresh_token';
  
  private static encryptionKey: CryptoKey | null = null;

  /**
   * Generate or retrieve the encryption key
   */
  private static async getEncryptionKey(): Promise<CryptoKey> {
    if (this.encryptionKey) {
      return this.encryptionKey;
    }

    // Try to get existing key from sessionStorage
    const storedKey = sessionStorage.getItem(this.ENCRYPTION_KEY_NAME);
    
    if (storedKey) {
      try {
        const keyData = JSON.parse(atob(storedKey));
        this.encryptionKey = await crypto.subtle.importKey(
          'raw',
          new Uint8Array(keyData),
          { name: 'AES-GCM' },
          false,
          ['encrypt', 'decrypt']
        );
        return this.encryptionKey;
      } catch (error) {
        console.warn('Failed to import stored encryption key, generating new one');
      }
    }

    // Generate new key
    this.encryptionKey = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    );

    // Export and store the key
    const exportedKey = await crypto.subtle.exportKey('raw', this.encryptionKey);
    const keyData = Array.from(new Uint8Array(exportedKey));
    sessionStorage.setItem(this.ENCRYPTION_KEY_NAME, btoa(JSON.stringify(keyData)));

    return this.encryptionKey;
  }

  /**
   * Encrypt data using AES-GCM
   */
  private static async encrypt(data: string): Promise<string> {
    try {
      const key = await this.getEncryptionKey();
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(data);
      
      // Generate random IV
      const iv = crypto.getRandomValues(new Uint8Array(12));
      
      // Encrypt the data
      const encryptedBuffer = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        dataBuffer
      );
      
      // Combine IV and encrypted data
      const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encryptedBuffer), iv.length);
      
      // Return base64 encoded result
      return btoa(String.fromCharCode(...combined));
    } catch (error) {
      console.error('Encryption failed:', error);
      throw new Error('Failed to encrypt data');
    }
  }

  /**
   * Decrypt data using AES-GCM
   */
  private static async decrypt(encryptedData: string): Promise<string> {
    try {
      const key = await this.getEncryptionKey();
      
      // Decode base64
      const combined = new Uint8Array(
        atob(encryptedData).split('').map(char => char.charCodeAt(0))
      );
      
      // Extract IV and encrypted data
      const iv = combined.slice(0, 12);
      const encrypted = combined.slice(12);
      
      // Decrypt the data
      const decryptedBuffer = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        key,
        encrypted
      );
      
      // Convert back to string
      const decoder = new TextDecoder();
      return decoder.decode(decryptedBuffer);
    } catch (error) {
      console.error('Decryption failed:', error);
      throw new Error('Failed to decrypt data');
    }
  }

  /**
   * Set httpOnly cookie for refresh token
   */
  private static setHttpOnlyCookie(name: string, value: string, expiry?: number): void {
    const expires = expiry ? new Date(expiry).toUTCString() : '';
    const expiresStr = expires ? `; expires=${expires}` : '';
    
    // Note: httpOnly can only be set server-side, but we can set secure and sameSite
    document.cookie = `${name}=${value}; path=/; secure; samesite=strict${expiresStr}`;
  }

  /**
   * Get cookie value
   */
  private static getCookie(name: string): string | null {
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const [cookieName, cookieValue] = cookie.trim().split('=');
      if (cookieName === name) {
        return cookieValue;
      }
    }
    return null;
  }

  /**
   * Delete cookie
   */
  private static deleteCookie(name: string): void {
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  }

  /**
   * Store access token securely (encrypted in sessionStorage)
   */
  public static async setAccessToken(token: string, options: StorageOptions = {}): Promise<void> {
    try {
      const encryptedToken = await this.encrypt(token);
      
      if (options.useHttpOnlyCookie) {
        // Note: For production, this should be set by the server
        console.warn('httpOnly cookies must be set server-side for security');
      }
      
      sessionStorage.setItem(this.ACCESS_TOKEN_KEY, encryptedToken);
      
      if (options.expiry) {
        sessionStorage.setItem(this.SESSION_EXPIRY_KEY, options.expiry.toString());
      }
    } catch (error) {
      console.error('Failed to store access token:', error);
      throw error;
    }
  }

  /**
   * Get access token (decrypt from sessionStorage)
   */
  public static async getAccessToken(): Promise<string | null> {
    try {
      const encryptedToken = sessionStorage.getItem(this.ACCESS_TOKEN_KEY);
      if (!encryptedToken) {
        return null;
      }
      
      return await this.decrypt(encryptedToken);
    } catch (error) {
      console.error('Failed to retrieve access token:', error);
      // Clear corrupted data
      this.clearAccessToken();
      return null;
    }
  }

  /**
   * Store refresh token in cookie (for server-side httpOnly setting)
   */
  public static setRefreshToken(token: string, expiry?: number): void {
    // In a real implementation, this would be set server-side as httpOnly
    // For now, we'll use a secure cookie with client-side limitations
    this.setHttpOnlyCookie(this.REFRESH_TOKEN_COOKIE, token, expiry);
  }

  /**
   * Get refresh token from cookie
   */
  public static getRefreshToken(): string | null {
    return this.getCookie(this.REFRESH_TOKEN_COOKIE);
  }

  /**
   * Get session expiry
   */
  public static getSessionExpiry(): number | null {
    const expiry = sessionStorage.getItem(this.SESSION_EXPIRY_KEY);
    return expiry ? parseInt(expiry) : null;
  }

  /**
   * Check if session is expired
   */
  public static isSessionExpired(): boolean {
    const expiry = this.getSessionExpiry();
    return expiry ? Date.now() > expiry : false;
  }

  /**
   * Clear access token
   */
  public static clearAccessToken(): void {
    sessionStorage.removeItem(this.ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(this.SESSION_EXPIRY_KEY);
  }

  /**
   * Clear refresh token
   */
  public static clearRefreshToken(): void {
    this.deleteCookie(this.REFRESH_TOKEN_COOKIE);
  }

  /**
   * Clear all stored tokens and encryption key
   */
  public static clearAll(): void {
    this.clearAccessToken();
    this.clearRefreshToken();
    sessionStorage.removeItem(this.ENCRYPTION_KEY_NAME);
    
    // Also clear legacy localStorage tokens if they exist
    localStorage.removeItem('ruleiq_auth_token');
    localStorage.removeItem('ruleiq_refresh_token');
    localStorage.removeItem('ruleiq_session_expiry');
    sessionStorage.removeItem('ruleiq_auth_token');
    sessionStorage.removeItem('ruleiq_refresh_token');
    sessionStorage.removeItem('ruleiq_session_expiry');
    
    this.encryptionKey = null;
  }

  /**
   * Migrate from legacy storage to secure storage
   */
  public static async migrateLegacyTokens(): Promise<void> {
    try {
      // Check for legacy tokens
      const legacyAccessToken = localStorage.getItem('ruleiq_auth_token') || 
                               sessionStorage.getItem('ruleiq_auth_token');
      const legacyRefreshToken = localStorage.getItem('ruleiq_refresh_token') || 
                                sessionStorage.getItem('ruleiq_refresh_token');
      const legacyExpiry = localStorage.getItem('ruleiq_session_expiry') || 
                          sessionStorage.getItem('ruleiq_session_expiry');

      if (legacyAccessToken) {
        await this.setAccessToken(legacyAccessToken, {
          expiry: legacyExpiry ? parseInt(legacyExpiry) : undefined
        });
      }

      if (legacyRefreshToken) {
        this.setRefreshToken(legacyRefreshToken, legacyExpiry ? parseInt(legacyExpiry) : undefined);
      }

      // Clear legacy tokens
      localStorage.removeItem('ruleiq_auth_token');
      localStorage.removeItem('ruleiq_refresh_token');
      localStorage.removeItem('ruleiq_session_expiry');
      sessionStorage.removeItem('ruleiq_auth_token');
      sessionStorage.removeItem('ruleiq_refresh_token');
      sessionStorage.removeItem('ruleiq_session_expiry');

      console.log('Legacy tokens migrated to secure storage');
    } catch (error) {
      console.error('Failed to migrate legacy tokens:', error);
    }
  }
}

export default SecureStorage;