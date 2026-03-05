import { ZodError, ZodSchema } from 'zod';
import { apiClient } from './client';
import { ApiResponseSchema } from '../validation/zod-schemas';

// Custom error class for validation failures
export class ValidationError extends Error {
  constructor(
    message: string,
    public readonly errors: ZodError,
    public readonly data?: unknown
  ) {
    super(message);
    this.name = 'ValidationError';
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      errors: this.errors.errors,
      data: this.data,
    };
  }
}

/**
 * Validates data against a Zod schema
 * @param data - The data to validate
 * @param schema - The Zod schema to validate against
 * @returns The validated and typed data
 * @throws ValidationError if validation fails
 */
export function validateApiResponse<T>(
  data: unknown,
  schema: ZodSchema<T>
): T {
  try {
    return schema.parse(data);
  } catch (error) {
    if (error instanceof ZodError) {
      const message = formatValidationError(error);
      throw new ValidationError(message, error, data);
    }
    throw error;
  }
}

/**
 * Safely validates data against a Zod schema
 * @param data - The data to validate
 * @param schema - The Zod schema to validate against
 * @returns A result object with either success and data, or error information
 */
export function safeValidateApiResponse<T>(
  data: unknown,
  schema: ZodSchema<T>
): { success: true; data: T } | { success: false; error: ValidationError } {
  try {
    const validated = validateApiResponse(data, schema);
    return { success: true, data: validated };
  } catch (error) {
    if (error instanceof ValidationError) {
      return { success: false, error };
    }
    return {
      success: false,
      error: new ValidationError(
        'Unknown validation error',
        new ZodError([]),
        data
      ),
    };
  }
}

/**
 * Formats Zod validation errors into user-friendly messages
 */
export function formatValidationError(error: ZodError): string {
  const issues = error.errors.map(issue => {
    const path = issue.path.join('.');
    return path ? `${path}: ${issue.message}` : issue.message;
  });
  return `Validation failed: ${issues.join(', ')}`;
}

/**
 * Creates a validated API client that automatically validates responses
 */
export class ValidatedAPIClient {
  /**
   * Makes a GET request with response validation
   */
  async getValidated<T>(
    url: string,
    schema: ZodSchema<T>,
    options?: { params?: Record<string, string | number | boolean | null | undefined> }
  ): Promise<T> {
    const response = await apiClient.get(url, options);
    return validateApiResponse(response, schema);
  }

  /**
   * Makes a POST request with response validation
   */
  async postValidated<TRequest, TResponse>(
    url: string,
    data: TRequest,
    responseSchema: ZodSchema<TResponse>,
    requestSchema?: ZodSchema<TRequest>,
    _options?: RequestInit
  ): Promise<TResponse> {
    // Validate request data if schema provided
    const validatedData = requestSchema
      ? validateApiResponse(data, requestSchema)
      : data;

    const response = await apiClient.post(url, validatedData);
    return validateApiResponse(response, responseSchema);
  }

  /**
   * Makes a PUT request with response validation
   */
  async putValidated<TRequest, TResponse>(
    url: string,
    data: TRequest,
    responseSchema: ZodSchema<TResponse>,
    requestSchema?: ZodSchema<TRequest>,
    _options?: RequestInit
  ): Promise<TResponse> {
    // Validate request data if schema provided
    const validatedData = requestSchema
      ? validateApiResponse(data, requestSchema)
      : data;

    const response = await apiClient.put(url, validatedData);
    return validateApiResponse(response, responseSchema);
  }

  /**
   * Makes a PATCH request with response validation
   */
  async patchValidated<TRequest, TResponse>(
    url: string,
    data: TRequest,
    responseSchema: ZodSchema<TResponse>,
    requestSchema?: ZodSchema<TRequest>,
    _options?: RequestInit
  ): Promise<TResponse> {
    // Validate request data if schema provided
    const validatedData = requestSchema
      ? validateApiResponse(data, requestSchema)
      : data;

    const response = await apiClient.patch(url, validatedData);
    return validateApiResponse(response, responseSchema);
  }

  /**
   * Makes a DELETE request with response validation
   */
  async deleteValidated<T>(
    url: string,
    schema: ZodSchema<T>,
    _options?: RequestInit
  ): Promise<T> {
    const response = await apiClient.delete(url);
    return validateApiResponse(response, schema);
  }
}

