# Gold Research API - Production Readiness Checklist

**Current Status:** Sandbox/Development ✅  
**Target Status:** Production Ready  
**Last Updated:** July 14, 2026

---

## **🎯 Phase 1: Visa Credentials & Certificates (Week 1)**

### **1.1 Obtain Production Visa Credentials**

**What to Do:**
- [ ] Go to [Visa Developer Portal](https://developer.visa.com)
- [ ] Navigate to **Credentials** section
- [ ] Request production API access for:
  - Visa IDX API (currently using sandbox)
  - Visa Merchant Search API (currently using sandbox)
- [ ] Request production certificates from Visa support
- [ ] You'll receive:
  - Production client certificate (.pem)
  - Production private key (.pem)
  - Production CA certificate (.pem)

**Timeline:** 1-3 business days (Visa requires manual verification)

**Success Criteria:**
- [ ] You have production certificates downloaded
- [ ] Certificates are in `.pem` format (not `.der` or `.p12`)
- [ ] Private key is secure (not shared, properly permissioned)

---

### **1.2 Store Certificates in Railway Secrets**

**Option A: Use Railway Secrets** (Recommended)

1. Go to Railway Dashboard → **Settings** → **Secrets**
2. Create three secrets:

```
Name: VISA_CERT_PATH
Value: (keep as /etc/visa/client.pem)

Name: VISA_CERT_CONTENT
Value: [Paste entire contents of production client.pem file]

Name: VISA_KEY_CONTENT
Value: [Paste entire contents of production key.pem file]

Name: VISA_CA_CONTENT
Value: [Paste entire contents of production ca.pem file]
```

3. Update `Dockerfile` to mount secrets:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Create certificate directory
RUN mkdir -p /etc/visa && chmod 700 /etc/visa

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python modules
COPY main.py .
COPY visa_idx_client.py .
COPY visa_idx_sync.py .
COPY visa_merchant_search.py .
COPY merchant_enrichment.py .

# Secrets will be mounted at /run/secrets/ by Railway
# Create cert files from mounted secrets
RUN echo "$VISA_CERT_CONTENT" > /etc/visa/client.pem && \
    echo "$VISA_KEY_CONTENT" > /etc/visa/key.pem && \
    echo "$VISA_CA_CONTENT" > /etc/visa/ca.pem && \
    chmod 600 /etc/visa/*.pem

EXPOSE 8000
CMD ["python", "main.py"]
```

**Option B: File-Based** (Less Secure)

1. Add cert files to your Git repo (in a `.gitignore`d directory)
2. Reference them in Railway environment variables

⚠️ **Security Note:** Never commit certificates to Git. Use Railway Secrets instead.

**Success Criteria:**
- [ ] All three secrets are stored in Railway
- [ ] Secrets are **not** committed to GitHub
- [ ] Certificate files are properly formatted (PEM, not binary)

---

### **1.3 Update Code for Production Mode**

**File: `visa_idx_client.py`**

Change:
```python
sandbox=True  # ← Currently this
```

To:
```python
sandbox=os.getenv("VISA_SANDBOX_MODE", "false").lower() != "true"
```

Then set environment variable in Railway:
```
VISA_SANDBOX_MODE=false
```

**File: `visa_merchant_search.py`**

Same change:
```python
sandbox=os.getenv("VISA_SANDBOX_MODE", "false").lower() != "true"
```

**Success Criteria:**
- [ ] Code is configured to read sandbox mode from environment
- [ ] `VISA_SANDBOX_MODE=false` is set in Railway
- [ ] You can toggle between sandbox/production without code changes

---

## **🔐 Phase 2: Security Hardening (Week 1)**

### **2.1 API Rate Limiting & Authentication**

**Current State:** API is open (no authentication)

**Add Basic API Key Authentication:**

```python
# In main.py
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("API_KEY", "")

async def verify_api_key(api_key: str = Header(..., alias="X-API-Key")):
    if not API_KEY or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# On each endpoint:
@app.get("/api/v1/research/buyers")
async def get_buyers(
    api_key: str = Depends(verify_api_key),
    ...
):
```

**Add Rate Limiting:**

```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/v1/research/buyers")
@limiter.limit("100/minute")
async def get_buyers(...):
```

**Railway Setup:**
```
API_KEY=your-secret-key-here-use-strong-password
RATELIMIT_ENABLED=true
```

**Success Criteria:**
- [ ] API requires `X-API-Key` header
- [ ] Rate limits are enforced (100 requests/minute/IP)
- [ ] API key is stored in Railway Secrets (not Git)

---

### **2.2 HTTPS & TLS Verification**

**Current State:** Using Railway's automatic HTTPS

**Verify:**
- [ ] Visit https://gold-research-api-production.up.railway.app (not http://)
- [ ] Certificate is valid (no browser warnings)
- [ ] SSL Labs test: A+ rating at https://www.ssllabs.com/ssltest/

**Enable HSTS Header:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Your domain only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

**Success Criteria:**
- [ ] All traffic is HTTPS
- [ ] HSTS headers are present
- [ ] Security headers are configured

---

### **2.3 Database Security**

**Current State:** PostgreSQL with default credentials

**Harden:**
- [ ] Change PostgreSQL password to strong random value
- [ ] Store in Railway Secrets (not plaintext)
- [ ] Enable PostgreSQL SSL for connections
- [ ] Restrict database access to Railway services only

**Update `docker-compose.yml` or Railway config:**
```
PGPASSWORD=$(openssl rand -base64 32)  # 32-char random password
PGSSLMODE=require
```

**Verify:**
```bash
# Test connection (from Railway console)
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c "SELECT version();"
```

**Success Criteria:**
- [ ] PostgreSQL password is 32+ characters
- [ ] Password is in Railway Secrets (not tracked in Git)
- [ ] SSL connections are enforced
- [ ] Database is not publicly accessible

---

## **📊 Phase 3: Monitoring & Alerting (Week 2)**

### **3.1 Application Logging**

**Current State:** Basic stdout logging

**Enhance:**
```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Configure JSON logging
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

**Log Critical Events:**
```python
logger.info("Purchase created", extra={"purchase_id": id, "amount": amount})
logger.warning("Visa sync failed", extra={"purchase_id": id, "error": error})
logger.error("Database connection error", extra={"database": DB_HOST})
```

**Success Criteria:**
- [ ] All logs are JSON formatted
- [ ] Critical events are logged (creation, sync, errors)
- [ ] Logs include timestamp, level, and context

---

### **3.2 Error Tracking**

**Integrate Sentry (Error Tracking):**

1. Sign up at https://sentry.io (free tier available)
2. Create project for your API
3. Get your DSN (Data Source Name)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment=os.getenv("ENV", "production")
)
```

Add to Railway:
```
SENTRY_DSN=https://your-sentry-dsn-here
ENV=production
```

**Success Criteria:**
- [ ] Sentry is configured and receiving errors
- [ ] Error notifications are working
- [ ] You can view error trends in Sentry dashboard

---

### **3.3 Visa Integration Monitoring**

**Monitor Sync Pipeline:**

```python
# In main.py startup
async def startup():
    # ... existing code ...
    
    # Log sync pipeline start
    if sync_pipeline:
        logger.info(
            "Visa IDX sync pipeline started",
            extra={
                "batch_size": sync_pipeline.BATCH_SIZE,
                "max_retries": sync_pipeline.MAX_RETRIES,
                "sandbox_mode": visa_client.sandbox
            }
        )

# Create monitoring endpoint
@app.get("/api/v1/integration/health-detailed")
async def detailed_health():
    """Detailed integration health check."""
    conn = get_connection()
    
    try:
        cursor = conn.cursor()
        
        # Sync stats
        cursor.execute("""
            SELECT 
              status,
              COUNT(*) as count
            FROM visa_idx_sync_log
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY status
        """)
        sync_stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Enrichment stats
        cursor.execute("""
            SELECT 
              search_type,
              COUNT(*) as total,
              COUNT(CASE WHEN success THEN 1 END) as successful
            FROM merchant_enrichment_history
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY search_type
        """)
        enrichment_stats = {row[0]: {"total": row[1], "successful": row[2]} for row in cursor.fetchall()}
        
        return {
            "sync_status": sync_stats,
            "enrichment_status": enrichment_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    finally:
        conn.close()
```

**Success Criteria:**
- [ ] Detailed health endpoint is available
- [ ] Sync pipeline statistics are tracked
- [ ] Enrichment success rates are visible

---

### **3.4 Performance Monitoring**

**Track Key Metrics:**

```python
from datetime import datetime
import time

@app.middleware("http")
async def track_performance(request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": int(process_time * 1000),
        }
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

**Success Criteria:**
- [ ] Response times are logged
- [ ] Slow requests (>1000ms) are flagged
- [ ] Performance trends are visible in logs

---

## **🚨 Phase 4: Operational Readiness (Week 2)**

### **4.1 Backup & Disaster Recovery**

**Current State:** Railway manages automatic backups

**Verify & Enhance:**
- [ ] PostgreSQL automatic backups are enabled (Railway default: 7-day retention)
- [ ] Test restore procedure (take a backup, restore to test environment)
- [ ] Document RTO/RPO targets:
  - RTO (Recovery Time Objective): How long until system is back online?
  - RPO (Recovery Point Objective): How much data loss is acceptable?

**For this project:**
- RTO: 1 hour (restore from backup)
- RPO: 1 hour (last backup)

**Test Backup:**
```bash
# 1. Create test data
curl -X POST .../api/v1/research/buyers

# 2. Railway console: Take manual backup
railway db backup

# 3. Delete test data (or entire table)
# 4. Restore from backup
# 5. Verify data is recovered
```

**Success Criteria:**
- [ ] Backups are automated and tested
- [ ] You can restore from backup if needed
- [ ] RTO/RPO targets are documented

---

### **4.2 Runbooks & Documentation**

**Create These Runbooks:**

**A. Incident Response**
```markdown
# Visa Sync Failures

## Symptoms
- Sync status shows "failed_max_retries"
- Error log shows SSL certificate errors

## Investigation
1. Check certificate expiration: openssl x509 -in /etc/visa/client.pem -dates
2. Verify Visa API status at https://developer.visa.com/status
3. Check Railway logs for network errors

## Resolution
1. If cert expired: Update certificates in Railway Secrets
2. If API down: Wait and retry
3. If network issue: Check Railway networking

## Escalation
- Contact Visa Developer Support if API is down
```

**B. Deployment Procedure**
```markdown
# Deploying Changes

1. Create feature branch
2. Test locally with sandbox credentials
3. Push to GitHub
4. Railway auto-deploys on push
5. Verify health endpoint: GET /health
6. Check latest logs in Railway dashboard
7. Run smoke test: create purchase + enrich it
8. Monitor Sentry for new errors (24 hours)
```

**C. Credential Rotation**
```markdown
# Rotating API Keys

1. Generate new key: openssl rand -hex 32
2. Add to Railway Secrets (don't delete old yet)
3. Redeploy to make active
4. After 24 hours, delete old key
5. Document rotation date
```

**Success Criteria:**
- [ ] Runbooks are written and shared with team
- [ ] Team has read and signed off on procedures
- [ ] Emergency contacts are documented

---

### **4.3 Change Management**

**Before deploying to production:**

- [ ] Code review completed (peer review)
- [ ] Unit tests pass
- [ ] Deployed to staging environment first
- [ ] Smoke tests pass on staging
- [ ] Security review completed
- [ ] Change ticket is created
- [ ] Deployment window is scheduled
- [ ] Team is notified

**Staging Environment Setup:**
```bash
# Create separate Railway environment
# Copy production config but use VISA_SANDBOX_MODE=true
# Deploy same code, test thoroughly before promoting to production
```

**Success Criteria:**
- [ ] Staging environment mirrors production
- [ ] All changes go through staging first
- [ ] Change approval process is documented

---

## **📋 Phase 5: Compliance & Audit (Week 2-3)**

### **5.1 Data Protection**

**Current State:** Basic PII stripping

**Enhance:**
- [ ] Implement data retention policy (delete old enrichments after 90 days)
- [ ] Audit logging (who accessed what, when)
- [ ] Encryption at rest (PostgreSQL SSL, backups encrypted)
- [ ] Encryption in transit (TLS 1.2+)

```python
# Data retention cleanup (run nightly via cron)
async def cleanup_old_enrichments():
    """Delete enrichments older than 90 days."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM merchant_enrichment_history
        WHERE created_at < NOW() - INTERVAL '90 days'
    """)
    
    deleted = cursor.rowcount
    conn.commit()
    
    logger.info(f"Cleaned up {deleted} old enrichment records")
```

**Success Criteria:**
- [ ] Data retention policy is documented
- [ ] Automated cleanup is implemented
- [ ] Encryption is enabled for all data flows

---

### **5.2 Visa Compliance**

**Required for Visa Integration:**
- [ ] Sign Visa API Agreement (provided by Visa during onboarding)
- [ ] Comply with PCI-DSS (Payment Card Industry Data Security Standard)
  - ✅ You're compliant because you DON'T store card numbers
  - ✅ You sanitize PANs before storage
  - ✅ You use Visa's secure APIs
- [ ] Annual security assessment
- [ ] Incident reporting to Visa (if breach occurs)

**Visa Compliance Checklist:**
- [ ] API agreement signed
- [ ] PCI-DSS self-assessment completed
- [ ] No credit card data stored
- [ ] Mutual TLS authentication enabled
- [ ] Audit logs retained for 12 months

**Success Criteria:**
- [ ] Visa API agreement is signed
- [ ] Compliance documentation is filed
- [ ] Team understands PCI-DSS requirements

---

### **5.3 Audit Logging**

**Enable Comprehensive Audit Trail:**

```python
# Track all Visa syncs
@event
def log_visa_sync(purchase_id, status, error=None):
    logger.info(
        "visa_sync",
        extra={
            "event": "visa_sync",
            "purchase_id": purchase_id,
            "status": status,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
            "user": "system"
        }
    )

# Track all enrichments
@event
def log_enrichment(purchase_id, search_type, success):
    logger.info(
        "enrichment",
        extra={
            "event": "enrichment",
            "purchase_id": purchase_id,
            "search_type": search_type,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
```

**Audit Log Retention:**
```sql
-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50),
    purchase_id INTEGER,
    status VARCHAR(50),
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Retention policy: Keep 12 months
CREATE POLICY audit_log_retention AS
DELETE FROM audit_log
WHERE created_at < NOW() - INTERVAL '12 months';
```

**Success Criteria:**
- [ ] All critical operations are logged
- [ ] Logs are immutable (append-only)
- [ ] 12-month retention is enforced

---

## **🚀 Phase 6: Go-Live Checklist (Week 3)**

### **Before You Switch to Production:**

**Infrastructure:**
- [ ] Production certificates are installed in Railway
- [ ] `VISA_SANDBOX_MODE=false` is set
- [ ] `API_KEY` is configured (strong, 32+ characters)
- [ ] `SENTRY_DSN` is configured
- [ ] Database backups are automated
- [ ] SSL/TLS is configured (A+ rating)

**Security:**
- [ ] Secrets are in Railway (not Git)
- [ ] Rate limiting is enabled
- [ ] HSTS headers are set
- [ ] CORS is restricted
- [ ] API key authentication is working

**Monitoring:**
- [ ] Sentry error tracking is active
- [ ] Logging is JSON formatted
- [ ] Performance metrics are being collected
- [ ] Health check endpoint is accessible

**Operations:**
- [ ] Runbooks are written
- [ ] Team is trained
- [ ] Incident response process is documented
- [ ] Change management process is in place

**Compliance:**
- [ ] Visa API agreement is signed
- [ ] Audit logging is enabled
- [ ] Data retention policy is implemented
- [ ] PCI-DSS compliance is verified

**Testing:**
- [ ] Smoke test passes (create purchase + enrich)
- [ ] Sync pipeline works end-to-end
- [ ] All endpoints return correct responses
- [ ] Rate limiting works as expected

---

## **✅ Go-Live Approval**

**Final Sign-Off:**
- [ ] CTO/Technical Lead: Approves security setup
- [ ] DevOps/Infrastructure: Approves monitoring/backups
- [ ] Compliance Officer: Approves Visa/PCI-DSS setup
- [ ] Product Manager: Approves feature completeness

**Go-Live Plan:**
1. Schedule deployment for low-traffic time
2. Have team on standby
3. Switch sandbox → production
4. Monitor errors in Sentry (24 hours)
5. Check sync stats every hour (first 8 hours)
6. Document any issues

**Rollback Plan:**
- If critical errors occur: Switch back to sandbox (5-minute rollback)
- Restore database from backup if needed
- Contact Visa support if API issues

---

## **📞 Production Support Contacts**

**Visa Developer Support:**
- Website: https://developer.visa.com/support
- Email: (provided during onboarding)
- Response time: 4-24 hours

**Railway Support:**
- Website: https://railway.com/support
- Community: Discord/GitHub
- Premium support available

**Your Team:**
- On-call rotation for production issues
- Escalation procedure for critical incidents
- Post-mortem process for outages

---

## **📊 Metrics to Track**

Once in production, monitor:

**API Health:**
- Uptime: Target 99.9%
- Response time: p95 < 500ms
- Error rate: < 0.1%

**Visa Integration:**
- Sync success rate: > 95%
- Sync latency: < 5 minutes
- Failed max retries: < 1%

**Enrichment:**
- Directory search success: > 90%
- Merchant match confidence: > 0.85
- Enrichment coverage: Track % of purchases enriched

**Security:**
- API key rotation: Every 90 days
- Certificate expiration: Never lapsed
- Zero security incidents

---

## **🎯 Timeline Summary**

| Phase | Task | Duration | Owner |
|-------|------|----------|-------|
| 1 | Get Visa credentials | 3 days | You (Visa support) |
| 1 | Setup certificates | 2 hours | You + DevOps |
| 2 | Security hardening | 4 hours | DevOps/Security |
| 3 | Monitoring setup | 4 hours | DevOps |
| 4 | Operational docs | 4 hours | You |
| 5 | Compliance review | 2 hours | Compliance |
| 6 | Final testing | 2 hours | QA |
| **Total** | | **~20 hours** | |

---

## **Next Steps**

1. **This week:** Start Phase 1 (request Visa credentials)
2. **Next week:** Complete Phases 2-3 (security + monitoring)
3. **Week 3:** Complete Phases 4-5 (ops + compliance)
4. **Week 3:** Go-live with Phase 6

**Ready to start? Begin with Phase 1.1: Request production Visa credentials.**

