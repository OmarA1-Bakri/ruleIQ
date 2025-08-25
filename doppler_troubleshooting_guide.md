# Doppler Secrets Management Troubleshooting Guide

**Project**: ruleIQ  
**Last Updated**: 2025-08-23  
**Version**: 1.0  

## Quick Diagnosis Commands

### Check Doppler Status
```bash
# Verify CLI installation and version
doppler --version

# Check authentication status
doppler whoami

# Verify project configuration
doppler configure get project
doppler configure get config

# Test connectivity
doppler secrets --only-names
```

### Expected Outputs
```bash
$ doppler --version
3.75.1

$ doppler whoami
omar

$ doppler configure get project
ruleiq

$ doppler configure get config
dev
```

## Common Issues & Solutions

### 1. Authentication Issues

#### Problem: "Not logged in" Error
```
Error: you must be logged in to run this command
```

**Solution:**
```bash
# Re-authenticate
doppler login

# Verify login
doppler whoami

# Should output: omar
```

#### Problem: "Invalid token" Error
```
Error: invalid token
```

**Solution:**
```bash
# Clear existing authentication
doppler logout

# Re-login with fresh token
doppler login

# Verify workplace access
doppler workplace
```

### 2. Project Configuration Issues

#### Problem: "No project configured"
```
Error: no project configured for this directory
```

**Solution:**
```bash
# Configure project
doppler setup --project ruleiq --config dev

# Verify configuration
doppler configure get project  # Should output: ruleiq
doppler configure get config   # Should output: dev
```

#### Problem: Wrong environment/config
```bash
# Check current config
doppler configure get config

# Switch to correct environment
doppler configure set config dev    # For development
doppler configure set config staging # For staging
doppler configure set config prod   # For production
```

### 3. Secret Retrieval Issues

#### Problem: Secret not found
```
Error: secret "SECRET_NAME" not found
```

**Solutions:**
```bash
# Check if secret exists
doppler secrets --only-names | grep SECRET_NAME

# List all secrets to verify name
doppler secrets --only-names

# Check correct project/config
doppler configure get project
doppler configure get config

# Switch to correct config if needed
doppler configure set config dev
```

#### Problem: Permission denied
```
Error: insufficient permissions
```

**Solutions:**
```bash
# Check workspace membership
doppler workplace list

# Verify project access
doppler projects list

# Contact admin to grant access to project
```

### 4. Network & Connectivity Issues

#### Problem: Connection timeout
```
Error: connection timeout
```

**Solutions:**
```bash
# Check internet connectivity
ping api.doppler.com

# Test with curl
curl -I https://api.doppler.com

# Check firewall/proxy settings
export HTTP_PROXY=your-proxy
export HTTPS_PROXY=your-proxy

# Retry operation
doppler secrets --only-names
```

#### Problem: SSL/TLS errors
```
Error: certificate verification failed
```

**Solutions:**
```bash
# Update CA certificates
sudo apt-get update && sudo apt-get install ca-certificates

# Skip SSL verification (temporary)
export DOPPLER_SKIP_SSL_VERIFY=true

# Use specific CA bundle
export DOPPLER_CA_BUNDLE=/path/to/ca-bundle.pem
```

### 5. Environment Integration Issues

#### Problem: Secrets not loading in application
```bash
# Test secret access
doppler secrets get DATABASE_URL --plain

# Test environment injection
doppler run -- env | grep DATABASE_URL

# If empty, check project configuration
doppler configure
```

#### Problem: Wrong secret values
```bash
# Verify current environment
doppler configure get config

# Check secret in specific environment
doppler secrets get SECRET_NAME --config dev --plain
doppler secrets get SECRET_NAME --config staging --plain

# Switch to correct environment
doppler configure set config dev
```

### 6. Fallback Mechanism Issues

#### Problem: .env.local file missing
```bash
# Check if file exists
ls -la .env.local

# Create from Doppler if missing
doppler secrets download --no-file --format env > .env.local

# Verify critical secrets are present
grep -E "(DATABASE_URL|REDIS_URL|JWT_SECRET_KEY)" .env.local
```

#### Problem: Outdated fallback secrets
```bash
# Update fallback file
doppler secrets download --no-file --format env > .env.local

# Verify update
grep "UPDATED=$(date)" .env.local || echo "UPDATED=$(date)" >> .env.local

# Compare key secrets
echo "Doppler JWT_SECRET_KEY:"
doppler secrets get JWT_SECRET_KEY --plain
echo "Fallback JWT_SECRET_KEY:"
grep "^JWT_SECRET_KEY=" .env.local | cut -d= -f2
```

## Environment-Specific Troubleshooting

