# ruleIQ Design System Tokens

## Overview

This document provides comprehensive guidance for using design tokens in the ruleIQ frontend. Design tokens ensure consistency, maintainability, and brand alignment across all components.

## Color Token Hierarchy

### Brand Colors (Dark Mode First)

```css
/* Midnight Blue - Primary Brand Color */
midnight: #0F172A       /* Primary buttons, headers, brand elements (dark mode default) */
midnight-dark: #020617  /* Deep backgrounds, hover states */
midnight-light: #1E293B /* Elevated surfaces, subtle emphasis */

/* Turquoise - Secondary Accent Color */
turquoise: #00BCD4      /* CTAs, highlights, interactive elements */
turquoise-dark: #00838F /* Turquoise hover states */
turquoise-light: #4DD0E1 /* Turquoise backgrounds, subtle accents */

/* Electric Blue - Supporting Accent */
electric: #1E40AF       /* Supporting interactions, info states */
electric-dark: #1E3A8A  /* Electric blue hover states */
electric-light: #3B82F6 /* Electric blue backgrounds */
```

### Surface Colors (Dark Mode First)

```css
/* Dark Theme Surfaces (Default) */
surface-primary: #0F172A      /* Cards, modals, main content areas (midnight) */
surface-secondary: #1E293B    /* Page backgrounds, section dividers */
surface-tertiary: #334155     /* Elevated surfaces, subtle backgrounds */

/* Light Theme Surfaces (Optional) */
surface-primary-light: #FFFFFF   /* Light theme cards, modals */
surface-secondary-light: #F8FAFC /* Light theme backgrounds */
surface-tertiary-light: #E2E8F0  /* Light theme subtle backgrounds */
```

### Text Colors (Dark Mode Optimized)

```css
/* Context-Specific Text Colors */
text-on-dark: #F1F5F9       /* Light text on dark surfaces (primary) */
text-on-light: #0F172A      /* Dark text on light surfaces */
text-on-turquoise: #FFFFFF  /* White text on turquoise backgrounds */
text-on-midnight: #F1F5F9   /* Light text on midnight blue */
text-secondary: #CBD5E1     /* Secondary information, metadata */
text-muted: #94A3B8        /* Placeholders, disabled text */
```

### Semantic Colors

```css
/* State-Based Colors (Dark Theme Optimized) */
success: #10B981         /* Success messages, completed states (emerald) */
warning: #F59E0B         /* Warnings (amber) */
error: #EF4444          /* Errors, destructive actions */
info: #00BCD4           /* Information (uses brand turquoise) */
```

## Component-to-Token Mapping

### Primary Buttons
```tsx
// Recommended token usage
className="bg-navy text-text-on-dark hover:bg-navy-dark"
// or using CSS variables
className="bg-primary text-primary-foreground hover:bg-primary/90"
```

### Secondary Buttons
```tsx
className="border-2 border-navy text-navy hover:bg-navy hover:text-text-on-dark"
```

### Cards
```tsx
className="bg-surface-primary border border-outline-muted shadow-sm"
```

### Form Inputs
```tsx
className="bg-surface-primary border border-outline-muted focus:border-outline-primary"
```

### Status Indicators
```tsx
// Success state
className="text-success bg-success/10 border border-success/20"

// Warning state  
className="text-warning bg-warning/10 border border-warning/20"

// Error state
className="text-error bg-error/10 border border-error/20"
```

## Spacing Token Usage

### 8px Grid System
```css
/* Base spacing units */
0.5 = 4px    /* Half-step for fine adjustments */
1 = 8px      /* Base unit */
2 = 16px     /* Standard spacing */
3 = 24px     /* Section spacing */
4 = 32px     /* Large spacing */
6 = 48px     /* Very large spacing */
8 = 64px     /* Layout spacing */
```

