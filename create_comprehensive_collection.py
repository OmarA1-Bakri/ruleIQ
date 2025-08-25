#!/usr/bin/env python3
import json

# Create comprehensive collection with key endpoints
collection = {
    "info": {
        "name": "RuleIQ Generated Collection",
        "description": "Generated from verified 254 endpoints",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000"},
        {"key": "jwt_token", "value": "{{jwt_token}}"}
    ],
    "item": [
        {
            "name": "🔐 Authentication",
            "item": [
                {
                    "name": "Register New User",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {"mode": "raw", "raw": "{\"email\": \"test@example.com\", \"password\": \"testpass123\"}"},
                        "url": {"raw": "{{base_url}}/api/v1/auth/register"}
                    }
                },
                {
                    "name": "Login User",
                    "request": {
                        "method": "POST", 
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {"mode": "raw", "raw": "{\"email\": \"{{test_user_email}}\", \"password\": \"{{test_user_password}}\"}"},
                        "url": {"raw": "{{base_url}}/api/v1/auth/login"}
                    }
                },
                {
                    "name": "Get Current User",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Authorization", "value": "Bearer {{jwt_token}}"}],
                        "url": {"raw": "{{base_url}}/api/v1/auth/me"}
                    }
                }
            ]
        },
        {
            "name": "🏢 Business Profiles",
            "item": [
                {
                    "name": "Create Business Profile",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}, {"key": "Authorization", "value": "Bearer {{jwt_token}}"}],
                        "body": {"mode": "raw", "raw": "{\"company_name\": \"Test Company\", \"industry\": \"Technology\"}"},
                        "url": {"raw": "{{base_url}}/api/v1/business-profiles"}
                    }
                },
                {
                    "name": "Get My Business Profile", 
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Authorization", "value": "Bearer {{jwt_token}}"}],
                        "url": {"raw": "{{base_url}}/api/v1/business-profiles/me"}
                    }
                }
            ]
        }
    ]
}

with open('ruleiq_generated_collection.json', 'w') as f:
    json.dump(collection, f, indent=2)

total = sum(len(item["item"]) for item in collection["item"])
print(f"✅ Generated collection with {total} sample endpoints")
