# Visa IDX Integration - Complete Setup Guide

## 🎉 Integration Overview

Your Gold Research API is fully configured and deployed with end-to-end Visa IDX integration. This document provides the final setup steps and verification procedures.

## ✅ What's Already Deployed

### Infrastructure
- ✅ FastAPI Application (Python 3.11)
- ✅ PostgreSQL Database with schema
- ✅ Redis Cache
- ✅ Railway deployment pipeline
- ✅ Automatic SSL/TLS mutual authentication client
- ✅ Background sync pipeline with retry logic

### API Endpoints
- ✅ `POST /api/v1/research/buyers` - Create purchase records (auto-queued for Visa)
- ✅ `GET /api/v1/research/buyers` - Query with filters (state, zip, amount range, date)
- ✅ `GET /api/v1/research/buyers/{id}/sync-status` - Check Visa IDX sync status
- ✅ `GET /api/v1/research/buyers/analytics/total` - Aggregate purchase analytics
- ✅ `GET /api/v1/integration/visa-idx/status` - Integration health check
- ✅ `GET /health` - Application health

### Compliance Features
- ✅ Automatic PAN stripping (credit card numbers)
- ✅ Automatic routing number stripping
- ✅ Dual sanitization (on ingest + before Visa transmission)
- ✅ Audit logging of all sync operations
- ✅ Compliance flags in sync logs (data_sanitized, no_pans_detected)
- ✅ USD to minor units (cents) conversion

## 📋 Final Setup Checklist

### Step 1: Obtain Visa Sandbox Certificates

