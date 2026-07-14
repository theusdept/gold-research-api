# Visa Merchant Search Integration

## Overview

The Gold Research API integrates Visa's Merchant Search suite for comprehensive merchant enrichment and discovery. This enables transaction cleaning, merchant profiling, and location-based research capabilities.

## Four Core Use Cases

### 1. Transaction History Cleaning

**Endpoint:** `POST /merchantsearch/v1/transactionsearch`

Transform messy, raw statement strings into clean merchant profiles.

**Use Case:** Bank statement shows "AMZN MKTPLACE PMTS WWW.AMZ..." → Get normalized "Amazon Marketplace", with category, location, and verified contact info.

**API Endpoint:**
```bash
POST /api/v1/merchants/enrich/transaction-search?purchase_id=1
Content-Type: application/json

{
  "raw_statement": "AMZN MKTPLACE PMTS WWW.AMZ",
  "merchant_city": "Seattle",
  "merchant_state": "WA"
}
```

**Response:**
```json
{
  "success": true,
  "purchase_id": 1,
  "merchant_id": 42,
  "enrichment_type": "transaction_search",
  "merchant_profile": {
    "name": "Amazon Marketplace",
    "city": "Seattle",
    "state": "WA",
    "country": "USA"
  }
}
```

### 2. General Business Directory Search (v2)

**Endpoint:** `POST /merchantsearch/v2/search`

Robust merchant lookup directory with comprehensive profiles, assets, and scoring.

**Best For:** 
- Building merchant lookup features
- Displaying comprehensive merchant profiles
- Accessing digital assets (logos, category icons)
- Getting confidence/match scores

**API Endpoint:**
```bash
POST /api/v1/merchants/enrich/directory-search?purchase_id=1
Content-Type: application/json

{
  "merchant_name": "Tiffany",
  "merchant_city": "New York",
  "merchant_state": "NY"
}
```

**Response:**
```json
{
  "success": true,
  "purchase_id": 1,
  "merchants_found": 3,
  "results": [
    {
      "name": "Tiffany & Co",
      "category": "Jewelry & Bullion",
      "city": "New York",
      "state": "NY",
      "country": "USA",
      "confidence_score": 0.98,
      "match_score": 0.95,
      "logo_url": "https://images.visa.com/merchants/...",
      "category_icon_url": "https://images.visa.com/categories/...",
      "mcc": "5944"
    },
    {
      "name": "Tiffany & Co - Fifth Avenue",
      "category": "Jewelry & Bullion",
      "city": "New York",
      "state": "NY",
      "country": "USA",
      "confidence_score": 0.92,
      "match_score": 0.89,
      "logo_url": "https://images.visa.com/merchants/...",
      "category_icon_url": "https://images.visa.com/categories/...",
      "mcc": "5944"
    }
  ]
}
```

### 3. Native Visa Card Network Lookup

**Endpoint:** `POST /merchantsearch/v1/merchantlookup`

Direct Visa network lookup using VisaNet transaction IDs and clearing data.

**Best For:**
- Formal backend integration with Visa clearing
- Transaction-specific network lookups
- Clearing and settlement operations

**API Endpoint:**
```bash
POST /api/v1/merchants/visa-lookup
Content-Type: application/json

{
  "transaction_id": "visa-net-123456789",
  "transaction_date": "2024-01-15T10:30:00Z",
  "transaction_type": "AUTHORIZATION"
}
```

**Response:**
```json
{
  "success": true,
  "transaction_id": "visa-net-123456789",
  "merchant": {
    "name": "Tiffany & Co",
    "category": "Jewelry & Bullion",
    "mcc": "5944",
    "clearing_data": {...}
  }
}
```

### 4. Location-Based Merchant Discovery

**Endpoint:** `POST /merchantsearch/v1/locator`

Find nearby Visa-accepting merchants by geographical location.

**Best For:**
- Map/locator features
- "Near me" merchant discovery
- Location-based research

**API Endpoint:**
```bash
POST /api/v1/merchants/nearby-locations
Content-Type: application/json

{
  "city": "Los Angeles",
  "state": "CA",
  "distance_miles": 5.0
}
```

