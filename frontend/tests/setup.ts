import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, afterAll, vi } from 'vitest';
import React from 'react';

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
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api';
// Note: NODE_ENV is read-only in some environments, so we skip setting it

// Global test setup
beforeAll(() => {
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

  // Mock fetch
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ success: true }),
    text: () => Promise.resolve('Mock response'),
    headers: new Headers(),
  } as Response);
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
  default: (props: any) => {
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

// Mock Lucide React icons with proper error handling
vi.mock('lucide-react', () => {
  const createMockIcon = (name: string) => (props: any) => {
    return React.createElement('svg', {
      'data-testid': `${name}-icon`,
      'aria-label': name,
      ...props,
      children: React.createElement('path', { d: 'M0 0h24v24H0z' }),
    });
  };

  return new Proxy(
    {},
    {
      get: (_target, prop) => {
        if (typeof prop === 'string') {
          return createMockIcon(prop.toLowerCase());
        }
        return undefined;
      },
    },
  );
});

// Mock Radix UI Dialog primitives
vi.mock('@radix-ui/react-dialog', () => {
  const MockDialog = ({ children, open, onOpenChange, ...props }: any) => {
    return open
      ? React.createElement('div', { 'data-testid': 'dialog-root', ...props }, children)
      : null;
  };

  const MockDialogTrigger = ({ children, asChild, ...props }: any) => {
    return React.createElement('button', { 'data-testid': 'dialog-trigger', ...props }, children);
  };

  const MockDialogContent = React.forwardRef(({ children, className, ...props }: any, ref: any) => {
    return React.createElement(
      'div',
      {
        ref,
        role: 'dialog',
        'data-testid': 'dialog-content',
        className,
        'aria-labelledby': 'dialog-title',
        'aria-describedby': 'dialog-description',
        ...props,
      },
      children,
    );
  });

  const MockDialogOverlay = React.forwardRef(({ className, ...props }: any, ref: any) => {
    return React.createElement('div', {
      ref,
      'data-testid': 'dialog-overlay',
      className,
      ...props,
    });
  });

  const MockDialogClose = ({ children, asChild, ...props }: any) => {
    return React.createElement(
      'button',
      {
        'data-testid': 'dialog-close',
        'aria-label': 'Close',
        ...props,
      },
      children,
    );
  };

  const MockDialogPortal = ({ children }: any) => {
    return React.createElement('div', { 'data-testid': 'dialog-portal' }, children);
  };

  const MockDialogTitle = React.forwardRef(({ children, className, ...props }: any, ref: any) => {
    return React.createElement(
      'h2',
      {
        ref,
        id: 'dialog-title',
        'data-testid': 'dialog-title',
        className,
        ...props,
      },
      children,
    );
  });

  const MockDialogDescription = React.forwardRef(
    ({ children, className, ...props }: any, ref: any) => {
      return React.createElement(
        'p',
        {
          ref,
          id: 'dialog-description',
          'data-testid': 'dialog-description',
          className,
          ...props,
        },
        children,
      );
    },
  );

  return {
    Root: MockDialog,
    Trigger: MockDialogTrigger,
    Content: MockDialogContent,
    Overlay: MockDialogOverlay,
    Close: MockDialogClose,
    Portal: MockDialogPortal,
    Title: MockDialogTitle,
    Description: MockDialogDescription,
  };
});

// Mock auth store
vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: vi.fn(() => ({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: vi.fn().mockResolvedValue({
      user: { id: 'user-123', email: 'test@example.com', name: 'Test User' },
      tokens: { access_token: 'mock-token', refresh_token: 'mock-refresh' },
    }),
    register: vi.fn().mockResolvedValue({
      user: { id: 'user-456', email: 'newuser@example.com', name: 'New User' },
      tokens: { access_token: 'new-token', refresh_token: 'new-refresh' },
    }),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn().mockResolvedValue(null),
    initialize: vi.fn().mockResolvedValue(undefined),
  })),
}));

// Cleanup after each test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Cleanup after all tests
afterAll(() => {
  vi.resetAllMocks();
});
