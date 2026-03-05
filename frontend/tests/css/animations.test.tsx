import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { motion, AnimatePresence } from 'framer-motion';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Mock Framer Motion for consistent testing
vi.mock('framer-motion', async () => {
  const actual = (await vi.importActual('framer-motion')) as any;
  return {
    ...actual,
    motion: {
      ...actual.motion,
      div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
      button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
      li: ({ children, ...props }: any) => <li {...props}>{children}</li>,
      ul: ({ children, ...props }: any) => <ul {...props}>{children}</ul>,
    },
  };
});

// Test Components
const FadeInComponent = ({ delay = 0 }: { delay?: number }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ duration: 0.5, delay }}
    data-testid="fade-in"
  >
    Fade In Content
  </motion.div>
);

const SlideInComponent = ({
  direction = 'left',
}: {
  direction?: 'left' | 'right' | 'up' | 'down';
}) => {
  const getInitialPosition = () => {
    switch (direction) {
      case 'left':
        return { x: -100 };
      case 'right':
        return { x: 100 };
      case 'up':
        return { y: -100 };
      case 'down':
        return { y: 100 };
    }
  };

  return (
    <motion.div
      initial={getInitialPosition()}
      animate={{ x: 0, y: 0 }}
      transition={{ type: 'spring', stiffness: 100 }}
      data-testid={`slide-${direction}`}
    >
      Slide In Content
    </motion.div>
  );
};

const ScaleComponent = () => (
  <motion.div
    initial={{ scale: 0 }}
    animate={{ scale: 1 }}
    transition={{ type: 'spring', damping: 15 }}
    data-testid="scale"
  >
    Scale Content
  </motion.div>
);

const StaggeredListComponent = () => {
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <motion.ul variants={container} initial="hidden" animate="show" data-testid="staggered-list">
      {[1, 2, 3, 4].map((i) => (
        <motion.li key={i} variants={item} data-testid={`list-item-${i}`}>
          Item {i}
        </motion.li>
      ))}
    </motion.ul>
  );
};

const HoverAnimationComponent = () => (
  <motion.button
    whileHover={{ scale: 1.05, backgroundColor: '#8B5CF6' }}
    whileTap={{ scale: 0.95 }}
    transition={{ type: 'spring', stiffness: 300 }}
    className="rounded bg-primary px-4 py-2 text-white"
    data-testid="hover-button"
  >
    Hover Me
  </motion.button>
);

const CSSTransitionComponent = () => (
  <div>
    <button
      className="hover:bg-primary-dark transition-all duration-300 ease-in-out hover:scale-105"
      data-testid="css-transition-button"
    >
      CSS Transition Button
    </button>
    <div className="transition-colors duration-200 hover:text-purple" data-testid="color-transition">
      Color Transition
    </div>
    <div
      className="transition-transform duration-500 hover:translate-x-2"
      data-testid="transform-transition"
    >
      Transform Transition
    </div>
  </div>
);

const ComplexAnimationComponent = () => {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div>
      <button onClick={() => setIsOpen(!isOpen)} data-testid="toggle-button">
        Toggle
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            data-testid="collapsible-content"
          >
            <div className="bg-gray-100 p-4">Collapsible Content</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const ScrollTriggeredComponent = () => {
  const ref = React.useRef(null);
  const [isVisible, setIsVisible] = React.useState(false);

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.1 },
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current);
      }
    };
  }, []);

  return (
    <div ref={ref} data-testid="scroll-container">
      <motion.div
        initial={{ opacity: 0, y: 50 }}
        animate={isVisible ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.6 }}
        data-testid="scroll-animated"
      >
        Scroll Triggered Content
      </motion.div>
    </div>
  );
};

const PerformanceTestComponent = () => {
  const [count, setCount] = React.useState(0);

  return (
    <div>
      <button onClick={() => setCount((c) => c + 1)} data-testid="increment">
        Add Item
      </button>
      <div data-testid="items-container">
        {Array.from({ length: count }, (_, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
            className="m-1 bg-gray-100 p-2"
            data-testid={`perf-item-${i}`}
          >
            Item {i + 1}
          </motion.div>
        ))}
      </div>
    </div>
  );
};

// Import React
import React from 'react';

