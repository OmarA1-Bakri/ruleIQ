import { describe, it, expect } from 'vitest';
import {
  purpleColors,
  silverColors,
  semanticColors,
  neutralColors,
  brandColors,
} from '@/lib/theme/colors';
import {
  neuralPurple,
  chartColors,
  legacyToNeuralPurpleMap,
  tailwindColorMap,
  silver,
  semantic,
  neutral,
} from '@/lib/theme/neural-purple-colors';

// Helper: valid 6-char hex
function isHex(value: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(value);
}

// ============================================================================
// purpleColors (lib/theme/colors.ts)
// ============================================================================

describe('purpleColors', () => {
  it('has all standard shade keys', () => {
    const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
    shades.forEach((shade) => {
      expect(purpleColors).toHaveProperty(shade);
    });
  });

  it('all values are valid hex colors', () => {
    Object.values(purpleColors).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });

  it('shade 50 is lighter than shade 900', () => {
    // Lighter colors have higher hex value; simple string comparison works for purple scale
    expect(purpleColors[50]).toBe('#FAF5FF');
    expect(purpleColors[900]).toBe('#581C87');
  });

  it('primary/base color is 500', () => {
    expect(purpleColors[500]).toBe('#A855F7');
  });
});

// ============================================================================
// silverColors (lib/theme/colors.ts)
// ============================================================================

describe('silverColors', () => {
  it('has standard shades 50-900', () => {
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].forEach((shade) => {
      expect(silverColors).toHaveProperty(shade);
    });
  });

  it('has semantic aliases: light, DEFAULT, dark', () => {
    expect(silverColors).toHaveProperty('light');
    expect(silverColors).toHaveProperty('DEFAULT');
    expect(silverColors).toHaveProperty('dark');
  });

  it('all shade values are valid hex colors', () => {
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].forEach((shade) => {
      expect(isHex((silverColors as any)[shade])).toBe(true);
    });
  });

  it('DEFAULT is the mid-range shade', () => {
    expect(silverColors.DEFAULT).toBe('#71717A');
  });
});

// ============================================================================
// semanticColors (lib/theme/colors.ts)
// ============================================================================

describe('semanticColors', () => {
  it('has success colors', () => {
    expect(semanticColors).toHaveProperty('success');
    expect(semanticColors).toHaveProperty('successLight');
    expect(semanticColors).toHaveProperty('successDark');
  });

  it('has warning colors', () => {
    expect(semanticColors).toHaveProperty('warning');
    expect(semanticColors).toHaveProperty('warningLight');
    expect(semanticColors).toHaveProperty('warningDark');
  });

  it('has error colors', () => {
    expect(semanticColors).toHaveProperty('error');
    expect(semanticColors).toHaveProperty('errorLight');
    expect(semanticColors).toHaveProperty('errorDark');
  });

  it('has info colors', () => {
    expect(semanticColors).toHaveProperty('info');
    expect(semanticColors).toHaveProperty('infoLight');
    expect(semanticColors).toHaveProperty('infoDark');
  });

  it('all values are valid hex colors', () => {
    Object.values(semanticColors).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });

  it('success uses green (#10B981)', () => {
    expect(semanticColors.success).toBe('#10B981');
  });

  it('error uses red (#EF4444)', () => {
    expect(semanticColors.error).toBe('#EF4444');
  });

  it('warning uses amber (#F59E0B)', () => {
    expect(semanticColors.warning).toBe('#F59E0B');
  });

  it('info uses blue (#3B82F6)', () => {
    expect(semanticColors.info).toBe('#3B82F6');
  });
});

// ============================================================================
// neutralColors (lib/theme/colors.ts)
// ============================================================================

describe('neutralColors', () => {
  it('has white and black', () => {
    expect(neutralColors.white).toBe('#FFFFFF');
    expect(neutralColors.black).toBe('#000000');
  });

  it('has gray sub-object', () => {
    expect(neutralColors.gray).toBeDefined();
    expect(typeof neutralColors.gray).toBe('object');
  });

  it('gray has all shades 50-950', () => {
    const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
    shades.forEach((shade) => {
      expect(neutralColors.gray).toHaveProperty(shade);
    });
  });

  it('all gray values are valid hex colors', () => {
    Object.values(neutralColors.gray).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });
});

// ============================================================================
// brandColors (lib/theme/colors.ts)
// ============================================================================

describe('brandColors', () => {
  it('has primary and its variants', () => {
    expect(brandColors).toHaveProperty('primary');
    expect(brandColors).toHaveProperty('primaryHover');
    expect(brandColors).toHaveProperty('primaryLight');
    expect(brandColors).toHaveProperty('primaryDark');
  });

  it('has accent and its variants', () => {
    expect(brandColors).toHaveProperty('accent');
    expect(brandColors).toHaveProperty('accentHover');
    expect(brandColors).toHaveProperty('accentLight');
    expect(brandColors).toHaveProperty('accentDark');
  });

  it('all values are valid hex colors', () => {
    Object.values(brandColors).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });

  it('primary is #8B5CF6', () => {
    expect(brandColors.primary).toBe('#8B5CF6');
  });
});

// ============================================================================
// neuralPurple (lib/theme/neural-purple-colors.ts)
// ============================================================================

