import os
import re
from datetime import datetime
from typing import Optional
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import logging
import asyncio

from visa_idx_client import get_visa_idx_client
from visa_idx_sync import get_sync_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gold Research API", version="1.0.0")

# Database configuration
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
DB_NAME = os.getenv("PGDATABASE", "gold_research")

# Connection pool
connection_pool = None
sync_pipeline = None


def init_connection_pool():
    """Initialize database connection pool."""
    global connection_pool
    try:
        connection_pool = SimpleConnectionPool(
            1, 20,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def get_connection():
    """Get a connection from the pool."""
    if connection_pool is None:
        init_connection_pool()
    return connection_pool.getconn()


def return_connection(conn):
    """Return a connection to the pool."""
    if connection_pool:
        connection_pool.putconn(conn)


def strip_sensitive_data(data: dict) -> dict:
    """Strip credit card numbers and routing numbers from data."""
    for key, value in data.items():
        if isinstance(value, str):
            # Remove credit card patterns (13-19 digits)
            value = re.sub(r'\b\d{13,19}\b', '', value)
            # Remove routing number patterns (9 digits)
            value = re.sub(r'\b\d{9}\b', '', value)
            data[key] = value.strip()
    return data


@app.on_event("startup")
async def startup():
    """Initialize database and Visa IDX sync pipeline on startup."""
    global sync_pipeline
    
    init_connection_pool()
    await init_db()
    
    # Initialize Visa IDX integration
    try:
        # Get sync pipeline
        db_params = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "database": DB_NAME
        }
        sync_pipeline = get_sync_pipeline(db_params)
        
        # Initialize sync tracking table
        conn = get_connection()
        await sync_pipeline.init_sync_table(conn)
        return_connection(conn)
        
        # Start background sync task
        asyncio.create_task(sync_pipeline.start_background_sync(interval_seconds=300))
        
        logger.info("Visa IDX sync pipeline initialized and background task started")
    
    except Exception as e:
        logger.warning(f"Failed to initialize Visa IDX integration: {e}. Continuing without sync.")


@app.on_event("shutdown")
async def shutdown():
    """Close all connections on shutdown."""
    global connection_pool, sync_pipeline
    
    # Stop sync pipeline
    if sync_pipeline:
        await sync_pipeline.stop_background_sync()
    
    if connection_pool:
        connection_pool.closeall()


async def init_db():
    """Create the gold_purchases table if it doesn't exist and add missing columns."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gold_purchases (
                id SERIAL PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                email_address VARCHAR(255) NOT NULL,
                phone_number VARCHAR(20),
                city VARCHAR(100),
                state VARCHAR(2),
                zip_code VARCHAR(10),
                purchase_amount NUMERIC(12, 2),
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Add purchase_amount column if it doesn't exist
        cursor.execute("""
            ALTER TABLE gold_purchases 
            ADD COLUMN IF NOT EXISTS purchase_amount NUMERIC(12, 2);
        """)
        
        # Create indexes (IF NOT EXISTS prevents errors if they already exist)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_state ON gold_purchases(state);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_zip_code ON gold_purchases(zip_code);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transaction_date ON gold_purchases(transaction_date);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchase_amount ON gold_purchases(purchase_amount);
        """)
        
        conn.commit()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            return_connection(conn)


class BuyerRecord(BaseModel):
    """Model for incoming buyer data."""
    customer_name: str
    email_address: EmailStr
    phone_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    purchase_amount: Optional[float] = None
    transaction_date: Optional[datetime] = None
    
    @field_validator('customer_name')
    @classmethod
    def validate_customer_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('customer_name cannot be empty')
        return v.strip()
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        if v and len(v) != 2:
            raise ValueError('state must be a 2-character code')
        return v.upper() if v else None
    
    @field_validator('purchase_amount')
    @classmethod
    def validate_purchase_amount(cls, v):
        if v is not None and v < 0:
            raise ValueError('purchase_amount must be a positive number')
        return v


class BuyerResponse(BaseModel):
    """Model for outgoing buyer data."""
    id: int
    customer_name: str
    email_address: str
    phone_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    purchase_amount: Optional[float] = None
    transaction_date: datetime


