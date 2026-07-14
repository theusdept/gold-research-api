# Phase 1 Quick Start - Get Production Credentials

**Objective:** Obtain production Visa credentials and certificates to move from sandbox to production mode.

**Time Required:** 30 minutes of setup + 1-3 days waiting for Visa approval

**Status:** 🔄 In Progress

---

## **Step 1: Access Visa Developer Portal** (5 minutes)

1. Go to https://developer.visa.com
2. Sign in with your existing account
   - If no account: Create one (use business email)
   - If never signed up: Go to **Developer Portal** → **Sign Up**

3. Once logged in, navigate to:
   - **Dashboard** → **Credentials** (left sidebar)
   - Or directly: https://developer.visa.com/credentials

---

## **Step 2: Request Production API Access** (10 minutes)

### **For Visa IDX API:**

1. In Credentials page, look for **Visa IDX** section
2. Click **"Activate Production"** or **"Request Production Access"**
3. Fill out the form:
   - **Use Case:** `Gold Research API - Transaction enrichment and merchant profiling`
   - **Organization:** Your company name
   - **Business Justification:** 
     ```
     Enrich precious metals and jewelry purchase records with 
     merchant information and identity verification using Visa IDX. 
     This enables compliance tracking and merchant profiling for 
     research purposes.
     ```
   - **Expected API Volume:** `100-1000 calls/day`
   - **Data Protection:** 
     ```
     All personally identifiable information is stripped and 
     sanitized before transmission. No credit card numbers or 
     routing numbers are transmitted. Data is stored securely 
     with audit logging and 90-day retention policy.
     ```

4. Submit the request

### **For Visa Merchant Search API:**

1. Repeat the process for **Merchant Search**
2. Fill out the form:
   - **Use Case:** `Gold Research API - Merchant enrichment and discovery`
   - **Business Justification:**
     ```
     Enrich purchase records with merchant profiles, logos, 
     category information, and location data. Build a comprehensive 
     merchant database for jewelry and precious metals retailers.
     ```
   - **Expected API Volume:** `100-1000 calls/day`

3. Submit the request

**Note:** Visa will review both requests. You'll receive an approval email within 1-3 business days.

---

## **Step 3: Download Production Certificates** (Once Approved)

When Visa approves your request (email notification):

1. Go back to Credentials page
2. Find **Visa IDX** section → **Production** tab
3. Download the certificate package:
   - `client_cert.pem` (client certificate)
   - `client_key.pem` (private key)
   - `ca_cert.pem` (CA certificate)

4. Save these files locally (keep them secure!)

**Important:** Never commit these to Git. They're secrets.

---

## **Step 4: Add Certificates to Railway Secrets** (5 minutes)

### **Create Three Railway Secrets:**

1. Go to Railway Dashboard → Your Project → **Settings** → **Secrets**

2. Create Secret #1: `VISA_CERT_CONTENT`
   - Click **New Secret**
   - Name: `VISA_CERT_CONTENT`
   - Value: Copy the entire contents of `client_cert.pem` (including `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`)
   - Click **Save**

