import { type NextRequest, NextResponse } from 'next/server';

/**
 * Sentry tunnel route to bypass ad blockers and provide better error tracking
 * This proxies requests to Sentry through our domain to avoid being blocked
 */
export async function POST(request: NextRequest) {
  try {
    const envelope = await request.text();
    const pieces = envelope.split('\n');
    const header = JSON.parse(pieces[0] || '{}');

    // Extract the DSN from the header
    const dsn = header?.dsn;
    if (!dsn) {
      return new NextResponse('Invalid DSN', { status: 400 });
    }

    // Validate that this is a legitimate Sentry DSN for our project
    const expectedHost = process.env['NEXT_PUBLIC_SENTRY_DSN']?.match(/https:\/\/(.+?)@(.+?)\//);
    const dsnHost = dsn.match(/https:\/\/(.+?)@(.+?)\//);

    if (!expectedHost || !dsnHost || dsnHost[2] !== expectedHost[2]) {
      return new NextResponse('Unauthorized DSN', { status: 403 });
    }

    // Construct the Sentry ingest URL
    const projectId = dsn.split('/').pop();
    const sentryIngestUrl = `https://${dsnHost[2]}/api/${projectId}/envelope/`;

    // Forward the request to Sentry
    const sentryResponse = await fetch(sentryIngestUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-sentry-envelope',
        'User-Agent': request.headers.get('User-Agent') || '',
      },
      body: envelope,
    });

    // Return Sentry's response
    return new NextResponse(sentryResponse.body, {
      status: sentryResponse.status,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  } catch (_error) {

    return new NextResponse('Internal Server Error', { status: 500 });
  }
}

// Also handle GET requests for health checks
export async function GET() {
  return NextResponse.json({
    status: 'ok',
    service: 'sentry-tunnel',
    timestamp: new Date().toISOString(),
  });
}
