import { describe, it, expect } from 'vitest';
import {
  fadeIn,
  fadeInUp,
  fadeInDown,
  scaleIn,
  scaleHover,
  slideInRight,
  slideInLeft,
  staggerContainer,
  staggerItem,
  cardHover,
  buttonPress,
  buttonGlow,
  pageTransition,
  modalOverlay,
  modalContent,
  shimmer,
  notificationSlide,
  progressBar,
  rotate360,
  accordionContent,
  tabContent,
  floating,
  pulse,
  shake,
} from '@/lib/animations/variants';

// ============================================================================
// Fade variants
// ============================================================================

describe('fadeIn', () => {
  it('has hidden state with opacity 0', () => {
    expect((fadeIn.hidden as any).opacity).toBe(0);
  });

  it('has visible state with opacity 1', () => {
    expect((fadeIn.visible as any).opacity).toBe(1);
  });

  it('has exit state', () => {
    expect(fadeIn.exit).toBeDefined();
    expect((fadeIn.exit as any).opacity).toBe(0);
  });
});

describe('fadeInUp', () => {
  it('has hidden state with y: 20', () => {
    expect((fadeInUp.hidden as any).y).toBe(20);
  });

  it('has visible state with y: 0', () => {
    expect((fadeInUp.visible as any).y).toBe(0);
  });

  it('has visible state with opacity 1', () => {
    expect((fadeInUp.visible as any).opacity).toBe(1);
  });
});

describe('fadeInDown', () => {
  it('has hidden state with y: -20', () => {
    expect((fadeInDown.hidden as any).y).toBe(-20);
  });

  it('has visible state with y: 0', () => {
    expect((fadeInDown.visible as any).y).toBe(0);
  });
});

// ============================================================================
// Scale variants
// ============================================================================

describe('scaleIn', () => {
  it('has hidden state with scale: 0.8', () => {
    expect((scaleIn.hidden as any).scale).toBe(0.8);
  });

  it('has visible state with scale: 1', () => {
    expect((scaleIn.visible as any).scale).toBe(1);
  });

  it('has exit state', () => {
    expect(scaleIn.exit).toBeDefined();
  });
});

describe('scaleHover', () => {
  it('has initial state with scale: 1', () => {
    expect((scaleHover.initial as any).scale).toBe(1);
  });

  it('has hover state with scale: 1.05', () => {
    expect((scaleHover.hover as any).scale).toBe(1.05);
  });

  it('has tap state with scale: 0.95', () => {
    expect((scaleHover.tap as any).scale).toBe(0.95);
  });
});

// ============================================================================
// Slide variants
// ============================================================================

describe('slideInRight', () => {
  it('has hidden state starting from x: 100', () => {
    expect((slideInRight.hidden as any).x).toBe(100);
  });

  it('has visible state at x: 0', () => {
    expect((slideInRight.visible as any).x).toBe(0);
  });
});

describe('slideInLeft', () => {
  it('has hidden state starting from x: -100', () => {
    expect((slideInLeft.hidden as any).x).toBe(-100);
  });

  it('has visible state at x: 0', () => {
    expect((slideInLeft.visible as any).x).toBe(0);
  });
});

// ============================================================================
// Stagger variants
// ============================================================================

describe('staggerContainer', () => {
  it('has staggerChildren in visible transition', () => {
    const transition = (staggerContainer.visible as any)?.transition;
    expect(transition?.staggerChildren).toBe(0.1);
  });

  it('has delayChildren in visible transition', () => {
    const transition = (staggerContainer.visible as any)?.transition;
    expect(transition?.delayChildren).toBe(0.2);
  });
});

describe('staggerItem', () => {
  it('has hidden state with opacity 0', () => {
    expect((staggerItem.hidden as any).opacity).toBe(0);
  });

  it('has visible state with opacity 1', () => {
    expect((staggerItem.visible as any).opacity).toBe(1);
  });
});

// ============================================================================
// Button variants
// ============================================================================

describe('buttonPress', () => {
  it('has initial scale of 1', () => {
    expect((buttonPress.initial as any).scale).toBe(1);
  });

  it('has hover scale > 1', () => {
    expect((buttonPress.hover as any).scale).toBeGreaterThan(1);
  });

  it('has tap scale < 1', () => {
    expect((buttonPress.tap as any).scale).toBeLessThan(1);
  });
});

describe('buttonGlow', () => {
  it('has initial state', () => {
    expect(buttonGlow.initial).toBeDefined();
  });

  it('has hover state', () => {
    expect(buttonGlow.hover).toBeDefined();
  });
});

// ============================================================================
// Card variants
// ============================================================================

