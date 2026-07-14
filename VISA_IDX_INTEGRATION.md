# Visa IDX Integration Guide

## Overview

The Gold Research API includes built-in integration with Visa's Identity eXchange (IDX) API for secure synchronization of gold purchase records. This document provides setup instructions, architecture overview, and compliance details.

## Features

✅ **Mutual TLS Authentication** - Two-way SSL authentication using client certificates  
✅ **Automatic Data Sanitization** - Strips PANs and routing numbers before transmission  
✅ **Background Sync Pipeline** - Asynchronous queue-based synchronization  
✅ **Retry Logic** - Exponential backoff with configurable max retries  
✅ **Compliance Tracking** - Audit trail of all sync operations  
✅ **Amount Formatting** - Automatic USD to minor units (cents) conversion  
✅ **Idempotent Operations** - Safe to retry without duplicate records  

## Architecture

### Components

```
FastAPI Application
    ├── visa_idx_client.py      (Visa API communication)
    ├── visa_idx_sync.py        (Background sync pipeline)
    └── main.py                 (API endpoints + integration)
```

### Data Flow

```
POST /api/v1/research/buyers
    ↓
1. Validate & Sanitize (strip PANs/routing numbers)
    ↓
2. Store in PostgreSQL (gold_purchases table)
    ↓
3. Queue for Visa IDX sync (visa_idx_sync_log table)
    ↓
4. Background Task (every 5 minutes)
    ├── Fetch pending records
    ├── Format for Visa IDX API
    ├── Send via Mutual TLS
    └── Track status & retries
    ↓
5. Response Available
    GET /api/v1/research/buyers/{id}/sync-status
```

## Setup & Configuration

### 1. Obtain Visa Sandbox Credentials