### Development Environment

#### Setup Verification
```bash
# Navigate to project directory
cd /home/omar/Documents/ruleIQ

# Check Doppler configuration
doppler configure get project  # Should be: ruleiq
doppler configure get config   # Should be: dev

# Verify critical development secrets
doppler secrets get DATABASE_URL --plain | head -c 50
doppler secrets get REDIS_URL --plain
doppler secrets get DEBUG --plain  # Should be: true
```

#### Common Dev Issues
```bash
# Database connection issues
doppler run -- python -c "
import psycopg
import os
try:
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

# Redis connection issues
doppler run -- python -c "
import redis
import os
try:
    r = redis.from_url(os.environ['REDIS_URL'])
    r.ping()
    print('✅ Redis connection successful')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
"
```

### Production Environment

#### Pre-deployment Checklist
```bash
# Switch to production config
doppler configure set config prod

# Verify all critical secrets exist
CRITICAL_SECRETS="DATABASE_URL REDIS_URL OPENAI_API_KEY JWT_SECRET_KEY SECRET_KEY"
for secret in $CRITICAL_SECRETS; do
    if doppler secrets get $secret --plain >/dev/null 2>&1; then
        echo "✅ $secret: Available"
    else
        echo "❌ $secret: Missing"
    fi
done

# Test service tokens (for CI/CD)
DOPPLER_TOKEN=dp.st.prod.YOUR_TOKEN doppler secrets --only-names
```

### Staging Environment
```bash
# Switch to staging
doppler configure set config staging

# Verify staging-specific configurations
doppler secrets get ENVIRONMENT --plain  # Should be: staging
doppler secrets get DEBUG --plain        # Should be: false
```

## CLI Command Reference

### Authentication Commands
```bash
doppler login                    # Interactive login
doppler login --token TOKEN     # Login with token
doppler logout                   # Logout
doppler whoami                   # Check current user
doppler workplace               # List workplaces
```

### Configuration Commands
```bash
doppler setup                           # Interactive setup
doppler setup --project PROJECT --config CONFIG
doppler configure get project          # Get current project
doppler configure get config           # Get current config
doppler configure set project PROJECT  # Set project
doppler configure set config CONFIG    # Set config
```

### Secret Management Commands
```bash
doppler secrets                        # List all secrets
doppler secrets --only-names          # List secret names only
doppler secrets get SECRET_NAME       # Get secret (masked)
doppler secrets get SECRET_NAME --plain  # Get secret (plaintext)
doppler secrets set SECRET_NAME=value # Set secret value
doppler secrets delete SECRET_NAME    # Delete secret
doppler secrets download              # Download all secrets
```

### Environment Injection Commands
```bash
doppler run -- command                # Run command with secrets injected
doppler run -- env                    # Show all environment variables
doppler run -- python main.py        # Run application with secrets
doppler secrets download --no-file --format env  # Export format
```

## Service Token Management

### Creating Service Tokens
```bash
# List existing tokens
doppler service-tokens list

# Create new token for CI/CD
doppler service-tokens create ci-cd --config dev

# Test service token
DOPPLER_TOKEN=dp.st.dev.YOUR_TOKEN doppler secrets --only-names
```

### Using Service Tokens
```bash
# In CI/CD environment
export DOPPLER_TOKEN=dp.st.dev.YOUR_SERVICE_TOKEN
doppler secrets download --no-file --format env >> $GITHUB_ENV

# In Docker
docker run -e DOPPLER_TOKEN=dp.st.prod.YOUR_TOKEN myapp
```

## Advanced Troubleshooting

### Debug Mode
```bash
# Enable verbose logging
export DOPPLER_DEBUG=true
doppler secrets get DATABASE_URL

# Enable API request logging
export DOPPLER_LOG_LEVEL=debug
doppler secrets --only-names
```

### Network Debugging
```bash
# Test API connectivity
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.doppler.com/v3/configs/config/secrets

# Check DNS resolution
nslookup api.doppler.com

# Test with different DNS
dig @8.8.8.8 api.doppler.com
```

### Configuration File Issues
```bash
# Check Doppler config file location
echo ~/.doppler/.doppler.yaml

# View configuration
cat ~/.doppler/.doppler.yaml

# Reset configuration
rm ~/.doppler/.doppler.yaml
doppler setup --project ruleiq --config dev
```

## Error Code Reference

### Common HTTP Status Codes
- **401 Unauthorized**: Invalid or expired token → Run `doppler login`
- **403 Forbidden**: Insufficient permissions → Contact admin
- **404 Not Found**: Project/secret doesn't exist → Check project/config
- **429 Too Many Requests**: Rate limited → Wait and retry
- **500 Internal Server Error**: Doppler service issue → Check status page

