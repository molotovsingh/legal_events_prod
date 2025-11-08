# TLS/HTTPS Setup Guide

This guide provides step-by-step instructions for securing your Legal Events Production system with TLS/HTTPS encryption.

## Table of Contents

- [Why TLS/HTTPS?](#why-tlshttps)
- [Prerequisites](#prerequisites)
- [Option A: Nginx Reverse Proxy (Recommended)](#option-a-nginx-reverse-proxy-recommended)
- [Option B: Cloud Load Balancer](#option-b-cloud-load-balancer)
- [Option C: Cloudflare Tunnel (Zero Trust)](#option-c-cloudflare-tunnel-zero-trust)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Why TLS/HTTPS?

**Security Requirements:**
- ✅ Encrypts data in transit (API keys, JWT tokens, document uploads)
- ✅ Prevents man-in-the-middle attacks
- ✅ Required for production deployments
- ✅ Required for browser security features (Secure cookies, CORS)
- ✅ Required for MinIO presigned URLs with `MINIO_SECURE=true`

**Without TLS, your deployment is vulnerable to:**
- Credential theft (API keys transmitted in plaintext)
- Session hijacking (JWT tokens intercepted)
- Data breaches (documents uploaded in plaintext)

---

## Prerequisites

**All Options Require:**
1. ✅ Domain name pointing to your server
   - Example: `api.yourdomain.com` → Your server IP
   - Example: `storage.yourdomain.com` → Your server IP (for MinIO)

2. ✅ Server with public IP address
   - VPS (DigitalOcean, Linode, Vultr)
   - Cloud VM (AWS EC2, GCP Compute Engine, Azure VM)
   - Self-hosted with public IP

3. ✅ DNS records configured
   - `api.yourdomain.com` A record → Server IP
   - `storage.yourdomain.com` A record → Server IP
   - Wait for DNS propagation (15-60 minutes)

**Verify DNS propagation:**
```bash
# Check if domain resolves to your server IP
nslookup api.yourdomain.com
dig api.yourdomain.com +short

# Test HTTP connectivity (before TLS)
curl -v http://api.yourdomain.com:8000/health
```

---

## Option A: Nginx Reverse Proxy (Recommended)

**Best for:** Most use cases, full control, self-hosted deployments

**Architecture:**
```
Internet → Nginx (443/TLS) → Docker API (8000/HTTP)
                          → Docker MinIO (9000/HTTP)
```

### Step 1: Install Nginx and Certbot

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

**CentOS/RHEL:**
```bash
sudo yum install -y epel-release
sudo yum install -y nginx certbot python3-certbot-nginx
```

**macOS (for testing only):**
```bash
brew install nginx certbot
```

### Step 2: Obtain SSL Certificates (Let's Encrypt)

**For API domain:**
```bash
sudo certbot certonly --nginx -d api.yourdomain.com
```

**For MinIO/Storage domain:**
```bash
sudo certbot certonly --nginx -d storage.yourdomain.com
```

**Note:** Let's Encrypt requires:
- Domain must resolve to your server IP
- Port 80 must be accessible (for HTTP-01 challenge)
- Server must be publicly accessible

**Certificates will be saved to:**
```
/etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
/etc/letsencrypt/live/api.yourdomain.com/privkey.pem
```

### Step 3: Configure Nginx

Create Nginx configuration file:

**`/etc/nginx/sites-available/legal-events`:**
```nginx
# API Server Configuration
server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL Certificate Configuration
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # SSL Security Settings (Mozilla Intermediate Config)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate Limiting (Optional but recommended)
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;

    # Proxy Configuration
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for SSE/streaming)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # File upload size limit
    client_max_body_size 100M;
}

# MinIO Storage Configuration
server {
    listen 80;
    server_name storage.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name storage.yourdomain.com;

    # SSL Certificate Configuration
    ssl_certificate /etc/letsencrypt/live/storage.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/storage.yourdomain.com/privkey.pem;

    # SSL Security Settings (same as API)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000" always;

    # Proxy to MinIO
    location / {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # MinIO requires larger buffers for presigned URLs
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # File upload size limit (100MB max for documents)
    client_max_body_size 100M;
}
```

### Step 4: Enable and Test Configuration

```bash
# Create symlink to enable site
sudo ln -s /etc/nginx/sites-available/legal-events /etc/nginx/sites-enabled/

# Test configuration syntax
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx
```

### Step 5: Update Environment Variables

**Update `.env.production`:**
```bash
# Enable TLS/HTTPS
MINIO_SECURE=true

# Update endpoints (no port needed, Nginx handles routing)
MINIO_PUBLIC_ENDPOINT=storage.yourdomain.com

# Update CORS to use HTTPS
CORS_ORIGINS=https://app.yourdomain.com
```

### Step 6: Certificate Auto-Renewal

Let's Encrypt certificates expire after 90 days. Set up auto-renewal:

```bash
# Test renewal (dry run)
sudo certbot renew --dry-run

# Certbot automatically installs a cron job for renewal
# Verify it exists:
sudo systemctl status certbot.timer

# Or check crontab:
sudo crontab -l | grep certbot
```

**Manual renewal (if needed):**
```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## Option B: Cloud Load Balancer

**Best for:** AWS, GCP, Azure deployments with existing cloud infrastructure

**Architecture:**
```
Internet → Cloud LB (443/TLS) → Docker API (8000/HTTP)
                               → Docker MinIO (9000/HTTP)
```

### AWS Application Load Balancer (ALB)

**Step 1: Create Target Groups**

```bash
# API Target Group
aws elbv2 create-target-group \
    --name legal-events-api-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id vpc-xxxxx \
    --health-check-path /health \
    --health-check-interval-seconds 30

# MinIO Target Group
aws elbv2 create-target-group \
    --name legal-events-minio-tg \
    --protocol HTTP \
    --port 9000 \
    --vpc-id vpc-xxxxx \
    --health-check-path /minio/health/live \
    --health-check-interval-seconds 30
```

**Step 2: Register Targets**

```bash
# Get your EC2 instance ID
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)

# Register API target
aws elbv2 register-targets \
    --target-group-arn arn:aws:elasticloadbalancing:region:account:targetgroup/legal-events-api-tg/xxxxx \
    --targets Id=$INSTANCE_ID

# Register MinIO target
aws elbv2 register-targets \
    --target-group-arn arn:aws:elasticloadbalancing:region:account:targetgroup/legal-events-minio-tg/xxxxx \
    --targets Id=$INSTANCE_ID
```

**Step 3: Request SSL Certificate (AWS Certificate Manager)**

```bash
# Request certificate for API domain
aws acm request-certificate \
    --domain-name api.yourdomain.com \
    --validation-method DNS

# Request certificate for MinIO domain
aws acm request-certificate \
    --domain-name storage.yourdomain.com \
    --validation-method DNS
```

**Note:** You'll need to create DNS validation records (ACM will provide them).

**Step 4: Create Application Load Balancer**

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name legal-events-alb \
    --subnets subnet-xxxxx subnet-yyyyy \
    --security-groups sg-xxxxx \
    --scheme internet-facing \
    --type application

# Create HTTPS listener for API (port 443)
aws elbv2 create-listener \
    --load-balancer-arn arn:aws:elasticloadbalancing:region:account:loadbalancer/app/legal-events-alb/xxxxx \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=arn:aws:acm:region:account:certificate/xxxxx \
    --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:region:account:targetgroup/legal-events-api-tg/xxxxx

# Create listener rule for MinIO (based on host header)
aws elbv2 create-rule \
    --listener-arn arn:aws:elasticloadbalancing:region:account:listener/app/legal-events-alb/xxxxx/xxxxx \
    --priority 10 \
    --conditions Field=host-header,Values=storage.yourdomain.com \
    --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:region:account:targetgroup/legal-events-minio-tg/xxxxx
```

**Step 5: Update DNS Records**

Point your domains to the ALB DNS name:

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --names legal-events-alb --query 'LoadBalancers[0].DNSName'

# Create Route53 alias records (or CNAME with your DNS provider)
# api.yourdomain.com → ALB DNS name
# storage.yourdomain.com → ALB DNS name
```

**Step 6: Update Environment Variables**

Same as Option A (Nginx) - set `MINIO_SECURE=true` and update endpoints.

### GCP Load Balancer

**Step 1: Reserve Static IP**

```bash
gcloud compute addresses create legal-events-ip --global
```

**Step 2: Create SSL Certificate**

```bash
# Managed certificate (Google manages renewal)
gcloud compute ssl-certificates create legal-events-cert \
    --domains=api.yourdomain.com,storage.yourdomain.com \
    --global
```

**Step 3: Create Backend Services**

```bash
# API backend
gcloud compute backend-services create legal-events-api-backend \
    --protocol=HTTP \
    --port-name=http \
    --health-checks=legal-events-api-health \
    --global

# MinIO backend
gcloud compute backend-services create legal-events-minio-backend \
    --protocol=HTTP \
    --port-name=http \
    --health-checks=legal-events-minio-health \
    --global
```

**Step 4: Create URL Map and HTTPS Proxy**

```bash
# URL map
gcloud compute url-maps create legal-events-lb \
    --default-service=legal-events-api-backend

# Path matcher for MinIO
gcloud compute url-maps add-path-matcher legal-events-lb \
    --path-matcher-name=storage \
    --default-service=legal-events-minio-backend \
    --new-hosts=storage.yourdomain.com

# HTTPS proxy
gcloud compute target-https-proxies create legal-events-https-proxy \
    --url-map=legal-events-lb \
    --ssl-certificates=legal-events-cert
```

**Step 5: Create Forwarding Rule**

```bash
gcloud compute forwarding-rules create legal-events-https-rule \
    --address=legal-events-ip \
    --global \
    --target-https-proxy=legal-events-https-proxy \
    --ports=443
```

**Step 6: Update DNS**

Point domains to the reserved static IP.

---

## Option C: Cloudflare Tunnel (Zero Trust)

**Best for:** No public IP needed, easiest setup, built-in DDoS protection

**Architecture:**
```
Internet → Cloudflare Edge → Cloudflare Tunnel → Docker API (8000/HTTP)
                                                → Docker MinIO (9000/HTTP)
```

**Advantages:**
- ✅ No port forwarding required
- ✅ No public IP required
- ✅ Works behind NAT/firewall
- ✅ Built-in DDoS protection
- ✅ Free SSL certificates
- ✅ Automatic certificate renewal

### Step 1: Sign Up for Cloudflare

1. Go to https://www.cloudflare.com
2. Add your domain
3. Update nameservers at your domain registrar
4. Wait for DNS propagation (15-60 minutes)

### Step 2: Install Cloudflared

**Linux:**
```bash
# Download latest release
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Or using package manager
wget -q https://pkg.cloudflare.com/cloudflare-main.gpg -O- | sudo tee /usr/share/keyrings/cloudflare-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

**macOS:**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Docker (Alternative):**
```bash
docker pull cloudflare/cloudflared:latest
```

### Step 3: Authenticate Cloudflared

```bash
cloudflared tunnel login
```

This opens a browser window. Select your domain to authorize.

### Step 4: Create Tunnel

```bash
# Create tunnel
cloudflared tunnel create legal-events-tunnel

# This generates a credentials file:
# ~/.cloudflared/<TUNNEL-ID>.json
# Keep this file secure!

# Get tunnel ID
cloudflared tunnel list
```

### Step 5: Configure Tunnel

**Create `~/.cloudflared/config.yml`:**
```yaml
tunnel: <YOUR-TUNNEL-ID>
credentials-file: /home/youruser/.cloudflared/<TUNNEL-ID>.json

# Define ingress rules
ingress:
  # API domain
  - hostname: api.yourdomain.com
    service: http://localhost:8000
    originRequest:
      noTLSVerify: true

  # MinIO domain
  - hostname: storage.yourdomain.com
    service: http://localhost:9000
    originRequest:
      noTLSVerify: true

  # Catch-all rule (required)
  - service: http_status:404
```

### Step 6: Create DNS Records

```bash
# API domain
cloudflared tunnel route dns legal-events-tunnel api.yourdomain.com

# MinIO domain
cloudflared tunnel route dns legal-events-tunnel storage.yourdomain.com
```

### Step 7: Run Tunnel

**Foreground (testing):**
```bash
cloudflared tunnel run legal-events-tunnel
```

**Background (systemd service):**
```bash
# Install as system service
sudo cloudflared service install

# Start service
sudo systemctl start cloudflared

# Enable on boot
sudo systemctl enable cloudflared

# Check status
sudo systemctl status cloudflared
```

### Step 8: Update Environment Variables

Same as previous options - set `MINIO_SECURE=true` and update endpoints.

**Note:** Cloudflare automatically handles HTTPS, so your application sees the connection as HTTPS even though the tunnel uses HTTP internally.

---

## Verification

After completing any option above, verify TLS is working:

### 1. Test SSL Certificate

```bash
# Check certificate validity
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com < /dev/null

# Should show:
# - Verify return code: 0 (ok)
# - Certificate chain
# - Subject: CN=api.yourdomain.com
```

### 2. Test API Endpoints

```bash
# Health check
curl -v https://api.yourdomain.com/health

# Should return:
# < HTTP/2 200
# {"status": "healthy"}

# Login endpoint
curl -X POST https://api.yourdomain.com/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin@legalevents.local", "password": "test"}'
```

### 3. Test MinIO

```bash
# MinIO health check
curl -v https://storage.yourdomain.com/minio/health/live

# Should return:
# < HTTP/2 200
```

### 4. Test Browser Access

Open in browser:
- `https://api.yourdomain.com/health` - Should show {"status": "healthy"}
- `https://storage.yourdomain.com/minio/health/live` - Should return empty 200 OK
- Check for green padlock icon in address bar
- View certificate (click padlock → Certificate)

### 5. Test SSL Labs

Go to: https://www.ssllabs.com/ssltest/

Enter your domain and run the test. Aim for A or A+ rating.

---

## Troubleshooting

### Certificate Errors

**Problem:** Browser shows "Your connection is not private" or "NET::ERR_CERT_AUTHORITY_INVALID"

**Solutions:**
```bash
# 1. Verify certificate files exist
sudo ls -la /etc/letsencrypt/live/api.yourdomain.com/

# 2. Check certificate expiry
openssl x509 -in /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem -noout -dates

# 3. Verify Nginx is using correct certificate paths
sudo nginx -T | grep ssl_certificate

# 4. Check certificate matches domain
openssl x509 -in /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem -noout -text | grep DNS

# 5. Reload Nginx after certificate changes
sudo systemctl reload nginx
```

### DNS Issues

**Problem:** Domain doesn't resolve or points to wrong IP

**Solutions:**
```bash
# Check DNS resolution
nslookup api.yourdomain.com
dig api.yourdomain.com +short

# Check from different DNS server
nslookup api.yourdomain.com 8.8.8.8

# Flush local DNS cache (if testing)
# Linux:
sudo systemd-resolve --flush-caches
# macOS:
sudo dscacheutil -flushcache

# Wait for DNS propagation (can take up to 48 hours, usually 15-60 minutes)
```

### Port Binding Issues

**Problem:** Nginx fails to start: "bind() to 0.0.0.0:443 failed (98: Address already in use)"

**Solutions:**
```bash
# Check what's using port 443
sudo lsof -i :443
sudo netstat -tulpn | grep :443

# Kill conflicting process
sudo systemctl stop apache2  # If Apache is running
sudo systemctl stop other-service

# Restart Nginx
sudo systemctl restart nginx
```

### MinIO CORS Errors

**Problem:** Browser console shows CORS errors when uploading to MinIO

**Solutions:**
```bash
# 1. Verify MINIO_SECURE matches reality
# If using HTTPS, set MINIO_SECURE=true

# 2. Check CORS_ORIGINS includes your frontend domain
# Example: CORS_ORIGINS=https://app.yourdomain.com

# 3. Test presigned URL generation
curl https://api.yourdomain.com/v1/documents/upload-url?client_id=1&case_id=1&run_id=1&filename=test.pdf

# 4. Verify MinIO is accessible through TLS
curl -v https://storage.yourdomain.com/minio/health/live
```

### Let's Encrypt Rate Limits

**Problem:** Certificate request fails with "too many certificates already issued"

**Solutions:**
- Let's Encrypt has rate limits: 50 certificates per domain per week
- Use `--dry-run` flag when testing: `certbot --dry-run certonly ...`
- Wait 7 days for rate limit to reset
- Consider using staging environment for testing: `certbot --staging ...`

### Cloudflare Tunnel Issues

**Problem:** Tunnel won't start or can't connect

**Solutions:**
```bash
# 1. Check tunnel status
cloudflared tunnel list

# 2. Check tunnel logs
sudo journalctl -u cloudflared -f

# 3. Test local services are running
curl http://localhost:8000/health
curl http://localhost:9000/minio/health/live

# 4. Verify DNS records
nslookup api.yourdomain.com

# 5. Restart tunnel
sudo systemctl restart cloudflared

# 6. Check firewall (tunnel needs outbound HTTPS)
sudo ufw allow out 443/tcp
```

---

## Security Best Practices

After setting up TLS, ensure:

1. ✅ **HTTP Redirects to HTTPS** - All HTTP traffic redirected to HTTPS
2. ✅ **HSTS Enabled** - Strict-Transport-Security header set
3. ✅ **TLS 1.2+ Only** - Disable TLS 1.0 and 1.1
4. ✅ **Strong Ciphers** - Use modern cipher suites
5. ✅ **Certificate Auto-Renewal** - Automated renewal before expiry
6. ✅ **Security Headers** - X-Frame-Options, X-Content-Type-Options, etc.
7. ✅ **Rate Limiting** - Protect against brute force attacks
8. ✅ **Firewall Rules** - Only allow necessary ports (443, not 8000/9000 directly)

**Test your security:**
- https://www.ssllabs.com/ssltest/ - SSL/TLS configuration
- https://securityheaders.com/ - HTTP security headers
- https://observatory.mozilla.org/ - Overall security assessment

---

## Next Steps

After TLS is working:

1. ✅ Update `.env.production` with `MINIO_SECURE=true`
2. ✅ Test all API endpoints over HTTPS
3. ✅ Test document uploads and downloads
4. ✅ Test frontend integration
5. ✅ Set up monitoring for certificate expiry
6. ✅ Configure firewall to block direct access to ports 8000, 9000
7. ✅ Run security audit with SSL Labs

See `DEPLOYMENT_GUIDE.md` for complete deployment checklist.
