import os
import re
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import logging

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
    """Initialize database on startup."""
    init_connection_pool()
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    """Close all connections on shutdown."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()


async def init_db():
    """Create the gold_purchases table if it doesn't exist."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gold_purchases (
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
        """)
        
        # Create index on state and zip_code for faster filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_state ON gold_purchases(state);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_zip_code ON gold_purchases(zip_code);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transaction_date ON gold_purchases(transaction_date);
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


class BuyerResponse(BaseModel):
    """Model for outgoing buyer data."""
    id: int
    customer_name: str
    email_address: str
    phone_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    transaction_date: datetime


@app.get("/api/v1/research/buyers", response_model=list[BuyerResponse])
async def get_buyers(
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    zip_code: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """
    Retrieve all gold purchase records with optional filters.
    
    Query Parameters:
    - state: Filter by 2-letter state code
    - zip_code: Filter by zip code
    - start_date: Filter by transaction start date (ISO 8601 format)
    - end_date: Filter by transaction end date (ISO 8601 format)
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
    Ingest a new gold purchase record. Credit card numbers and routing numbers are automatically stripped.
    """
    conn = None
    try:
        # Strip sensitive data
        data = strip_sensitive_data(record.model_dump())
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            INSERT INTO gold_purchases
            (customer_name, email_address, phone_number, city, state, zip_code, transaction_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *;
        """, (
            data['customer_name'],
            data['email_address'],
            data['phone_number'],
            data['city'],
            data['state'],
            data['zip_code'],
            data['transaction_date'] or datetime.now()
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        logger.info(f"Created buyer record with ID {result['id']}")
        return dict(result)
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating buyer: {e}")
        raise HTTPException(status_code=500, detail="Failed to create record")
    
    finally:
        if conn:
            return_connection(conn)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

