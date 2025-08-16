import * as Sentry from '@sentry/nextjs';

export async function register() {
  if (process.env['NEXT_RUNTIME'] === 'nodejs') {
    await import('./sentry.server.config');
  }

  if (process.env['NEXT_RUNTIME'] === 'edge') {
    await import('./sentry.edge.config');
  }
}

// Handle errors from nested React Server Components
export async function onRequestError(
  error: Error,
  request: {
    path: string;
    method: string;
    headers: Record<string, string>;
  }
) {
  Sentry.captureRequestError(error, request, {
    // mechanism property removed in newer versions
  } as any);
}