describe('cardHover', () => {
  it('has initial scale of 1', () => {
    expect((cardHover.initial as any).scale).toBe(1);
  });

  it('has hover scale > 1', () => {
    expect((cardHover.hover as any).scale).toBeGreaterThan(1);
  });

  it('has tap scale < 1', () => {
    expect((cardHover.tap as any).scale).toBeLessThan(1);
  });
});

// ============================================================================
// Page transitions
// ============================================================================

describe('pageTransition', () => {
  it('has initial state with opacity 0', () => {
    expect((pageTransition.initial as any).opacity).toBe(0);
  });

  it('has animate state with opacity 1', () => {
    expect((pageTransition.animate as any).opacity).toBe(1);
  });

  it('has exit state', () => {
    expect(pageTransition.exit).toBeDefined();
  });
});

// ============================================================================
// Modal variants
// ============================================================================

describe('modalOverlay', () => {
  it('starts hidden with opacity 0', () => {
    expect((modalOverlay.hidden as any).opacity).toBe(0);
  });

  it('becomes visible with opacity 1', () => {
    expect((modalOverlay.visible as any).opacity).toBe(1);
  });
});

describe('modalContent', () => {
  it('starts hidden with scale < 1', () => {
    expect((modalContent.hidden as any).scale).toBeLessThan(1);
  });

  it('becomes visible with scale: 1', () => {
    expect((modalContent.visible as any).scale).toBe(1);
  });

  it('has exit state', () => {
    expect(modalContent.exit).toBeDefined();
  });
});

// ============================================================================
// Shimmer
// ============================================================================

describe('shimmer', () => {
  it('has initial state with x: -100%', () => {
    expect((shimmer.initial as any).x).toBe('-100%');
  });

  it('has animate state with x: 100%', () => {
    expect((shimmer.animate as any).x).toBe('100%');
  });

  it('repeats infinitely', () => {
    const transition = (shimmer.animate as any)?.transition;
    expect(transition?.repeat).toBe(Infinity);
  });
});

// ============================================================================
// Notification
// ============================================================================

describe('notificationSlide', () => {
  it('starts with x: 300 and opacity 0', () => {
    expect((notificationSlide.initial as any).x).toBe(300);
    expect((notificationSlide.initial as any).opacity).toBe(0);
  });

  it('animates to x: 0 and opacity 1', () => {
    expect((notificationSlide.animate as any).x).toBe(0);
    expect((notificationSlide.animate as any).opacity).toBe(1);
  });
});

// ============================================================================
// Progress bar
// ============================================================================

describe('progressBar', () => {
  it('has initial state with scaleX: 0', () => {
    expect((progressBar.initial as any).scaleX).toBe(0);
  });

  it('animate is a function', () => {
    expect(typeof progressBar.animate).toBe('function');
  });

  it('animate function returns scaleX equal to progress', () => {
    const result = (progressBar.animate as Function)(0.75);
    expect(result.scaleX).toBe(0.75);
  });
});

// ============================================================================
// Rotate, Accordion, Tab, Floating, Pulse, Shake
// ============================================================================

describe('rotate360', () => {
  it('has animate state that rotates 360', () => {
    expect((rotate360.animate as any).rotate).toBe(360);
  });

  it('repeats infinitely', () => {
    const transition = (rotate360.animate as any)?.transition;
    expect(transition?.repeat).toBe(Infinity);
  });
});

describe('accordionContent', () => {
  it('has closed state with height: 0', () => {
    expect((accordionContent.closed as any).height).toBe(0);
  });

  it('has open state with height: auto', () => {
    expect((accordionContent.open as any).height).toBe('auto');
  });
});

describe('tabContent', () => {
  it('has hidden state with opacity 0', () => {
    expect((tabContent.hidden as any).opacity).toBe(0);
  });

  it('has visible state with opacity 1', () => {
    expect((tabContent.visible as any).opacity).toBe(1);
  });
});

describe('floating', () => {
  it('has animate state with y array', () => {
    expect(Array.isArray((floating.animate as any).y)).toBe(true);
    expect((floating.animate as any).y).toHaveLength(3);
  });
});

describe('pulse', () => {
  it('has animate state with scale array', () => {
    expect(Array.isArray((pulse.animate as any).scale)).toBe(true);
  });

  it('has animate state with opacity array', () => {
    expect(Array.isArray((pulse.animate as any).opacity)).toBe(true);
  });
});

describe('shake', () => {
  it('has initial state with x: 0', () => {
    expect((shake.initial as any).x).toBe(0);
  });

  it('has shake state with x array', () => {
    expect(Array.isArray((shake.shake as any).x)).toBe(true);
    expect((shake.shake as any).x[4]).toBe(0); // ends at rest
  });
});
