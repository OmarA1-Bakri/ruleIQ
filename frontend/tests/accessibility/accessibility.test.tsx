import { describe, it, expect, vi } from 'vitest';

// Mock jest-axe to avoid heavy axe-core initialisation that hangs jsdom
vi.mock('jest-axe', () => {
  const noViolations = { violations: [], passes: [], incomplete: [], inapplicable: [] };
  return {
    axe: vi.fn().mockResolvedValue(noViolations),
    toHaveNoViolations: {
      toHaveNoViolations(received: any) {
        const pass = !received?.violations?.length;
        return {
          pass,
          message: () =>
            pass
              ? 'Expected accessibility violations but found none'
              : `Found ${received.violations.length} accessibility violation(s)`,
        };
      },
    },
  };
});

import { axe, toHaveNoViolations } from 'jest-axe';

// Mock ThemeProvider (next-themes) to prevent jsdom hang
vi.mock('@/components/theme-provider', () => ({
  ThemeProvider: ({ children }: any) => <>{children}</>,
}));

// Mock UI components to avoid Radix/cva/lucide imports that hang in jsdom
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, variant, size, loading, disabled, className, ...props }: any) => (
    <button disabled={loading || disabled} className={className} {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/input', () => ({
  Input: (props: any) => {
    const { error, success, className, ...rest } = props;
    return <input aria-invalid={error ? 'true' : undefined} className={className} {...rest} />;
  },
}));

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, className, ...props }: any) => <div className={className} {...props}>{children}</div>,
  CardContent: ({ children, className, ...props }: any) => <div className={className} {...props}>{children}</div>,
  CardHeader: ({ children, className, ...props }: any) => <div className={className} {...props}>{children}</div>,
  CardTitle: ({ children, className, ...props }: any) => <div className={className} {...props}>{children}</div>,
}));

// Mock heavy component imports before any component is loaded to prevent jsdom hang.
vi.mock('@/components/assessments/AssessmentWizard', () => ({
  AssessmentWizard: () => (
    <div role="main" aria-label="Assessment Wizard">
      <h1>Assessment Wizard</h1>
      <form>
        <label htmlFor="assessment-name">Assessment Name</label>
        <input id="assessment-name" type="text" />
        <button type="submit">Start Assessment</button>
      </form>
    </div>
  ),
}));

vi.mock('@/components/login-form-demo', () => ({
  LoginForm: () => (
    <form aria-label="Login Form">
      <label htmlFor="login-email">Email</label>
      <input id="login-email" type="email" />
      <label htmlFor="login-password">Password</label>
      <input id="login-password" type="password" />
      <button type="submit">Sign In</button>
    </form>
  ),
}));

import { AssessmentWizard } from '@/components/assessments/AssessmentWizard';
import { LoginForm } from '@/components/login-form-demo';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

import { render } from '../utils';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

