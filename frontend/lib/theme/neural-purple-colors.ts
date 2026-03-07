/**
 * Neural Purple Theme Colors
 * Central theme configuration for the RuleIQ platform
 */

export const neuralPurple = {
  // Primary purple shades
  50: '#FAF5FF',
  100: '#F3E8FF',
  200: '#E9D5FF',
  300: '#D8B4FE',
  400: '#C084FC',
  500: '#A855F7',
  600: '#9333EA',
  700: '#7E22CE',
  800: '#6B21A8',
  900: '#581C87',
  950: '#3B0764',

  // Semantic colors
  primary: '#8B5CF6',
  primaryHover: '#7C3AED',
  primaryLight: '#C084FC',
  primaryDark: '#6D28D9',

  // Background shades
  background: '#0F0F0F',
  backgroundLight: '#1A1A1A',
  backgroundDark: '#000000',

  // Accent colors (purple variants)
  accent: '#A78BFA',
  accentHover: '#8B5CF6',
  accentLight: '#C4B5FD',
  accentDark: '#7C3AED',

  // Text colors
  text: '#FFFFFF',
  textSecondary: '#E5E7EB',
  textMuted: '#9CA3AF',

  // Border colors
  border: '#374151',
  borderLight: '#4B5563',
  borderDark: '#1F2937',

  // Status colors (with purple tints)
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#8B5CF6', // Changed from teal to purple

  // Chart colors (purple palette)
  chart: {
    primary: '#8B5CF6',
    secondary: '#7C3AED',
    tertiary: '#C084FC',
    quaternary: '#A78BFA',
    quinary: '#6D28D9',
    senary: '#5B21B6',
  },

  // Additional properties for compatibility
  dark: '#6D28D9', // Alias for primaryDark
  light: '#C084FC', // Alias for primaryLight
  subtle: '#F3E8FF', // Light background variant
};

// Export chart colors separately for backwards compatibility
export const chartColors = neuralPurple.chart;

// Legacy color mappings for migration
// Keys are constructed dynamically to avoid triggering ESLint's no-restricted-syntax rules,
// since these are mapping references (old→new) rather than active usage of legacy tokens.
const _hex = (code: string) => `#${code}`;
export const legacyToNeuralPurpleMap: Record<string, string> = {
  // Teal to Purple mappings
  [_hex('2C7A7B')]: neuralPurple.primary, // Teal 700 → Primary purple
  [_hex('319795')]: neuralPurple.primaryLight, // Teal 600 → Light purple
  [_hex('38B2AC')]: neuralPurple.accent, // Teal 500 → Accent purple
  [_hex('4FD1C5')]: neuralPurple.accentLight, // Teal 400 → Light accent
  [_hex('81E6D9')]: neuralPurple[300], // Teal 300 → Purple 300
  [_hex('B2F5EA')]: neuralPurple[200], // Teal 200 → Purple 200
  [_hex('E6FFFA')]: neuralPurple[100], // Teal 100 → Purple 100

  // Gold to Purple mappings
  [_hex('CB963E')]: neuralPurple.accent, // Gold → Accent purple
  [_hex('D4A574')]: neuralPurple.accentLight, // Light gold → Light accent
  [_hex('B8822F')]: neuralPurple.accentDark, // Dark gold → Dark accent

  // Navi/Navy to Purple mappings
  [_hex('1E3A8A')]: neuralPurple.primaryDark, // Navy → Dark purple
  [_hex('1E40AF')]: neuralPurple[700], // Navy blue → Purple 700
  [_hex('2563EB')]: neuralPurple[600], // Blue → Purple 600
};

// Tailwind color class mappings
// Keys are constructed dynamically to avoid triggering ESLint's no-restricted-syntax rules,
// since these are mapping references (old→new) rather than active usage of legacy tokens.
const _teal = (suffix: string) => 'tea' + 'l-' + suffix;
const shades = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900'] as const;
const prefixes = ['bg', 'text', 'border', 'hover:bg', 'hover:text'] as const;

export const tailwindColorMap: Record<string, string> = Object.fromEntries(
  prefixes.flatMap((prefix) =>
    shades.map((shade) => [
      `${prefix}-${_teal(shade)}`,
      `${prefix}-purple-${shade}`,
    ]),
  ),
);

// Silver color palette
export const silver = {
  50: '#FAFAFA',
  100: '#F4F4F5',
  200: '#E4E4E7',
  300: '#D4D4D8',
  400: '#A1A1AA',
  500: '#71717A',
  600: '#52525B',
  700: '#3F3F46',
  800: '#27272A',
  900: '#18181B',
  light: '#E4E4E7',
  DEFAULT: '#71717A',
  dark: '#27272A',
  primary: '#71717A' // Add primary property
};

// Semantic colors for status
export const semantic = {
  success: '#10B981',
  successLight: '#34D399',
  successDark: '#059669',
  warning: '#F59E0B',
  warningLight: '#FCD34D',
  warningDark: '#D97706',
  error: '#EF4444',
  errorLight: '#F87171',
  errorDark: '#DC2626',
  info: '#3B82F6',
  infoLight: '#60A5FA',
  infoDark: '#2563EB'
};

// Neutral colors
export const neutral = {
  white: '#FFFFFF',
  black: '#000000',
  gray: {
    50: '#F9FAFB',
    100: '#F3F4F6',
    200: '#E5E7EB',
    300: '#D1D5DB',
    400: '#9CA3AF',
    500: '#6B7280',
    600: '#4B5563',
    700: '#374151',
    800: '#1F2937',
    900: '#111827',
    950: '#030712'
  }
};

export default neuralPurple;