import { describe, it, expect } from 'vitest';
import { getCsrfHeaders, createCsrfFormData } from '@/lib/hooks/use-csrf-token';

describe('getCsrfHeaders', () => {
  it('returns headers with CSRF token', () => {
    const headers = getCsrfHeaders('test-token-123');

    expect(headers['X-CSRF-Token']).toBe('test-token-123');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('returns headers with empty token', () => {
    const headers = getCsrfHeaders('');

    expect(headers['X-CSRF-Token']).toBe('');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('preserves exact token value', () => {
    const token = 'abc-def-ghi-jkl-mno-pqr';
    const headers = getCsrfHeaders(token);
    expect(headers['X-CSRF-Token']).toBe(token);
  });
});

describe('createCsrfFormData', () => {
  it('creates FormData with CSRF token', () => {
    const formData = createCsrfFormData('csrf-token', {});

    expect(formData.get('_csrf')).toBe('csrf-token');
  });

  it('includes data fields', () => {
    const formData = createCsrfFormData('csrf-token', {
      name: 'John',
      email: 'john@example.com',
    });

    expect(formData.get('_csrf')).toBe('csrf-token');
    expect(formData.get('name')).toBe('John');
    expect(formData.get('email')).toBe('john@example.com');
  });

  it('skips null values', () => {
    const formData = createCsrfFormData('token', {
      name: 'John',
      email: null,
    });

    expect(formData.get('name')).toBe('John');
    expect(formData.has('email')).toBe(false);
  });

  it('skips undefined values', () => {
    const formData = createCsrfFormData('token', {
      name: 'John',
      age: undefined,
    });

    expect(formData.get('name')).toBe('John');
    expect(formData.has('age')).toBe(false);
  });

  it('includes falsy but non-null values', () => {
    const formData = createCsrfFormData('token', {
      count: 0,
      active: false,
      label: '',
    });

    expect(formData.get('count')).toBe('0');
    expect(formData.get('active')).toBe('false');
    expect(formData.get('label')).toBe('');
  });

  it('handles empty data object', () => {
    const formData = createCsrfFormData('token', {});

    expect(formData.get('_csrf')).toBe('token');
    // Only the _csrf field should be present
    const entries = Array.from(formData.entries());
    expect(entries.length).toBe(1);
  });
});
