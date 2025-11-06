# Security Configuration Guide

**Last Updated**: 2025-11-06
**Phase**: Production Security Hardening (Phase 1)

## Overview

This document covers the security configuration required to deploy the Legal Events API to production. All security measures are critical and must be implemented before any production deployment.

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Authentication](#authentication)
3. [Credentials Management](#credentials-management)
4. [Database Security](#database-security)
5. [MinIO Storage Security](#minio-storage-security)
6. [API Security](#api-security)
7. [Deployment Checklist](#deployment-checklist)

---

## Environment Variables

All sensitive configuration must be provided via environment variables, **never** hardcoded in source files.

### Required Variables

These variables **MUST** be set before starting the application:

| Variable | Purpose | Required | Generation |
|----------|---------|----------|-----------|
| `JWT_SECRET_KEY` | JWT token signing | ✅ Yes | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD` | Database password | ✅ Yes | Generate strong password |
| `MINIO_ROOT_PASSWORD` | MinIO admin password | ✅ Yes | Generate strong password |

### Optional Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `POSTGRES_DB` | Database name | `legal_events` |
| `POSTGRES_USER` | Database user | `legal_user` |
| `MINIO_ROOT_USER` | MinIO root user | `minioadmin` |
| `MINIO_ENDPOINT` | MinIO endpoint | `minio:9000` |
| `MINIO_PUBLIC_ENDPOINT` | MinIO public URL | `localhost:9000` |
| `MINIO_BUCKET` | MinIO bucket name | `legal-documents` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379` |
| `API_KEY_ADMIN` | Admin API key | (optional) |
| `API_KEY_USER` | User API key | (optional) |

### Environment File Setup

1. **Copy the template:**
   ```bash
   cp .env.template .env
   ```

2. **Edit .env with secure values:**
   ```bash
   # Generate secure passwords
   python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env
   python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))" >> .env
   python3 -c "import secrets; print('MINIO_ROOT_PASSWORD=' + secrets.token_urlsafe(32))" >> .env
   ```

3. **Restrict file permissions:**
   ```bash
   chmod 600 .env
   ```

4. **Add .env to .gitignore:**
   ```bash
   echo ".env" >> .gitignore
   ```

---

## Authentication

### JWT Bearer Token Authentication

The API uses JWT (JSON Web Tokens) for stateless authentication.

#### How It Works

1. **Token Creation**: Users authenticate with email/password → receive JWT token
2. **Token Storage**: Client stores token securely (e.g., HTTPOnly cookies)
3. **Token Validation**: Each request includes `Authorization: Bearer <token>`
4. **Token Expiration**: Tokens expire after 24 hours (configurable)

#### Protected Endpoints

All write operations (`POST`, `PUT`) require authentication:

- `POST /v1/clients` - Create client
- `POST /v1/cases` - Create case
- `POST /v1/cases/{case_id}/assign` - Assign user to case
- `POST /v1/runs` - Create run
- `PUT /v1/runs/{run_id}/start` - Start processing

#### Request Format

```bash
# With JWT token
curl -H "Authorization: Bearer <your-jwt-token>" \
  -X POST http://localhost:8000/v1/clients \
  -H "Content-Type: application/json" \
  -d '{"name": "Client Name", "reference_code": "REF001"}'
```

#### Token Payload

JWTs contain:
- `sub` - User email (subject)
- `role` - User role (admin, case_manager, reviewer)
- `exp` - Expiration time (Unix timestamp)

### Disabling Optional Auth (Phase 1 Behavior)

Currently, the `get_current_user()` dependency returns `None` if no token is provided (optional auth). For strict production auth, modify `api/auth.py:104-113`:

```python
# CURRENT (optional auth)
if not credentials:
    return None

# PRODUCTION (required auth)
if not credentials:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

---

## Credentials Management

### Password Hashing

User passwords are hashed using **bcrypt** via passlib:

- Algorithm: bcrypt
- Cost factor: 12 (default)
- Never stored in plaintext

### API Keys (Alternative)

For service-to-service authentication, API keys can be configured:

```env
API_KEY_ADMIN=<secure-random-key>
API_KEY_USER=<secure-random-key>
```

### Secrets Rotation

**Schedule**: Rotate all secrets quarterly (every 90 days)

**Process**:
1. Generate new secret value
2. Update environment variable
3. Restart affected services
4. Update old secret in secrets management system
5. Remove old secret after verification

**Critical Variables to Rotate**:
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- API provider keys (OpenRouter, Anthropic, etc.)

---

## Database Security

### PostgreSQL Configuration

**Host**: Only accessible within Docker network (not exposed)

**Network Access**:
```yaml
# SECURE: Only internal access
postgres:
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Environment variable
  ports:
    - "5432:5432"  # Only for local development
```

**For Production**:
- Do NOT expose port 5432 externally
- Use managed PostgreSQL service (RDS, Cloud SQL, etc.)
- Enable encryption at rest
- Enable SSL/TLS for connections

### Connection Pool

SQLAlchemy pool configuration (api/database.py):
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True
)
```

---

## MinIO Storage Security

### CORS Configuration

MinIO requires manual CORS setup (see docs/MINIO_CORS_SETUP.md):

1. **Via Web Console**: http://localhost:9001
2. **Via mc CLI**:
   ```bash
   mc cors set minio/legal-documents \
     --config-json cors-config.xml
   ```

### MinIO Credentials

**Default** (development only):
```env
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
```

**Production** (required):
```env
MINIO_ROOT_USER=secure-username
MINIO_ROOT_PASSWORD=<strong-random-password>
```

### Bucket Security

- **Public Access**: Disabled (not exposed to internet)
- **Versioning**: Enabled for backup/recovery
- **Encryption**: TLS for all connections
- **Access Logs**: Enabled for audit trail

### Presigned URLs

The API generates presigned URLs with:
- **Expiration**: 24 hours
- **Permissions**: GET/PUT (no DELETE)
- **Path Format**: `clients/{client_id}/cases/{case_id}/runs/{run_id}/...`

---

## API Security

### CORS Configuration

Currently allows development origins:
```python
allow_origins=[
    "http://localhost:3000",    # React dev server
    "http://localhost:5001",    # Alternative
]
```

**For Production**, restrict to actual frontend domain:
```python
allow_origins=[os.getenv("FRONTEND_URL")]
```

### Rate Limiting (Future)

Plan for Phase 2:
- Rate limit: 100 requests/minute per IP
- Burst limit: 10 requests/second
- Throttle slowdown endpoints

### Input Validation

All endpoints use Pydantic v2 models for validation:
```python
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    reference_code: str = Field(..., pattern="^[A-Z0-9_-]+$")
    notes: Optional[str] = Field(None, max_length=2000)
```

### HTTPS/TLS

**Development**: HTTP (localhost only)
**Production**: HTTPS required with valid certificate

Configuration:
```python
# Production setup via reverse proxy (nginx)
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /api {
        proxy_pass http://api:8000;
    }
}
```

### Security Headers

Add via reverse proxy (nginx/Apache):
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

---

## Deployment Checklist

### Pre-Deployment ✅

- [ ] Generate all required secrets (see Environment Variables above)
- [ ] Create .env file with secure values
- [ ] Restrict .env permissions: `chmod 600 .env`
- [ ] Verify JWT_SECRET_KEY is set and non-empty
- [ ] Review CORS origins for your deployment
- [ ] Disable CORS debug origins in production
- [ ] Set up HTTPS/TLS certificates
- [ ] Configure rate limiting (if Phase 2 complete)
- [ ] Enable input validation (default)
- [ ] Review database backup strategy
- [ ] Configure database encryption at rest
- [ ] Test all authentication flows

### Deployment ✅

- [ ] Deploy with environment variables (never .env file)
- [ ] Verify all services health (GET /health)
- [ ] Test protected endpoints return 401/403 without auth
- [ ] Test protected endpoints work with valid JWT
- [ ] Verify database connectivity
- [ ] Verify MinIO connectivity
- [ ] Verify Redis connectivity
- [ ] Monitor logs for authentication failures
- [ ] Load test with expected request volume

### Post-Deployment ✅

- [ ] Enable CloudWatch/Datadog monitoring
- [ ] Set up log aggregation
- [ ] Configure alerts for failed auth attempts
- [ ] Configure alerts for secret expiration
- [ ] Schedule quarterly secret rotation
- [ ] Review audit logs for suspicious activity
- [ ] Backup database configuration
- [ ] Test disaster recovery procedures
- [ ] Document emergency access procedures

---

## Security Incident Response

### Suspected Secret Compromise

1. **Immediate Action** (within 1 hour):
   - Revoke compromised secret
   - Generate new secret value
   - Update all systems with new secret
   - Restart all services

2. **Investigation** (within 24 hours):
   - Review access logs for unauthorized access
   - Check for data exfiltration
   - Identify timeline of compromise
   - Notify security team

3. **Follow-up** (within 1 week):
   - Rotate all related secrets
   - Update security procedures
   - Conduct security audit
   - Document lessons learned

### Unauthorized Access

1. **Immediate**:
   - Block suspicious IP addresses
   - Disable compromised user accounts
   - Review recent changes

2. **Investigation**:
   - Check audit logs
   - Identify access patterns
   - Review database changes

3. **Recovery**:
   - Restore from clean backup if needed
   - Implement additional monitoring
   - Update security policies

---

## Compliance

### Data Protection

- **Encryption in Transit**: TLS/HTTPS required
- **Encryption at Rest**: Database encryption enabled
- **Data Retention**: Configurable per case (90-day default)
- **Data Deletion**: Automatic cleanup after retention period

### Audit Trail

All protected endpoints log:
- User ID (from JWT)
- Timestamp
- Action (create, update, delete)
- Resource ID
- IP address (from request)

### Documentation

- This file documents all security measures
- Update this file when security changes
- Review quarterly with security team
- Share with all developers

---

## Additional Resources

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

**Questions?** Contact the security team or file an issue.
