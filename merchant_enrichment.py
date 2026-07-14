"""
Merchant Enrichment Service
Enriches purchase records with Visa Merchant Search data.
Handles merchant profiling, statement cleaning, and location-based lookup.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from visa_merchant_search import get_visa_merchant_search_client, MerchantSearchEndpoint

logger = logging.getLogger(__name__)


class MerchantEnrichmentService:
    """
    Enriches purchase records with comprehensive merchant data.
    
    Features:
    - Clean raw transaction statements
    - Lookup merchant profiles and logos
    - Find nearby merchants for research
    - Build merchant master database
    """
    
    def __init__(self, db_connection_params: Dict[str, str]):
        """
        Initialize enrichment service.
        
        Args:
            db_connection_params: Database connection parameters
        """
        self.db_params = db_connection_params
        self.merchant_client = get_visa_merchant_search_client()
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(**self.db_params)
    
    async def init_merchant_tables(self, conn) -> None:
        """
        Create merchant enrichment tables if they don't exist.
        
        Tracks:
        - Merchant profiles (normalized data, logos, etc.)
        - Enrichment history (what searches were run)
        - Cache of recent lookups
        """
        try:
            cursor = conn.cursor()
            
            # Merchant profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merchant_profiles (
                    id SERIAL PRIMARY KEY,
                    merchant_name VARCHAR(255) NOT NULL UNIQUE,
                    merchant_city VARCHAR(100),
                    merchant_state VARCHAR(2),
                    merchant_country VARCHAR(3) DEFAULT 'USA',
                    merchant_category VARCHAR(100),
                    merchant_category_code VARCHAR(4),
                    logo_url TEXT,
                    category_icon_url TEXT,
                    confidence_score FLOAT,
                    match_score FLOAT,
                    latitude FLOAT,
                    longitude FLOAT,
                    phone_number VARCHAR(20),
                    address TEXT,
                    postal_code VARCHAR(10),
                    last_enriched_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Link table between purchases and merchants
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_merchants (
                    id SERIAL PRIMARY KEY,
                    purchase_record_id INTEGER NOT NULL REFERENCES gold_purchases(id),
                    merchant_profile_id INTEGER NOT NULL REFERENCES merchant_profiles(id),
                    enrichment_type VARCHAR(50),  -- 'transaction_search', 'general_search', 'lookup'
                    enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CONSTRAINT unique_purchase_merchant UNIQUE(purchase_record_id, merchant_profile_id)
                );
            """)
            
            # Enrichment history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merchant_enrichment_history (
                    id SERIAL PRIMARY KEY,
                    purchase_record_id INTEGER NOT NULL REFERENCES gold_purchases(id),
                    raw_merchant_name VARCHAR(255),
                    search_type VARCHAR(50),  -- 'transaction_search', 'directory', 'visa_lookup', 'locator'
                    search_params JSONB,
                    results_count INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT false,
                    error_message TEXT,
                    confidence_score FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_merchant_name 
                ON merchant_profiles(merchant_name);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_merchant_location 
                ON merchant_profiles(merchant_city, merchant_state);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_purchase_merchant 
                ON purchase_merchants(purchase_record_id);
            """)
            
            conn.commit()
            logger.info("Merchant enrichment tables initialized")
        
        except Exception as e:
            logger.error(f"Failed to initialize merchant tables: {e}")
            conn.rollback()
            raise
    
    async def enrich_purchase_with_transaction_search(
        self,
        purchase_id: int,
        raw_statement: str,
        city: Optional[str] = None,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich purchase record by cleaning transaction statement.
        
        Args:
            purchase_id: ID of purchase record
            raw_statement: Raw transaction statement string
            city: Optional merchant city
            state: Optional merchant state
        
        Returns:
            Enrichment result with merchant profile
        """
        conn = self._get_connection()
        
        try:
            # Call Visa transaction search
            result = await self.merchant_client.clean_transaction_statement(
                raw_statement=raw_statement,
                city=city,
                state=state
            )
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error"),
                    "purchase_id": purchase_id
                }
            
            # Parse response
            parsed = self.merchant_client.parse_merchant_response(
                result,
                MerchantSearchEndpoint.TRANSACTION_SEARCH
            )
            
            # Store enrichment in database
            merchant_id = await self._store_merchant_profile(
                conn,
                parsed.get("suggested_merchant", {})
            )
            
            # Link purchase to merchant
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO purchase_merchants (purchase_record_id, merchant_profile_id, enrichment_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (purchase_record_id, merchant_profile_id) DO NOTHING
            """, (purchase_id, merchant_id, "transaction_search"))
            
            # Log enrichment history
            cursor.execute("""
                INSERT INTO merchant_enrichment_history 
                (purchase_record_id, raw_merchant_name, search_type, success, confidence_score)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                purchase_id,
                raw_statement,
                "transaction_search",
                True,
                result.get("confidence_score")
            ))
            
            conn.commit()
            
            return {
                "success": True,
                "purchase_id": purchase_id,
                "merchant_id": merchant_id,
                "merchant_profile": parsed.get("suggested_merchant"),
                "enrichment_type": "transaction_search"
            }
        
        except Exception as e:
            logger.error(f"Error enriching purchase {purchase_id}: {e}")
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "purchase_id": purchase_id
            }
        
        finally:
            conn.close()
    
    async def enrich_purchase_with_directory_search(
        self,
        purchase_id: int,
        merchant_name: str,
        city: Optional[str] = None,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich purchase record with merchant directory search.
        
        Returns comprehensive merchant profiles with logos, categories, scores.
        
        Args:
            purchase_id: ID of purchase record
            merchant_name: Merchant name to search
            city: Optional merchant city
            state: Optional merchant state
        
        Returns:
            Enrichment result with merchant matches
        """
        conn = self._get_connection()
        
        try:
            # Call Visa merchant directory search
            result = await self.merchant_client.search_merchant_directory(
                merchant_name=merchant_name,
                city=city,
                state=state
            )
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error"),
                    "purchase_id": purchase_id
                }
            
            # Parse response
            parsed = self.merchant_client.parse_merchant_response(
                result,
                MerchantSearchEndpoint.GENERAL_SEARCH_V2
            )
            
            # Store top matches
            top_merchants = []
            cursor = conn.cursor()
            
            for merchant in parsed.get("merchants", [])[:5]:  # Top 5 results
                merchant_id = await self._store_merchant_profile(conn, merchant)
                top_merchants.append(merchant_id)
                
                # Link purchase to merchant
                cursor.execute("""
                    INSERT INTO purchase_merchants (purchase_record_id, merchant_profile_id, enrichment_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (purchase_record_id, merchant_profile_id) DO NOTHING
                """, (purchase_id, merchant_id, "general_search"))
            
            # Log enrichment history
            cursor.execute("""
                INSERT INTO merchant_enrichment_history 
                (purchase_record_id, raw_merchant_name, search_type, results_count, success, confidence_score)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                purchase_id,
                merchant_name,
                "directory",
                len(top_merchants),
                True,
                parsed["merchants"][0].get("confidence_score") if parsed["merchants"] else None
            ))
            
            conn.commit()
            
            return {
                "success": True,
                "purchase_id": purchase_id,
                "merchants_found": len(top_merchants),
                "top_merchants": top_merchants,
                "results": parsed.get("merchants", [])[:5]
            }
        
        except Exception as e:
            logger.error(f"Error enriching purchase {purchase_id} with directory search: {e}")
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "purchase_id": purchase_id
            }
        
        finally:
            conn.close()
    
    async def find_nearby_merchants_for_research(
        self,
        city: str,
        state: str,
        distance_miles: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Find nearby merchants for research purposes (map/locator feature).
        
        Args:
            city: Search city
            state: Search state
            distance_miles: Optional search radius
        
        Returns:
            Nearby merchant locations
        """
        try:
            result = await self.merchant_client.find_nearby_merchants(
                city=city,
                state=state,
                distance=distance_miles,
                distance_unit="MILES" if distance_miles else None
            )
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error")
                }
            
            # Parse response
            parsed = self.merchant_client.parse_merchant_response(
                result,
                MerchantSearchEndpoint.MERCHANT_LOCATOR
            )
            
            return {
                "success": True,
                "location": f"{city}, {state}",
                "merchants_found": parsed.get("results_count", 0),
                "merchants": parsed.get("merchants", [])
            }
        
        except Exception as e:
            logger.error(f"Error finding nearby merchants: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_merchant_profile(
        self,
        conn,
        merchant_data: Dict[str, Any]
    ) -> int:
        """
        Store or update merchant profile in database.
        
        Returns merchant ID.
        """
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        merchant_name = merchant_data.get("name") or merchant_data.get("merchant_name")
        
        if not merchant_name:
            raise ValueError("Merchant name required")
        
        try:
            # Try to insert (will skip if exists due to UNIQUE constraint)
            cursor.execute("""
                INSERT INTO merchant_profiles 
                (merchant_name, merchant_city, merchant_state, merchant_country, 
                 merchant_category, merchant_category_code, logo_url, category_icon_url,
                 confidence_score, match_score, latitude, longitude, phone_number, 
                 address, postal_code, last_enriched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (merchant_name) DO UPDATE 
                SET last_enriched_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                merchant_name,
                merchant_data.get("city") or merchant_data.get("merchant_city"),
                merchant_data.get("state") or merchant_data.get("merchant_state"),
                merchant_data.get("country") or merchant_data.get("merchant_country") or "USA",
                merchant_data.get("category") or merchant_data.get("merchant_category"),
                merchant_data.get("mcc") or merchant_data.get("merchant_category_code"),
                merchant_data.get("logo_url") or merchant_data.get("merchantLogoUrl"),
                merchant_data.get("category_icon_url") or merchant_data.get("categoryIconUrl"),
                merchant_data.get("confidence_score") or merchant_data.get("confidenceScore"),
                merchant_data.get("match_score") or merchant_data.get("matchScore"),
                merchant_data.get("latitude"),
                merchant_data.get("longitude"),
                merchant_data.get("phone") or merchant_data.get("phoneNumber"),
                merchant_data.get("address"),
                merchant_data.get("postal_code") or merchant_data.get("postalCode")
            ))
            
            result = cursor.fetchone()
            merchant_id = result["id"]
            
            conn.commit()
            return merchant_id
        
        except Exception as e:
            logger.error(f"Error storing merchant profile: {e}")
            conn.rollback()
            raise
    
    async def get_purchase_merchants(self, purchase_id: int) -> List[Dict[str, Any]]:
        """
        Get all enriched merchant profiles for a purchase.
        
        Args:
            purchase_id: ID of purchase record
        
        Returns:
            List of merchant profiles
        """
        conn = self._get_connection()
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    m.*,
                    pm.enrichment_type,
                    pm.enriched_at
                FROM merchant_profiles m
                JOIN purchase_merchants pm ON m.id = pm.merchant_profile_id
                WHERE pm.purchase_record_id = %s
                ORDER BY m.confidence_score DESC NULLS LAST
            """, (purchase_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
        
        finally:
            conn.close()
    
    async def get_enrichment_status(self, purchase_id: int) -> Dict[str, Any]:
        """
        Get enrichment status for a purchase record.
        
        Args:
            purchase_id: ID of purchase record
        
        Returns:
            Enrichment status and history
        """
        conn = self._get_connection()
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_enrichments,
                    COUNT(CASE WHEN success THEN 1 END) as successful_searches,
                    COUNT(CASE WHEN NOT success THEN 1 END) as failed_searches,
                    MAX(created_at) as last_enriched_at
                FROM merchant_enrichment_history
                WHERE purchase_record_id = %s
            """, (purchase_id,))
            
            status = cursor.fetchone()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as merchant_profiles_count
                FROM purchase_merchants
                WHERE purchase_record_id = %s
            """, (purchase_id,))
            
            merchant_count = cursor.fetchone()
            
            return {
                "purchase_id": purchase_id,
                "total_enrichments": status["total_enrichments"] if status else 0,
                "successful_searches": status["successful_searches"] if status else 0,
                "failed_searches": status["failed_searches"] if status else 0,
                "merchant_profiles_found": merchant_count["merchant_profiles_count"] if merchant_count else 0,
                "last_enriched_at": status["last_enriched_at"] if status else None
            }
        
        finally:
            conn.close()


# Global enrichment service
_enrichment_service: Optional[MerchantEnrichmentService] = None


def get_enrichment_service(db_params: Dict[str, str]) -> MerchantEnrichmentService:
    """Get or create singleton merchant enrichment service."""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = MerchantEnrichmentService(db_params)
    return _enrichment_service

