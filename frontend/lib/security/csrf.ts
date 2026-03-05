import { createHash } from 'crypto';

import { type NextRequest } from 'next/server';

/**
 * CSRF token utilities for ruleIQ
 */

export const CSRF_HEADER_NAME = 'x-csrf-token';

/**
 * Verify CSRF token from request
 */
export function verifyCsrfToken(request: NextRequest): boolean {
  try {
    // Get token from header or body
    const token = request.headers.get('x-csrf-token') || request.headers.get('csrf-token');

    if (!token) {
      return false;
    }

    // Get stored hash from cookie
    const storedHash = request.cookies.get('csrf-token-hash')?.value;

    if (!storedHash) {
      return false;
    }

    // Recreate hash and compare
    const secret = process.env['CSRF_SECRET'] || 'fallback-secret-change-in-production';
    const expectedHash = createHash('sha256')
      .update(token + secret)
      .digest('hex');

    if (storedHash !== expectedHash) {
      return false;
    }

    return true;
  } catch (_error) {

    return false;
  }
}

/**
 * Middleware wrapper for CSRF protection
 */
export function withCsrfProtection<T>(
  handler: (request: NextRequest, context: T) => Promise<Response>,
) {
  return async (request: NextRequest, context: T): Promise<Response> => {
    // Only check CSRF for state-changing methods
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(request.method)) {
      if (!verifyCsrfToken(request)) {
        return new Response(
          JSON.stringify({
            error: 'CSRF token verification failed',
            code: 'CSRF_INVALID',
          }),
          {
            status: 403,
            headers: { 'Content-Type': 'application/json' },
          },
        );
      }
    }

    return handler(request, context);
  };
}

/**
 * Extract CSRF token from form data
 */
export async function extractCsrfFromFormData(request: NextRequest): Promise<string | null> {
  try {
    const formData = await request.formData();
    return (formData.get('_csrf') as string) || null;
  } catch (_error) {
    return null;
  }
}

/**
 * Verify CSRF token from form data
 */
export async function verifyCsrfFromFormData(request: NextRequest): Promise<boolean> {
  const token = await extractCsrfFromFormData(request);

  if (!token) {
    return false;
  }

  // Temporarily set token in header for verification
  const tempRequest = new Request(request.url, {
    method: request.method,
    headers: {
      ...Object.fromEntries(request.headers),
      'x-csrf-token': token,
    },
  });

  // Copy cookies
  const { cookies } = request;
  Object.defineProperty(tempRequest, 'cookies', {
    value: cookies,
    writable: false,
  });

  return verifyCsrfToken(tempRequest as NextRequest);
}
