# Production Deployment Guide

Complete guide for deploying Legal Events Production system to staging and production environments.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Decision Points](#decision-points)
4. [Phase 1: Prepare Configuration](#phase-1-prepare-configuration)
5. [Phase 2: Set Up Infrastructure](#phase-2-set-up-infrastructure)
6. [Phase 3: Deploy Staging](#phase-3-deploy-staging)
7. [Phase 4: Testing](#phase-4-testing)
8. [Phase 5: Production Deployment](#phase-5-production-deployment)
9. [Phase 6: Post-Deployment](#phase-6-post-deployment)
10. [Rollback Procedures](#rollback-procedures)
11. [Troubleshooting](#troubleshooting)

---

## Overview

This guide walks you through deploying the Legal Events Production system using a **staging-first approach**:

```
Development → Staging → Production
```

**Timeline Estimate:**
- Phase 1-2 (Setup): 3-4 hours
- Phase 3 (Staging): 1-2 hours
- Phase 4 (Testing): 8-12 hours
- Phase 5 (Production): 2-3 hours
- **Total: 14-21 hours**

**What You'll Need:**
- Server/VPS with Docker
- Domain name(s)
- LLM provider API keys
- 1-2 days for staging testing

---

## Prerequisites

### Technical Requirements

**Server Specifications (Minimum):**
- ✅ CPU: 4 cores (8+ recommended)
- ✅ RAM: 8 GB (16+ GB recommended)
- ✅ Storage: 50 GB SSD (100+ GB recommended)
- ✅ OS: Ubuntu 22.04 LTS or similar Linux distribution
- ✅ Network: Public IP address

**Software Requirements:**
- ✅ Docker Engine 24.0+
- ✅ Docker Compose v2.20+
- ✅ Git
- ✅ curl, jq (for testing)

**Verify prerequisites:**
```bash
# Check Docker version
docker --version  # Should be 24.0+
docker compose version  # Should be v2.20+

# Check system resources
free -h  # RAM
df -h    # Disk space
nproc    # CPU cores

# Check network
curl -4 ifconfig.me  # Your public IP
```

### Domain Setup

You need **two subdomains** (or one domain with subdomains):

1. **API Domain:** `api.yourdomain.com`
2. **Storage Domain:** `storage.yourdomain.com`

**DNS Configuration:**
```
# A Records (point to your server IP)
api.yourdomain.com       → YOUR_SERVER_IP
storage.yourdomain.com   → YOUR_SERVER_IP

# Optional: Staging subdomains
api-staging.yourdomain.com     → YOUR_STAGING_IP
storage-staging.yourdomain.com → YOUR_STAGING_IP
```

**Verify DNS:**
```bash
nslookup api.yourdomain.com
dig api.yourdomain.com +short
```

### LLM Provider API Keys

Get API keys from one or more providers:

| Provider | Dashboard URL | Free Tier? |
|----------|--------------|------------|
| Google Gemini | https://makersuite.google.com/app/apikey | Yes (generous) |
| OpenRouter | https://openrouter.ai/keys | Paid ($5 min) |
| OpenAI | https://platform.openai.com/api-keys | Paid ($5 min) |
| Anthropic | https://console.anthropic.com/settings/keys | Paid ($5 min) |
| DeepSeek | https://platform.deepseek.com/api-keys | Paid |

**Recommended:** Start with **Google Gemini** (free tier, generous limits).

---

## Decision Points

Before proceeding, decide on the following:

### 1. Deployment Target

**Where will you deploy?**

- [ ] **Option A:** VPS (DigitalOcean, Linode, Vultr)
  - Cost: $20-40/month
  - Control: Full
  - Complexity: Medium

- [ ] **Option B:** Cloud VM (AWS EC2, GCP Compute, Azure VM)
  - Cost: $30-60/month
  - Control: Full
  - Complexity: Medium-High

- [ ] **Option C:** Self-hosted (home server, office server)
  - Cost: Hardware only
  - Control: Full
  - Complexity: High (network setup)

**Recommendation:** VPS (Option A) for simplicity and cost-effectiveness.

### 2. TLS/HTTPS Setup

**How will you secure connections?**

- [ ] **Option A:** Nginx Reverse Proxy (Recommended)
  - Best for: Most use cases
  - Complexity: Medium
  - Guide: `docs/TLS_SETUP_GUIDE.md` - Option A

- [ ] **Option B:** Cloud Load Balancer
  - Best for: Cloud deployments (AWS/GCP/Azure)
  - Complexity: Medium
  - Guide: `docs/TLS_SETUP_GUIDE.md` - Option B

- [ ] **Option C:** Cloudflare Tunnel (Zero Trust)
  - Best for: No public IP, behind NAT, easiest setup
  - Complexity: Low
  - Guide: `docs/TLS_SETUP_GUIDE.md` - Option C

**Recommendation:** Nginx (Option A) for maximum control, Cloudflare Tunnel (Option C) for easiest setup.

### 3. LLM Provider

**Which provider will you use?**

- [ ] Google Gemini (Free tier, recommended for starting)
- [ ] OpenRouter (Access to multiple models)
- [ ] OpenAI (GPT-4, reliable)
- [ ] Anthropic (Claude, excellent quality)
- [ ] Mix of providers (configure multiple)

**Recommendation:** Start with **Google Gemini** (free and generous limits).

### 4. Staging Environment

**Do you need a separate staging environment?**

- [ ] **Yes, separate server** (Recommended)
  - Cost: Additional server ($10-20/month)
  - Safety: High (isolated testing)

- [ ] **Yes, same server, different ports** (Budget option)
  - Cost: None
  - Safety: Medium (shared resources)

- [ ] **No, deploy directly to production** (Not recommended)
  - Cost: None
  - Safety: Low (risky)

**Recommendation:** Separate staging environment for safety.

### 5. Backup Strategy

**How will you back up data?**

- [ ] **Daily automated backups** (Recommended)
  - PostgreSQL dumps
  - MinIO bucket snapshots
  - Configuration files

- [ ] **Weekly manual backups**
  - Lower cost, higher risk

- [ ] **No backups** (Not recommended)

**Recommendation:** Daily automated backups.

### 6. Monitoring

**How will you monitor the system?**

- [ ] **Basic:** Docker logs + manual checks
- [ ] **Intermediate:** Prometheus + Grafana dashboards
- [ ] **Advanced:** Full observability stack (APM, alerts)

**Recommendation:** Start with basic monitoring, upgrade as needed.

---

## Phase 1: Prepare Configuration

**Time Required:** 30-60 minutes

### Step 1.1: Clone Repository (If Not Already)

```bash
git clone https://github.com/molotovsingh/legal_events_prod.git
cd legal_events_prod
```

### Step 1.2: Generate Secure Credentials

Run the credential generator:

```bash
python3 scripts/generate_secrets.py > secrets.txt
```

**Output example:**
```
JWT_SECRET_KEY=Abc123XyzRandomSecureString...
POSTGRES_PASSWORD=Def456RandomPassword...
MINIO_ROOT_USER=minio_a1b2c3d4
MINIO_ROOT_PASSWORD=Ghi789RandomPassword...
...
```

**⚠️ SECURITY:** Save `secrets.txt` to a **secure location** (password manager, secrets vault) and delete it from the server after copying values.

### Step 1.3: Create Production Environment File

```bash
# Copy template
cp .env.production.template .env.production

# Edit with your values
nano .env.production
```

**Fill in ALL placeholders:**

1. **Copy generated credentials** from `secrets.txt`
2. **Set domain names:**
   ```bash
   MINIO_PUBLIC_ENDPOINT=storage.yourdomain.com
   CORS_ORIGINS=https://app.yourdomain.com
   ```

3. **Add LLM provider API keys:**
   ```bash
   GOOGLE_API_KEY=your-google-api-key-here
   ```

4. **Set production environment:**
   ```bash
   APP_ENV=production
   ```

5. **Enable TLS (after setup):**
   ```bash
   # Set to true AFTER TLS is configured
   MINIO_SECURE=false  # Change to true later
   ```

### Step 1.4: Create Staging Environment File

```bash
# Copy template
cp .env.staging.template .env.staging

# Edit with your values
nano .env.staging
```

**Use different credentials than production!**

### Step 1.5: Verify Configuration

```bash
# Check production config has no placeholders
grep -i "<YOUR_" .env.production
# Should return no results

# Check staging config has no placeholders
grep -i "<YOUR_" .env.staging
# Should return no results
```

**✅ Checklist:**
- [ ] Credentials generated and saved securely
- [ ] `.env.production` created with all values filled
- [ ] `.env.staging` created with all values filled
- [ ] No placeholder values remaining
- [ ] Files added to `.gitignore` (already done)

---

## Phase 2: Set Up Infrastructure

**Time Required:** 2-4 hours (depending on TLS option)

### Step 2.1: Prepare Server

**Install Docker and Docker Compose:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect

# Verify installation
docker --version
docker compose version
```

### Step 2.2: Configure Firewall

```bash
# Install UFW (if not already installed)
sudo apt install -y ufw

# Allow SSH (IMPORTANT: Do this first!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct access to application ports (security)
sudo ufw deny 8000/tcp  # API should be accessed via reverse proxy
sudo ufw deny 9000/tcp  # MinIO should be accessed via reverse proxy

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Step 2.3: Set Up TLS/HTTPS

**Follow the detailed guide:** `docs/TLS_SETUP_GUIDE.md`

**Choose your option:**
- **Option A:** Nginx Reverse Proxy
- **Option B:** Cloud Load Balancer
- **Option C:** Cloudflare Tunnel

**After completing TLS setup:**

1. Verify HTTPS works:
   ```bash
   curl -v https://api.yourdomain.com
   ```

2. Update `.env.production` and `.env.staging`:
   ```bash
   MINIO_SECURE=true
   ```

**✅ Checklist:**
- [ ] TLS certificates obtained
- [ ] Reverse proxy/load balancer configured
- [ ] HTTPS working for both domains
- [ ] Firewall configured
- [ ] `MINIO_SECURE=true` in env files

---

## Phase 3: Deploy Staging

**Time Required:** 1-2 hours

### Step 3.1: Transfer Files to Staging Server

```bash
# From your local machine, sync to staging server
rsync -avz --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.env' \
    ./ user@staging-server:/opt/legal-events/

# SSH into staging server
ssh user@staging-server
cd /opt/legal-events
```

### Step 3.2: Deploy Staging Environment

```bash
# Start staging environment
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d

# Check all services are running
docker compose -f docker-compose.staging.yml ps

# Expected output:
# NAME                          STATUS
# legal_events_staging_api      Up
# legal_events_staging_worker   Up
# legal_events_staging_db       Up
# legal_events_staging_redis    Up
# legal_events_staging_minio    Up
# legal_events_staging_ui       Up
```

### Step 3.3: Verify Services

```bash
# Check API logs
docker compose -f docker-compose.staging.yml logs api

# Check worker logs
docker compose -f docker-compose.staging.yml logs worker

# Test API health endpoint
curl https://api-staging.yourdomain.com/health
# Should return: {"status":"healthy"}
```

### Step 3.4: Initialize Database

```bash
# Database migrations run automatically on startup
# Verify by checking API logs

docker compose -f docker-compose.staging.yml logs api | grep -i "migration\|alembic"
# Should show successful migration messages
```

### Step 3.5: Create Admin User

```bash
# Option 1: Via API (if user creation endpoint exists)
curl -X POST https://api-staging.yourdomain.com/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{
      "email": "admin@legalevents.local",
      "password": "admin",
      "role": "admin"
    }'

# Option 2: Via database
docker compose -f docker-compose.staging.yml exec postgres psql -U legal_user_staging -d legal_events_staging
# Then run SQL to create user
```

**✅ Checklist:**
- [ ] All staging services running
- [ ] API health check returns 200 OK
- [ ] Worker registered in Redis
- [ ] Database migrations completed
- [ ] Admin user created

---

## Phase 4: Testing

**Time Required:** 8-12 hours (can be spread over multiple days)

### Step 4.1: Run Automated Test Suite

```bash
# Configure test script
export API_URL="https://api-staging.yourdomain.com"
export TEST_EMAIL="admin@legalevents.local"
export TEST_PASSWORD="admin"

# Run tests
./scripts/test_staging.sh

# Expected output:
# ============================================================================
# Test Summary
# ============================================================================
# Tests Run:    15
# Tests Passed: 15
# Tests Failed: 0
#
# ✓ All tests passed!
# 🚀 Staging environment is ready for production deployment.
```

### Step 4.2: Manual Testing Checklist

**Authentication & Authorization:**
- [ ] User can log in
- [ ] JWT token generated correctly
- [ ] Invalid credentials rejected
- [ ] Token expiry works

**Client Management:**
- [ ] Create client
- [ ] View client list
- [ ] Update client
- [ ] Delete client (if implemented)

**Case Management:**
- [ ] Create case for client
- [ ] View cases
- [ ] Update case
- [ ] Filter cases by client

**Document Processing:**
- [ ] Upload document
- [ ] Create run with provider selection
- [ ] Start processing
- [ ] Monitor run status
- [ ] View extracted events
- [ ] Verify event data accuracy

**Export Functionality:**
- [ ] Export events as CSV
- [ ] Export events as Excel
- [ ] Export events as JSON
- [ ] Verify downloaded files contain correct data

**Provider Testing:**
- [ ] Test with primary provider (e.g., Gemini)
- [ ] Test with secondary provider (if configured)
- [ ] Verify all providers show in dropdown
- [ ] Verify model selection works

**Error Handling:**
- [ ] Upload invalid file (should fail gracefully)
- [ ] Process with missing API key (should show error)
- [ ] Submit invalid API request (should return 400/422)
- [ ] Test rate limiting (if configured)

**Performance:**
- [ ] Document upload completes within 30 seconds
- [ ] Event extraction completes within 2 minutes
- [ ] Export generation completes within 10 seconds
- [ ] API response times < 500ms

### Step 4.3: Load Testing (Optional)

```bash
# Install Apache Bench
sudo apt install -y apache2-utils

# Test API health endpoint
ab -n 1000 -c 10 https://api-staging.yourdomain.com/health

# Expected results:
# - 0 failed requests
# - Mean response time < 100ms
```

### Step 4.4: Security Testing

**Run security checks:**

1. **SSL/TLS Test:**
   - Go to: https://www.ssllabs.com/ssltest/
   - Enter: `api-staging.yourdomain.com`
   - Aim for: A or A+ rating

2. **Security Headers:**
   - Go to: https://securityheaders.com/
   - Enter: `api-staging.yourdomain.com`
   - Aim for: A or B rating

3. **Check for exposed secrets:**
   ```bash
   # Verify environment variables not exposed
   curl https://api-staging.yourdomain.com/debug
   # Should return 404 (endpoint shouldn't exist)

   # Check headers don't leak version info
   curl -I https://api-staging.yourdomain.com/
   ```

### Step 4.5: Document Issues

Create a test results document:

```markdown
# Staging Test Results

Date: YYYY-MM-DD
Tester: Your Name

## Summary
- Total Tests: X
- Passed: Y
- Failed: Z

## Failed Tests (if any)
1. Test Name
   - Issue: Description
   - Severity: High/Medium/Low
   - Fix Required: Yes/No

## Performance Results
- Average API response time: Xms
- Document processing time: Xm Ys
- Export generation time: Xs

## Security Results
- SSL Labs Rating: A+
- Security Headers Rating: B
- Known Vulnerabilities: None

## Recommendation
☐ Ready for production
☐ Needs fixes before production
```

**✅ Checklist:**
- [ ] All automated tests passed
- [ ] All manual tests completed
- [ ] Performance acceptable
- [ ] Security checks passed
- [ ] Issues documented
- [ ] Fixes applied (if needed)

---

## Phase 5: Production Deployment

**Time Required:** 2-3 hours

### Step 5.1: Final Pre-Deployment Checks

```bash
# Verify production config
cat .env.production | grep -E "(APP_ENV|MINIO_SECURE|MINIO_PUBLIC_ENDPOINT)"

# Should show:
# APP_ENV=production
# MINIO_SECURE=true
# MINIO_PUBLIC_ENDPOINT=storage.yourdomain.com

# Check Git status (should be clean)
git status

# Verify latest code
git log -1
```

### Step 5.2: Transfer Files to Production Server

```bash
# From your local machine
rsync -avz --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='.env.staging' \
    ./ user@production-server:/opt/legal-events/

# SSH into production server
ssh user@production-server
cd /opt/legal-events
```

### Step 5.3: Deploy Production

```bash
# IMPORTANT: Use production compose file (no hot-reload)
docker compose -f docker-compose.yml --env-file .env.production up -d

# Monitor startup
docker compose logs -f

# Wait for all services to be healthy
# Press Ctrl+C after services are up
```

### Step 5.4: Verify Production Deployment

```bash
# Check service status
docker compose ps

# All services should show "Up" status

# Test health endpoint
curl https://api.yourdomain.com/health

# Should return: {"status":"healthy"}

# Check API logs for errors
docker compose logs api --tail=100 | grep -i error

# Check worker logs
docker compose logs worker --tail=100 | grep -i error
```

### Step 5.5: Create Admin User

```bash
# Same as staging (Step 3.5)
curl -X POST https://api.yourdomain.com/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{
      "email": "admin@yourdomain.com",
      "password": "SECURE_PASSWORD_HERE",
      "role": "admin"
    }'
```

### Step 5.6: Smoke Tests

Run critical tests on production:

```bash
# Test login
curl -X POST https://api.yourdomain.com/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{
      "username": "admin@yourdomain.com",
      "password": "SECURE_PASSWORD_HERE"
    }'

# Should return JWT token

# Test provider discovery
curl https://api.yourdomain.com/v1/providers?enabled=true \
    -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should return list of providers
```

### Step 5.7: Monitor for Issues

```bash
# Watch logs for 5-10 minutes
docker compose logs -f

# Look for:
# - API startup complete
# - Worker registered
# - No error messages
# - Health checks passing
```

**✅ Checklist:**
- [ ] Production services deployed
- [ ] All containers healthy
- [ ] Health endpoint returns 200 OK
- [ ] Admin user created
- [ ] Login works
- [ ] Provider discovery works
- [ ] No errors in logs
- [ ] Frontend accessible

---

## Phase 6: Post-Deployment

### Step 6.1: Set Up Monitoring

**Basic monitoring script:**

Create `/opt/legal-events/scripts/monitor.sh`:

```bash
#!/bin/bash
# Simple health check script

API_URL="https://api.yourdomain.com"
EMAIL="your-email@example.com"

# Check API health
response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")

if [ "$response" != "200" ]; then
    echo "API is down! Status: $response" | mail -s "Legal Events API Alert" "$EMAIL"
fi

# Check disk space
disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 80 ]; then
    echo "Disk usage is high: ${disk_usage}%" | mail -s "Legal Events Disk Alert" "$EMAIL"
fi

# Check docker services
down_services=$(docker compose ps --format json | jq -r 'select(.State != "running") | .Name')
if [ -n "$down_services" ]; then
    echo "Services down: $down_services" | mail -s "Legal Events Service Alert" "$EMAIL"
fi
```

**Schedule with cron:**

```bash
# Edit crontab
crontab -e

# Add line (check every 5 minutes)
*/5 * * * * /opt/legal-events/scripts/monitor.sh
```

### Step 6.2: Set Up Backups

**Database backup script:**

Create `/opt/legal-events/scripts/backup.sh`:

```bash
#!/bin/bash
# Backup script

BACKUP_DIR="/opt/backups/legal-events"
DATE=$(date +%Y%m%d-%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
docker compose exec -T postgres pg_dump -U legal_user legal_events > "$BACKUP_DIR/database-$DATE.sql"

# Backup MinIO (optional, if using file storage)
# docker compose exec -T minio-client mc mirror minio/legal-documents "$BACKUP_DIR/minio-$DATE/"

# Backup configuration
cp .env.production "$BACKUP_DIR/env-$DATE.backup"

# Compress backups older than 1 day
find "$BACKUP_DIR" -name "*.sql" -mtime +1 -exec gzip {} \;

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Schedule daily backups:**

```bash
# Edit crontab
crontab -e

# Add line (daily at 2 AM)
0 2 * * * /opt/legal-events/scripts/backup.sh
```

### Step 6.3: Set Up Log Rotation

**Configure Docker log rotation:**

Create `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Restart Docker:**

```bash
sudo systemctl restart docker
docker compose up -d
```

### Step 6.4: Document Deployment

Create deployment record:

```markdown
# Production Deployment Record

## Deployment Details
- Date: YYYY-MM-DD HH:MM
- Deployed By: Your Name
- Git Commit: abc123def
- Version: v0.2.1

## Services Deployed
- API: legal_events_api
- Worker: legal_events_worker
- Database: PostgreSQL 16
- Cache: Redis 7
- Storage: MinIO
- Frontend: Nginx

## Configuration
- Domain: api.yourdomain.com
- TLS: Enabled (Let's Encrypt)
- Provider: Google Gemini
- Environment: production

## Post-Deployment Checks
- [x] Health endpoint: OK
- [x] Login: OK
- [x] Document processing: OK
- [x] Exports: OK

## Known Issues
- None

## Rollback Plan
- Previous version: v0.2.0
- Rollback command: docker compose down && git checkout v0.2.0 && docker compose up -d
```

**✅ Checklist:**
- [ ] Monitoring set up
- [ ] Backups scheduled
- [ ] Log rotation configured
- [ ] Deployment documented
- [ ] Team notified

---

## Rollback Procedures

If deployment fails or critical issues are discovered:

### Emergency Rollback

```bash
# Stop current deployment
docker compose down

# Checkout previous working version
git checkout <PREVIOUS_TAG>  # e.g., v0.2.0

# Restore previous environment (if changed)
cp .env.production.backup .env.production

# Rebuild and restart
docker compose build
docker compose up -d

# Restore database backup (if needed)
docker compose exec -T postgres psql -U legal_user legal_events < /opt/backups/database-YYYYMMDD.sql

# Verify rollback
curl https://api.yourdomain.com/health
docker compose logs
```

### Partial Rollback (Single Service)

```bash
# Rollback only API service
docker compose stop api
git checkout <PREVIOUS_TAG> -- api/
docker compose build api
docker compose up -d api

# Or rollback worker
docker compose stop worker
git checkout <PREVIOUS_TAG> -- worker/
docker compose build worker
docker compose up -d worker
```

---

## Troubleshooting

### Issue: Services Won't Start

**Symptoms:** `docker compose ps` shows "Exited" or "Restarting"

**Solutions:**
```bash
# Check logs
docker compose logs <service-name>

# Common causes:
# 1. Environment variables missing
docker compose config  # Validates config

# 2. Port conflicts
sudo lsof -i :8000  # Check what's using the port

# 3. Database connection fails
docker compose exec postgres psql -U legal_user -d legal_events

# 4. Redis connection fails
docker compose exec redis redis-cli ping
```

### Issue: API Returns 500 Errors

**Symptoms:** Health check fails, API endpoints return 500

**Solutions:**
```bash
# Check API logs
docker compose logs api --tail=100

# Common causes:
# 1. Database connection error - check DATABASE_URL
# 2. Missing environment variable - check .env.production
# 3. Redis connection error - check REDIS_URL

# Test database connectivity
docker compose exec api python3 << 'EOF'
import psycopg2
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print("Database connected!")
conn.close()
EOF
```

### Issue: Document Processing Fails

**Symptoms:** Runs stay in "queued" status, never complete

**Solutions:**
```bash
# Check worker is running
docker compose ps worker

# Check worker logs
docker compose logs worker --tail=100

# Common causes:
# 1. Worker not registered in Redis
docker compose exec redis redis-cli SCARD rq:workers

# 2. API key missing/invalid
# Check .env.production has correct API keys

# 3. Provider not registered
curl https://api.yourdomain.com/v1/providers

# Restart worker
docker compose restart worker
```

### Issue: MinIO Upload Fails

**Symptoms:** CORS errors, presigned URL errors

**Solutions:**
```bash
# 1. Verify MINIO_SECURE matches reality
# If using HTTPS, must be: MINIO_SECURE=true

# 2. Check MINIO_PUBLIC_ENDPOINT is accessible from browser
curl https://storage.yourdomain.com/minio/health/live

# 3. Check CORS_ORIGINS includes frontend domain
grep CORS_ORIGINS .env.production

# 4. Test presigned URL generation
curl "https://api.yourdomain.com/v1/documents/upload-url?client_id=1&case_id=1&run_id=1&filename=test.pdf" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Issue: TLS Certificate Errors

**Symptoms:** Browser shows "Not Secure", certificate expired

**Solutions:**
```bash
# Check certificate validity
openssl x509 -in /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem -noout -dates

# Renew certificate
sudo certbot renew

# Reload reverse proxy
sudo systemctl reload nginx  # or your reverse proxy

# Check auto-renewal is working
sudo systemctl status certbot.timer
```

### Getting Help

If you're stuck:

1. **Check logs:** `docker compose logs -f`
2. **Review documentation:** `docs/` directory
3. **Search issues:** Check GitHub issues
4. **Create issue:** File bug report with logs

---

## Success Criteria

Your deployment is successful when:

- ✅ All services running (`docker compose ps` shows all "Up")
- ✅ Health endpoint returns 200 OK
- ✅ User can log in
- ✅ User can create client, case, run
- ✅ Document processing works end-to-end
- ✅ Events display correctly
- ✅ Exports work (CSV, Excel, JSON)
- ✅ TLS/HTTPS working (green padlock)
- ✅ No errors in logs
- ✅ Monitoring active
- ✅ Backups scheduled

**Congratulations!** 🎉 Your production deployment is complete.

---

## Next Steps

After successful deployment:

1. **Monitor for 24-48 hours** - Watch for any issues
2. **User onboarding** - Create accounts for real users
3. **Load testing** - Test with realistic workload
4. **Performance tuning** - Adjust resources as needed
5. **Documentation** - Document any custom configurations
6. **Disaster recovery plan** - Test backup restoration

---

## Additional Resources

- **Architecture Guide:** `docs/SERVICE_BOUNDARIES.md`
- **TLS Setup:** `docs/TLS_SETUP_GUIDE.md`
- **Deployment Readiness:** `docs/DEPLOYMENT_READINESS.md`
- **Current State:** `docs/CURRENT_STATE_SNAPSHOT.md`
- **Analysis Index:** `docs/ANALYSIS_INDEX.md`

---

**Need help?** Create an issue on GitHub with:
- Deployment phase you're in
- Error messages (full logs)
- Environment details (OS, Docker version, etc.)
- What you've already tried
