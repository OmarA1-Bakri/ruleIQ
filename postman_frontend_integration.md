# Postman Frontend Integration Guide

## 1. Export API Client Code from Postman

Postman can generate JavaScript/TypeScript code for your API calls:

1. Open any request in Postman
2. Click "Code" button (</> icon)
3. Select "JavaScript - Fetch" or "JavaScript - Axios"
4. Copy the generated code

## 2. Create a Postman-Based API Client

```typescript
// frontend/lib/api/postman-client.ts
import { PostmanCollection } from 'postman-collection';

class PostmanAPIClient {
  private collection: any;
  private environment: any;
  
  constructor() {
    // Load your Postman collection
    this.collection = require('@/postman/ruleiq_collection.json');
    this.environment = require('@/postman/environment.json');
  }
  
  async executeRequest(requestName: string, variables?: Record<string, any>) {
    const request = this.findRequest(requestName);
    
    // Replace variables
    const url = this.replaceVariables(request.url, variables);
    const headers = this.replaceVariables(request.header, variables);
    
    return fetch(url, {
      method: request.method,
      headers: this.parseHeaders(headers),
      body: request.body?.raw
    });
  }
  
  private findRequest(name: string) {
    // Find request in collection by name
    return this.collection.item.find((item: any) => item.name === name);
  }
  
  private replaceVariables(text: string, variables?: Record<string, any>) {
    // Replace {{variable}} with actual values
    return text.replace(/\{\{(\w+)\}\}/g, (match, key) => {
      return variables?.[key] || this.environment[key] || match;
    });
  }
}

// Usage in your React components:
const postmanClient = new PostmanAPIClient();

// Execute a request from your Postman collection
const response = await postmanClient.executeRequest('Login', {
  email: 'user@example.com',
  password: 'password123'
});
```

## 3. Use Newman as a Service

Run Newman programmatically from your frontend build process:

```javascript
// scripts/test-api.js
const newman = require('newman');

newman.run({
  collection: require('./ruleiq_collection.json'),
  environment: require('./newman-environment.json'),
  reporters: ['cli', 'json'],
  reporter: {
    json: {
      export: './api-test-results.json'
    }
  }
}, (err, summary) => {
  if (err) throw err;
  console.log('API tests complete!');
});
```

## 4. Postman Interceptor for Browser

Use Postman Interceptor to capture actual API calls from your frontend:

1. Install Postman Interceptor browser extension
2. Enable in Postman desktop app
3. All frontend API calls are captured in Postman
4. Build your collection from real traffic

## 5. Environment-Based Configuration

```typescript
// frontend/lib/api/config.ts
export const getAPIConfig = () => {
  const env = process.env.NEXT_PUBLIC_ENV || 'development';
  
  switch (env) {
    case 'postman-mock':
      return {
        baseURL: 'https://YOUR-MOCK.mock.pstmn.io',
        headers: { 'x-api-key': 'POSTMAN_API_KEY' }
      };
    
    case 'production':
      return {
        baseURL: 'https://api.ruleiq.com',
        headers: { 'x-api-key': process.env.NEXT_PUBLIC_API_KEY }
      };
    
    default:
      return {
        baseURL: 'http://localhost:8000',
        headers: {}
      };
  }
};
```

## 6. Sync Postman with OpenAPI

Generate TypeScript types from your Postman collection:

```bash
# Install openapi-typescript
npm install -D openapi-typescript

# Convert Postman to OpenAPI
postman-to-openapi ruleiq_collection.json -o openapi.yaml

# Generate TypeScript types
npx openapi-typescript openapi.yaml -o types/api.ts
```

## 7. Real-time Sync with Postman API

```typescript
// Fetch latest collection from Postman API
async function syncPostmanCollection() {
  const response = await fetch('https://api.getpostman.com/collections/YOUR_COLLECTION_ID', {
    headers: {
      'X-Api-Key': process.env.POSTMAN_API_KEY
    }
  });
  
  const collection = await response.json();
  
  // Use collection to generate API calls
  return collection;
}
```

## 8. Frontend Testing with Postman

```json
// package.json
{
  "scripts": {
    "test:api": "newman run ruleiq_collection.json -e newman-environment.json",
    "test:api:mock": "newman run ruleiq_collection.json -e mock-environment.json",
    "predev": "npm run test:api:mock",
    "prebuild": "npm run test:api"
  }
}
```

## Benefits of Postman Integration:

1. **Single Source of Truth**: Postman collection defines all API contracts
2. **Auto-generated Code**: No manual API client maintenance
3. **Mock Data**: Test frontend without backend running
4. **Type Safety**: Generate TypeScript types from collection
5. **Automated Testing**: Run API tests before deployment
6. **Documentation**: Postman serves as live API documentation
7. **Monitoring**: Track API health and performance

## Quick Start Commands:

```bash
# Test with real backend
newman run ruleiq_comprehensive_test.json -e newman-working-environment.json

# Test with mock server
newman run ruleiq_comprehensive_test.json -e postman-mock-environment.json

# Generate API client code
postman-code-gen -l javascript -o frontend/lib/api/generated
```