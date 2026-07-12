"""
Gold Research API - Test Version
This version uses in-memory storage for testing purposes
"""
import os
import re
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gold Research API (Test)", version="1.0.0")

# In-memory storage for testing
buyers_db = []
next_id = 1


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
    results = buyers_db.copy()
    
    if state:
        results = [b for b in results if b.get('state') == state.upper()]
    
    if zip_code:
        results = [b for b in results if b.get('zip_code') == zip_code]
    
    if start_date:
        results = [b for b in results if b.get('transaction_date', datetime.now()) >= start_date]
    
    if end_date:
        results = [b for b in results if b.get('transaction_date', datetime.now()) <= end_date]
    
    # Sort by transaction date descending
    results.sort(key=lambda x: x.get('transaction_date', datetime.now()), reverse=True)
    
    return results


@app.post("/api/v1/research/buyers", response_model=BuyerResponse, status_code=201)
async def create_buyer(record: BuyerRecord):
    """
    Ingest a new gold purchase record. Credit card numbers and routing numbers are automatically stripped.
    """
    global next_id
    
    try:
        # Strip sensitive data
        data = strip_sensitive_data(record.model_dump())
        
        buyer = {
            "id": next_id,
            "customer_name": data['customer_name'],
            "email_address": data['email_address'],
            "phone_number": data['phone_number'],
            "city": data['city'],
            "state": data['state'],
            "zip_code": data['zip_code'],
            "transaction_date": data['transaction_date'] or datetime.now()
        }
        
        buyers_db.append(buyer)
        next_id += 1
        
        logger.info(f"Created buyer record with ID {buyer['id']}")
        return buyer
    
    except Exception as e:
        logger.error(f"Error creating buyer: {e}")
        raise HTTPException(status_code=500, detail="Failed to create record")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "mode": "test (in-memory)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