Visit [Visa Developer Portal](https://developer.visa.com):

1. Create a developer account
2. Register for IDX API access
3. Download certificates:
   - **Client Certificate** (.pem) - identifies your application to Visa
   - **Client Private Key** (.pem) - keeps this secure!
   - **CA Certificate** (.pem) - verifies Visa's identity

### 2. Deploy Certificates to Railway

Create environment variables in Railway dashboard:

```
VISA_CERT_PATH=/etc/visa/client.pem
VISA_KEY_PATH=/etc/visa/key.pem
VISA_CA_PATH=/etc/visa/ca.pem
```

Or use Railway's Secrets feature:
1. Go to project settings
2. Add raw certificates as secrets
3. Reference in container via volume mounts

### 3. Example: Mount Certificates via Docker

Update `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy certificates (must be in repo or mounted from Railway secrets)
COPY certs/client.pem /etc/visa/client.pem
COPY certs/key.pem /etc/visa/key.pem
COPY certs/ca.pem /etc/visa/ca.pem

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

EXPOSE 8000
CMD ["python", "main.py"]
```

### 4. Environment Variables

```bash
# Visa IDX Configuration (optional if certs are in repo/mounted)
VISA_CERT_PATH=/etc/visa/client.pem
VISA_KEY_PATH=/etc/visa/key.pem
VISA_CA_PATH=/etc/visa/ca.pem

# Database (already configured)
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=***
PGDATABASE=gold_research
```

## API Endpoints

### Create Purchase Record (Auto-Queued for Sync)

**Request:**
```bash
curl -X POST https://api.example.com/api/v1/research/buyers \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Jane Smith",
    "email_address": "jane@example.com",
    "phone_number": "+1-555-0100",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001",
    "purchase_amount": 25000.50
  }'
```

**Response (201):**
```json
{
  "id": 1,
  "customer_name": "Jane Smith",
  "email_address": "jane@example.com",
  "phone_number": "+1-555-0100",
  "city": "Los Angeles",
  "state": "CA",
  "zip_code": "90001",
  "purchase_amount": 25000.50,
  "transaction_date": "2026-01-15T10:30:00"
}
```

✅ Record is automatically queued for Visa IDX sync

### Check Sync Status

**Request:**
```bash
curl https://api.example.com/api/v1/research/buyers/1/sync-status
```

**Response:**
```json
{
  "id": 1,
  "purchase_record_id": 1,
  "status": "success",
  "attempts": 1,
  "synced_at": "2026-01-15T10:32:15.123456",
  "visa_record_id": "visa-idx-rec-12345",
  "data_sanitized": true,
  "no_pans_detected": true,
  "last_error": null
}
```

**Possible Status Values:**
- `pending` - Queued, waiting to sync
- `syncing` - Currently being sent to Visa
- `success` - Successfully synced to Visa IDX
- `failed` - Sync failed, will retry
- `failed_max_retries` - Max retries exceeded, manual intervention needed

### Get Integration Status

**Request:**
```bash
curl https://api.example.com/api/v1/integration/visa-idx/status
```

**Response:**
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

## Data Sanitization & Compliance

### Automatic PII Stripping

The API automatically strips sensitive data before any transmission:

**On Ingest (POST):**
- Removes credit card numbers (13-19 digit patterns)
- Removes bank routing numbers (9 digit patterns)
- Normalizes state codes to uppercase

**On Sync to Visa:**
- Secondary sanitization pass before formatting for IDX
- Ensures defense-in-depth compliance
- Flags `data_sanitized=true` in sync log

### What's Sent to Visa

Only non-sensitive identity and location data:

```json
{
  "goldenRecord": {
    "identity": {
      "name": "Jane Smith",
      "email": "jane@example.com",
      "phoneNumber": "+1-555-0100"
    },
    "location": {
      "city": "Los Angeles",
      "state": "CA",
      "postalCode": "90001"
    }
  },
  "transaction": {
    "amount": {
      "value": 2500050,              // In cents (minor units)
      "currency": "840"              // USD
    },
    "timestamp": "2026-01-15T10:30:00Z",
    "merchantCategoryCode": "5944"   // Jewelry & Bullion
  }
}
```

### What's Never Sent

❌ Credit card numbers (PANs)  
❌ Bank routing numbers  
❌ Payment method information  
❌ Raw purchase prices before sanitization  
❌ IP addresses or device identifiers  

### Compliance Audit Trail

Every sync operation is logged:

```sql
SELECT 
  purchase_record_id,
  status,
  synced_at,
  data_sanitized,
  no_pans_detected,
  attempts,
  last_error
FROM visa_idx_sync_log
ORDER BY synced_at DESC;
```

## Currency Conversion

The API handles USD to minor units (cents) automatically:

```python
# Input: $125.50
purchase_amount = 125.50

# Automatically converted to Visa IDX format
minor_units = int(round(125.50 * 100))  # = 12550

# Sent to Visa as:
{
  "amount": {
    "value": 12550,
    "currency": "840"  // USD
  }
}
```

## Retry Logic

The sync pipeline implements exponential backoff:

- **Initial Delay:** 60 seconds
- **Max Delay:** 3600 seconds (1 hour)
- **Max Retries:** 3 attempts
- **Batch Processing:** 10 records per sync cycle
- **Sync Interval:** 5 minutes (configurable)

### Retry Scenarios

```
Attempt 1 → Failed       (Status: failed, will retry)
  ↓ wait 60s
Attempt 2 → Failed       (Status: failed, will retry)
  ↓ wait 300s
Attempt 3 → Failed       (Status: failed_max_retries)
  ↓ Manual review required
```

## SSL/TLS Configuration

### Mutual Authentication

The client authenticates to Visa and Visa authenticates to the client:

```
Client (Your App)
├── Provides: Client Certificate + Private Key
├── Verifies: Server (Visa) Certificate
└── Uses: TLS 1.2+

Visa API
├── Provides: Server Certificate
├── Verifies: Client Certificate
└── Rejects: Unknown clients
```

### Certificate Validation

```python
# visa_idx_client.py
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
```

## Troubleshooting

### Integration Not Starting

**Symptom:** Warning message in logs
```
Failed to initialize Visa IDX integration
```

**Solution:**
1. Check certificates exist in correct paths
2. Verify environment variables set correctly
3. Review Railway logs for detailed error
4. In sandbox, app continues without IDX; in production, this blocks startup

### Sync Stuck in "Pending" State

**Symptom:** Records not syncing
```bash
curl https://api.example.com/api/v1/research/buyers/1/sync-status
# Returns status: pending (after 5+ minutes)
```

**Solution:**
1. Check `/health` endpoint shows sync pipeline running
2. Review Railway deployment logs for errors
3. Verify certificates are readable by container
4. Check Visa sandbox credentials are valid

### Certificate Errors

**Symptom:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:**
1. Verify CA certificate path is correct
2. Check certificate hasn't expired: `openssl x509 -in cert.pem -dates -noout`
3. Ensure cert is in PEM format (not DER)
4. For Visa sandbox, use sandbox CA certificate

### High Retry Rates

**Symptom:** Many `failed_max_retries` records
```sql
SELECT COUNT(*) FROM visa_idx_sync_log 
WHERE status = 'failed_max_retries';
```

**Investigation:**
1. Check last_error field for clues
2. Verify Visa API credentials/sandbox still active
3. Check network connectivity from Railway to Visa API
4. Review Visa API documentation for breaking changes

## Monitoring & Observability

### Check Sync Queue Health

```bash
# Pending syncs (should process within 5 minutes)
curl "https://api.example.com/api/v1/research/buyers/RECORD_ID/sync-status"

# Integration status
curl "https://api.example.com/api/v1/integration/visa-idx/status"

# Health check
curl "https://api.example.com/health"
```

### Database Queries

```sql
-- Overall sync statistics
SELECT 
  status,
  COUNT(*) as count,
  AVG(attempts) as avg_attempts
FROM visa_idx_sync_log
GROUP BY status;

-- Failed syncs with errors
SELECT 
  purchase_record_id,
  last_error,
  attempts,
  created_at
FROM visa_idx_sync_log
WHERE status IN ('failed', 'failed_max_retries')
ORDER BY created_at DESC;

-- Recently synced records
SELECT 
  purchase_record_id,
  synced_at,
  attempts,
  visa_record_id
FROM visa_idx_sync_log
WHERE status = 'success'
ORDER BY synced_at DESC
LIMIT 10;
```

## Moving to Production

1. **Get Production Credentials**
   - Request production API access from Visa
   - Download production certificates

2. **Update Configuration**
   ```python
   # In visa_idx_client.py initialization
   sandbox=False  # Switch to production endpoint
   ```

3. **Deploy**
   - Update Railway environment variables with production certs
   - Redeploy application
   - Verify integration status shows `sandbox_mode: false`

4. **Monitor**
   - Watch first week of syncs closely
   - Set up alerts on `failed_max_retries` status
   - Review Visa API logs for any issues

## Support & References

- **Visa IDX API Docs:** https://developer.visa.com/reference/visa-idx
- **Certificate Management:** Contact Visa Developer Support
- **Integration Issues:** Check `visa_idx_sync_log` table for detailed error messages
- **Railway Logs:** View real-time application logs in Railway dashboard

## API Reference

### POST /api/v1/research/buyers

Creates a record and automatically queues for Visa IDX sync.

### GET /api/v1/research/buyers/{buyer_id}/sync-status

Returns current Visa IDX sync status for a record.

### GET /api/v1/integration/visa-idx/status

Returns integration health and configuration.

### GET /health

Application health check (includes sync pipeline status).

