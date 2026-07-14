# Visa IDX Certificate Setup Guide

## Overview

This guide walks through obtaining and configuring Two-Way SSL certificates for Visa IDX sandbox integration.

## Step 1: Access Visa Developer Portal

1. Go to [Visa Developer Portal](https://developer.visa.com)
2. Sign in to your developer account
3. Navigate to **Apps** → **My Apps**
4. Select your IDX application (or create new if needed)

## Step 2: Locate Sandbox Certificates

In your app settings, find the **Credentials** section:

1. Look for **Sandbox Credentials**
2. You should see certificate download options:
   - **Client Certificate** (.pem or .crt format)
   - **Private Key** (.pem or .key format)
   - **CA Certificate** (.pem format) - for verifying Visa's server

### Expected Files

```
visa-sandbox-certs/
├── client-cert.pem          (Your client certificate)
├── client-key.pem           (Your private key)
└── ca-cert.pem              (Visa's CA certificate)
```

### Certificate Details

You can inspect certificates with:

```bash
# View certificate details
openssl x509 -in client-cert.pem -text -noout

# Check private key validity
openssl rsa -in client-key.pem -check

# Verify certificate chain
openssl verify -CAfile ca-cert.pem client-cert.pem
```

## Step 3: Configure Railway Environment Variables

### Option A: Using Railway Dashboard (Recommended for Secrets)

1. Go to your Railway project dashboard
2. Select the **gold-research-api** service
3. Go to **Variables** tab
4. Add these environment variables:

```
VISA_CERT_PATH=/etc/visa/client.pem
VISA_KEY_PATH=/etc/visa/key.pem
VISA_CA_PATH=/etc/visa/ca.pem
```

### Option B: Using Railway CLI

```bash
railway variables set VISA_CERT_PATH=/etc/visa/client.pem
railway variables set VISA_KEY_PATH=/etc/visa/key.pem
railway variables set VISA_CA_PATH=/etc/visa/ca.pem
```

## Step 4: Securely Mount Certificates

### Option A: Store in GitHub (Development Only)

⚠️ **WARNING**: Only for non-production sandbox testing!

1. Create directory in repo:
```bash
mkdir -p certs/visa
cd certs/visa
```

2. Copy certificate files:
```bash
cp /path/to/client-cert.pem .
cp /path/to/client-key.pem .
cp /path/to/ca-cert.pem .
```

3. Update `.gitignore`:
```bash
echo "certs/visa/*.pem" >> .gitignore
echo "certs/visa/*.crt" >> .gitignore
echo "certs/visa/*.key" >> .gitignore
```

4. Update `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy certificates
COPY certs/visa/client-cert.pem /etc/visa/client.pem
COPY certs/visa/client-key.pem /etc/visa/key.pem
COPY certs/visa/ca-cert.pem /etc/visa/ca.pem

# Make certificate directory readable
RUN chmod 644 /etc/visa/*.pem && \
    chmod 400 /etc/visa/client-key.pem

# Copy application files
COPY main.py .
COPY visa_idx_client.py .
COPY visa_idx_sync.py .

EXPOSE 8000
CMD ["python", "main.py"]
```

### Option B: Use Railway Secrets (Production)

1. In Railway dashboard, go to **Variables**
2. Click **+ New Variable** → **Secret**
3. Create secret variables:
   - `VISA_CLIENT_CERT` - paste entire client certificate (.pem content)
   - `VISA_CLIENT_KEY` - paste entire private key content
   - `VISA_CA_CERT` - paste CA certificate content

4. In your startup script or init, write secrets to files:

```python
import os

# Create certificate files from Railway secrets
cert_dir = "/etc/visa"
os.makedirs(cert_dir, exist_ok=True)

if os.getenv("VISA_CLIENT_CERT"):
    with open(f"{cert_dir}/client.pem", "w") as f:
        f.write(os.getenv("VISA_CLIENT_CERT"))
    os.chmod(f"{cert_dir}/client.pem", 0o644)

if os.getenv("VISA_CLIENT_KEY"):
    with open(f"{cert_dir}/key.pem", "w") as f:
        f.write(os.getenv("VISA_CLIENT_KEY"))
    os.chmod(f"{cert_dir}/key.pem", 0o400)

if os.getenv("VISA_CA_CERT"):
    with open(f"{cert_dir}/ca.pem", "w") as f:
        f.write(os.getenv("VISA_CA_CERT"))
    os.chmod(f"{cert_dir}/ca.pem", 0o644)
```

## Step 5: Verify Certificate Paths

In your Railway **Variables**, confirm these are set:

```
VISA_CERT_PATH=/etc/visa/client.pem
VISA_KEY_PATH=/etc/visa/key.pem
VISA_CA_PATH=/etc/visa/ca.pem
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=***
PGDATABASE=gold_research
```

## Step 6: Test Certificate Installation

Once deployed, check logs for successful certificate loading:

```bash
# In Railway dashboard, view deployment logs
# Look for messages like:
# "Client certificates loaded for mutual TLS authentication"
# OR
# "Client certificates not available for mutual TLS"
```

If you see the warning message, certificates aren't configured. Verify:
1. Files exist at correct paths
2. File permissions are correct (644 for certs, 400 for key)
3. Container has read access

## Certificate Renewal

Visa sandbox certificates typically expire after 1-2 years. When renewing:

1. Download new certificates from Visa Developer Portal
2. Update files on filesystem or GitHub
3. Redeploy application
4. No code changes needed

## Security Best Practices

✅ **DO:**
- Store private keys securely (use Railway Secrets for production)
- Use strong file permissions (400 for private keys)
- Rotate certificates before expiration
- Keep private key separate from certificate
- Use HTTPS for all transmission

❌ **DON'T:**
- Commit private keys to GitHub (even in private repos)
- Share certificates via email or chat
- Log certificate content
- Use self-signed certificates in production
- Hardcode certificate paths in code (use env vars)

## Troubleshooting Certificate Issues

### Certificate Not Found

```
Error: Failed to create SSL context: [Errno 2] No such file or directory
```

**Solution:**
1. Verify file paths in environment variables
2. Check that files exist: `ls -la /etc/visa/`
3. Ensure files have correct permissions
4. Check container logs for exact error

### Certificate Verification Failed

```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solution:**
1. Verify CA certificate path is correct
2. Check certificate hasn't expired: `openssl x509 -in cert.pem -dates -noout`
3. Ensure cert is in PEM format (not DER)
4. For Visa sandbox, use correct sandbox CA certificate

### Permission Denied

```
PermissionError: [Errno 13] Permission denied: '/etc/visa/client-key.pem'
```

**Solution:**
1. Check file permissions: `ls -la /etc/visa/`
2. Private key must be readable by app user: `chmod 400 client-key.pem`
3. In Dockerfile, set correct permissions during build

### Connection Refused

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution:**
1. Verify Visa API endpoint is correct (sandbox vs production)
2. Check network connectivity from Railway to Visa API
3. Verify certificates are valid and not expired
4. Check if Visa API is under maintenance

## Testing Certificate Configuration

Use this curl command to test connectivity:

```bash
curl -v \
  --cert /etc/visa/client.pem \
  --key /etc/visa/client-key.pem \
  --cacert /etc/visa/ca.pem \
  https://sandbox.api.visa.com/visaidx/v1/goldRecords
```

Expected response: 400-level HTTP error (missing data), NOT SSL error

## Next Steps

Once certificates are configured:
1. Run test script: `python test_visa_integration.py`
2. Check sync logs: `GET /api/v1/research/buyers/{id}/sync-status`
3. Monitor compliance audit: Query `visa_idx_sync_log` table
4. Review integration status: `GET /api/v1/integration/visa-idx/status`

See `test_visa_integration.py` for end-to-end testing guide.

