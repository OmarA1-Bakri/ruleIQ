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

    // Configure browser tracing
    integrations: [
      Sentry.browserTracingIntegration({
        // Set up automatic route change tracking in Next.js App Router
        instrumentNavigation: true,
        instrumentPageLoad: true,
      }),
      Sentry.replayIntegration({
        // Capture 10% of the sessions in production
        replaysSessionSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,
        // Of those, capture 100% of error sessions
        replaysOnErrorSampleRate: 1.0,
      } as any), // Type casting for compatibility
    ],

    // Environment configuration
    environment: process.env.NODE_ENV,

    // Release tracking
    release: process.env['NEXT_PUBLIC_SENTRY_DSN'] || 'ruleiq-frontend@unknown',

    // Performance Monitoring
    tracesSampler: (samplingContext) => {
      // Adjust sample rates based on context
      const { location } = samplingContext;

      if (location?.pathname === '/api/health') {
        return 0.1; // Lower sampling for health checks
      }

      if (location?.pathname?.startsWith('/api/')) {
        return 0.5; // Moderate sampling for API routes
      }

      if (process.env.NODE_ENV === 'production') {
        return 0.1; // Lower sampling in production
      }

      return 1.0; // Full sampling in development
    },

    // Error filtering
    beforeSend(event) {
      // Filter out development-only errors
      if (process.env.NODE_ENV === 'development') {
        // Filter out some common development errors
        if (event.exception?.values?.[0]?.value?.includes('ResizeObserver loop limit exceeded')) {
          return null;
        }
      }

      return event;
    },

    // User context
    beforeSendTransaction(event) {
      // You can modify the transaction before it's sent
      return event;
    },

    // Additional context
    initialScope: {
      tags: {
        component: 'frontend',
      },
    },
  });
} else {
  console.log('Sentry disabled: No valid DSN provided or placeholder DSN detected');
}