describe('Animation and Transition Tests', () => {
  describe('Framer Motion Animations', () => {
    it('should handle fade in animations', async () => {
      const { rerender } = render(<FadeInComponent />);
      const element = screen.getByTestId('fade-in');

      expect(element).toBeInTheDocument();
      expect(element).toHaveTextContent('Fade In Content');

      // Test with delay
      rerender(<FadeInComponent delay={0.5} />);
      expect(element).toBeInTheDocument();
    });

    it('should handle slide animations from different directions', () => {
      const directions = ['left', 'right', 'up', 'down'] as const;

      directions.forEach((direction) => {
        const { container } = render(<SlideInComponent direction={direction} />);
        const element = container.querySelector(`[data-testid="slide-${direction}"]`);
        expect(element).toBeInTheDocument();
        expect(element).toHaveTextContent('Slide In Content');
      });
    });

    it('should handle scale animations', () => {
      render(<ScaleComponent />);
      const element = screen.getByTestId('scale');

      expect(element).toBeInTheDocument();
      expect(element).toHaveTextContent('Scale Content');
    });

    it('should handle staggered animations', () => {
      render(<StaggeredListComponent />);

      const list = screen.getByTestId('staggered-list');
      expect(list).toBeInTheDocument();

      const items = screen.getAllByTestId(/list-item-/);
      expect(items).toHaveLength(4);
      items.forEach((item, index) => {
        expect(item).toHaveTextContent(`Item ${index + 1}`);
      });
    });

    it('should handle complex animations with AnimatePresence', async () => {
      const user = userEvent.setup();
      render(<ComplexAnimationComponent />);

      const toggleButton = screen.getByTestId('toggle-button');
      expect(screen.queryByTestId('collapsible-content')).not.toBeInTheDocument();

      // Open
      await user.click(toggleButton);
      await waitFor(() => {
        expect(screen.getByTestId('collapsible-content')).toBeInTheDocument();
      });

      // Close
      await user.click(toggleButton);
      await waitFor(() => {
        expect(screen.queryByTestId('collapsible-content')).not.toBeInTheDocument();
      });
    });

    it('should handle gesture animations with whileHover and whileTap', async () => {
      const user = userEvent.setup();
      render(<HoverAnimationComponent />);

      const button = screen.getByTestId('hover-button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('bg-primary', 'text-white');

      // Hover
      await user.hover(button);

      // Click (tap)
      await user.click(button);
    });
  });

  describe('CSS Transitions', () => {
    it('should apply transition classes correctly', () => {
      const { container } = render(<CSSTransitionComponent />);

      const button = screen.getByTestId('css-transition-button');
      expect(button).toHaveClass('transition-all');
      expect(button).toHaveClass('duration-300');
      expect(button).toHaveClass('ease-in-out');
      expect(button).toHaveClass('hover:scale-105');
      expect(button).toHaveClass('hover:bg-primary-dark');

      const colorDiv = screen.getByTestId('color-transition');
      expect(colorDiv).toHaveClass('transition-colors');
      expect(colorDiv).toHaveClass('duration-200');
      expect(colorDiv).toHaveClass('hover:text-purple');

      const transformDiv = screen.getByTestId('transform-transition');
      expect(transformDiv).toHaveClass('transition-transform');
      expect(transformDiv).toHaveClass('duration-500');
      expect(transformDiv).toHaveClass('hover:translate-x-2');
    });

    it('should handle multiple transition properties', () => {
      const { container } = render(
        <div>
          <div className="transition duration-300">All Properties</div>
          <div className="transition-[opacity,transform] duration-500">Specific Properties</div>
          <div className="transition-none">No Transition</div>
        </div>,
      );

      expect(container.querySelector('.transition')).toBeInTheDocument();
      expect(container.querySelector('.transition-\\[opacity\\,transform\\]')).toBeInTheDocument();
      expect(container.querySelector('.transition-none')).toBeInTheDocument();
    });

    it('should handle different timing functions', () => {
      const { container } = render(
        <div>
          <div className="transition ease-linear">Linear</div>
          <div className="transition ease-in">Ease In</div>
          <div className="transition ease-out">Ease Out</div>
          <div className="transition ease-in-out">Ease In Out</div>
          <div className="transition-timing-function-[cubic-bezier(0.4,0,0.2,1)]">Custom</div>
        </div>,
      );

      expect(container.querySelector('.ease-linear')).toBeInTheDocument();
      expect(container.querySelector('.ease-in')).toBeInTheDocument();
      expect(container.querySelector('.ease-out')).toBeInTheDocument();
      expect(container.querySelector('.ease-in-out')).toBeInTheDocument();
    });
  });

  describe('Hover States and Interactive Animations', () => {
    it('should handle hover state classes', () => {
      const { container } = render(
        <div>
          <button className="hover:bg-primary-dark hover:text-gold hover:shadow-lg">
            Hover Button
          </button>
          <div className="group">
            <div className="group-hover:scale-105 group-hover:text-primary">Group Hover</div>
          </div>
        </div>,
      );

      const button = container.querySelector('button');
      expect(button).toHaveClass('hover:bg-primary-dark');
      expect(button).toHaveClass('hover:text-gold');
      expect(button).toHaveClass('hover:shadow-lg');

      const groupHover = container.querySelector('.group-hover\\:scale-105');
      expect(groupHover).toBeInTheDocument();
      expect(groupHover).toHaveClass('group-hover:text-primary');
    });

    it('should handle focus and active states', () => {
      const { container } = render(
        <button className="active:bg-primary-light focus:outline-none focus:ring-2 focus:ring-primary active:scale-95">
          Interactive Button
        </button>,
      );

      const button = container.querySelector('button');
      expect(button).toHaveClass('focus:outline-none');
      expect(button).toHaveClass('focus:ring-2');
      expect(button).toHaveClass('focus:ring-primary');
      expect(button).toHaveClass('active:scale-95');
      expect(button).toHaveClass('active:bg-primary-light');
    });

    it('should handle disabled state animations', () => {
      const { container } = render(
        <button
          disabled
          className="transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
        >
          Disabled Button
        </button>,
      );

      const button = container.querySelector('button');
      expect(button).toBeDisabled();
      expect(button).toHaveClass('disabled:opacity-50');
      expect(button).toHaveClass('disabled:cursor-not-allowed');
    });
  });

  describe('Animation Performance', () => {
    it('should handle multiple animated items efficiently', async () => {
      const user = userEvent.setup();
      render(<PerformanceTestComponent />);

      const incrementButton = screen.getByTestId('increment');
      const container = screen.getByTestId('items-container');

      // Add multiple items
      for (let i = 0; i < 5; i++) {
        await user.click(incrementButton);
      }

      await waitFor(() => {
        const items = container.querySelectorAll('[data-testid^="perf-item-"]');
        expect(items).toHaveLength(5);
      });
    });

    it('should use GPU-accelerated properties', () => {
      const { container } = render(
        <div>
          <div className="translate-x-4 translate-y-4 transform">Transform</div>
          <div className="opacity-50">Opacity</div>
          <div className="scale-110">Scale</div>
          <div className="rotate-45">Rotate</div>
        </div>,
      );

      // These properties trigger GPU acceleration
      expect(container.querySelector('.transform')).toBeInTheDocument();
      expect(container.querySelector('.opacity-50')).toBeInTheDocument();
      expect(container.querySelector('.scale-110')).toBeInTheDocument();
      expect(container.querySelector('.rotate-45')).toBeInTheDocument();
    });

    it('should handle will-change property', () => {
      const { container } = render(
        <div>
          <div className="will-change-transform">Will Change Transform</div>
          <div className="will-change-opacity">Will Change Opacity</div>
          <div className="will-change-auto">Will Change Auto</div>
        </div>,
      );

      expect(container.querySelector('.will-change-transform')).toBeInTheDocument();
      expect(container.querySelector('.will-change-opacity')).toBeInTheDocument();
      expect(container.querySelector('.will-change-auto')).toBeInTheDocument();
    });
  });

  describe('Scroll-Triggered Animations', () => {
    beforeEach(() => {
      // Mock IntersectionObserver
      global.IntersectionObserver = vi.fn().mockImplementation((callback) => ({
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn(),
      }));
    });

    it('should handle scroll-triggered animations', () => {
      render(<ScrollTriggeredComponent />);

      const container = screen.getByTestId('scroll-container');
      const animatedContent = screen.getByTestId('scroll-animated');

      expect(container).toBeInTheDocument();
      expect(animatedContent).toBeInTheDocument();
      expect(animatedContent).toHaveTextContent('Scroll Triggered Content');
    });
  });

  describe('Animation Utilities', () => {
    it('should handle animation delay utilities', () => {
      const { container } = render(
        <div>
          <div className="animate-fade-in delay-100">Delay 100ms</div>
          <div className="animate-fade-in delay-200">Delay 200ms</div>
          <div className="animate-fade-in delay-500">Delay 500ms</div>
          <div className="animate-fade-in delay-1000">Delay 1000ms</div>
        </div>,
      );

      expect(container.querySelector('.delay-100')).toBeInTheDocument();
      expect(container.querySelector('.delay-200')).toBeInTheDocument();
      expect(container.querySelector('.delay-500')).toBeInTheDocument();
      expect(container.querySelector('.delay-1000')).toBeInTheDocument();
    });

    it('should handle animation duration utilities', () => {
      const { container } = render(
        <div>
          <div className="animate-pulse duration-75">Duration 75ms</div>
          <div className="animate-pulse duration-200">Duration 200ms</div>
          <div className="animate-pulse duration-500">Duration 500ms</div>
          <div className="animate-pulse duration-1000">Duration 1000ms</div>
        </div>,
      );

      expect(container.querySelector('.duration-75')).toBeInTheDocument();
      expect(container.querySelector('.duration-200')).toBeInTheDocument();
      expect(container.querySelector('.duration-500')).toBeInTheDocument();
      expect(container.querySelector('.duration-1000')).toBeInTheDocument();
    });
  });
});
