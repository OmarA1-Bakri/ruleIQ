import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  duration,
  easing,
  variants,
  transitions,
  animationClasses,
  animationVars,
  shouldReduceMotion,
  createAnimationProps,
  staggerDelay,
} from '@/lib/styles/animations';

// ============================================================================
// duration constants
// ============================================================================

describe('duration', () => {
  it('has instant = 0', () => {
    expect(duration.instant).toBe(0);
  });

  it('has fast = 150', () => {
    expect(duration.fast).toBe(150);
  });

  it('has normal = 250', () => {
    expect(duration.normal).toBe(250);
  });

  it('has slow = 500', () => {
    expect(duration.slow).toBe(500);
  });

  it('has slower = 750', () => {
    expect(duration.slower).toBe(750);
  });

  it('has slowest = 1000', () => {
    expect(duration.slowest).toBe(1000);
  });

  it('values are in ascending order', () => {
    expect(duration.instant).toBeLessThan(duration.fast);
    expect(duration.fast).toBeLessThan(duration.normal);
    expect(duration.normal).toBeLessThan(duration.slow);
    expect(duration.slow).toBeLessThan(duration.slower);
    expect(duration.slower).toBeLessThan(duration.slowest);
  });
});

// ============================================================================
// easing constants
// ============================================================================

describe('easing', () => {
  it('has linear = "linear"', () => {
    expect(easing.linear).toBe('linear');
  });

  it('has ease = "ease"', () => {
    expect(easing.ease).toBe('ease');
  });

  it('has easeIn, easeOut, easeInOut', () => {
    expect(easing.easeIn).toBe('ease-in');
    expect(easing.easeOut).toBe('ease-out');
    expect(easing.easeInOut).toBe('ease-in-out');
  });

  it('spring contains cubic-bezier', () => {
    expect(easing.spring).toContain('cubic-bezier');
  });

  it('bounce contains cubic-bezier', () => {
    expect(easing.bounce).toContain('cubic-bezier');
  });

  it('smooth contains cubic-bezier', () => {
    expect(easing.smooth).toContain('cubic-bezier');
  });

  it('snappy contains cubic-bezier', () => {
    expect(easing.snappy).toContain('cubic-bezier');
  });
});

// ============================================================================
// variants
// ============================================================================

describe('variants.fadeIn', () => {
  it('has initial opacity 0', () => {
    expect(variants.fadeIn.initial.opacity).toBe(0);
  });

  it('has animate opacity 1', () => {
    expect(variants.fadeIn.animate.opacity).toBe(1);
  });

  it('has exit opacity 0', () => {
    expect(variants.fadeIn.exit.opacity).toBe(0);
  });
});

describe('variants.slideUp', () => {
  it('has initial y: 20 and opacity 0', () => {
    expect((variants.slideUp.initial as any).y).toBe(20);
    expect(variants.slideUp.initial.opacity).toBe(0);
  });

  it('has animate y: 0 and opacity 1', () => {
    expect((variants.slideUp.animate as any).y).toBe(0);
    expect(variants.slideUp.animate.opacity).toBe(1);
  });
});

describe('variants.slideDown', () => {
  it('has initial y: -20', () => {
    expect((variants.slideDown.initial as any).y).toBe(-20);
  });

  it('has animate y: 0', () => {
    expect((variants.slideDown.animate as any).y).toBe(0);
  });
});

describe('variants.slideLeft', () => {
  it('has initial x: 20', () => {
    expect((variants.slideLeft.initial as any).x).toBe(20);
  });

  it('has animate x: 0', () => {
    expect((variants.slideLeft.animate as any).x).toBe(0);
  });
});

describe('variants.slideRight', () => {
  it('has initial x: -20', () => {
    expect((variants.slideRight.initial as any).x).toBe(-20);
  });
});

describe('variants.scaleIn', () => {
  it('has initial scale: 0.9', () => {
    expect((variants.scaleIn.initial as any).scale).toBe(0.9);
  });

  it('has animate scale: 1', () => {
    expect((variants.scaleIn.animate as any).scale).toBe(1);
  });
});

describe('variants.container', () => {
  it('has staggerChildren in animate transition', () => {
    const transition = (variants.container.animate as any).transition;
    expect(transition.staggerChildren).toBe(0.1);
  });

  it('has delayChildren in animate transition', () => {
    const transition = (variants.container.animate as any).transition;
    expect(transition.delayChildren).toBe(0.2);
  });
});