**Response:**
```json
{
  "success": true,
  "location": "Los Angeles, CA",
  "merchants_found": 12,
  "merchants": [
    {
      "name": "Tiffany & Co - Beverly Hills",
      "category": "Jewelry & Bullion",
      "address": "210 N Rodeo Dr, Beverly Hills, CA 90210",
      "city": "Beverly Hills",
      "state": "CA",
      "postal_code": "90210",
      "latitude": 34.0522,
      "longitude": -118.2437,
      "distance": 8.2,
      "phone": "+1-310-555-0100"
    }
  ]
}
```

## Merchant Enrichment Service

The `MerchantEnrichmentService` orchestrates all merchant search operations and maintains a merchant database.

### Data Storage

Three tables track merchant enrichment:

**1. merchant_profiles**
- Normalized merchant data
- Digital assets (logo URLs, category icons)
- Location data (coordinates, address)
- Category and MCC codes
- Confidence/match scores

**2. purchase_merchants**
- Link table between purchases and merchants
- Tracks enrichment type (transaction_search, directory, etc.)
- Enables one-to-many enrichment (one purchase → multiple merchant matches)

**3. merchant_enrichment_history**
- Complete audit trail of all searches
- Raw input, search type, results count
- Success/failure status
- Error messages

### Confidence Scoring

Each merchant match includes scoring metrics:

- **Confidence Score** (0.0 - 1.0): How confident Visa is in the match
- **Match Score** (0.0 - 1.0): Strength of match to input criteria
- **Used for:** Ranking results, filtering low-confidence matches

## API Endpoints

### Enrich Purchase with Transaction Search

```
POST /api/v1/merchants/enrich/transaction-search?purchase_id=1
```

Cleans raw statement strings into merchant profiles.

**Request:**
```json
{
  "raw_statement": "AMZN MKTPLACE PMTS WWW.AMZ",
  "merchant_city": "Seattle",
  "merchant_state": "WA"
}
```

**Response:**
```json
{
  "success": true,
  "purchase_id": 1,
  "merchant_id": 42,
  "enrichment_type": "transaction_search",
  "merchant_profile": {
    "name": "Amazon Marketplace",
    "city": "Seattle",
    "state": "WA"
  }
}
```

### Enrich Purchase with Directory Search

```
POST /api/v1/merchants/enrich/directory-search?purchase_id=1
```

Search merchant directory with logos, categories, and scores.

**Request:**
```json
{
  "merchant_name": "Tiffany",
  "merchant_city": "New York",
  "merchant_state": "NY"
}
```

**Response:**
```json
{
  "success": true,
  "purchase_id": 1,
  "merchants_found": 3,
  "top_merchants": [42, 43, 44],
  "results": [...]
}
```

### Find Nearby Merchants

```
POST /api/v1/merchants/nearby-locations
```

Discover merchants by location (map/locator feature).

**Request:**
```json
{
  "city": "Los Angeles",
  "state": "CA",
  "distance_miles": 5.0
}
```

**Response:**
```json
{
  "success": true,
  "location": "Los Angeles, CA",
  "merchants_found": 12,
  "merchants": [...]
}
```

### Get Purchase Merchant Profiles

```
GET /api/v1/merchants/merchant-profiles/{purchase_id}
```

Retrieve all merchants enriched for a purchase, ranked by confidence.

**Response:**
```json
[
  {
    "id": 42,
    "merchant_name": "Tiffany & Co",
    "merchant_city": "New York",
    "merchant_state": "NY",
    "merchant_category": "Jewelry & Bullion",
    "merchant_category_code": "5944",
    "confidence_score": 0.98,
    "logo_url": "https://...",
    "enrichment_type": "directory_search",
    "enriched_at": "2024-01-15T10:32:15Z"
  }
]
```

### Get Enrichment Status

```
GET /api/v1/merchants/enrichment-status/{purchase_id}
```

Summary of all enrichment operations for a purchase.

**Response:**
```json
{
  "purchase_id": 1,
  "total_enrichments": 3,
  "successful_searches": 2,
  "failed_searches": 1,
  "merchant_profiles_found": 5,
  "last_enriched_at": "2024-01-15T10:32:15Z"
}
```

## Data Privacy & Compliance

### What's Sent to Visa Merchant Search

Only structured merchant search data:
- Merchant name
- City/state/country
- Transaction date (if applicable)
- Distance/location parameters

### What's Never Sent

❌ Personal customer data  
❌ Credit card information  
❌ Account numbers  
❌ Email addresses or phone numbers  
❌ Purchase amounts or payment details

### Storage & Retention