/**
 * Creates a validated wrapper for API client methods
 */
export function createValidatedApiClient() {
  return new ValidatedAPIClient();
}

/**
 * Middleware for validating API responses
 */
export function createValidationMiddleware<T>(schema: ZodSchema<T>) {
  return async (response: unknown): Promise<T> => {
    return validateApiResponse(response, schema);
  };
}

/**
 * Validates request data before sending
 */
export function validateRequest<T>(
  data: unknown,
  schema: ZodSchema<T>
): T {
  try {
    return schema.parse(data);
  } catch (error) {
    if (error instanceof ZodError) {
      const message = `Invalid request data: ${formatValidationError(error)}`;
      throw new ValidationError(message, error, data);
    }
    throw error;
  }
}

/**
 * Creates a type-safe API endpoint wrapper
 */
export function createTypedEndpoint<
  TRequest = void,
  TResponse = void
>(config: {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  requestSchema?: ZodSchema<TRequest>;
  responseSchema: ZodSchema<TResponse>;
}) {
  const client = new ValidatedAPIClient();

  return async (
    data?: TRequest,
    options?: RequestInit
  ): Promise<TResponse> => {
    const { url, method, requestSchema, responseSchema } = config;

    switch (method) {
      case 'GET':
        return client.getValidated(url, responseSchema, options as { params?: Record<string, string | number | boolean | null | undefined> });
      
      case 'POST':
        if (data === undefined) {
          throw new Error('POST request requires data');
        }
        return client.postValidated(
          url,
          data,
          responseSchema,
          requestSchema,
          options
        );
      
      case 'PUT':
        if (data === undefined) {
          throw new Error('PUT request requires data');
        }
        return client.putValidated(
          url,
          data,
          responseSchema,
          requestSchema,
          options
        );
      
      case 'PATCH':
        if (data === undefined) {
          throw new Error('PATCH request requires data');
        }
        return client.patchValidated(
          url,
          data,
          responseSchema,
          requestSchema,
          options
        );
      
      case 'DELETE':
        return client.deleteValidated(url, responseSchema, options);
      
      default:
        throw new Error(`Unsupported method: ${method}`);
    }
  };
}

/**
 * Development mode logger for validation issues
 */
export function logValidationWarning(
  context: string,
  error: ValidationError
): void {
  if (process.env.NODE_ENV === 'development') {
    console.warn(
      `[Validation Warning] ${context}:`,
      {
        message: error.message,
        errors: error.errors.errors,
        data: error.data,
      }
    );
  }
}

/**
 * Production error reporter for validation failures
 */
export function reportValidationError(
  context: string,
  error: ValidationError
): void {
  if (process.env.NODE_ENV === 'production') {
    // In production, you might want to send this to an error tracking service
    console.error(
      `[Validation Error] ${context}:`,
      {
        message: error.message,
        errorCount: error.errors.errors.length,
        // Don't log actual data in production for security
      }
    );
  }
}

/**
 * Helper to create validated API response wrapper
 */
export function createApiResponseValidator<T>(
  schema: ZodSchema<T>
) {
  const responseSchema = ApiResponseSchema(schema);
  return (response: unknown): T => {
    const validated = validateApiResponse(response, responseSchema);

    if (!validated.success) {
      throw new Error(
        validated.error || validated.message || 'API request failed'
      );
    }

    if (validated.data === undefined) {
      throw new Error('API response data is undefined');
    }

    return validated.data;
  };
}

/**
 * Batch validation for multiple items
 */
export function validateBatch<T>(
  items: unknown[],
  schema: ZodSchema<T>
): { valid: T[]; invalid: Array<{ index: number; error: ValidationError }> } {
  const valid: T[] = [];
  const invalid: Array<{ index: number; error: ValidationError }> = [];

  items.forEach((item, index) => {
    const result = safeValidateApiResponse(item, schema);
    if (result.success) {
      valid.push(result.data);
    } else {
      invalid.push({ index, error: result.error });
    }
  });

  return { valid, invalid };
}

// Export singleton instance for convenience
export const validatedApiClient = new ValidatedAPIClient();

// Re-export types for convenience
export type { ZodSchema } from 'zod';