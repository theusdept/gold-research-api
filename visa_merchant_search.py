"""
Visa Merchant Search Integration
Provides merchant lookup, enrichment, and location-based services.
Supports transaction history cleaning, business search, and network lookup.
"""
import os
import ssl
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class MerchantSearchEndpoint(Enum):
    """Visa Merchant Search API endpoints."""
    TRANSACTION_SEARCH = "merchantsearch/v1/transactionsearch"
    MERCHANT_LOOKUP = "merchantsearch/v1/merchantlookup"
    MERCHANT_LOCATOR = "merchantsearch/v1/locator"
    GENERAL_SEARCH_V2 = "merchantsearch/v2/search"


class VisaMerchantSearchClient:
    """
    Client for Visa Merchant Search API integration.
    
    Provides:
    - Transaction history cleaning (raw statement strings → merchant profiles)
    - Merchant directory lookup with confidence scores
    - Native Visa network lookups (VisaNet identifiers)
    - Location-based / "near me" merchant discovery
    """
    
    def __init__(
        self,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_path: Optional[str] = None,
        sandbox: bool = True
    ):
        """
        Initialize Visa Merchant Search Client with SSL certificates.
        
        Args:
            cert_path: Path to client certificate (.pem)
            key_path: Path to client private key (.pem)
            ca_path: Path to CA certificate (.pem) for server verification
            sandbox: Use sandbox or production endpoint (default: sandbox)
        """
        self.sandbox = sandbox
        self.base_url = (
            "https://sandbox.api.visa.com" if sandbox
            else "https://api.visa.com"
        )
        
        # Certificate paths
        self.cert_path = cert_path or os.getenv("VISA_CERT_PATH", "/etc/visa/client.pem")
        self.key_path = key_path or os.getenv("VISA_KEY_PATH", "/etc/visa/key.pem")
        self.ca_path = ca_path or os.getenv("VISA_CA_PATH", "/etc/visa/ca.pem")
        
        # SSL context for mutual TLS
        self.ssl_context = self._create_ssl_context()
        
        logger.info(f"Visa Merchant Search Client initialized ({'sandbox' if sandbox else 'production'} mode)")
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with mutual authentication."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        try:
            if os.path.exists(self.ca_path):
                context.load_verify_locations(cafile=self.ca_path)
            
            if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
                context.load_cert_chain(
                    certfile=self.cert_path,
                    keyfile=self.key_path
                )
                logger.info("Client certificates loaded for merchant search")
            else:
                logger.warning("Client certificates not available for merchant search")
        
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            if not self.sandbox:
                raise
        
        return context
    
    async def clean_transaction_statement(
        self,
        raw_statement: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country_code: str = "USA"
    ) -> Dict[str, Any]:
        """
        Clean and enrich messy transaction statement strings.
        
        Transforms raw merchant names (e.g., "AMZN MKTPLACE PMTS WWW.AMZ...")
        into structured merchant profiles with confirmed details.
        
        Args:
            raw_statement: Raw transaction statement string
            city: Merchant city (optional, improves matching)
            state: Merchant state (optional, improves matching)
            country_code: Merchant country code (default: USA)
        
        Returns:
            Enriched merchant profile with normalized data
        """
        try:
            payload = {
                "merchantName": raw_statement,
                "merchantCity": city,
                "merchantState": state,
                "merchantCountryCode": country_code
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            logger.info(f"Cleaning transaction statement: {raw_statement}")
            
            response = await self._make_request(
                MerchantSearchEndpoint.TRANSACTION_SEARCH,
                payload
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error cleaning transaction statement: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_input": raw_statement
            }
    
    async def search_merchant_directory(
        self,
        merchant_name: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country_code: str = "USA"
    ) -> Dict[str, Any]:
        """
        Search merchant directory with comprehensive profiles and assets.
        
        Uses v2 search for best results, returning:
        - Confidence/match scores
        - Digital assets (logos, icons)
        - Category information
        - Multiple matching merchants
        
        Args:
            merchant_name: Merchant name to search
            city: Merchant city (improves matching)
            state: Merchant state (improves matching)
            country_code: Merchant country code (default: USA)
        
        Returns:
            Directory search results with merchant profiles and assets
        """
        try:
            payload = {
                "merchantName": merchant_name,
                "merchantCity": city,
                "merchantState": state,
                "merchantCountryCode": country_code
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            logger.info(f"Searching merchant directory: {merchant_name}")
            
            response = await self._make_request(
                MerchantSearchEndpoint.GENERAL_SEARCH_V2,
                payload
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error searching merchant directory: {e}")
            return {
                "success": False,
                "error": str(e),
                "search_query": merchant_name
            }
    
    async def lookup_visa_merchant(
        self,
        transaction_id: str,
        transaction_date: datetime,
        transaction_type: str = "AUTHORIZATION"
    ) -> Dict[str, Any]:
        """
        Native Visa card network lookup using VisaNet identifiers.
        
        For use with formal backend clearing identifiers and transaction IDs
        directly from Visa network processing.
        
        Args:
            transaction_id: VisaNet transaction ID
            transaction_date: Date of transaction
            transaction_type: Type of transaction (AUTHORIZATION, etc.)
        
        Returns:
            Visa network merchant lookup results
        """
        try:
            payload = {
                "transactionId": transaction_id,
                "transactionDate": transaction_date.isoformat() if isinstance(transaction_date, datetime) else transaction_date,
                "transactionType": transaction_type
            }
            
            logger.info(f"Looking up Visa merchant: {transaction_id}")
            
            response = await self._make_request(
                MerchantSearchEndpoint.MERCHANT_LOOKUP,
                payload
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error looking up Visa merchant: {e}")
            return {
                "success": False,
                "error": str(e),
                "transaction_id": transaction_id
            }
    
    async def find_nearby_merchants(
        self,
        city: str,
        state: str,
        distance: Optional[float] = None,
        distance_unit: str = "MILES",
        country_code: str = "USA"
    ) -> Dict[str, Any]:
        """
        Location-based merchant discovery for map/locator features.
        
        Find nearby Visa-accepting merchants by geographical location.
        
        Args:
            city: Merchant city
            state: Merchant state
            distance: Search radius (optional)
            distance_unit: Distance unit (MILES, KILOMETERS)
            country_code: Country code (default: USA)
        
        Returns:
            List of nearby merchants with location data
        """
        try:
            payload = {
                "merchantCity": city,
                "merchantState": state,
                "merchantCountryCode": country_code
            }
            
            if distance:
                payload["distance"] = distance
            
            payload["distanceUnit"] = distance_unit
            
            logger.info(f"Finding nearby merchants in {city}, {state}")
            
            response = await self._make_request(
                MerchantSearchEndpoint.MERCHANT_LOCATOR,
                payload
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error finding nearby merchants: {e}")
            return {
                "success": False,
                "error": str(e),
                "location": f"{city}, {state}"
            }
    
    async def _make_request(
        self,
        endpoint: MerchantSearchEndpoint,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Visa Merchant Search API.
        
        Args:
            endpoint: Target API endpoint
            payload: Request payload
        
        Returns:
            API response
        """
        try:
            url = f"{self.base_url}/{endpoint.value}"
            
            logger.debug(f"Request to {url}: {json.dumps(payload, default=str)}")
            
            async with httpx.AsyncClient(verify=self.ssl_context) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=30.0
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"Merchant search successful. Status: {response.status_code}")
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json() if response.text else {}
                }
            
            else:
                logger.error(
                    f"Merchant search failed. Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        
        except Exception as e:
            logger.error(f"Exception during merchant search request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def parse_merchant_response(
        self,
        response: Dict[str, Any],
        endpoint_type: MerchantSearchEndpoint
    ) -> Dict[str, Any]:
        """
        Parse and normalize merchant search response.
        
        Extracts key fields from API response and provides
        normalized structure regardless of endpoint used.
        
        Args:
            response: API response
            endpoint_type: Type of search performed
        
        Returns:
            Normalized merchant profile(s)
        """
        if not response.get("success"):
            return {"error": response.get("error", "Unknown error")}
        
        data = response.get("data", {})
        
        # Normalize based on endpoint type
        if endpoint_type == MerchantSearchEndpoint.TRANSACTION_SEARCH:
            return self._parse_transaction_search(data)
        
        elif endpoint_type == MerchantSearchEndpoint.GENERAL_SEARCH_V2:
            return self._parse_general_search(data)
        
        elif endpoint_type == MerchantSearchEndpoint.MERCHANT_LOOKUP:
            return self._parse_visa_lookup(data)
        
        elif endpoint_type == MerchantSearchEndpoint.MERCHANT_LOCATOR:
            return self._parse_locator(data)
        
        return data
    
    def _parse_transaction_search(self, data: Dict) -> Dict[str, Any]:
        """Parse transaction search response."""
        return {
            "endpoint": "transaction_search",
            "merchants": data.get("merchants", []),
            "suggested_merchant": {
                "name": data.get("merchantName"),
                "city": data.get("merchantCity"),
                "state": data.get("merchantState"),
                "country": data.get("merchantCountryCode")
            }
        }
    
    def _parse_general_search(self, data: Dict) -> Dict[str, Any]:
        """Parse v2 general search response."""
        merchants = data.get("merchants", [])
        
        return {
            "endpoint": "general_search_v2",
            "total_results": len(merchants),
            "merchants": [
                {
                    "name": m.get("merchantName"),
                    "category": m.get("merchantCategory"),
                    "city": m.get("merchantCity"),
                    "state": m.get("merchantState"),
                    "country": m.get("merchantCountryCode"),
                    "confidence_score": m.get("confidenceScore"),
                    "match_score": m.get("matchScore"),
                    "logo_url": m.get("merchantLogoUrl"),
                    "category_icon_url": m.get("categoryIconUrl"),
                    "mcc": m.get("merchantCategoryCode")
                }
                for m in merchants
            ]
        }
    
    def _parse_visa_lookup(self, data: Dict) -> Dict[str, Any]:
        """Parse Visa network lookup response."""
        return {
            "endpoint": "visa_network_lookup",
            "transaction_id": data.get("transactionId"),
            "merchant": {
                "name": data.get("merchantName"),
                "category": data.get("merchantCategory"),
                "mcc": data.get("merchantCategoryCode"),
                "clearing_data": data.get("clearingData")
            }
        }
    
    def _parse_locator(self, data: Dict) -> Dict[str, Any]:
        """Parse location-based merchant locator response."""
        merchants = data.get("merchants", [])
        
        return {
            "endpoint": "merchant_locator",
            "search_location": {
                "city": data.get("merchantCity"),
                "state": data.get("merchantState"),
                "country": data.get("merchantCountryCode")
            },
            "results_count": len(merchants),
            "merchants": [
                {
                    "name": m.get("merchantName"),
                    "category": m.get("merchantCategory"),
                    "address": m.get("address"),
                    "city": m.get("city"),
                    "state": m.get("state"),
                    "postal_code": m.get("postalCode"),
                    "latitude": m.get("latitude"),
                    "longitude": m.get("longitude"),
                    "distance": m.get("distance"),
                    "phone": m.get("phoneNumber")
                }
                for m in merchants
            ]
        }


# Singleton instance
_merchant_search_client: Optional[VisaMerchantSearchClient] = None


def get_visa_merchant_search_client() -> VisaMerchantSearchClient:
    """Get or create singleton Visa Merchant Search client."""
    global _merchant_search_client
    if _merchant_search_client is None:
        _merchant_search_client = VisaMerchantSearchClient(sandbox=True)
    return _merchant_search_client

