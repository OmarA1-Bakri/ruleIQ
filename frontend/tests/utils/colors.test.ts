import { describe, it, expect } from 'vitest';
import { colors } from '@/lib/colors';

describe('colors', () => {
  describe('midnight', () => {
    it('has DEFAULT value', () => {
      expect(colors.midnight.DEFAULT).toBe('#0F172A');
    });

    it('has dark variant', () => {
      expect(colors.midnight.dark).toBe('#020617');
    });

    it('has light variant', () => {
      expect(colors.midnight.light).toBe('#1E293B');
    });
  });

  describe('turquoise', () => {
    it('has DEFAULT value', () => {
      expect(colors.turquoise.DEFAULT).toBe('#00BCD4');
    });

    it('has dark variant', () => {
      expect(colors.turquoise.dark).toBe('#00838F');
    });

    it('has light variant', () => {
      expect(colors.turquoise.light).toBe('#4DD0E1');
    });
  });

  describe('electric', () => {
    it('has DEFAULT value', () => {
      expect(colors.electric.DEFAULT).toBe('#1E40AF');
    });
  });

  describe('semantic', () => {
    it('has success color', () => {
      expect(colors.semantic.success).toBe('#10B981');
    });

    it('has warning color', () => {
      expect(colors.semantic.warning).toBe('#F59E0B');
    });

    it('has error color', () => {
      expect(colors.semantic.error).toBe('#EF4444');
    });

    it('has info color', () => {
      expect(colors.semantic.info).toBe('#00BCD4');
    });
  });

  describe('surface', () => {
    it('has primary dark surface', () => {
      expect(colors.surface.primary).toBe('#0F172A');
    });

    it('has primary light surface', () => {
      expect(colors.surface['primary-light']).toBe('#FFFFFF');
    });
  });

  describe('text', () => {
    it('has on-dark text color', () => {
      expect(colors.text['on-dark']).toBe('#F1F5F9');
    });

    it('has on-light text color', () => {
      expect(colors.text['on-light']).toBe('#0F172A');
    });

    it('has muted text color', () => {
      expect(colors.text.muted).toBe('#94A3B8');
    });
  });

  describe('legacy primary', () => {
    it('has primary color', () => {
      expect(colors.primary).toBe('#0F172A');
    });
  });

  it('all hex values are valid 6-digit hex codes', () => {
    const hexPattern = /^#[0-9A-Fa-f]{6}$/;

    // Check a sample of values
    expect(colors.midnight.DEFAULT).toMatch(hexPattern);
    expect(colors.turquoise.DEFAULT).toMatch(hexPattern);
    expect(colors.semantic.success).toMatch(hexPattern);
    expect(colors.semantic.error).toMatch(hexPattern);
    expect(colors.surface.primary).toMatch(hexPattern);
  });
});
