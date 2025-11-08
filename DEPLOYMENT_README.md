# Production Deployment - Quick Reference

**All deployment artifacts are ready!** This document provides a quick reference for the deployment process.

## 🎯 What's Been Prepared

All files needed for production deployment have been created and are ready to use:

### Configuration Files
- ✅ `.env.production.template` - Production environment template with secure defaults
- ✅ `.env.staging.template` - Staging environment template for testing
- ✅ `docker-compose.staging.yml` - Staging deployment configuration

### Scripts
- ✅ `scripts/generate_secrets.py` - Generate secure credentials (JWT, passwords, keys)
- ✅ `scripts/test_staging.sh` - Comprehensive staging test suite (15 automated tests)

### Documentation
- ✅ `DEPLOYMENT_GUIDE.md` - Complete step-by-step deployment guide (6 phases)
- ✅ `docs/TLS_SETUP_GUIDE.md` - TLS/HTTPS setup for 3 options (Nginx, Cloud LB, Cloudflare)
- ✅ `docs/DEPLOYMENT_READINESS.md` - Deployment readiness checklist and risk assessment
- ✅ `docs/CURRENT_STATE_SNAPSHOT.md` - Current codebase state and recent fixes
- ✅ `docs/ANALYSIS_INDEX.md` - Navigation guide for all documentation

---

## 🚀 Quick Start (30-Second Overview)

### For Staging Deployment:

```bash
# 1. Generate credentials
python3 scripts/generate_secrets.py > secrets.txt

# 2. Create .env.staging from template
cp .env.staging.template .env.staging
nano .env.staging  # Fill in credentials and API keys

# 3. Deploy staging
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d

# 4. Run tests
./scripts/test_staging.sh
```

### For Production Deployment:

```bash
# 1. Generate credentials
python3 scripts/generate_secrets.py > secrets.txt

# 2. Create .env.production from template
cp .env.production.template .env.production
nano .env.production  # Fill in credentials, domains, and API keys

# 3. Set up TLS/HTTPS (see docs/TLS_SETUP_GUIDE.md)
# Choose: Nginx, Cloud Load Balancer, or Cloudflare Tunnel

# 4. Deploy production
docker compose -f docker-compose.yml --env-file .env.production up -d

# 5. Verify deployment
curl https://api.yourdomain.com/health
```

**Full guide:** See `DEPLOYMENT_GUIDE.md` for complete instructions.

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

### Infrastructure
- [ ] Server/VPS with Docker installed
- [ ] Domain name configured (DNS A records)
- [ ] TLS/HTTPS set up (certificates obtained)
- [ ] Firewall configured (ports 80, 443 open)

### Credentials
- [ ] JWT secret generated
- [ ] PostgreSQL password generated
- [ ] MinIO credentials generated
- [ ] LLM provider API key(s) obtained

### Configuration
- [ ] `.env.production` created and filled
- [ ] No placeholder values (`<YOUR_*>`) remaining
- [ ] Domain names configured correctly
- [ ] `MINIO_SECURE=true` (if using HTTPS)

### Files Ready
- [ ] All Docker images build successfully
- [ ] Docker Compose configuration validated
- [ ] Test document available for verification

---

## 🔧 Available Scripts

### Generate Secure Credentials

```bash
python3 scripts/generate_secrets.py
```

**What it does:**
- Generates JWT secret key (512-bit entropy)
- Generates PostgreSQL password (256-bit entropy)
- Generates MinIO root credentials (256-bit entropy)
- Generates MinIO access/secret keys (256-bit entropy)
- Provides entropy information and security recommendations

**Output format:**
- Ready to copy-paste into `.env` files
- Includes comments with generation commands for reference

### Test Staging Environment

```bash
./scripts/test_staging.sh
```

**What it tests:**
- Prerequisites (curl, jq, docker)
- Docker services health (all 6 services)
- API health endpoint
- Authentication (JWT login)
- CRUD operations (clients, cases, runs)
- Document upload (presigned URLs)
- Provider discovery API
- Database connectivity
- Redis connectivity
- MinIO connectivity
- Worker registration
- API response time
- Security headers

**Exit codes:**
- `0` = All tests passed (ready for production)
- `1` = Some tests failed (fix before production)

---

## 📚 Documentation Guide

### For First-Time Deployment

Start here:

1. **`DEPLOYMENT_GUIDE.md`** - Complete step-by-step guide
   - 6 phases from setup to post-deployment
   - Timeline: 14-21 hours total
   - Decision points and recommendations
   - Troubleshooting section

