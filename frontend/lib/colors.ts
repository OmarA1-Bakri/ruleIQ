/**
 * ruleIQ Design System Colors - Teal Professional Theme
 * Consolidated color tokens aligned with Tailwind config
 * Use these tokens for programmatic color access
 */

export const colors = {
  // Brand Colors - Teal Professional Theme
  teal: {
    50: '#E6FFFA', // Lightest - backgrounds, subtle highlights
    100: '#B2F5EA', // Light backgrounds, hover states
    200: '#81E6D9', // Light accents, borders
    300: '#4FD1C5', // Bright accent, highlights
    400: '#38B2AC', // Medium teal, icons
    500: '#319795', // Standard teal
    600: '#2C7A7B', // PRIMARY - Main brand color
    700: '#285E61', // Dark - hover states, emphasis
    800: '#234E52', // Darker text on light
    900: '#1D4044', // Darkest
  },

  // Neutral Colors (Light Theme Optimized)
  neutral: {
    50: '#F9FAFB', // Lightest backgrounds
    100: '#F3F4F6', // Light backgrounds
    200: '#E5E7EB', // Borders, dividers
    300: '#D1D5DB', // Disabled borders
    400: '#9CA3AF', // Placeholder text
    500: '#6B7280', // Muted text
    600: '#4B5563', // Secondary text
    700: '#374151', // Body text
    800: '#1F2937', // Headings
    900: '#111827', // Primary text
  },

  // Semantic Colors (Light Theme)
  semantic: {
    success: '#10B981', // Emerald green
    warning: '#F59E0B', // Amber for warnings
    error: '#EF4444', // Red for errors
    info: '#319795', // Teal-500 for info states
  },

  // Surface Colors (Light Theme First)
  surface: {
    primary: '#FFFFFF', // Light theme primary surface (white)
    secondary: '#F9FAFB', // Light theme secondary surface (neutral-50)
    tertiary: '#F3F4F6', // Light theme tertiary surface (neutral-100)
    elevated: '#FFFFFF', // Elevated components with shadow
  },

  // Text Colors (Light Theme Optimized)
  text: {
    primary: '#111827', // Dark text on light surfaces (neutral-900)
    secondary: '#4B5563', // Secondary text (neutral-600)
    tertiary: '#6B7280', // Muted text (neutral-500)
    inverse: '#FFFFFF', // White text for dark backgrounds
    brand: '#2C7A7B', // Brand teal text (teal-600)
    accent: '#319795', // Teal accent text (teal-500)
  },

  // Brand shortcuts for easy access
  brand: {
    primary: '#2C7A7B', // teal-600
    secondary: '#319795', // teal-500
    light: '#E6FFFA', // teal-50
    dark: '#285E61', // teal-700
  },
} as const;

export type ColorKey = keyof typeof colors;
