import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ThemeUtils, useThemeClasses } from '@/lib/theme-utils';

// ============================================================================
// ThemeUtils.isDarkMode
// ============================================================================

describe('ThemeUtils.isDarkMode', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
  });

  it('returns false when dark class is absent', () => {
    expect(ThemeUtils.isDarkMode()).toBe(false);
  });

  it('returns true when dark class is present', () => {
    document.documentElement.classList.add('dark');
    expect(ThemeUtils.isDarkMode()).toBe(true);
  });

  it('returns false after dark class is removed', () => {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('dark');
    expect(ThemeUtils.isDarkMode()).toBe(false);
  });
});

// ============================================================================
// ThemeUtils.getThemeClasses
// ============================================================================

describe('ThemeUtils.getThemeClasses', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
  });

  it('returns root class neural-purple', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.root).toBe('neural-purple');
  });

  it('returns light background in light mode', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.background).toBe('bg-gray-50');
  });

  it('returns dark background in dark mode', () => {
    document.documentElement.classList.add('dark');
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.background).toBe('bg-gray-900');
  });

  it('returns light surface in light mode', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.surface).toBe('bg-white');
  });

  it('returns dark surface in dark mode', () => {
    document.documentElement.classList.add('dark');
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.surface).toBe('bg-gray-800');
  });

  it('returns light text in light mode', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.text).toBe('text-gray-900');
  });

  it('returns dark text in dark mode', () => {
    document.documentElement.classList.add('dark');
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.text).toBe('text-gray-100');
  });

  it('includes primary class', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.primary).toContain('bg-purple-600');
  });

  it('includes accent class', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.accent).toContain('purple');
  });

  it('returns light border in light mode', () => {
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.border).toBe('border-gray-200');
  });

  it('returns dark border in dark mode', () => {
    document.documentElement.classList.add('dark');
    const classes = ThemeUtils.getThemeClasses();
    expect(classes.border).toBe('border-gray-700');
  });
});

// ============================================================================
// ThemeUtils.toggleDarkMode
// ============================================================================

describe('ThemeUtils.toggleDarkMode', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
    localStorage.clear();
  });

  it('adds dark class when not currently dark', () => {
    ThemeUtils.toggleDarkMode();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('removes dark class when currently dark', () => {
    document.documentElement.classList.add('dark');
    ThemeUtils.toggleDarkMode();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('saves "dark" to localStorage when enabling dark mode', () => {
    ThemeUtils.toggleDarkMode();
    expect(localStorage.getItem('ruleiq-theme-mode')).toBe('dark');
  });

  it('saves "light" to localStorage when disabling dark mode', () => {
    document.documentElement.classList.add('dark');
    ThemeUtils.toggleDarkMode();
    expect(localStorage.getItem('ruleiq-theme-mode')).toBe('light');
  });
});

// ============================================================================
// ThemeUtils.initializeTheme
// ============================================================================

describe('ThemeUtils.initializeTheme', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
    localStorage.clear();
  });

  it('adds dark class when localStorage has "dark"', () => {
    localStorage.setItem('ruleiq-theme-mode', 'dark');
    ThemeUtils.initializeTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('removes dark class when localStorage has "light"', () => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('ruleiq-theme-mode', 'light');
    ThemeUtils.initializeTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('removes dark class when localStorage is empty', () => {
    document.documentElement.classList.add('dark');
    ThemeUtils.initializeTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});

// ============================================================================
// ThemeUtils.getThemeColors
// ============================================================================

describe('ThemeUtils.getThemeColors', () => {
  it('returns an object with primary color', () => {
    const colors = ThemeUtils.getThemeColors();
    expect(colors.primary).toBeDefined();
    expect(typeof colors.primary).toBe('string');
  });

  it('returns semantic colors (success, error, warning, info)', () => {
    const colors = ThemeUtils.getThemeColors();
    expect(colors.success).toBeDefined();
    expect(colors.error).toBeDefined();
    expect(colors.warning).toBeDefined();
    expect(colors.info).toBeDefined();
  });

  it('returns background and surface colors', () => {
    const colors = ThemeUtils.getThemeColors();
    expect(colors.background).toBeDefined();
    expect(colors.surface).toBeDefined();
  });

  it('returns text and border colors', () => {
    const colors = ThemeUtils.getThemeColors();
    expect(colors.text).toBeDefined();
    expect(colors.border).toBeDefined();
  });

  it('returns secondary and accent colors', () => {
    const colors = ThemeUtils.getThemeColors();
    expect(colors.secondary).toBeDefined();
    expect(colors.secondaryLight).toBeDefined();
    expect(colors.secondaryDark).toBeDefined();
  });
});

// ============================================================================
// ThemeUtils.getGradients
// ============================================================================

describe('ThemeUtils.getGradients', () => {
  it('returns a purple gradient string', () => {
    const gradients = ThemeUtils.getGradients();
    expect(typeof gradients.purple).toBe('string');
    expect(gradients.purple).toContain('gradient');
  });

  it('returns a silver gradient string', () => {
    const gradients = ThemeUtils.getGradients();
    expect(typeof gradients.silver).toBe('string');
    expect(gradients.silver).toContain('gradient');
  });

  it('returns a radial gradient string', () => {
    const gradients = ThemeUtils.getGradients();
    expect(typeof gradients.radial).toBe('string');
    expect(gradients.radial).toContain('radial-gradient');
  });

  it('purple gradient contains hex color codes', () => {
    const gradients = ThemeUtils.getGradients();
    expect(gradients.purple).toContain('#');
  });
});

// ============================================================================
// ThemeUtils.getThemeConfig
// ============================================================================

describe('ThemeUtils.getThemeConfig', () => {
  it('returns a config object with colors', () => {
    const config = ThemeUtils.getThemeConfig();
    expect(config).toHaveProperty('colors');
  });

  it('has primary, accent, semantic, neutral color groups', () => {
    const config = ThemeUtils.getThemeConfig();
    expect(config.colors).toHaveProperty('primary');
    expect(config.colors).toHaveProperty('accent');
    expect(config.colors).toHaveProperty('semantic');
    expect(config.colors).toHaveProperty('neutral');
  });
});

// ============================================================================
// useThemeClasses
// ============================================================================

describe('useThemeClasses', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
    localStorage.clear();
  });

  it('returns isDarkMode boolean', () => {
    const result = useThemeClasses();
    expect(typeof result.isDarkMode).toBe('boolean');
  });

  it('returns false for isDarkMode in light mode', () => {
    const result = useThemeClasses();
    expect(result.isDarkMode).toBe(false);
  });

  it('returns true for isDarkMode in dark mode', () => {
    document.documentElement.classList.add('dark');
    const result = useThemeClasses();
    expect(result.isDarkMode).toBe(true);
  });

  it('returns classes object', () => {
    const result = useThemeClasses();
    expect(result.classes).toBeDefined();
    expect(typeof result.classes.root).toBe('string');
  });

  it('returns colors object', () => {
    const result = useThemeClasses();
    expect(result.colors).toBeDefined();
    expect(result.colors.primary).toBeDefined();
  });

  it('returns gradients object', () => {
    const result = useThemeClasses();
    expect(result.gradients).toBeDefined();
    expect(typeof result.gradients.purple).toBe('string');
  });

  it('exposes toggleDarkMode as a function', () => {
    const result = useThemeClasses();
    expect(typeof result.toggleDarkMode).toBe('function');
  });
});