**Location:** [Visa Developer Portal](https://developer.visa.com) → Apps → Your App → Credentials

**Files to Download:**
- [ ] Client Certificate (.pem or .crt)
- [ ] Private Key (.pem or .key)
- [ ] CA Certificate (.pem)

**Verify files:**
```bash
# Check certificate details
openssl x509 -in client-cert.pem -text -noout

# Check expiration
openssl x509 -in client-cert.pem -dates -noout

# Verify key
openssl rsa -in client-key.pem -check
```

### Step 2: Configure Railway Environment Variables

**In Railway Dashboard:**
1. Go to **gold-research-api** service
2. Click **Variables**
3. Add these environment variables:

```
VISA_CERT_PATH=/etc/visa/client.pem
VISA_KEY_PATH=/etc/visa/key.pem
VISA_CA_PATH=/etc/visa/ca.pem
```

**Verify current variables:**
```
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=***
PGDATABASE=gold_research
PORT=8000
```

### Step 3: Mount Certificates in Container

**Option A: Store in GitHub (Development/Sandbox Only)**

```bash
# Create directory
mkdir -p certs/visa
cd certs/visa

# Copy files
cp /path/to/client-cert.pem ./client.pem
cp /path/to/client-key.pem ./key.pem
cp /path/to/ca-cert.pem ./ca.pem

# Update .gitignore
echo "certs/visa/*.pem" >> ../../.gitignore
```

Update Dockerfile:
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Copy certificates
COPY certs/visa/client.pem /etc/visa/client.pem
COPY certs/visa/key.pem /etc/visa/key.pem
COPY certs/visa/ca.pem /etc/visa/ca.pem

# Set permissions
RUN chmod 644 /etc/visa/*.pem && chmod 400 /etc/visa/key.pem

# Copy app files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py visa_idx_client.py visa_idx_sync.py .
EXPOSE 8000
CMD ["python", "main.py"]
```

**Option B: Use Railway Secrets (Production)**

1. In Railway **Variables**, create secret variables:
   - `VISA_CLIENT_CERT` - paste certificate PEM content
   - `VISA_CLIENT_KEY` - paste private key content
   - `VISA_CA_CERT` - paste CA certificate content

2. Certificates will be written to `/etc/visa/` at startup

### Step 4: Deploy Updates

```bash
# If using Option A (GitHub):
git add certs/
git commit -m "Add Visa sandbox certificates"
git push origin main

# Railway will auto-deploy
# Monitor: https://railway.app/project/[project-id]
```

**Verify deployment success:**
- Check build logs for: "Client certificates loaded for mutual TLS authentication"
- Or: "Client certificates not available for mutual TLS" (warning, app still runs)

### Step 5: Verify Integration Status

```bash
# Check integration endpoint
curl https://gold-research-api-production.up.railway.app/api/v1/integration/visa-idx/status
```

**Expected response:**
```json
{
  "integration_enabled": true,
  "sandbox_mode": true,
  "certificates_configured": true,
  "sync_pipeline_running": true,
  "sync_batch_size": 10,
  "max_sync_retries": 3
}
```

## 🧪 Testing the Integration

### Option 1: Run End-to-End Test Script

```bash
# Clone repo locally
git clone https://github.com/theusdept/gold-research-api.git
cd gold-research-api

# Install dependencies
pip install httpx

# Run tests against production
python test_visa_integration.py \
  --api-url https://gold-research-api-production.up.railway.app \
  --verbose

# Or test locally
python test_visa_integration.py --localhost --verbose
```

**Test covers:**
- ✅ API health check
- ✅ Visa IDX integration status
- ✅ Create basic purchase record
- ✅ Create record with sensitive data (tests PAN/routing stripping)
- ✅ Create high-value record (tests amount formatting)
- ✅ Query by amount range
- ✅ Analytics endpoint
- ✅ Visa sync status for created records
- ✅ Compliance flag verification

### Option 2: Manual Testing with cURL

**Create a test record:**
```bash
curl -X POST https://gold-research-api-production.up.railway.app/api/v1/research/buyers \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test User",
    "email_address": "test@example.com",
    "phone_number": "+1-555-0100",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "purchase_amount": 12345.67
  }'
```

**Response (201):**
```json
{
  "id": 1,
  "customer_name": "Test User",
  "email_address": "test@example.com",
  "phone_number": "+1-555-0100",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94102",
  "purchase_amount": 12345.67,
  "transaction_date": "2026-01-15T10:30:00"
}
```

**Check sync status (wait 5+ seconds):**
```bash
curl https://gold-research-api-production.up.railway.app/api/v1/research/buyers/1/sync-status
```

**Expected response:**
```json
{
  "id": 1,
  "purchase_record_id": 1,
  "status": "success|pending|failed",
  "attempts": 1,
  "synced_at": "2026-01-15T10:32:15.123456",
  "visa_record_id": "visa-idx-rec-12345",
  "data_sanitized": true,
  "no_pans_detected": true,
  "last_error": null
}
```

## 🔍 Verify Compliance & Data Sanitization

### Database Audit Queries

Use PostgreSQL directly to verify PAN/routing number stripping:

```bash
# Connect to database
psql -h [PGHOST] -U [PGUSER] -d gold_research
```

**Quick compliance check:**
```sql
-- Overall sync statistics
SELECT 
  status,
  COUNT(*) as count,
  COUNT(CASE WHEN data_sanitized = true THEN 1 END) as sanitized
FROM visa_idx_sync_log
GROUP BY status;
```

**Check for failed syncs (requires manual review):**
```sql
SELECT 
  purchase_record_id,
  status,
  attempts,
  last_error,
  last_attempted_at
FROM visa_idx_sync_log
WHERE status IN ('failed', 'failed_max_retries')
ORDER BY last_attempted_at DESC;
```

**Verify PAN/routing stripping worked:**
```sql
SELECT 
  psl.purchase_record_id,
  gp.customer_name,
  gp.phone_number,
  psl.data_sanitized,
  psl.no_pans_detected,
  psl.status
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.created_at >= NOW() - INTERVAL '1 hour'
ORDER BY psl.created_at DESC;
```

### Use Provided Audit Scripts

Run comprehensive compliance queries:

```bash
# Download and run audit script
psql -h [PGHOST] -U [PGUSER] -d gold_research -f audit_compliance.sql
```

**Key reports:**
1. **Overall Sync Status Summary** - Total syncs by status
2. **Recently Synced Records** - Last 24 hours of syncs
3. **Compliance Audit** - Verification that all synced records were sanitized
4. **Data Sanitization Verification** - Spot check of stored records
5. **Sync Pipeline Health Check** - System metrics
6. **Compliance Report for Audit** - Summary statistics

## 📊 Monitoring & Maintenance

### Daily Checks

```bash
# 1. Health check
curl https://gold-research-api-production.up.railway.app/health

# 2. Integration status
curl https://gold-research-api-production.up.railway.app/api/v1/integration/visa-idx/status

# 3. Check failed syncs (should be 0 or very low)
psql ... -c "SELECT COUNT(*) FROM visa_idx_sync_log WHERE status = 'failed_max_retries'"
```

### Weekly Audit

1. **Run end-to-end test:**
   ```bash
   python test_visa_integration.py --api-url [YOUR_API_URL]
   ```

2. **Review compliance logs:**
   ```bash
   psql ... -f audit_compliance.sql
   ```

3. **Check for certificate expiration:**
   ```bash
   openssl x509 -in /path/to/client.pem -dates -noout
   ```

### Monthly Maintenance

1. **Certificate renewal** (if within 3 months of expiration)
   - Download new certs from Visa Developer Portal
   - Update GitHub/Railway
   - Redeploy

2. **Database cleanup** (optional)
   - Archive old sync logs to separate table
   - Review error patterns
   - File support tickets if needed

## 🚨 Troubleshooting

### "Client certificates not available for mutual TLS"

**Solution:**
1. Verify certificate files exist at paths specified in environment variables
2. Check file permissions: `chmod 644 /etc/visa/*.pem` and `chmod 400 /etc/visa/key.pem`
3. Verify Railway deployment includes certificate files
4. Check Docker build logs for certificate copy errors

### "Connection refused" from Visa API

**Solution:**
1. Verify certificates are valid: `openssl x509 -in cert.pem -dates -noout`
2. Test connection: `curl --cert cert.pem --key key.pem --cacert ca.pem https://sandbox.api.visa.com/...`
3. Check Visa API status
4. Verify network connectivity from Railway to Visa (firewall rules)

### Records stuck in "pending" or "failed" status

**Solution:**
1. Check Railway deployment logs for exceptions
2. Review `visa_idx_sync_log` table for error messages
3. Verify certificates are still valid
4. Check Visa API credentials
5. File support ticket with Visa if persistent

### High failure rate in sync logs

**Solution:**
1. Review `last_error` field for clues
2. Common errors:
   - SSL certificate expired → renew certificates
   - Connection timeout → check network connectivity
   - Invalid payload → verify amount formatting (should be cents as integer)
   - Rate limiting → Visa API limit exceeded, wait and retry

## 🔐 Security Checklist

Before moving to production:

- [ ] Private keys are not in GitHub
- [ ] Certificates stored securely in Railway Secrets
- [ ] File permissions correct (400 for private keys)
- [ ] API uses HTTPS only
- [ ] PAN/routing stripping verified working
- [ ] Audit logs protected from unauthorized access
- [ ] SSL certificate expiration monitored
- [ ] Backup certificates stored securely offline
- [ ] Access controls on database verified
- [ ] Logging does not expose sensitive data

## 📞 Support & References

- **Visa IDX Documentation:** [developer.visa.com/reference/visa-idx](https://developer.visa.com/reference/visa-idx)
- **Certificate Help:** Contact Visa Developer Support
- **Integration Guide:** See `VISA_IDX_INTEGRATION.md`
- **Certificate Setup:** See `VISA_CERTIFICATE_SETUP.md`
- **Test Script:** See `test_visa_integration.py`
- **Audit Queries:** See `audit_compliance.sql`

## ✨ Next Steps

1. **Obtain certificates** from Visa Developer Portal
2. **Configure Railway environment** with certificate paths
3. **Mount certificates** in Dockerfile or via Railway Secrets
4. **Deploy to Railway** - auto-build will pull latest from GitHub
5. **Verify integration** - run test script
6. **Monitor compliance** - run audit queries daily
7. **Plan production** - when ready, obtain production credentials from Visa

## Summary

Your Visa IDX integration is complete and ready for testing. The system will:
- ✅ Automatically strip PANs and routing numbers from all incoming data
- ✅ Queue every purchase record for Visa IDX synchronization
- ✅ Sync in background (every 5 minutes, up to 10 records per batch)
- ✅ Retry failed syncs up to 3 times with exponential backoff
- ✅ Maintain complete audit trail of all sync operations
- ✅ Convert USD amounts to Visa's required format (cents as integer)
- ✅ Verify all data is properly sanitized before transmission

**You're all set!** 🚀

Proceed to Step 1: Obtain Visa Sandbox Certificates

