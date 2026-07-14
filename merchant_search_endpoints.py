"""
Merchant Search API Endpoints
FastAPI route handlers for merchant enrichment and search.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

from merchant_enrichment import get_enrichment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/merchants", tags=["merchants"])


class TransactionSearchRequest(BaseModel):
    """Request model for transaction statement cleaning."""
    raw_statement: str
    merchant_city: Optional[str] = None
    merchant_state: Optional[str] = None


class DirectorySearchRequest(BaseModel):
    """Request model for merchant directory search."""
    merchant_name: str
    merchant_city: Optional[str] = None
    merchant_state: Optional[str] = None


class NearbyMerchantsRequest(BaseModel):
    """Request model for nearby merchants search."""
    city: str
    state: str
    distance_miles: Optional[float] = None


@router.post("/enrich/transaction-search", response_model=Dict[str, Any])
async def enrich_with_transaction_search(
    purchase_id: int = Query(..., description="ID of purchase record to enrich"),
    request: TransactionSearchRequest = None
):
    """
    Enrich a purchase record by cleaning raw transaction statement.
    
    Transforms messy statement strings (e.g., "AMZN MKTPLACE PMTS...") 
    into clean merchant profiles using Visa Merchant Search.
    
    Query Parameters:
    - purchase_id: ID of gold_purchases record
    
    Request Body:
    - raw_statement: Raw transaction text to clean
    - merchant_city: (optional) Merchant city to improve matching
    - merchant_state: (optional) Merchant state to improve matching
    
    Returns: Cleaned merchant profile and enrichment result
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request body required")
    
    try:
        # This will be implemented by integrating with enrichment service in main.py
        # Placeholder for now
        return {
            "status": "enrich_endpoints_pending_main_py_update",
            "purchase_id": purchase_id
        }
    
    except Exception as e:
        logger.error(f"Error enriching purchase: {e}")
        raise HTTPException(status_code=500, detail="Enrichment failed")


@router.post("/enrich/directory-search", response_model=Dict[str, Any])
async def enrich_with_directory_search(
    purchase_id: int = Query(..., description="ID of purchase record to enrich"),
    request: DirectorySearchRequest = None
):
    """
    Enrich a purchase record with merchant directory search.
    
    Returns comprehensive merchant profiles with:
    - Confidence/match scores
    - Category information
    - Digital assets (logos, icons)
    - Multiple matching merchants
    
    Query Parameters:
    - purchase_id: ID of gold_purchases record
    
    Request Body:
    - merchant_name: Name to search for
    - merchant_city: (optional) City for better matching
    - merchant_state: (optional) State for better matching
    
    Returns: Top matching merchants with assets and scores
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request body required")
    
    try:
        # This will be implemented by integrating with enrichment service in main.py
        return {
            "status": "directory_search_pending_main_py_update",
            "purchase_id": purchase_id,
            "search_query": request.merchant_name
        }
    
    except Exception as e:
        logger.error(f"Error searching merchant directory: {e}")
        raise HTTPException(status_code=500, detail="Directory search failed")


@router.post("/nearby-locations", response_model=Dict[str, Any])
async def find_nearby_merchants(request: NearbyMerchantsRequest):
    """
    Find nearby Visa-accepting merchants by location.
    
    Enables "near me" features for merchant discovery and research.
    
    Request Body:
    - city: Search location city
    - state: Search location state
    - distance_miles: (optional) Search radius
    
    Returns: Nearby merchants with location data and contact info
    """
    try:
        # This will be implemented by integrating with enrichment service in main.py
        return {
            "status": "nearby_search_pending_main_py_update",
            "location": f"{request.city}, {request.state}"
        }
    
    except Exception as e:
        logger.error(f"Error finding nearby merchants: {e}")
        raise HTTPException(status_code=500, detail="Location search failed")


@router.get("/merchant-profiles/{purchase_id}", response_model=List[Dict[str, Any]])
async def get_purchase_merchant_profiles(purchase_id: int):
    """
    Get all merchant profiles enriched for a purchase record.
    
    Returns all merchants found through enrichment searches,
    ranked by confidence score.
    
    Path Parameters:
    - purchase_id: ID of gold_purchases record
    
    Returns: List of merchant profiles with enrichment details
    """
    try:
        # This will be implemented by integrating with enrichment service in main.py
        return [{
            "status": "profiles_pending_main_py_update",
            "purchase_id": purchase_id
        }]
    
    except Exception as e:
        logger.error(f"Error retrieving merchant profiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve profiles")


@router.get("/enrichment-status/{purchase_id}", response_model=Dict[str, Any])
async def get_enrichment_status(purchase_id: int):
    """
    Get enrichment status for a purchase record.
    
    Returns summary of all enrichment searches performed:
    - Total searches executed
    - Success/failure counts
    - Merchant profiles found
    - Last enrichment timestamp
    
    Path Parameters:
    - purchase_id: ID of gold_purchases record
    
    Returns: Enrichment status summary
    """
    try:
        # This will be implemented by integrating with enrichment service in main.py
        return {
            "status": "enrichment_status_pending_main_py_update",
            "purchase_id": purchase_id
        }
    
    except Exception as e:
        logger.error(f"Error getting enrichment status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status")

