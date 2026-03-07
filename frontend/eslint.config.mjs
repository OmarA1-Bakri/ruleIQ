import { FlatCompat } from '@eslint/eslintrc';
import js from '@eslint/js';
import typescriptEslint from '@typescript-eslint/eslint-plugin';
import typescriptParser from '@typescript-eslint/parser';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import prettier from 'eslint-config-prettier';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

export default [
  js.configs.recommended,
  ...compat.extends('next/core-web-vitals'),
  prettier,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      '@typescript-eslint': typescriptEslint,
      'jsx-a11y': jsxA11y,
    },
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        project: false, // Disable project-based parsing for production readiness
      },
    },
    rules: {
      // Critical TypeScript Rules Only - Production Ready
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_|^error$|^loading$|^data$', caughtErrorsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'off', // Allow for development flexibility
      '@typescript-eslint/consistent-type-imports': 'off',

      // Critical React Rules Only  
      'react/prop-types': 'off', // Using TypeScript for prop validation
      'react/react-in-jsx-scope': 'off', // Not needed in React 17+
      'react/no-unescaped-entities': 'off', // Allow content flexibility

      // Critical JavaScript Rules Only
      'no-unused-vars': 'off', // Using @typescript-eslint version
      'no-console': 'off', // Allow console for debugging
      'no-debugger': 'error', // Block debugger in production
      'no-undef': 'off', // TypeScript handles this better
      'prefer-const': 'off',
      'no-var': 'error', // Block var usage
      'eqeqeq': 'off',
      'no-case-declarations': 'off',
      'no-empty-pattern': 'off',
      'no-useless-catch': 'off',
      'no-async-promise-executor': 'off',
      'no-useless-escape': 'off',
      'no-control-regex': 'off',

      // Critical Next.js Rules Only
      '@next/next/no-img-element': 'off', // Allow img elements

      // Critical Hook Rules
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'off', // Allow flexible deps

      // Neural Purple Theme Guardrails
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/teal-/i]',
          message: 'Use Neural Purple theme tokens from @/lib/theme/neural-purple-colors instead of Teal classes',
        },
        {
          selector: 'Literal[value=/#2C7A7B/i]',
          message: 'Use Neural Purple theme tokens instead of legacy hex #2C7A7B',
        },
        {
          selector: 'Literal[value=/#319795/i]',
          message: 'Use Neural Purple theme tokens instead of legacy hex #319795',
        },
        {
          selector: 'Literal[value=/#4FD1C5/i]',
          message: 'Use Neural Purple theme tokens instead of legacy hex #4FD1C5',
        },
        {
          selector: 'Literal[value=/#17255A/i]',
          message: 'Use neuralPurple.primary instead of legacy hex #17255A',
        },
        {
          selector: 'Literal[value=/#CB963E/i]',
          message: 'Use silver.primary or semantic tokens instead of legacy hex #CB963E',
        },
        {
          selector: 'TemplateElement[value.cooked=/teal-/i]',
          message: 'Use Neural Purple theme classes instead of Teal in template literals',
        },
      ],
    },
  },
  {
    ignores: [
      '.next/**',
      'out/**',
      'node_modules/**',
      'coverage/**',
      '*.config.js',
      '*.config.mjs',
      'public/**',
      'tests/**', // Ignore test files for production
      '__tests__/**',
      '*.test.*',
      '*.spec.*',
      'build/**',
      'dist/**',
    ],
  },
];
