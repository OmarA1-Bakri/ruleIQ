import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, afterAll, vi } from 'vitest';
import React from 'react';
import { server } from './mocks/server';

// HTMLFormElement.prototype.requestSubmit polyfill for JSDOM
if (typeof HTMLFormElement !== 'undefined' && !HTMLFormElement.prototype.requestSubmit) {
  HTMLFormElement.prototype.requestSubmit = function (submitter?: HTMLElement) {
    if (submitter && (submitter as any).form !== this) {
      throw new DOMException(
        'The specified element is not a descendant of this form element',
        'NotFoundError',
      );
    }

    const submitEvent = new Event('submit', {
      bubbles: true,
      cancelable: true,
    });

    if (submitter) {
      Object.defineProperty(submitEvent, 'submitter', {
        value: submitter,
        configurable: true,
      });
    }

    this.dispatchEvent(submitEvent);
  };
}

// Mock environment variables
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
// Note: NODE_ENV is read-only in some environments, so we skip setting it

// Start MSW server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' });
  
  // Other global test setup
  // Mock window.matchMedia
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Mock ResizeObserver
  global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));

  // Mock localStorage
  const localStorageStore: Record<string, string> = {};
  const localStorageMock = {
    getItem: vi.fn((key: string) => localStorageStore[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      localStorageStore[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete localStorageStore[key];
    }),
    clear: vi.fn(() => {
      Object.keys(localStorageStore).forEach((key) => delete localStorageStore[key]);
    }),
    get length() {
      return Object.keys(localStorageStore).length;
    },
    key: vi.fn((index: number) => {
      const keys = Object.keys(localStorageStore);
      return keys[index] || null;
    }),
  };
  Object.defineProperty(window, 'localStorage', {
    writable: true,
    value: localStorageMock,
  });


});

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
  usePathname: vi.fn(() => '/'),
  useSearchParams: vi.fn(() => new URLSearchParams()),
}));

// Mock Next.js image
vi.mock('next/image', () => ({
  default: (props: Record<string, unknown>) => {
    const { src, alt, ...rest } = props;
    return React.createElement('img', { src, alt, ...rest });
  },
}));

// Mock clsx and tailwind-merge for cn utility
vi.mock('clsx', () => ({
  clsx: vi.fn((inputs) => {
    if (Array.isArray(inputs)) {
      return inputs
        .filter(Boolean)
        .map((arg) => {
          if (typeof arg === 'string') return arg;
          if (typeof arg === 'object' && arg !== null) {
            return Object.keys(arg)
              .filter((key) => arg[key])
              .join(' ');
          }
          return '';
        })
        .join(' ');
    }
    return inputs || '';
  }),
}));

vi.mock('tailwind-merge', () => ({
  twMerge: vi.fn((classString) => {
    if (typeof classString !== 'string') return '';
    // Clean up and deduplicate classes
    return classString
      .split(/\s+/)
      .filter(Boolean)
      .filter((cls, index, arr) => arr.indexOf(cls) === index)
      .join(' ');
  }),
}));

// Mock Lucide React icons with a robust and simple mock
vi.mock('lucide-react', () => {
  const MockIcon = React.forwardRef((props, ref) =>
    React.createElement('svg', { ...props, ref, 'data-testid': 'lucide-icon' })
  );
  MockIcon.displayName = 'MockIcon';

  return new Proxy({}, {
    get: () => MockIcon,
  });
});

// Mock Radix UI Dialog primitives with a simpler implementation
vi.mock('@radix-ui/react-dialog', async () => {
  const original = await vi.importActual<any>('@radix-ui/react-dialog');

  const MockDialog = ({ children, ...props }: { children: React.ReactNode }) =>
    React.createElement('div', { ...props, 'data-testid': 'dialog-root' }, children);

  const MockTrigger = ({ children }: { children: React.ReactNode }) => children;

  const MockContent = React.forwardRef<HTMLDivElement, { children: React.ReactNode }>(
    ({ children, ...props }, ref) =>
      React.createElement('div', { ...props, ref, 'data-testid': 'dialog-content' }, children)
  );
  MockContent.displayName = 'MockDialogContent';

  const MockOverlay = () => React.createElement('div', { 'data-testid': 'dialog-overlay' });

  const MockClose = ({ children }: { children: React.ReactNode }) =>
    React.createElement('button', { 'data-testid': 'dialog-close' }, children);

  const MockPortal = ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'dialog-portal' }, children);

  const MockTitle = React.forwardRef<HTMLHeadingElement, { children: React.ReactNode }>(
    ({ children, ...props }, ref) =>
      React.createElement('h2', { ...props, ref, 'data-testid': 'dialog-title' }, children)
  );
  MockTitle.displayName = 'MockDialogTitle';

  const MockDescription = React.forwardRef<HTMLParagraphElement, { children: React.ReactNode }>(
    ({ children, ...props }, ref) =>
      React.createElement('p', { ...props, ref, 'data-testid': 'dialog-description' }, children)
  );
  MockDescription.displayName = 'MockDialogDescription';

  return {
    ...original,
    Root: MockDialog,
    Trigger: MockTrigger,
    Content: MockContent,
    Overlay: MockOverlay,
    Close: MockClose,
    Portal: MockPortal,
    Title: MockTitle,
    Description: MockDescription,
  };
});



// Cleanup after each test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  server.resetHandlers();
  // Clear local storage to prevent state leakage between tests
  if (typeof localStorage !== 'undefined') {
    localStorage.clear();
  }
});

// Cleanup after all tests
afterAll(() => {
  vi.resetAllMocks();
  server.close();
});