describe('variants.item', () => {
  it('has initial opacity 0 and y: 20', () => {
    expect(variants.item.initial.opacity).toBe(0);
    expect((variants.item.initial as any).y).toBe(20);
  });

  it('has animate opacity 1 and y: 0', () => {
    expect(variants.item.animate.opacity).toBe(1);
    expect((variants.item.animate as any).y).toBe(0);
  });
});

// ============================================================================
// transitions
// ============================================================================

describe('transitions', () => {
  it('base includes transition-all', () => {
    expect(transitions.base).toContain('transition-all');
  });

  it('colors includes transition-colors', () => {
    expect(transitions.colors).toContain('transition-colors');
  });

  it('opacity includes transition-opacity', () => {
    expect(transitions.opacity).toContain('transition-opacity');
  });

  it('transform includes transition-transform', () => {
    expect(transitions.transform).toContain('transition-transform');
  });

  it('fast includes duration-150', () => {
    expect(transitions.fast).toContain('duration-150');
  });

  it('slow includes duration-500', () => {
    expect(transitions.slow).toContain('duration-500');
  });
});

// ============================================================================
// animationClasses
// ============================================================================

describe('animationClasses', () => {
  it('has animate-in class', () => {
    expect(animationClasses['animate-in']).toBe('animate-in');
  });

  it('has fade-in class', () => {
    expect(animationClasses['fade-in']).toBe('fade-in');
  });

  it('has animate-out class', () => {
    expect(animationClasses['animate-out']).toBe('animate-out');
  });

  it('has fade-out class', () => {
    expect(animationClasses['fade-out']).toBe('fade-out');
  });

  it('has zoom-in class', () => {
    expect(animationClasses['zoom-in']).toContain('zoom-in');
  });

  it('has zoom-out class', () => {
    expect(animationClasses['zoom-out']).toContain('zoom-out');
  });
});

// ============================================================================
// animationVars
// ============================================================================

describe('animationVars', () => {
  it('has --animation-duration', () => {
    expect(animationVars['--animation-duration']).toBeDefined();
    expect(animationVars['--animation-duration']).toContain('ms');
  });

  it('has --animation-easing', () => {
    expect(animationVars['--animation-easing']).toBeDefined();
    expect(animationVars['--animation-easing']).toContain('cubic-bezier');
  });
});

// ============================================================================
// shouldReduceMotion
// ============================================================================

describe('shouldReduceMotion', () => {
  it('returns false when matchMedia does not prefer reduced motion', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    expect(shouldReduceMotion()).toBe(false);
  });

  it('returns true when matchMedia prefers reduced motion', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    expect(shouldReduceMotion()).toBe(true);
  });
});

// ============================================================================
// createAnimationProps
// ============================================================================

describe('createAnimationProps', () => {
  beforeEach(() => {
    // Default: no reduced motion
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it('returns variant props for normal motion', () => {
    const props = createAnimationProps('fadeIn');
    expect(props.initial).toBeDefined();
    expect(props.animate).toBeDefined();
  });

  it('uses default duration when none provided', () => {
    const props = createAnimationProps('fadeIn');
    expect((props as any).transition.duration).toBe(duration.normal / 1000);
  });

  it('uses custom duration when provided', () => {
    const props = createAnimationProps('fadeIn', 500);
    expect((props as any).transition.duration).toBe(500 / 1000);
  });

  it('when reduced motion: initial is false and duration is 0', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    const props = createAnimationProps('fadeIn');
    expect(props.initial).toBe(false);
    expect((props as any).transition.duration).toBe(0);
  });
});

// ============================================================================
// staggerDelay
// ============================================================================

describe('staggerDelay', () => {
  beforeEach(() => {
    // Default: no reduced motion
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it('returns 0 for index 0', () => {
    expect(staggerDelay(0)).toBe(0);
  });

  it('returns baseDelay for index 1 with default baseDelay', () => {
    expect(staggerDelay(1)).toBe(50);
  });

  it('returns index * baseDelay', () => {
    expect(staggerDelay(3, 100)).toBe(300);
  });

  it('returns 0 for any index when reduced motion', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    expect(staggerDelay(5)).toBe(0);
    expect(staggerDelay(10, 200)).toBe(0);
  });
});
