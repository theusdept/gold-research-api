# Gold Research API

A FastAPI-based REST API for tracking physical gold and bullion purchases with transaction values, automatic PII masking, and data privacy compliance.

## Overview

This API tracks gold and bullion purchases based on Merchant Category Code (MCC 5944) data while maintaining strict data privacy and capturing transaction values:
- Automatically strips credit card numbers (PANs) and bank routing numbers
- Stores only identity, location, and transaction amount data
- Supports filtering by state, zip code, date range, and purchase amount
- Provides analytics endpoints for aggregated purchase data

## Features

- **Purchase Amount Tracking**: Captures and stores transaction values (USD)
- **Automatic Data Sanitization**: Credit card numbers and routing numbers are automatically removed from all incoming data
- **Flexible Querying**: Filter records by state, zip code, date range, and purchase amount
- **Analytics Endpoint**: Get total, count, and average purchase amounts with optional filters
- **PostgreSQL Database**: Persistent storage with indexed fields for fast queries
- **RESTful JSON API**: Standard REST endpoints for data ingestion and retrieval

## Database Schema

```sql
CREATE TABLE gold_purchases (
  id SERIAL PRIMARY KEY,
  customer_name VARCHAR(255) NOT NULL,
  email_address VARCHAR(255) NOT NULL,
  phone_number VARCHAR(20),
  city VARCHAR(100),
  state VARCHAR(2),
  zip_code VARCHAR(10),
  purchase_amount NUMERIC(12, 2),              -- NEW: USD transaction value
  transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `state` — Fast filtering by state
- `zip_code` — Fast filtering by zip code
- `transaction_date` — Fast date range filtering
- `purchase_amount` — Fast amount filtering

## API Endpoints

### GET /api/v1/research/buyers
Retrieve all gold purchase records with optional filtering.

**Query Parameters:**
- `state` (optional): Filter by 2-letter state code (e.g., CA, NY)
- `zip_code` (optional): Filter by zip code
- `start_date` (optional): Filter by transaction start date (ISO 8601 format)
- `end_date` (optional): Filter by transaction end date (ISO 8601 format)
- `min_amount` (optional): Filter by minimum purchase amount (USD, >= 0)
- `max_amount` (optional): Filter by maximum purchase amount (USD, >= 0)

**Examples:**
```bash
# Get all records from California
curl "http://localhost:8000/api/v1/research/buyers?state=CA"

# Filter by date range
curl "http://localhost:8000/api/v1/research/buyers?start_date=2024-01-01&end_date=2024-12-31"

# Filter by purchase amount range ($5,000 - $50,000)
curl "http://localhost:8000/api/v1/research/buyers?min_amount=5000&max_amount=50000"

# Combine filters: CA + Jan 2024 + $10k minimum
curl "http://localhost:8000/api/v1/research/buyers?state=CA&start_date=2024-01-01&end_date=2024-01-31&min_amount=10000"
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "customer_name": "John Doe",
    "email_address": "john@example.com",
    "phone_number": "+1-555-0123",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "purchase_amount": 25000.50,
    "transaction_date": "2024-01-15T10:30:00"
  },
  {
    "id": 2,
    "customer_name": "Jane Smith",
    "email_address": "jane@example.com",
    "phone_number": "+1-555-0124",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001",
    "purchase_amount": 15750.00,
    "transaction_date": "2024-01-20T14:15:00"
  }
]
```

### POST /api/v1/research/buyers
Ingest a new gold purchase record. Credit card and routing numbers are automatically stripped.

**Request Body:**
```json
{
  "customer_name": "John Doe",
  "email_address": "john@example.com",
  "phone_number": "+1-555-0123",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94102",
  "purchase_amount": 25000.50,
  "transaction_date": "2024-01-15T10:30:00"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "customer_name": "John Doe",
  "email_address": "john@example.com",
  "phone_number": "+1-555-0123",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94102",
  "purchase_amount": 25000.50,
  "transaction_date": "2024-01-15T10:30:00"
}
```

**Field Validation:**
- `customer_name`: Required, non-empty string
- `email_address`: Required, valid email format
- `phone_number`: Optional string
- `city`: Optional string
- `state`: Optional, must be 2-character code (normalized to uppercase)
- `zip_code`: Optional string
- `purchase_amount`: Optional, must be >= 0 if provided
- `transaction_date`: Optional ISO 8601 datetime (defaults to current timestamp)

### GET /api/v1/research/buyers/analytics/total
Get aggregated purchase analytics with optional filtering.

**Query Parameters:**
- `state` (optional): Filter by 2-letter state code
- `start_date` (optional): Filter by transaction start date
- `end_date` (optional): Filter by transaction end date

**Examples:**
```bash
# Total purchases across all transactions
curl "http://localhost:8000/api/v1/research/buyers/analytics/total"

# Total purchases in California
curl "http://localhost:8000/api/v1/research/buyers/analytics/total?state=CA"

# Total purchases in Q1 2024
curl "http://localhost:8000/api/v1/research/buyers/analytics/total?start_date=2024-01-01&end_date=2024-03-31"
```

**Response (200 OK):**
```json
{
  "total_amount": 250000.75,
  "transaction_count": 12,
  "average_amount": 20833.40
}
```

## Deployment on Railway

1. **Create a new Railway project** and connect your GitHub repository
2. **Add PostgreSQL service** using the Railway template
3. **Deploy this service** with the following environment variables linked from Postgres:
   - `PGHOST`
   - `PGPORT`
   - `PGUSER`
   - `PGPASSWORD`
   - `PGDATABASE`
   - `PORT=8000`

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables (copy `.env.example` to `.env`):
   ```bash
   cp .env.example .env
   ```

3. Start a local PostgreSQL server or update `.env` with remote database credentials

4. Run the application:
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:8000`

API documentation at `http://localhost:8000/docs` (Swagger UI)

## Data Privacy & Security

- All incoming data is automatically sanitized to remove:
  - Credit card numbers (13-19 digit patterns)
  - Bank routing numbers (9 digit patterns)
- Email validation ensures data integrity
- State codes are normalized to uppercase
- Purchase amounts are stored as NUMERIC(12,2) for financial accuracy
- No sensitive financial data is stored (only amounts, no payment methods)
- Connection pooling prevents resource exhaustion

## Migration from Previous Schema

If you have an existing `gold_purchases` table without the `purchase_amount` column, add it with:

```sql
ALTER TABLE gold_purchases ADD COLUMN purchase_amount NUMERIC(12, 2);
CREATE INDEX idx_purchase_amount ON gold_purchases(purchase_amount);
```

## Testing

The repository includes test data scripts. Run tests with:

```bash
pytest tests/
```

Or use curl for quick testing:

```bash
# Create multiple test records
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/v1/research/buyers \
    -H "Content-Type: application/json" \
    -d "{
      \"customer_name\": \"Test User $i\",
      \"email_address\": \"user$i@example.com\",
      \"state\": \"CA\",
      \"zip_code\": \"9000$i\",
      \"purchase_amount\": $((5000 + i * 1000))
    }"
done

# Get all records
curl http://localhost:8000/api/v1/research/buyers

# Get analytics
curl http://localhost:8000/api/v1/research/buyers/analytics/total
```

## API Documentation

Interactive API docs available at `/docs` (Swagger UI) or `/redoc` (ReDoc)