3. Create Secret #2: `VISA_KEY_CONTENT`
   - Name: `VISA_KEY_CONTENT`
   - Value: Copy the entire contents of `client_key.pem` (including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----`)
   - Click **Save**

4. Create Secret #3: `VISA_CA_CONTENT`
   - Name: `VISA_CA_CONTENT`
   - Value: Copy the entire contents of `ca_cert.pem`
   - Click **Save**

### **Also Add:**

5. Create Secret #4: `VISA_SANDBOX_MODE`
   - Name: `VISA_SANDBOX_MODE`
   - Value: `false` (switches from sandbox to production)
   - Click **Save**

6. Create Secret #5: `API_KEY`
   - Name: `API_KEY`
   - Value: Generate a strong API key:
     ```bash
     openssl rand -hex 32
     ```
   - Example: `a3f8d2b1c4e7f9a2c5d8e1b4f7a0c3e6d9f2b5c8e1a4d7f0c3b6e9a2d5f8c1`
   - Click **Save**

---

## **Step 5: Update Dockerfile** (5 minutes)

Update your `Dockerfile` to mount the secrets:

**File:** `Dockerfile`

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

# Mount certificates from Railway secrets
# These environment variables are set by Railway from Secrets
RUN if [ ! -z "$VISA_CERT_CONTENT" ]; then echo "$VISA_CERT_CONTENT" > /etc/visa/client.pem; fi && \
    if [ ! -z "$VISA_KEY_CONTENT" ]; then echo "$VISA_KEY_CONTENT" > /etc/visa/key.pem; fi && \
    if [ ! -z "$VISA_CA_CONTENT" ]; then echo "$VISA_CA_CONTENT" > /etc/visa/ca.pem; fi && \
    chmod 600 /etc/visa/*.pem 2>/dev/null || true

EXPOSE 8000
CMD ["python", "main.py"]
```

Push this to GitHub:
```bash
git add Dockerfile
git commit -m "Production: Mount Visa certificates from Railway secrets"
git push
```

---

## **Step 6: Deploy to Production** (5 minutes)

1. Your Dockerfile and secrets are ready
2. Push to GitHub (if not already done)
3. Railway auto-deploys
4. Monitor deployment in Railway dashboard
5. Check health: `GET https://gold-research-api-production.up.railway.app/health`

Response should show:
```json
{
  "status": "healthy",
  "visa_idx_integration": "enabled",
  "merchant_enrichment": "enabled"
}
```

---

## **Step 7: Verify Production Mode** (5 minutes)

### **Check Integration Status:**

```bash
curl https://gold-research-api-production.up.railway.app/api/v1/integration/visa-idx/status
```

Expected response:
```json
{
  "integration_enabled": true,
  "sandbox_mode": false,           # ← Should be false!
  "certificates_configured": true,
  "sync_pipeline_running": true,
  "sync_batch_size": 10,
  "max_sync_retries": 3
}
```

### **Check Merchant Search Status:**

```bash
curl https://gold-research-api-production.up.railway.app/api/v1/integration/merchant-search/status
```

Expected response:
```json
{
  "integration_enabled": true,
  "sandbox_mode": false,           # ← Should be false!
  "certificates_configured": true,
  "enrichment_endpoints": [
    "POST /api/v1/merchants/enrich/transaction-search",
    "POST /api/v1/merchants/enrich/directory-search",
    "POST /api/v1/merchants/nearby-locations",
    "GET /api/v1/merchants/merchant-profiles/{purchase_id}",
    "GET /api/v1/merchants/enrichment-status/{purchase_id}"
  ]
}
```

---

## **Troubleshooting**

### **Certificates Not Loading**

**Symptom:** 
```
WARNING: Client certificates not available for merchant search
```

**Fix:**
1. Verify secrets are set in Railway: `Settings` → `Secrets`
2. Check secret values contain full certificate (with `-----BEGIN` and `-----END`)
3. Redeploy: Railway → Deployments → Trigger deploy
4. Check logs in Railway dashboard for errors

### **Still in Sandbox Mode**

**Symptom:** 
```json
{
  "sandbox_mode": true  # ← Should be false
}
```

**Fix:**
1. Verify `VISA_SANDBOX_MODE=false` is set in secrets
2. Verify code is reading it: Check `visa_idx_client.py` line ~29
3. Redeploy and wait 2-3 minutes

### **Certificate Expiration Error**

**Symptom:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Fix:**
1. Check certificate dates:
   ```bash
   openssl x509 -in your_cert.pem -dates -noout
   ```
2. If expired: Download new certificates from Visa
3. Update secrets in Railway
4. Redeploy

---

## **Checklist - Phase 1 Complete When:**

- [ ] You have requested production access from Visa
- [ ] Visa has approved your request (email received)
- [ ] You have downloaded production certificates
- [ ] You have added 5 secrets to Railway (3 certs + SANDBOX_MODE + API_KEY)
- [ ] You have updated Dockerfile
- [ ] You have pushed Dockerfile to GitHub
- [ ] Railway has deployed successfully
- [ ] `/api/v1/integration/visa-idx/status` shows `sandbox_mode: false`
- [ ] `/api/v1/integration/merchant-search/status` shows `sandbox_mode: false`

---

## **What's Next?**

Once Phase 1 is complete, move to **Phase 2: Security Hardening**

See: `PRODUCTION_READINESS_CHECKLIST.md` → Phase 2

---

## **Key Dates to Track**

| Milestone | Target Date | Status |
|-----------|------------|--------|
| Request Visa credentials | **Today** | 🔄 Start here |
| Visa approval | **+1-3 days** | ⏳ Waiting |
| Add to Railway secrets | **+3 days** | ⏳ Waiting |
| Deploy to production | **+3 days** | ⏳ Waiting |
| Complete Phase 1 | **+3 days** | ⏳ Waiting |

---

**Status:** 🟡 Ready to start Phase 1

**Next Action:** Go to https://developer.visa.com/credentials and request production access

Need help? See the full checklist: https://github.com/theusdept/gold-research-api/blob/main/PRODUCTION_READINESS_CHECKLIST.md

