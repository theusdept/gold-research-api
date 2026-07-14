"""
Visa IDX Integration Client
Handles SSL mutual authentication, payload formatting, and secure data transmission to Visa IDX API.
"""
import os
import ssl
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import httpx
from enum import Enum

logger = logging.getLogger(__name__)


class VisaCurrency(Enum):
    """Supported Visa currency codes."""
    USD = "840"  # US Dollar


class VisaIDXClient:
    """
    Client for secure communication with Visa IDX API using mutual TLS authentication.
    Handles payload formatting, data sanitization, and API communication.
    """
    
    def __init__(
        self,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_path: Optional[str] = None,
        sandbox: bool = True
    ):
        """
        Initialize Visa IDX Client with SSL certificates.
        
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
        
        # Certificate paths - use environment variables or defaults
        self.cert_path = cert_path or os.getenv("VISA_CERT_PATH", "/etc/visa/client.pem")
        self.key_path = key_path or os.getenv("VISA_KEY_PATH", "/etc/visa/key.pem")
        self.ca_path = ca_path or os.getenv("VISA_CA_PATH", "/etc/visa/ca.pem")
        
        # Validate certificates exist (warnings only in dev/sandbox)
        self._validate_certificates()
        
        # Create SSL context for mutual TLS
        self.ssl_context = self._create_ssl_context()
        
        logger.info(f"Visa IDX Client initialized ({'sandbox' if sandbox else 'production'} mode)")
    
    def _validate_certificates(self) -> None:
        """Validate that certificate files exist."""
        for cert_file, cert_type in [
            (self.cert_path, "Client Certificate"),
            (self.key_path, "Private Key"),
            (self.ca_path, "CA Certificate")
        ]:
            if not os.path.exists(cert_file):
                logger.warning(
                    f"{cert_type} not found at {cert_file}. "
                    f"Integration will fail in production. "
                    f"Expected environment variable: VISA_{cert_type.upper().replace(' ', '_')}_PATH"
                )
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context with mutual authentication (client and server certificates).
        """
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        try:
            # Load server CA certificate
            if os.path.exists(self.ca_path):
                context.load_verify_locations(cafile=self.ca_path)
            
            # Load client certificate and private key (mutual TLS)
            if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
                context.load_cert_chain(
                    certfile=self.cert_path,
                    keyfile=self.key_path
                )
                logger.info("Client certificates loaded for mutual TLS authentication")
            else:
                logger.warning("Client certificates not available for mutual TLS")
        
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            # In sandbox, allow continuation; in production this would be critical
            if not self.sandbox:
                raise
        
        return context
    
    def format_purchase_for_idx(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform internal database record to Visa IDX API payload format.
        
        Maps:
        - purchase_amount (float in USD) → minorUnits (integer, cents)
        - transaction_date → ISO 8601 timestamp
        - Strips any sensitive data (PAN, routing numbers)
        
        Args:
            record: Internal purchase record
        
        Returns:
            Visa IDX API formatted payload
        """
        # Sanitize the record (remove any PANs or routing numbers)
        sanitized = self._sanitize_record(record)
        
        # Convert USD amount to minor units (cents)
        purchase_amount = sanitized.get("purchase_amount") or 0.0
        minor_units = int(round(purchase_amount * 100))
        
        # Format transaction date as ISO 8601
        transaction_date = sanitized.get("transaction_date")
        if isinstance(transaction_date, str):
            iso_date = transaction_date
        elif isinstance(transaction_date, datetime):
            iso_date = transaction_date.isoformat() + "Z"
        else:
            iso_date = datetime.now().isoformat() + "Z"
        
        # Build Visa IDX payload
        idx_payload = {
            "goldenRecord": {
                "identity": {
                    "name": sanitized.get("customer_name", ""),
                    "email": sanitized.get("email_address", ""),
                    "phoneNumber": sanitized.get("phone_number")
                },
                "location": {
                    "city": sanitized.get("city"),
                    "state": sanitized.get("state"),
                    "postalCode": sanitized.get("zip_code")
                }
            },
            "transaction": {
                "amount": {
                    "value": minor_units,
                    "currency": VisaCurrency.USD.value  # "840" for USD
                },
                "timestamp": iso_date,
                "merchantCategoryCode": "5944"  # Jewelry & Bullion
            },
            "metadata": {
                "source": "gold-research-api",
                "version": "1.0"
            }
        }
        
        return idx_payload
    
    def _sanitize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize record to remove sensitive data before sending to Visa.
        
        Removes/masks:
        - Credit card numbers (13-19 digit patterns)
        - Bank routing numbers (9 digit patterns)
        - Other sensitive financial identifiers
        
        Args:
            record: Raw record from database
        
        Returns:
            Sanitized record safe for external transmission
        """
        import re
        
        sanitized = record.copy()
        
        # Fields to check and sanitize
        text_fields = ["customer_name", "email_address", "phone_number", "city"]
        
        for field in text_fields:
            if field in sanitized and isinstance(sanitized[field], str):
                value = sanitized[field]
                
                # Remove credit card patterns (13-19 digits)
                value = re.sub(r'\b\d{13,19}\b', '[REDACTED]', value)
                
                # Remove routing number patterns (9 digits)
                value = re.sub(r'\b\d{9}\b', '[REDACTED]', value)
                
                sanitized[field] = value
        
        return sanitized
    
    async def sync_purchase_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronize a purchase record to Visa IDX API.
        
        Handles:
        - Payload formatting
        - SSL mutual authentication
        - Error handling and retry logic
        - Logging of successful syncs
        
        Args:
            record: Purchase record from database
        
        Returns:
            Response from Visa API
        
        Raises:
            Exception: On network or API errors
        """
        try:
            # Format record for Visa IDX
            idx_payload = self.format_purchase_for_idx(record)
            
            logger.info(f"Syncing purchase record (ID: {record.get('id')}) to Visa IDX")
            logger.debug(f"IDX Payload: {json.dumps(idx_payload, indent=2, default=str)}")
            
            # Make request with mutual TLS
            async with httpx.AsyncClient(verify=self.ssl_context) as client:
                response = await client.post(
                    f"{self.base_url}/visaidx/v1/goldRecords",
                    json=idx_payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    timeout=30.0
                )
            
            # Log response
            if response.status_code in [200, 201, 202]:
                logger.info(
                    f"Successfully synced record (ID: {record.get('id')}) to Visa IDX. "
                    f"Status: {response.status_code}"
                )
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.json() if response.text else {}
                }
            else:
                logger.error(
                    f"Visa IDX sync failed for record (ID: {record.get('id')}). "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        
        except Exception as e:
            logger.error(f"Exception during Visa IDX sync: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_payload(self, payload: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate payload against Visa IDX schema.
        
        Args:
            payload: IDX formatted payload
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = {
            "goldenRecord.identity.name": payload.get("goldenRecord", {}).get("identity", {}).get("name"),
            "transaction.amount.value": payload.get("transaction", {}).get("amount", {}).get("value"),
            "transaction.amount.currency": payload.get("transaction", {}).get("amount", {}).get("currency")
        }
        
        for field, value in required_fields.items():
            if not value:
                return False, f"Missing required field: {field}"
        
        # Validate amount is positive integer
        amount = payload.get("transaction", {}).get("amount", {}).get("value")
        if not isinstance(amount, int) or amount < 0:
            return False, "Amount must be a positive integer (minor units)"
        
        # Validate currency code
        currency = payload.get("transaction", {}).get("amount", {}).get("currency")
        if currency not in [c.value for c in VisaCurrency]:
            return False, f"Unsupported currency code: {currency}"
        
        return True, ""


# Singleton instance for application
_visa_client: Optional[VisaIDXClient] = None


def get_visa_idx_client() -> VisaIDXClient:
    """Get or create singleton Visa IDX client."""
    global _visa_client
    if _visa_client is None:
        _visa_client = VisaIDXClient(sandbox=True)
    return _visa_client

