import * as Sentry from '@sentry/nextjs';

// Only initialize Sentry if a valid DSN is provided
const sentryDsn = process.env['NEXT_PUBLIC_SENTRY_DSN'];
const isValidDsn =
  sentryDsn &&
  sentryDsn !== 'https://your-dsn@sentry.io/project-id' &&
  sentryDsn.startsWith('https://') &&
  sentryDsn.includes('@sentry.io');

if (isValidDsn) {
  Sentry.init({
    dsn: sentryDsn,

    // Adjust this value in production, or use tracesSampler for greater control
    tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

    // Environment configuration
    environment: process.env.NODE_ENV,

    // Release tracking
    release: process.env['NEXT_PUBLIC_SENTRY_RELEASE'] || 'ruleiq-frontend@unknown',

    // Edge runtime specific configuration
    integrations: [
      // No special integrations needed for edge runtime
    ],

    // Performance Monitoring for edge
    tracesSampler: (samplingContext) => {
      const { name } = samplingContext;

      // Lower sampling for health checks
      if (name === 'GET /api/health') {
        return 0.1;
      }

      return process.env.NODE_ENV === 'production' ? 0.1 : 1.0;
    },

    // Initial scope for edge
    initialScope: {
      tags: {
        component: 'edge',
        runtime: 'edge',
      },
    },
  });
} else {
  // intentionally empty - Sentry DSN not configured
}
