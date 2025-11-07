# Security Setup Guide

## Overview

This guide explains how to configure authentication and security settings for Legal Events Extraction v2 in different environments.

## JWT Authentication

### Environment Modes

The system supports three environment modes controlled by `APP_ENV`:

1. **development** - Local development with relaxed security (default in docker-compose.yml)
2. **staging** - Pre-production with production security requirements
3. **production** - Production with strict security requirements

**Default behavior**: If `APP_ENV` is not set, the system defaults to `production` mode for safety-by-default.

### JWT Secret Key Configuration

#### Development Mode (`APP_ENV=development`)

**Behavior:**
- If `JWT_SECRET_KEY` is not set, uses an insecure fallback key
- Displays warning message: "⚠️ Using insecure development JWT secret"
- **ONLY safe for local development** - never use in staging or production

**Setup:**
```bash
# In .env or environment
APP_ENV=development

# JWT_SECRET_KEY is optional (fallback will be used)
```

**Warning:** The development fallback key is publicly known and should NEVER be used in any environment accessible from outside your local machine.

#### Staging/Production Mode (`APP_ENV=staging` or `APP_ENV=production`)

**Behavior:**
- `JWT_SECRET_KEY` **MUST** be explicitly set
- If not set, the API will fail to start with a clear error message
- Ensures no production deployment can accidentally use insecure credentials

**Setup:**

1. **Generate a secure secret key:**
   ```bash
   openssl rand -hex 32
   ```

   Example output:
   ```
   a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
   ```

2. **Set in environment:**
   ```bash
   # In .env file
   APP_ENV=production
   JWT_SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
   ```

3. **For Docker deployments:**
   ```bash
   # Set in .env file (recommended)
   echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env
   echo "APP_ENV=production" >> .env

   # Then start services
   docker compose -f docker-compose.yml up -d
   ```

4. **For Kubernetes/cloud deployments:**
   ```bash
   # Create secret
   kubectl create secret generic legal-events-secrets \
     --from-literal=jwt-secret-key=$(openssl rand -hex 32)

   # Reference in deployment
   env:
     - name: APP_ENV
       value: "production"
     - name: JWT_SECRET_KEY
       valueFrom:
         secretKeyRef:
           name: legal-events-secrets
           key: jwt-secret-key
   ```

### Testing JWT Configuration

#### Test Development Mode
```bash
# Unset JWT_SECRET_KEY to test fallback
unset JWT_SECRET_KEY
export APP_ENV=development

# Start API - should start with warning
uvicorn api.main:app --reload

# Expected output:
# ⚠️  Using insecure development JWT secret.
# This is ONLY safe for local development (APP_ENV=development).
# Generate a production key with: openssl rand -hex 32
```

#### Test Production Mode
```bash
# Unset JWT_SECRET_KEY to test fail-fast
unset JWT_SECRET_KEY
export APP_ENV=production

# Start API - should fail with clear error
uvicorn api.main:app --reload

# Expected output:
# ValueError: JWT_SECRET_KEY environment variable is required in production mode.
# Generate a secure secret with: openssl rand -hex 32
# Then set: JWT_SECRET_KEY=<generated-key> in your .env file or environment
```

#### Test Explicit Key
```bash
# Set explicit key (works in all modes)
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export APP_ENV=production

# Start API - should start successfully
uvicorn api.main:app --reload
```

## Migration Guide

### For Existing Deployments

#### If You Have `JWT_SECRET_KEY` Already Set
✅ **No action needed** - Your deployment will continue working in all `APP_ENV` modes.

#### If You Don't Have `JWT_SECRET_KEY` Set

⚠️ **Action required before upgrading to this version**

**Option 1: Generate and set a production key** (recommended for staging/production)
```bash
# Generate key
JWT_KEY=$(openssl rand -hex 32)

# Add to .env or set in environment
echo "JWT_SECRET_KEY=$JWT_KEY" >> .env
echo "APP_ENV=production" >> .env

# Restart services
docker compose restart api worker
```

**Option 2: Use development mode** (only for local development)
```bash
# Add to .env
echo "APP_ENV=development" >> .env

# Restart services
docker compose restart api worker
```