describe('neuralPurple', () => {
  it('has numeric shades 50-950', () => {
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].forEach((shade) => {
      expect(neuralPurple).toHaveProperty(shade);
      expect(isHex((neuralPurple as any)[shade])).toBe(true);
    });
  });

  it('has primary brand color', () => {
    expect(neuralPurple.primary).toBe('#8B5CF6');
  });

  it('has background colors', () => {
    expect(neuralPurple).toHaveProperty('background');
    expect(neuralPurple).toHaveProperty('backgroundLight');
    expect(neuralPurple).toHaveProperty('backgroundDark');
    expect(isHex(neuralPurple.background)).toBe(true);
  });

  it('has text colors', () => {
    expect(neuralPurple.text).toBe('#FFFFFF');
    expect(isHex(neuralPurple.textSecondary)).toBe(true);
    expect(isHex(neuralPurple.textMuted)).toBe(true);
  });

  it('has chart sub-object with 6 colors', () => {
    expect(neuralPurple.chart).toBeDefined();
    expect(typeof neuralPurple.chart).toBe('object');
    expect(Object.keys(neuralPurple.chart).length).toBe(6);
  });

  it('chart colors are all valid hex', () => {
    Object.values(neuralPurple.chart).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });

  it('has semantic status colors', () => {
    expect(isHex(neuralPurple.success)).toBe(true);
    expect(isHex(neuralPurple.warning)).toBe(true);
    expect(isHex(neuralPurple.error)).toBe(true);
    expect(isHex(neuralPurple.info)).toBe(true);
  });
});

// ============================================================================
// chartColors
// ============================================================================

describe('chartColors', () => {
  it('is the same object as neuralPurple.chart', () => {
    expect(chartColors).toBe(neuralPurple.chart);
  });

  it('has primary, secondary, tertiary, quaternary, quinary, senary', () => {
    expect(chartColors).toHaveProperty('primary');
    expect(chartColors).toHaveProperty('secondary');
    expect(chartColors).toHaveProperty('tertiary');
    expect(chartColors).toHaveProperty('quaternary');
    expect(chartColors).toHaveProperty('quinary');
    expect(chartColors).toHaveProperty('senary');
  });
});

// ============================================================================
// legacyToNeuralPurpleMap
// ============================================================================

describe('legacyToNeuralPurpleMap', () => {
  it('is a non-empty object', () => {
    expect(typeof legacyToNeuralPurpleMap).toBe('object');
    expect(Object.keys(legacyToNeuralPurpleMap).length).toBeGreaterThan(0);
  });

  it('all keys are hex colors (#RRGGBB format)', () => {
    Object.keys(legacyToNeuralPurpleMap).forEach((key) => {
      expect(isHex(key)).toBe(true);
    });
  });

  it('all values are hex colors', () => {
    Object.values(legacyToNeuralPurpleMap).forEach((value) => {
      expect(isHex(value)).toBe(true);
    });
  });

  it('maps teal #2C7A7B to primary purple', () => {
    expect(legacyToNeuralPurpleMap['#2C7A7B']).toBe(neuralPurple.primary);
  });
});

// ============================================================================
// tailwindColorMap
// ============================================================================

describe('tailwindColorMap', () => {
  it('is a non-empty object', () => {
    expect(typeof tailwindColorMap).toBe('object');
    expect(Object.keys(tailwindColorMap).length).toBeGreaterThan(0);
  });

  it('has 50 entries (5 prefixes × 10 shades)', () => {
    expect(Object.keys(tailwindColorMap).length).toBe(50);
  });

  it('all values are purple equivalents', () => {
    Object.values(tailwindColorMap).forEach((value) => {
      expect(value).toContain('purple-');
    });
  });

  it('maps bg-teal-500 to bg-purple-500', () => {
    expect(tailwindColorMap['bg-teal-500']).toBe('bg-purple-500');
  });

  it('maps text-teal-700 to text-purple-700', () => {
    expect(tailwindColorMap['text-teal-700']).toBe('text-purple-700');
  });

  it('maps border-teal-100 to border-purple-100', () => {
    expect(tailwindColorMap['border-teal-100']).toBe('border-purple-100');
  });
});

// ============================================================================
// silver (neural-purple-colors.ts)
// ============================================================================

describe('silver (from neural-purple-colors)', () => {
  it('has shades 50-900', () => {
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].forEach((shade) => {
      expect(silver).toHaveProperty(shade);
    });
  });

  it('has light, DEFAULT, dark, primary aliases', () => {
    expect(silver).toHaveProperty('light');
    expect(silver).toHaveProperty('DEFAULT');
    expect(silver).toHaveProperty('dark');
    expect(silver).toHaveProperty('primary');
  });

  it('DEFAULT is #71717A', () => {
    expect(silver.DEFAULT).toBe('#71717A');
  });
});

// ============================================================================
// semantic (neural-purple-colors.ts)
// ============================================================================

describe('semantic (from neural-purple-colors)', () => {
  it('has all 12 semantic color fields', () => {
    expect(semantic).toHaveProperty('success');
    expect(semantic).toHaveProperty('successLight');
    expect(semantic).toHaveProperty('successDark');
    expect(semantic).toHaveProperty('warning');
    expect(semantic).toHaveProperty('warningLight');
    expect(semantic).toHaveProperty('warningDark');
    expect(semantic).toHaveProperty('error');
    expect(semantic).toHaveProperty('errorLight');
    expect(semantic).toHaveProperty('errorDark');
    expect(semantic).toHaveProperty('info');
    expect(semantic).toHaveProperty('infoLight');
    expect(semantic).toHaveProperty('infoDark');
  });

  it('all values are valid hex colors', () => {
    Object.values(semantic).forEach((hex) => {
      expect(isHex(hex)).toBe(true);
    });
  });
});

// ============================================================================
// neutral (neural-purple-colors.ts)
// ============================================================================

describe('neutral (from neural-purple-colors)', () => {
  it('has white and black', () => {
    expect(neutral.white).toBe('#FFFFFF');
    expect(neutral.black).toBe('#000000');
  });

  it('has gray sub-object with shades 50-950', () => {
    [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].forEach((shade) => {
      expect(neutral.gray).toHaveProperty(shade);
    });
  });
});