2. **`docs/TLS_SETUP_GUIDE.md`** - HTTPS/TLS setup
   - 3 options: Nginx, Cloud LB, Cloudflare Tunnel
   - Certificate management (Let's Encrypt)
   - Security best practices
   - Troubleshooting

### For Understanding Current State

3. **`docs/DEPLOYMENT_READINESS.md`** - Readiness assessment
   - What's done, what's needed
   - Risk assessment
   - Infrastructure requirements
   - Confidence levels

4. **`docs/CURRENT_STATE_SNAPSHOT.md`** - Code state
   - Recent bug fixes
   - Architecture status
   - Git history
   - Known issues

### For Navigation

5. **`docs/ANALYSIS_INDEX.md`** - Documentation index
   - Quick reference by role
   - Quick reference by timeline
   - All documents organized

---

## 🎯 Decision Matrix

Before deployment, you need to decide:

| Decision | Options | Recommended |
|----------|---------|-------------|
| **Deployment Target** | VPS / Cloud VM / Self-hosted | VPS (simplest) |
| **TLS Setup** | Nginx / Cloud LB / Cloudflare | Nginx (control) or Cloudflare (easy) |
| **LLM Provider** | Gemini / OpenRouter / OpenAI / Anthropic | Gemini (free tier) |
| **Staging** | Separate server / Same server / None | Separate server (safest) |
| **Backups** | Daily auto / Weekly manual / None | Daily auto (essential) |
| **Monitoring** | Basic / Intermediate / Advanced | Basic (start here) |

See `DEPLOYMENT_GUIDE.md` section "Decision Points" for detailed analysis.

---

## 🔒 Security Checklist

Before going to production:

### Credentials
- [ ] All default passwords changed
- [ ] JWT secret is cryptographically secure (64+ bytes)
- [ ] API keys stored in `.env`, not hardcoded
- [ ] `.env.production` added to `.gitignore` (already done)
- [ ] Secrets stored in password manager or vault

### Network Security
- [ ] TLS/HTTPS enabled (`MINIO_SECURE=true`)
- [ ] Firewall configured (only 80, 443 open)
- [ ] Direct access to app ports blocked (8000, 9000)
- [ ] CORS origins configured correctly
- [ ] Rate limiting configured (if using Nginx)

### Application Security
- [ ] `APP_ENV=production` (not development)
- [ ] Debug mode disabled
- [ ] Security headers configured
- [ ] Database uses strong password
- [ ] MinIO uses secure credentials

### Operational Security
- [ ] Backups scheduled (daily)
- [ ] Monitoring set up
- [ ] Log rotation configured
- [ ] Admin accounts use strong passwords
- [ ] SSH keys used (not passwords)

**Test your security:**
- https://www.ssllabs.com/ssltest/ (SSL/TLS config)
- https://securityheaders.com/ (HTTP headers)
- https://observatory.mozilla.org/ (overall security)

---

## 📊 System Requirements

### Minimum (Development/Staging)
- CPU: 4 cores
- RAM: 8 GB
- Storage: 50 GB SSD
- Network: 100 Mbps

### Recommended (Production)
- CPU: 8 cores
- RAM: 16 GB
- Storage: 100 GB SSD
- Network: 1 Gbps

### Software
- OS: Ubuntu 22.04 LTS (or similar Linux)
- Docker Engine: 24.0+
- Docker Compose: v2.20+
- Git: 2.40+

---

## 🐛 Common Issues

### Issue: Services won't start

**Solution:**
```bash
# Check logs
docker compose logs

# Check environment
docker compose config

# Verify all required env vars are set
grep -v '^#' .env.production | grep '='
```

### Issue: API health check fails

**Solution:**
```bash
# Check API logs
docker compose logs api

# Test database connection
docker compose exec postgres psql -U legal_user -d legal_events

# Restart services
docker compose restart api
```

### Issue: Document processing stuck

**Solution:**
```bash
# Check worker status
docker compose ps worker

# Check worker logs
docker compose logs worker

# Verify worker registered
docker compose exec redis redis-cli SCARD rq:workers

# Restart worker
docker compose restart worker
```

### Issue: MinIO upload fails

**Solution:**
```bash
# Verify MINIO_SECURE matches your setup
# If using HTTPS: MINIO_SECURE=true
# If using HTTP: MINIO_SECURE=false

# Test MinIO connectivity
curl http://localhost:9000/minio/health/live

# Check CORS configuration
# CORS_ORIGINS must include your frontend domain
```

**Full troubleshooting:** See `DEPLOYMENT_GUIDE.md` section "Troubleshooting".

---

## 📈 Deployment Timeline

### Phase 1: Prepare Configuration (30-60 minutes)
- Generate credentials
- Create `.env.production`
- Create `.env.staging`
- Verify configuration

### Phase 2: Set Up Infrastructure (2-4 hours)
- Provision server
- Install Docker
- Configure firewall
- Set up TLS/HTTPS

### Phase 3: Deploy Staging (1-2 hours)
- Transfer files
- Deploy services
- Initialize database
- Create admin user

### Phase 4: Testing (8-12 hours)
- Run automated tests
- Manual testing
- Load testing (optional)
- Security testing
- Document issues

### Phase 5: Production Deployment (2-3 hours)
- Transfer files
- Deploy production
- Verify deployment
- Smoke tests
- Monitor

### Phase 6: Post-Deployment (ongoing)
- Set up monitoring
- Schedule backups
- Configure log rotation
- Document deployment

**Total: 14-21 hours** (can be spread over 3-5 days)

---

## 🎓 Learning Resources

### Docker & Docker Compose
- [Docker Official Docs](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)

### TLS/HTTPS
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [SSL Labs Best Practices](https://github.com/ssllabs/research/wiki/SSL-and-TLS-Deployment-Best-Practices)

### Security
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Security Headers](https://securityheaders.com/)

### Nginx
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Nginx SSL Configuration](https://ssl-config.mozilla.org/)

---

## 💬 Getting Help

If you need assistance:

1. **Check documentation:**
   - Start with `DEPLOYMENT_GUIDE.md`
   - Review relevant `docs/*.md` files
   - Check troubleshooting sections

2. **Search existing issues:**
   - GitHub repository issues
   - Stack Overflow (tag: docker, fastapi, minio)

3. **Create detailed issue:**
   - Include: deployment phase, error messages, environment details
   - Attach: relevant logs, configuration (redact secrets!)
   - Describe: what you tried, what happened

4. **Community support:**
   - Docker Community Forums
   - FastAPI Discord
   - MinIO Community Slack

---

## ✅ Success Criteria

Your deployment is successful when:

**Services:**
- ✅ All Docker containers running (`docker compose ps`)
- ✅ Health endpoint returns 200 OK
- ✅ Worker registered in Redis
- ✅ No errors in logs

**Functionality:**
- ✅ User can log in
- ✅ Document processing works end-to-end
- ✅ Events display correctly
- ✅ Exports work (CSV, Excel, JSON)

**Security:**
- ✅ TLS/HTTPS enabled (green padlock)
- ✅ Security headers configured
- ✅ SSL Labs rating A or A+
- ✅ Firewall configured correctly

**Operations:**
- ✅ Monitoring active
- ✅ Backups scheduled
- ✅ Log rotation configured
- ✅ Deployment documented

---

## 🎉 Next Steps After Deployment

Once your production deployment is successful:

1. **Monitor for 24-48 hours** - Watch for issues
2. **User onboarding** - Create accounts, provide training
3. **Performance tuning** - Adjust resources based on usage
4. **Backup verification** - Test restoration process
5. **Disaster recovery plan** - Document recovery procedures
6. **Scale as needed** - Add workers, increase resources

---

## 📝 Quick Command Reference

### Deployment

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# Check status
docker compose ps

# Restart service
docker compose restart api
```

### Maintenance

```bash
# Backup database
docker compose exec postgres pg_dump -U legal_user legal_events > backup.sql

# Restore database
docker compose exec -T postgres psql -U legal_user legal_events < backup.sql

# Update images
docker compose pull
docker compose up -d

# Clean up old images
docker system prune -a
```

### Monitoring

```bash
# Check health
curl https://api.yourdomain.com/health

# Check disk space
df -h

# Check memory
free -h

# Check CPU
top

# Check logs for errors
docker compose logs | grep -i error
```

---

## 📄 File Inventory

All deployment artifacts created:

### Configuration Templates
```
.env.production.template     - Production environment template
.env.staging.template        - Staging environment template
docker-compose.staging.yml   - Staging deployment config
```

### Scripts
```
scripts/generate_secrets.py  - Credential generator
scripts/test_staging.sh      - Staging test suite
```

### Documentation
```
DEPLOYMENT_GUIDE.md                 - Main deployment guide
DEPLOYMENT_README.md                - This file (quick reference)
docs/TLS_SETUP_GUIDE.md            - TLS/HTTPS setup guide
docs/DEPLOYMENT_READINESS.md       - Readiness assessment
docs/CURRENT_STATE_SNAPSHOT.md     - Current codebase state
docs/ANALYSIS_INDEX.md             - Documentation index
```

### Existing Files (Not Modified)
```
docker-compose.yml           - Production deployment config
.env (user creates)          - Active environment file
```

---

## 🏁 Final Words

**You're ready to deploy!** 🚀

All the groundwork has been laid:
- Configuration templates prepared
- Scripts ready to use
- Comprehensive documentation written
- Security best practices included
- Testing procedures defined

**Your path forward:**

1. Make the 6 key decisions (see Decision Matrix above)
2. Follow `DEPLOYMENT_GUIDE.md` step by step
3. Test thoroughly in staging (8-12 hours)
4. Deploy to production with confidence

**Remember:**
- Take your time with staging testing
- Don't skip security steps
- Document any customizations
- Monitor closely after deployment

**Good luck!** 🎯

---

**Questions?** See `DEPLOYMENT_GUIDE.md` section "Getting Help" or create a GitHub issue.