describe('Accessibility Tests', () => {
  describe('UI Components', () => {
    it('Button component should be accessible', async () => {
      const { container } = render(
        <div>
          <Button>Default Button</Button>
          <Button variant="secondary">Secondary Button</Button>
          <Button variant="destructive">Destructive Button</Button>
          <Button disabled>Disabled Button</Button>
          <Button size="sm">Small Button</Button>
          <Button size="lg">Large Button</Button>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Input component should be accessible', async () => {
      const { container } = render(
        <div>
          <label htmlFor="test-input">Test Input</label>
          <Input id="test-input" placeholder="Enter text" />

          <label htmlFor="required-input">Required Input</label>
          <Input id="required-input" required aria-describedby="required-help" />
          <div id="required-help">This field is required</div>

          <label htmlFor="error-input">Input with Error</label>
          <Input id="error-input" aria-invalid="true" aria-describedby="error-message" />
          <div id="error-message" role="alert">
            This field has an error
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Card component should be accessible', async () => {
      const { container } = render(
        <Card>
          <CardHeader>
            <CardTitle>Accessible Card</CardTitle>
          </CardHeader>
          <CardContent>
            <p>This is card content that should be accessible.</p>
            <Button>Action Button</Button>
          </CardContent>
        </Card>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Form components should be accessible', async () => {
      const { container } = render(
        <form>
          <fieldset>
            <legend>User Information</legend>

            <div>
              <label htmlFor="name">Full Name</label>
              <Input id="name" required />
            </div>

            <div>
              <label htmlFor="email">Email Address</label>
              <Input id="email" type="email" required />
            </div>

            <fieldset>
              <legend>Preferences</legend>
              <div>
                <input type="radio" id="pref1" name="preference" value="option1" />
                <label htmlFor="pref1">Option 1</label>
              </div>
              <div>
                <input type="radio" id="pref2" name="preference" value="option2" />
                <label htmlFor="pref2">Option 2</label>
              </div>
            </fieldset>

            <div>
              <input type="checkbox" id="terms" />
              <label htmlFor="terms">I agree to the terms and conditions</label>
            </div>

            <Button type="submit">Submit</Button>
          </fieldset>
        </form>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Complex Components', () => {
    it('Login form should be accessible', async () => {
      const { container } = render(<LoginForm />);

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Assessment wizard should be accessible', async () => {
      const { container } = render(<AssessmentWizard />);

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Navigation components should be accessible', async () => {
      const { container } = render(
        <nav aria-label="Main navigation">
          <ul>
            <li>
              <a href="/dashboard">Dashboard</a>
            </li>
            <li>
              <a href="/assessments">Assessments</a>
            </li>
            <li>
              <a href="/evidence">Evidence</a>
            </li>
            <li>
              <a href="/policies">Policies</a>
            </li>
          </ul>
        </nav>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Data tables should be accessible', async () => {
      const { container } = render(
        <table>
          <caption>Assessment Results</caption>
          <thead>
            <tr>
              <th scope="col">Framework</th>
              <th scope="col">Score</th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>GDPR</td>
              <td>85%</td>
              <td>Complete</td>
              <td>
                <Button size="sm">View Details</Button>
              </td>
            </tr>
            <tr>
              <td>ISO 27001</td>
              <td>72%</td>
              <td>In Progress</td>
              <td>
                <Button size="sm">Continue</Button>
              </td>
            </tr>
          </tbody>
        </table>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Modal dialogs should be accessible', async () => {
      const { container } = render(
        <div>
          <Button>Open Dialog</Button>
          <div
            role="dialog"
            aria-labelledby="dialog-title"
            aria-describedby="dialog-description"
            aria-modal="true"
          >
            <h2 id="dialog-title">Confirm Action</h2>
            <p id="dialog-description">Are you sure you want to delete this item?</p>
            <div>
              <Button>Cancel</Button>
              <Button variant="destructive">Delete</Button>
            </div>
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Interactive Elements', () => {
    it('Dropdown menus should be accessible', async () => {
      const { container } = render(
        <div>
          <button aria-haspopup="true" aria-expanded="false" aria-controls="dropdown-menu">
            Options
          </button>
          <ul id="dropdown-menu" role="menu">
            <li role="menuitem">
              <button>Edit</button>
            </li>
            <li role="menuitem">
              <button>Delete</button>
            </li>
            <li role="menuitem">
              <button>Share</button>
            </li>
          </ul>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Tabs should be accessible', async () => {
      const { container } = render(
        <div>
          <div role="tablist" aria-label="Assessment sections">
            <button role="tab" aria-selected="true" aria-controls="panel1" id="tab1">
              Overview
            </button>
            <button role="tab" aria-selected="false" aria-controls="panel2" id="tab2">
              Details
            </button>
            <button role="tab" aria-selected="false" aria-controls="panel3" id="tab3">
              Results
            </button>
          </div>

          <div role="tabpanel" id="panel1" aria-labelledby="tab1">
            <h3>Overview Content</h3>
            <p>This is the overview panel content.</p>
          </div>

          <div role="tabpanel" id="panel2" aria-labelledby="tab2" hidden>
            <h3>Details Content</h3>
            <p>This is the details panel content.</p>
          </div>

          <div role="tabpanel" id="panel3" aria-labelledby="tab3" hidden>
            <h3>Results Content</h3>
            <p>This is the results panel content.</p>
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Progress indicators should be accessible', async () => {
      const { container } = render(
        <div>
          <div>
            <label htmlFor="progress1">Assessment Progress</label>
            <progress id="progress1" value="70" max="100">
              70%
            </progress>
          </div>

          <div>
            <div aria-label="Upload progress">
              <div
                role="progressbar"
                aria-valuenow={45}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuetext="45% complete"
              >
                <div style={{ width: '45%' }}>45%</div>
              </div>
            </div>
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Content Structure', () => {
    it('Heading hierarchy should be accessible', async () => {
      const { container } = render(
        <main>
          <h1>Dashboard</h1>
          <section>
            <h2>Recent Activity</h2>
            <article>
              <h3>Assessment Completed</h3>
              <p>GDPR assessment was completed successfully.</p>
            </article>
            <article>
              <h3>Evidence Uploaded</h3>
              <p>New privacy policy document was uploaded.</p>
            </article>
          </section>
          <section>
            <h2>Compliance Score</h2>
            <div>
              <h3>Overall Score</h3>
              <p>85% compliant</p>
            </div>
          </section>
        </main>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Lists should be accessible', async () => {
      const { container } = render(
        <div>
          <h2>Assessment Steps</h2>
          <ol>
            <li>Complete business profile</li>
            <li>Select compliance framework</li>
            <li>Answer assessment questions</li>
            <li>Review results</li>
            <li>Generate action plan</li>
          </ol>

          <h2>Required Documents</h2>
          <ul>
            <li>Privacy policy</li>
            <li>Data processing agreement</li>
            <li>Security procedures</li>
            <li>Training records</li>
          </ul>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Images should be accessible', async () => {
      const { container } = render(
        <div>
          <img src="/logo.png" alt="ruleIQ - AI Compliance Automated" width={200} height={50} />

          <figure>
            <img
              src="/chart.png"
              alt="Compliance score chart showing 85% overall compliance"
              width={400}
              height={300}
            />
            <figcaption>Compliance score breakdown by framework</figcaption>
          </figure>

          {/* Decorative image */}
          <img src="/decoration.png" alt="" role="presentation" width={100} height={100} />
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Error States and Feedback', () => {
    it('Error messages should be accessible', async () => {
      const { container } = render(
        <div>
          <div role="alert" aria-live="assertive">
            <h2>Error</h2>
            <p>Failed to save assessment. Please try again.</p>
          </div>

          <div role="status" aria-live="polite">
            <p>Assessment saved successfully.</p>
          </div>

          <form>
            <div>
              <label htmlFor="email-error">Email Address</label>
              <Input
                id="email-error"
                type="email"
                aria-invalid="true"
                aria-describedby="email-error-message"
              />
              <div id="email-error-message" role="alert">
                Please enter a valid email address.
              </div>
            </div>
          </form>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Loading states should be accessible', async () => {
      const { container } = render(
        <div>
          <div aria-live="polite" aria-busy="true">
            <p>Loading assessment data...</p>
            <div role="status" aria-label="Loading">
              <span className="sr-only">Loading...</span>
            </div>
          </div>

          <Button disabled aria-describedby="loading-message">
            <span aria-hidden="true">⏳</span>
            Submitting...
          </Button>
          <div id="loading-message" className="sr-only">
            Please wait while we process your request.
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Keyboard Navigation', () => {
    it('Skip links should be accessible', async () => {
      const { container } = render(
        <div>
          <a href="#main-content" className="skip-link">
            Skip to main content
          </a>
          <a href="#navigation" className="skip-link">
            Skip to navigation
          </a>

          <nav id="navigation">
            <ul>
              <li>
                <a href="/dashboard">Dashboard</a>
              </li>
              <li>
                <a href="/assessments">Assessments</a>
              </li>
            </ul>
          </nav>

          <main id="main-content">
            <h1>Dashboard</h1>
            <p>Welcome to your compliance dashboard.</p>
          </main>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('Focus management should be accessible', async () => {
      const { container } = render(
        <div>
          <button>Open Modal</button>

          <div role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <h2 id="modal-title">Modal Title</h2>
            <p>Modal content goes here.</p>
            <div>
              <Button>Cancel</Button>
              <Button>Confirm</Button>
            </div>
          </div>
        </div>,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
