import { describe, it, expect } from 'vitest';
import {
  ValidationError,
  QuestionValidator,
  ValidationPatterns,
  CommonValidations,
} from '@/lib/assessment-engine/validators';

// ============================================================================
// Test helpers
// ============================================================================

function makeQuestion(id: string, type: string, validation?: any) {
  return { id, type, text: `Q ${id}`, validation } as any;
}

const emptyContext = {} as any;

// ============================================================================
// ValidationError
// ============================================================================

describe('ValidationError', () => {
  it('is an instance of Error', () => {
    const err = new ValidationError('q1', 'This field is required');
    expect(err).toBeInstanceOf(Error);
  });

  it('has name "ValidationError"', () => {
    const err = new ValidationError('q1', 'msg');
    expect(err.name).toBe('ValidationError');
  });

  it('stores questionId', () => {
    const err = new ValidationError('q-123', 'msg');
    expect(err.questionId).toBe('q-123');
  });

  it('stores message', () => {
    const err = new ValidationError('q1', 'This field is required');
    expect(err.message).toBe('This field is required');
  });

  it('stores optional field', () => {
    const err = new ValidationError('q1', 'msg', 'email');
    expect(err.field).toBe('email');
  });

  it('field is undefined when not provided', () => {
    const err = new ValidationError('q1', 'msg');
    expect(err.field).toBeUndefined();
  });
});

// ============================================================================
// QuestionValidator — required
// ============================================================================