@app.get("/api/v1/research/buyers", response_model=list[BuyerResponse])
async def get_buyers(
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    zip_code: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0)
):
    """
    Retrieve all gold purchase records with optional filters.
    
    Query Parameters:
    - state: Filter by 2-letter state code
    - zip_code: Filter by zip code
    - start_date: Filter by transaction start date (ISO 8601 format)
    - end_date: Filter by transaction end date (ISO 8601 format)
    - min_amount: Filter by minimum purchase amount (USD)
    - max_amount: Filter by maximum purchase amount (USD)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM gold_purchases WHERE 1=1"
        params = []
        
        if state:
            query += " AND UPPER(state) = UPPER(%s)"
            params.append(state)
        
        if zip_code:
            query += " AND zip_code = %s"
            params.append(zip_code)
        
        if start_date:
            query += " AND transaction_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= %s"
            params.append(end_date)
        
        if min_amount is not None:
            query += " AND purchase_amount >= %s"
            params.append(min_amount)
        
        if max_amount is not None:
            query += " AND purchase_amount <= %s"
            params.append(max_amount)
        
        query += " ORDER BY transaction_date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        logger.error(f"Error retrieving buyers: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve records")
    
    finally:
        if conn:
            return_connection(conn)


@app.post("/api/v1/research/buyers", response_model=BuyerResponse, status_code=201)
async def create_buyer(record: BuyerRecord):
    """
    Ingest a new gold purchase record. 
    - Credit card numbers and routing numbers are automatically stripped.
    - Record is automatically queued for Visa IDX synchronization.
    """
    conn = None
    try:
        # Strip sensitive data
        data = strip_sensitive_data(record.model_dump())
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            INSERT INTO gold_purchases
            (customer_name, email_address, phone_number, city, state, zip_code, purchase_amount, transaction_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *;
        """, (
            data['customer_name'],
            data['email_address'],
            data['phone_number'],
            data['city'],
            data['state'],
            data['zip_code'],
            data['purchase_amount'],
            data['transaction_date'] or datetime.now()
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        purchase_id = result['id']
        logger.info(f"Created buyer record with ID {purchase_id}")
        
        # Queue for Visa IDX sync (non-blocking)
        if sync_pipeline:
            try:
                await sync_pipeline.queue_purchase_for_sync(purchase_id, conn)
            except Exception as e:
                logger.warning(f"Failed to queue record for sync: {e}")
        
        return dict(result)
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating buyer: {e}")
        raise HTTPException(status_code=500, detail="Failed to create record")
    
    finally:
        if conn:
            return_connection(conn)


@app.get("/api/v1/research/buyers/{buyer_id}/sync-status")
async def get_buyer_sync_status(buyer_id: int):
    """
    Get Visa IDX sync status for a specific buyer record.
    
    Returns sync status including:
    - Current sync state (pending, syncing, success, failed)
    - Number of sync attempts
    - Last error (if any)
    - Visa record ID (if synced)
    - Compliance flags (data_sanitized, no_pans_detected)
    """
    if not sync_pipeline:
        raise HTTPException(status_code=503, detail="Visa IDX sync pipeline not available")
    
    try:
        status = await sync_pipeline.get_sync_status(buyer_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Record not found in sync queue")
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync status")


@app.get("/api/v1/research/buyers/analytics/total", response_model=dict)
async def get_total_purchase_amount(
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """
    Get total purchase amount for gold transactions.
    
    Query Parameters:
    - state: Filter by 2-letter state code
    - start_date: Filter by transaction start date (ISO 8601 format)
    - end_date: Filter by transaction end date (ISO 8601 format)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT SUM(purchase_amount) as total_amount, COUNT(*) as transaction_count FROM gold_purchases WHERE 1=1"
        params = []
        
        if state:
            query += " AND UPPER(state) = UPPER(%s)"
            params.append(state)
        
        if start_date:
            query += " AND transaction_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= %s"
            params.append(end_date)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return {
            "total_amount": float(result['total_amount']) if result['total_amount'] else 0.0,
            "transaction_count": result['transaction_count'],
            "average_amount": float(result['total_amount'] / result['transaction_count']) if result['transaction_count'] and result['total_amount'] else 0.0
        }
    
    except Exception as e:
        logger.error(f"Error calculating totals: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate analytics")
    
    finally:
        if conn:
            return_connection(conn)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "visa_idx_integration": "enabled" if sync_pipeline else "disabled"
    }


@app.get("/api/v1/integration/visa-idx/status")
async def get_visa_idx_status():
    """
    Get Visa IDX integration status and configuration.
    
    Returns information about:
    - Integration availability
    - Sandbox/production mode
    - Mutual TLS authentication status
    - Background sync pipeline status
    """
    try:
        visa_client = get_visa_idx_client()
        
        return {
            "integration_enabled": sync_pipeline is not None,
            "sandbox_mode": visa_client.sandbox,
            "certificates_configured": (
                os.path.exists(visa_client.cert_path) and
                os.path.exists(visa_client.key_path)
            ),
            "sync_pipeline_running": sync_pipeline.is_running if sync_pipeline else False,
            "sync_batch_size": sync_pipeline.BATCH_SIZE if sync_pipeline else None,
            "max_sync_retries": sync_pipeline.MAX_RETRIES if sync_pipeline else None
        }
    
    except Exception as e:
        logger.error(f"Error getting integration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get integration status")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

