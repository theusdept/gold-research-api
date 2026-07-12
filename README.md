# Gold Research API

A FastAPI-based REST API for tracking physical gold and bullion purchases, with automatic PII masking and data privacy compliance.

## Overview

This API tracks gold and bullion purchases based on Merchant Category Code (MCC 5944) data while maintaining strict data privacy:
- Automatically strips credit card numbers (PANs) and bank routing numbers
- Stores only identity and location data
- Supports filtering by state, zip code, and transaction date range

## Features

- **Automatic Data Sanitization**: Credit card numbers and routing numbers are automatically removed from all incoming data
- **Flexible Querying**: Filter records by state, zip code, and date range
- **PostgreSQL Database**: Persistent storage with indexed fields for fast queries
- **RESTful JSON API**: Standard REST endpoints for data ingestion and retrieval

## API Endpoints

### GET /api/v1/research/buyers
Retrieve all gold purchase records with optional filtering.

**Query Parameters:**
- `state` (optional): Filter by 2-letter state code (e.g., CA, NY)
- `zip_code` (optional): Filter by zip code
- `start_date` (optional): Filter by transaction start date (ISO 8601 format)
- `end_date` (optional): Filter by transaction end date (ISO 8601 format)

**Example:**
```bash
curl "http://localhost:8000/api/v1/research/buyers?state=CA&zip_code=90210"
curl "http://localhost:8000/api/v1/research/buyers?start_date=2024-01-01&end_date=2024-12-31"
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
  "transaction_date": "2024-01-15T10:30:00"
}
```

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
  transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Indexes are created on `state`, `zip_code`, and `transaction_date` for optimized queries.

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

API documentation at `http://localhost:8000/docs`

## Data Privacy & Security

- All incoming data is automatically sanitized to remove:
  - Credit card numbers (13-19 digit patterns)
  - Bank routing numbers (9 digit patterns)
- Email validation ensures data integrity
- State codes are normalized to uppercase
- No sensitive financial data is stored