describe('QuestionValidator.validate — required', () => {
  it('returns null when validation is absent', () => {
    const q = makeQuestion('q1', 'text');
    expect(QuestionValidator.validate(q, 'any value', emptyContext)).toBeNull();
  });

  it('returns error when required and value is empty string', () => {
    const q = makeQuestion('q1', 'text', { required: true });
    const err = QuestionValidator.validate(q, '', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toBe('This field is required');
  });

  it('returns error when required and value is null', () => {
    const q = makeQuestion('q1', 'text', { required: true });
    expect(QuestionValidator.validate(q, null, emptyContext)).toBeInstanceOf(ValidationError);
  });

  it('returns error when required and value is undefined', () => {
    const q = makeQuestion('q1', 'text', { required: true });
    expect(QuestionValidator.validate(q, undefined, emptyContext)).toBeInstanceOf(ValidationError);
  });

  it('returns error when required and value is empty array', () => {
    const q = makeQuestion('q1', 'checkbox', { required: true });
    expect(QuestionValidator.validate(q, [], emptyContext)).toBeInstanceOf(ValidationError);
  });

  it('returns null when required and value is provided', () => {
    const q = makeQuestion('q1', 'text', { required: true });
    expect(QuestionValidator.validate(q, 'hello', emptyContext)).toBeNull();
  });

  it('returns null when not required and value is empty', () => {
    const q = makeQuestion('q1', 'text', { required: false });
    expect(QuestionValidator.validate(q, '', emptyContext)).toBeNull();
  });
});

// ============================================================================
// QuestionValidator — text
// ============================================================================

describe('QuestionValidator.validate — text type', () => {
  it('returns error when text is shorter than minLength', () => {
    const q = makeQuestion('q1', 'text', { minLength: 5 });
    const err = QuestionValidator.validate(q, 'hi', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('Minimum 5 characters');
  });

  it('returns null when text meets minLength', () => {
    const q = makeQuestion('q1', 'text', { minLength: 5 });
    expect(QuestionValidator.validate(q, 'hello', emptyContext)).toBeNull();
  });

  it('returns error when text exceeds maxLength', () => {
    const q = makeQuestion('q1', 'text', { maxLength: 5 });
    const err = QuestionValidator.validate(q, 'toolongvalue', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('Maximum 5 characters');
  });

  it('returns null when text meets maxLength', () => {
    const q = makeQuestion('q1', 'text', { maxLength: 10 });
    expect(QuestionValidator.validate(q, 'hello', emptyContext)).toBeNull();
  });

  it('returns error when text does not match pattern', () => {
    const q = makeQuestion('q1', 'text', { pattern: '^[0-9]+$' });
    const err = QuestionValidator.validate(q, 'abc', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toBe('Invalid format');
  });

  it('returns null when text matches pattern', () => {
    const q = makeQuestion('q1', 'text', { pattern: '^[0-9]+$' });
    expect(QuestionValidator.validate(q, '12345', emptyContext)).toBeNull();
  });

  it('applies same rules to textarea type', () => {
    const q = makeQuestion('q1', 'textarea', { minLength: 10 });
    const err = QuestionValidator.validate(q, 'short', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
  });
});

// ============================================================================
// QuestionValidator — number
// ============================================================================

describe('QuestionValidator.validate — number type', () => {
  it('returns error for non-numeric value', () => {
    const q = makeQuestion('q1', 'number', {});
    const err = QuestionValidator.validate(q, 'abc', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('valid number');
  });

  it('returns error when number is below min', () => {
    const q = makeQuestion('q1', 'number', { min: 5 });
    const err = QuestionValidator.validate(q, 3, emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('Minimum value is 5');
  });

  it('returns null when number meets min', () => {
    const q = makeQuestion('q1', 'number', { min: 5 });
    expect(QuestionValidator.validate(q, 5, emptyContext)).toBeNull();
  });

  it('returns error when number exceeds max', () => {
    const q = makeQuestion('q1', 'number', { max: 100 });
    const err = QuestionValidator.validate(q, 150, emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('Maximum value is 100');
  });

  it('returns null when number meets max', () => {
    const q = makeQuestion('q1', 'number', { max: 100 });
    expect(QuestionValidator.validate(q, 100, emptyContext)).toBeNull();
  });
});

// ============================================================================
// QuestionValidator — checkbox
// ============================================================================

describe('QuestionValidator.validate — checkbox type', () => {
  it('returns error when selections are below min', () => {
    const q = makeQuestion('q1', 'checkbox', { min: 2 });
    const err = QuestionValidator.validate(q, ['one'], emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('at least 2');
  });

  it('returns null when selections meet min', () => {
    const q = makeQuestion('q1', 'checkbox', { min: 2 });
    expect(QuestionValidator.validate(q, ['a', 'b'], emptyContext)).toBeNull();
  });

  it('returns error when selections exceed max', () => {
    const q = makeQuestion('q1', 'checkbox', { max: 2 });
    const err = QuestionValidator.validate(q, ['a', 'b', 'c'], emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toContain('at most 2');
  });

  it('returns error when value is not an array', () => {
    const q = makeQuestion('q1', 'checkbox', {});
    const err = QuestionValidator.validate(q, 'not-array', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
  });
});

// ============================================================================
// QuestionValidator — custom validation
// ============================================================================

describe('QuestionValidator.validate — custom validation', () => {
  // custom validation only runs for types not handled by the switch
  // (e.g., 'radio', 'select') — text/number etc return early from switch
  it('returns ValidationError when custom returns error string (radio type)', () => {
    const q = makeQuestion('q1', 'radio', {
      custom: (_val: any, _ctx: any) => 'Custom error message',
    });
    const err = QuestionValidator.validate(q, 'option-a', emptyContext);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err!.message).toBe('Custom error message');
  });

  it('returns null when custom returns null/undefined (radio type)', () => {
    const q = makeQuestion('q1', 'radio', {
      custom: (_val: any, _ctx: any) => null,
    });
    expect(QuestionValidator.validate(q, 'option-a', emptyContext)).toBeNull();
  });
});

// ============================================================================
// ValidationPatterns
// ============================================================================

describe('ValidationPatterns', () => {
  it('email pattern accepts valid email', () => {
    const re = new RegExp(ValidationPatterns.email);
    expect(re.test('user@example.com')).toBe(true);
  });

  it('email pattern rejects invalid email', () => {
    const re = new RegExp(ValidationPatterns.email);
    expect(re.test('not-an-email')).toBe(false);
  });

  it('ukPostcode pattern accepts valid UK postcode', () => {
    const re = new RegExp(ValidationPatterns.ukPostcode);
    expect(re.test('SW1A 1AA')).toBe(true);
  });

  it('alphanumeric pattern accepts alphanumeric', () => {
    const re = new RegExp(ValidationPatterns.alphanumeric);
    expect(re.test('abc123')).toBe(true);
    expect(re.test('abc!123')).toBe(false);
  });

  it('numbersOnly pattern accepts digits only', () => {
    const re = new RegExp(ValidationPatterns.numbersOnly);
    expect(re.test('12345')).toBe(true);
    expect(re.test('123a5')).toBe(false);
  });

  it('exposes url, phone, lettersOnly, noSpecialChars patterns', () => {
    expect(typeof ValidationPatterns.url).toBe('string');
    expect(typeof ValidationPatterns.phone).toBe('string');
    expect(typeof ValidationPatterns.lettersOnly).toBe('string');
    expect(typeof ValidationPatterns.noSpecialChars).toBe('string');
  });
});

// ============================================================================
// CommonValidations
// ============================================================================

describe('CommonValidations', () => {
  it('required has required=true', () => {
    expect(CommonValidations.required.required).toBe(true);
  });

  it('email has required=true and a pattern', () => {
    expect(CommonValidations.email.required).toBe(true);
    expect(typeof CommonValidations.email.pattern).toBe('string');
  });

  it('description has required=false', () => {
    expect(CommonValidations.description.required).toBe(false);
  });

  it('percentage has min=0 and max=100', () => {
    expect(CommonValidations.percentage.min).toBe(0);
    expect(CommonValidations.percentage.max).toBe(100);
  });

  it('year has min=1900', () => {
    expect(CommonValidations.year.min).toBe(1900);
  });

  it('positiveNumber has min=0', () => {
    expect(CommonValidations.positiveNumber.min).toBe(0);
  });

  it('companyName has minLength=2 and maxLength=100', () => {
    expect(CommonValidations.companyName.minLength).toBe(2);
    expect(CommonValidations.companyName.maxLength).toBe(100);
  });
});
