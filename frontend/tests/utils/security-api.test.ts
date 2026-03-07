import { describe, it, expect } from 'vitest';
import { ApiSecurityError, generateCSP } from '@/lib/security/api';

// ============================================================================
// ApiSecurityError
// ============================================================================

describe('ApiSecurityError', () => {
  it('is an instance of Error', () => {
    const err = new ApiSecurityError('Unauthorized', 'UNAUTHORIZED', 401);
    expect(err).toBeInstanceOf(Error);
  });

  it('has name "ApiSecurityError"', () => {
    const err = new ApiSecurityError('msg', 'CODE', 400);
    expect(err.name).toBe('ApiSecurityError');
  });

  it('stores message', () => {
    const err = new ApiSecurityError('CSRF token invalid', 'CSRF_INVALID', 403);
    expect(err.message).toBe('CSRF token invalid');
  });

  it('stores code', () => {
    const err = new ApiSecurityError('msg', 'RATE_LIMIT_EXCEEDED', 429);
    expect(err.code).toBe('RATE_LIMIT_EXCEEDED');
  });

  it('stores statusCode', () => {
    const err = new ApiSecurityError('msg', 'CODE', 422);
    expect(err.statusCode).toBe(422);
  });

  it('stores optional details', () => {
    const details = [{ field: 'email', message: 'Invalid email' }];
    const err = new ApiSecurityError('Validation failed', 'VALIDATION_ERROR', 400, details);
    expect(err.details).toEqual(details);
  });

  it('details is undefined when not provided', () => {
    const err = new ApiSecurityError('msg', 'CODE', 400);
    expect(err.details).toBeUndefined();
  });

  it('can be caught as Error', () => {
    expect(() => {
      throw new ApiSecurityError('Forbidden', 'FORBIDDEN', 403);
    }).toThrow(Error);
  });

  it('can be caught as ApiSecurityError', () => {
    expect(() => {
      throw new ApiSecurityError('Forbidden', 'FORBIDDEN', 403);
    }).toThrow(ApiSecurityError);
  });
});

// ============================================================================
// generateCSP
// ============================================================================

describe('generateCSP', () => {
  it('returns a non-empty string', () => {
    const csp = generateCSP();
    expect(typeof csp).toBe('string');
    expect(csp.length).toBeGreaterThan(0);
  });

  it('includes default-src directive', () => {
    const csp = generateCSP();
    expect(csp).toContain("default-src 'self'");
  });

  it('includes script-src directive', () => {
    const csp = generateCSP();
    expect(csp).toContain('script-src');
  });

  it('includes style-src directive', () => {
    const csp = generateCSP();
    expect(csp).toContain('style-src');
  });

  it('includes img-src directive', () => {
    const csp = generateCSP();
    expect(csp).toContain('img-src');
  });

  it('includes connect-src directive', () => {
    const csp = generateCSP();
    expect(csp).toContain('connect-src');
  });

  it('includes object-src "none"', () => {
    const csp = generateCSP();
    expect(csp).toContain("object-src 'none'");
  });

  it('includes frame-ancestors "none"', () => {
    const csp = generateCSP();
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it('does NOT include unsafe-inline for scripts by default', () => {
    const csp = generateCSP({ allowInlineScripts: false });
    const scriptPart = csp.split(';').find((p) => p.trim().startsWith('script-src'));
    expect(scriptPart).not.toContain("'unsafe-inline'");
  });

  it('includes unsafe-inline for scripts when allowInlineScripts=true', () => {
    const csp = generateCSP({ allowInlineScripts: true });
    expect(csp).toContain("'unsafe-inline'");
  });

  it('does NOT include unsafe-inline for styles by default', () => {
    const csp = generateCSP({ allowInlineStyles: false });
    const stylePart = csp.split(';').find((p) => p.trim().startsWith('style-src'));
    expect(stylePart).not.toContain("'unsafe-inline'");
  });

  it('includes unsafe-inline for styles when allowInlineStyles=true', () => {
    const csp = generateCSP({ allowInlineStyles: true });
    const stylePart = csp.split(';').find((p) => p.trim().startsWith('style-src'));
    expect(stylePart).toContain("'unsafe-inline'");
  });

  it('does NOT include unsafe-eval by default', () => {
    const csp = generateCSP();
    expect(csp).not.toContain("'unsafe-eval'");
  });

  it('includes unsafe-eval when allowEval=true', () => {
    const csp = generateCSP({ allowEval: true });
    expect(csp).toContain("'unsafe-eval'");
  });

  it('includes custom script sources', () => {
    const csp = generateCSP({ customSources: { script: ['https://cdn.example.com'] } });
    expect(csp).toContain('https://cdn.example.com');
  });

  it('includes custom style sources', () => {
    const csp = generateCSP({ customSources: { style: ['https://fonts.googleapis.com'] } });
    expect(csp).toContain('https://fonts.googleapis.com');
  });

  it('includes custom img sources', () => {
    const csp = generateCSP({ customSources: { img: ['https://images.example.com'] } });
    expect(csp).toContain('https://images.example.com');
  });

  it('includes custom connect sources', () => {
    const csp = generateCSP({ customSources: { connect: ['https://api.example.com'] } });
    expect(csp).toContain('https://api.example.com');
  });

  it('img-src always includes data: and https:', () => {
    const csp = generateCSP();
    const imgPart = csp.split(';').find((p) => p.trim().startsWith('img-src'));
    expect(imgPart).toContain('data:');
    expect(imgPart).toContain('https:');
  });

  it('directives are separated by semicolons', () => {
    const csp = generateCSP();
    const parts = csp.split(';');
    expect(parts.length).toBeGreaterThan(5);
  });

  it('includes upgrade-insecure-requests', () => {
    const csp = generateCSP();
    expect(csp).toContain('upgrade-insecure-requests');
  });

  it('works with all options combined', () => {
    const csp = generateCSP({
      allowInlineStyles: true,
      allowInlineScripts: true,
      allowEval: true,
      customSources: {
        script: ['https://cdn.example.com'],
        style: ['https://fonts.googleapis.com'],
        img: ['https://images.example.com'],
        connect: ['https://api.example.com'],
      },
    });
    expect(csp).toContain("'unsafe-inline'");
    expect(csp).toContain("'unsafe-eval'");
    expect(csp).toContain('https://cdn.example.com');
  });
});
