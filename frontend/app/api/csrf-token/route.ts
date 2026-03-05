import { randomBytes, createHash } from 'crypto';

import { NextResponse } from 'next/server';

/**
 * GET /api/csrf-token
 * Returns a CSRF token for forms
 */
export async function GET() {
  try {
    // Generate a secure random token
    const token = randomBytes(32).toString('hex');

    // Create a hash for verification
    const secret = process.env['CSRF_SECRET'] || 'fallback-secret-change-in-production';
    const tokenHash = createHash('sha256')
      .update(token + secret)
      .digest('hex');

    // Set token in httpOnly cookie for server-side verification
    const response = NextResponse.json({
      csrfToken: token,
      message: 'CSRF token generated successfully',
    });

    response.cookies.set('csrf-token-hash', tokenHash, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60, // 1 hour
    });

    return response;
  } catch (_error) {

    return NextResponse.json({ error: 'Failed to generate CSRF token' }, { status: 500 });
  }
}