### Docker Compose Users

**Before upgrading:**
```bash
# Check current JWT configuration
docker compose exec api printenv JWT_SECRET_KEY

# If empty, set before upgrading
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env
```

**After upgrading:**
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose down
docker compose up -d --build

# Verify API started successfully
docker compose logs api | grep -i "jwt\|error"
```

## Security Best Practices

### JWT Secret Key Requirements

✅ **DO:**
- Generate keys with `openssl rand -hex 32` (256-bit entropy)
- Use different keys for development, staging, and production
- Store keys in secure secret management systems (HashiCorp Vault, AWS Secrets Manager, etc.)
- Rotate keys periodically (e.g., every 90 days)
- Use environment variables or mounted secrets, never commit to git

❌ **DON'T:**
- Use short or predictable keys
- Share keys between environments
- Commit keys to version control
- Use the development fallback in non-development environments
- Store keys in plain text files on servers

### Key Rotation Procedure

When rotating JWT secret keys:

1. **Generate new key:**
   ```bash
   NEW_JWT_KEY=$(openssl rand -hex 32)
   ```

2. **Update environment:**
   ```bash
   # Update .env or secret management system
   JWT_SECRET_KEY=$NEW_JWT_KEY
   ```

3. **Rolling restart:**
   ```bash
   # Zero-downtime restart (if using multiple replicas)
   docker compose up -d --force-recreate --no-deps api

   # Or gradual rollout in Kubernetes
   kubectl set env deployment/legal-events-api JWT_SECRET_KEY=$NEW_JWT_KEY
   kubectl rollout status deployment/legal-events-api
   ```

4. **Verify:**
   ```bash
   # Test authentication still works
   curl -H "Authorization: Bearer <test-token>" http://localhost:8000/v1/health
   ```

**Note:** Key rotation will invalidate all existing JWT tokens. Users will need to re-authenticate.

## Troubleshooting

### Error: "JWT_SECRET_KEY environment variable is required"

**Cause:** Running in staging/production mode without `JWT_SECRET_KEY` set.

**Solution:**
```bash
# Generate and set key
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# Or for temporary local development
export APP_ENV=development
```

### Warning: "Using insecure development JWT secret"

**Cause:** Running in development mode without `JWT_SECRET_KEY` set.

**Solution:**
- **If local development:** This is expected and safe. Ignore the warning.
- **If staging/production:** Set `APP_ENV=production` and `JWT_SECRET_KEY` immediately.

### API fails to start after upgrade

**Cause:** Upgraded to version with JWT security fix, but `JWT_SECRET_KEY` not set.

**Solution:**
```bash
# Quick fix: Enable development mode (local only)
export APP_ENV=development
docker compose restart api

# Proper fix: Set production key
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export APP_ENV=production
docker compose restart api
```

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `production` | Environment mode: `development`, `staging`, or `production` |
| `JWT_SECRET_KEY` | Conditional | None | JWT signing secret. Required in staging/production, optional in development |
| `JWT_TOKEN_EXPIRE_MINUTES` | No | `1440` (24h) | JWT token expiration time in minutes |

## Security Checklist

Before deploying to production:

- [ ] `APP_ENV=production` is set
- [ ] `JWT_SECRET_KEY` is set to a 256-bit random value
- [ ] `JWT_SECRET_KEY` is stored securely (not in git)
- [ ] Different `JWT_SECRET_KEY` values are used for dev/staging/prod
- [ ] API starts without warnings
- [ ] Authentication endpoints are working
- [ ] SSL/TLS is enabled (HTTPS)
- [ ] Firewall rules restrict API access
- [ ] Monitoring and alerting is configured

## References

- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Docker Secrets Management](https://docs.docker.com/engine/swarm/secrets/)

## Support

For security questions or issues:
1. Check this documentation first
2. Review logs: `docker compose logs api | grep -i "jwt\|auth\|security"`
3. Open an issue with `[SECURITY]` prefix (for non-sensitive issues)
4. For sensitive security issues, contact the maintainers directly