### CLI Exit Codes
- **0**: Success
- **1**: General error
- **2**: Authentication error
- **3**: Configuration error
- **4**: Network error

## Emergency Recovery Procedures

### Complete Service Failure
If Doppler service is completely unavailable:

1. **Use fallback file**:
   ```bash
   # Load from backup
   source .env.local
   
   # Verify critical secrets
   echo $DATABASE_URL
   echo $REDIS_URL
   ```

2. **Manual secret retrieval** (if you have backup):
   ```bash
   # From previous doppler export
   source doppler-backup-$(date +%Y%m%d).env
   ```

### Lost Authentication
If completely locked out:

1. **Revoke and recreate tokens**:
   - Log into Doppler dashboard
   - Revoke compromised tokens
   - Create new service tokens

2. **Re-authenticate CLI**:
   ```bash
   doppler logout
   doppler login
   doppler setup --project ruleiq --config dev
   ```

### Configuration Reset
If configuration is corrupted:

1. **Complete reset**:
   ```bash
   # Remove all configuration
   rm -rf ~/.doppler
   
   # Re-setup from scratch
   doppler login
   doppler setup --project ruleiq --config dev
   
   # Verify setup
   doppler secrets --only-names
   ```

## Monitoring & Health Checks

### Automated Health Check Script
```bash
#!/bin/bash
# File: doppler-health-check.sh

echo "🔍 Doppler Health Check - $(date)"
echo "========================================"

# Check CLI availability
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI not installed"
    exit 1
fi

# Check authentication
if ! doppler whoami &> /dev/null; then
    echo "❌ Not authenticated to Doppler"
    exit 1
fi

# Check project configuration
PROJECT=$(doppler configure get project 2>/dev/null)
CONFIG=$(doppler configure get config 2>/dev/null)

if [ "$PROJECT" != "ruleiq" ]; then
    echo "❌ Wrong project: $PROJECT (expected: ruleiq)"
    exit 1
fi

echo "✅ Project: $PROJECT"
echo "✅ Config: $CONFIG"

# Test secret access
CRITICAL_SECRETS="DATABASE_URL REDIS_URL OPENAI_API_KEY JWT_SECRET_KEY"
for secret in $CRITICAL_SECRETS; do
    if doppler secrets get $secret --plain >/dev/null 2>&1; then
        echo "✅ $secret: Accessible"
    else
        echo "❌ $secret: Failed"
        exit 1
    fi
done

# Test fallback availability
if [ -f ".env.local" ]; then
    echo "✅ Fallback file: Available"
else
    echo "⚠️  Fallback file: Missing"
fi

echo "========================================"
echo "🎉 All checks passed!"
```

### Usage
```bash
# Make executable
chmod +x doppler-health-check.sh

# Run health check
./doppler-health-check.sh

# Schedule in cron (optional)
# 0 */6 * * * /path/to/doppler-health-check.sh >> /var/log/doppler-health.log 2>&1
```

## Integration Testing

### Application Integration Test
```bash
# Test application startup with Doppler
doppler run -- python -c "
import os
required = ['DATABASE_URL', 'REDIS_URL', 'JWT_SECRET_KEY', 'OPENAI_API_KEY']
missing = [key for key in required if not os.getenv(key)]
if missing:
    print(f'❌ Missing secrets: {missing}')
    exit(1)
else:
    print('✅ All required secrets available')
"
```

### Newman/Postman Integration Test
```bash
# Test Postman collection with Doppler secrets
doppler run -- newman run ruleiq_postman_collection_with_doppler.json \
  --reporters cli,json \
  --reporter-json-export test-results.json

# Verify results
if [ -f "test-results.json" ]; then
    echo "✅ Postman integration test completed"
    jq '.run.stats' test-results.json
else
    echo "❌ Postman integration test failed"
fi
```

## Support Contacts

### Internal Support
- **Primary**: Check this troubleshooting guide first
- **Validation Report**: `/home/omar/Documents/ruleIQ/doppler_validation_report.md`
- **Setup Script**: `/home/omar/Documents/ruleIQ/setup_doppler_secrets.sh`

### Doppler Support
- **Documentation**: https://docs.doppler.com
- **Status Page**: https://status.doppler.com
- **Community**: https://community.doppler.com

### Emergency Escalation
1. Check Doppler status page for service outages
2. Use fallback `.env.local` file for immediate recovery
3. Review this troubleshooting guide for specific error patterns
4. Validate configuration using health check script

---

**Last Updated**: 2025-08-23  
**Next Review**: As needed based on issues encountered  
**Maintained By**: Archon AI Agent