- Merchant profiles cached indefinitely
- Enrichment history retained for audit trail
- No personally identifiable customer information stored
- Compliant with data minimization principles

## Integration Architecture

```
Purchase Record Created
    ↓
1. Stored in gold_purchases table
    ↓
2. Optional: Enrich with Merchant Search (async)
    ├─ Transaction Statement Search (clean raw strings)
    ├─ Directory Search (find multiple matches)
    ├─ Visa Network Lookup (VisaNet IDs)
    └─ Location Search (nearby merchants)
    ↓
3. Results stored in merchant_profiles table
    ↓
4. Links created in purchase_merchants table
    ↓
5. Audit trail in merchant_enrichment_history table
```

## Example Usage Scenarios

### Scenario 1: Cleaning Bank Statement

```python
# Raw statement from credit card
raw_statement = "AMZN MKTPLACE PMTS WWW.AMAZON.COM"

# API call to clean
await enrich_with_transaction_search(
    purchase_id=1,
    raw_statement=raw_statement,
    merchant_city="Seattle",
    merchant_state="WA"
)

# Result: Normalized as "Amazon Marketplace" with verified details
```

### Scenario 2: Jewelry Store Research

```python
# User researching "Tiffany"
await enrich_with_directory_search(
    purchase_id=2,
    merchant_name="Tiffany",
    merchant_city="New York",
    merchant_state="NY"
)

# Results: Top 5 Tiffany locations with logos, categories, confidence scores
```

### Scenario 3: Map Feature

```python
# Build "near me" locator for Los Angeles
nearby = await find_nearby_merchants(
    city="Los Angeles",
    state="CA",
    distance_miles=10.0
)

# Results: List of 50+ nearby merchants with coordinates, phone, address
```

## Monitoring & Observability

### Database Queries

**Top enriched merchants:**
```sql
SELECT merchant_name, COUNT(*) as enrichment_count
FROM purchase_merchants pm
JOIN merchant_profiles m ON pm.merchant_profile_id = m.id
GROUP BY merchant_name
ORDER BY enrichment_count DESC
LIMIT 10;
```

**Enrichment success rate:**
```sql
SELECT 
  search_type,
  COUNT(*) as total,
  COUNT(CASE WHEN success THEN 1 END) as successful,
  ROUND(100.0 * COUNT(CASE WHEN success THEN 1 END) / COUNT(*), 2) as success_rate
FROM merchant_enrichment_history
GROUP BY search_type;
```

**High-confidence merchants:**
```sql
SELECT 
  merchant_name,
  AVG(confidence_score) as avg_confidence,
  COUNT(*) as occurrences
FROM merchant_profiles
WHERE confidence_score > 0.9
GROUP BY merchant_name
ORDER BY avg_confidence DESC;
```

## Error Handling

The enrichment service handles errors gracefully:

- **Missing merchant:** Returns `null` with error message
- **Failed search:** Logged in enrichment_history, can retry manually
- **API timeout:** Wrapped in exception handler, returns error response
- **Network issue:** Propagated with detailed error message

## Performance Considerations

- **Merchant profile caching:** Prevents duplicate API calls for same merchant name
- **Batch enrichment:** Can enrich multiple purchases in parallel
- **Index optimization:** Indexes on merchant_name, location, purchase_record_id
- **Async/await:** Non-blocking enrichment operations

## Production Deployment

1. **Get Merchant Search Credentials**
   - Contact Visa Developer Support
   - Obtain production API credentials

2. **Update Configuration**
   ```python
   # In visa_merchant_search.py
   sandbox=False  # Switch to production
   ```

3. **Deploy**
   - Update Railway with production certificates
   - Redeploy application
   - Verify /api/v1/integration/visa-idx/status shows production mode

4. **Monitor**
   - Watch enrichment success rates
   - Monitor API response times
   - Track confidence scores for quality assurance

## References

- **Visa Merchant Search API:** https://developer.visa.com/reference/merchant-search
- **Merchant Category Codes:** https://developer.visa.com/reference/mcc-codes
- **API Authentication:** Mutual TLS (handled automatically)
- **Rate Limits:** Check Visa documentation for current limits

## Support

For integration issues:
1. Check `/api/v1/integration/visa-idx/status` endpoint
2. Review merchant_enrichment_history table for error details
3. Verify certificates are configured correctly
4. Check Railway logs for API communication errors

