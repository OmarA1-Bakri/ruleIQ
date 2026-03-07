import { cookies } from 'next/headers';
import { type NextRequest, NextResponse } from 'next/server';

import { CSRF_HEADER_NAME } from './csrf';

/**
 * CSRF protection middleware for API routes
 */
export async function withCSRFProtection(
  request: NextRequest,
  handler: (request: NextRequest) => Promise<NextResponse> | NextResponse,
): Promise<NextResponse> {
  // Only apply CSRF protection to state-changing methods
  const method = request.method.toUpperCase();
  const protectedMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];

  if (!protectedMethods.includes(method)) {
    return handler(request);
  }

  try {
    // Get CSRF token from header
    const csrfToken = request.headers.get(CSRF_HEADER_NAME);

    if (!csrfToken) {
      return NextResponse.json(
        {
          error: 'CSRF token missing',
          detail: 'CSRF token is required for this operation',
        },
        { status: 403 },
      );
    }

    // Validate CSRF token
    const cookieStore = await cookies();
    const storedToken = cookieStore.get('ruleiq_csrf_token')?.value;

    if (!storedToken || !constantTimeEquals(storedToken, csrfToken)) {
      return NextResponse.json(
        {
          error: 'CSRF token invalid',
          detail: 'Invalid CSRF token provided',
        },
        { status: 403 },
      );
    }

    // CSRF validation passed, proceed with the request
    return handler(request);
  } catch (_error) {

    return NextResponse.json(
      {
        error: 'CSRF validation failed',
        detail: 'Unable to validate CSRF token',
      },
      { status: 500 },
    );
  }
}

/**
 * Constant-time string comparison to prevent timing attacks
 */
function constantTimeEquals(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }

  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }

  return result === 0;
}

/**
 * Higher-order function to wrap API route handlers with CSRF protection
 */
export function withCSRF(handler: (request: NextRequest) => Promise<NextResponse> | NextResponse) {
  return async (request: NextRequest): Promise<NextResponse> => {
    return withCSRFProtection(request, handler);
  };
}