### Component Spacing Patterns
```tsx
// Card internal spacing
className="p-6"  // 48px padding

// Button spacing
className="px-4 py-2"  // 32px horizontal, 16px vertical

// Form field spacing
className="space-y-4"  // 32px vertical spacing between fields

// Section spacing
className="mb-8"  // 64px bottom margin for sections
```

## Typography Token Usage

### Heading Hierarchy
```tsx
// H1 - Page titles
className="text-4xl font-bold text-text-on-light"

// H2 - Section titles
className="text-2xl font-semibold text-text-on-light"

// H3 - Subsection titles
className="text-lg font-medium text-text-on-light"

// Body text
className="text-base text-text-secondary"

// Small text / metadata
className="text-sm text-text-muted"
```

## Focus and Interaction States

### Focus Management
```css
/* Universal focus states */
focus-visible:ring-2 focus-visible:ring-outline-primary focus-visible:ring-offset-2

/* Button focus */
focus-visible:ring-2 focus-visible:ring-outline-secondary

/* Input focus */
focus-visible:border-outline-primary focus-visible:ring-1 focus-visible:ring-outline-primary
```

### Hover States
```css
/* Button hover */
hover:bg-navy-dark hover:scale-[1.02]

/* Card hover */
hover:shadow-md hover:shadow-navy/10

/* Link hover */
hover:text-navy-light hover:underline
```

## Animation Token Usage

### Duration
```css
transition-all duration-200   /* Standard transitions */
transition-all duration-150   /* Quick feedback */
transition-all duration-500   /* Complex layout changes */
```

### Easing
```css
ease-out     /* Standard easing for most interactions */
ease-in-out  /* For reversible animations */
ease-in      /* For exit animations */
```

## Accessibility Considerations

### Contrast Ratios
- **Navy on white**: 9.5:1 (AAA compliant)
- **Gold on white**: 4.8:1 (AA compliant)
- **Text-secondary on white**: 4.6:1 (AA compliant)
- **Text-muted on white**: 3.2:1 (Large text only)

### Motion Preferences
```tsx
// Respect reduced motion preferences
className={`transition-all ${
  shouldReduceMotion() ? 'duration-0' : 'duration-200'
} ease-out`}
```

## Token Usage Best Practices

### ✅ Do
- Use semantic tokens for component states (`success`, `warning`, `error`)
- Use surface tokens for background layers (`surface-primary`, `surface-secondary`)
- Use text tokens for proper contrast (`text-on-light`, `text-on-dark`)
- Use outline tokens for borders and focus states
- Reference tokens through CSS custom properties when possible

### ❌ Don't
- Use hex values directly in components
- Mix different color systems within the same component
- Use arbitrary values when tokens are available
- Ignore accessibility contrast requirements
- Override focus states without maintaining accessibility

## Token Validation

### Automated Checks
```bash
# Type check token usage
pnpm typecheck

# Lint for token consistency
pnpm lint

# Test contrast ratios
pnpm test:accessibility
```

### Manual Validation
- Verify brand consistency across all components
- Test color combinations for accessibility compliance
- Validate focus states across all interactive elements
- Check responsive behavior at all breakpoints

## Migration Guide

### From Legacy Colors
```tsx
// Old approach
className="bg-[#17255A] text-white"

// New approach
className="bg-navy text-text-on-dark"
```

### Component Updates
```tsx
// Before
<Button className="bg-blue-600 hover:bg-blue-700">

// After  
<Button variant="primary" className="bg-navy hover:bg-navy-dark">
```

## Design Token Roadmap

### Phase 1 (Current)
- ✅ Color token consolidation
- ✅ Surface and text token implementation
- ✅ Component mapping documentation

### Phase 2 (Next Sprint)
- [ ] Animation token standardization
- [ ] Component variant alignment
- [ ] Design tool integration

### Phase 3 (Future)
- [ ] Multi-brand token support
- [ ] Advanced theming capabilities
- [ ] Automated token generation from design files