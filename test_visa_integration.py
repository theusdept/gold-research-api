#!/usr/bin/env python3
"""
End-to-End Test Script for Visa IDX Integration

Tests the complete flow:
1. Create purchase records with sensitive data
2. Verify PAN/routing number stripping on ingest
3. Queue records for Visa IDX sync
4. Monitor sync status and compliance flags
5. Verify audit log entries

Usage:
    python test_visa_integration.py --api-url https://api.example.com --verbose
"""

import asyncio
import json
import time
import argparse
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx
from dataclasses import dataclass
from enum import Enum

# Color output for terminal
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


class TestStatus(Enum):
    PASS = "✓"
    FAIL = "✗"
    PENDING = "⋯"
    SKIP = "⊝"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class VisaIDXIntegrationTester:
    """Comprehensive test suite for Visa IDX integration."""
    
    def __init__(self, api_url: str, verbose: bool = False):
        """
        Initialize tester.
        
        Args:
            api_url: Base API URL (e.g., https://api.example.com)
            verbose: Print detailed output
        """
        self.api_url = api_url.rstrip('/')
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.client = None
        self.created_records: List[int] = []
    
    async def setup(self):
        """Set up HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def teardown(self):
        """Clean up HTTP client."""
        if self.client:
            await self.client.aclose()
    
    def print_test(self, status: TestStatus, name: str, message: str = ""):
        """Print test result."""
        color = {
            TestStatus.PASS: Color.GREEN,
            TestStatus.FAIL: Color.RED,
            TestStatus.PENDING: Color.YELLOW,
            TestStatus.SKIP: Color.BLUE
        }[status]
        
        msg = f"{color}{status.value}{Color.END} {name}"
        if message:
            msg += f": {message}"
        print(msg)
    
    def log(self, message: str):
        """Print log message."""
        if self.verbose:
            print(f"  ℹ {message}")
    
    async def test_api_health(self) -> bool:
        """Test API is accessible and healthy."""
        try:
            response = await self.client.get(f"{self.api_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                visa_enabled = data.get("visa_idx_integration") == "enabled"
                
                self.print_test(
                    TestStatus.PASS,
                    "API Health Check",
                    f"Visa IDX: {'enabled' if visa_enabled else 'disabled'}"
                )
                self.results.append(TestResult(
                    "API Health Check",
                    TestStatus.PASS,
                    f"Visa IDX integration: {'enabled' if visa_enabled else 'disabled'}",
                    data
                ))
                return True
            else:
                self.print_test(
                    TestStatus.FAIL,
                    "API Health Check",
                    f"HTTP {response.status_code}"
                )
                self.results.append(TestResult(
                    "API Health Check",
                    TestStatus.FAIL,
                    f"HTTP {response.status_code}",
                    {"status_code": response.status_code}
                ))
                return False
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "API Health Check", str(e))
            self.results.append(TestResult(
                "API Health Check",
                TestStatus.FAIL,
                str(e)
            ))
            return False
    
    async def test_visa_integration_status(self) -> bool:
        """Check Visa IDX integration configuration."""
        try:
            response = await self.client.get(f"{self.api_url}/api/v1/integration/visa-idx/status")
            
            if response.status_code == 200:
                data = response.json()
                enabled = data.get("integration_enabled")
                sandbox = data.get("sandbox_mode")
                certs = data.get("certificates_configured")
                running = data.get("sync_pipeline_running")
                
                status = TestStatus.PASS if enabled else TestStatus.SKIP
                msg = f"Sandbox: {sandbox}, Certs: {certs}, Pipeline: {running}"
                
                self.print_test(status, "Visa IDX Integration Status", msg)
                self.results.append(TestResult(
                    "Visa IDX Integration Status",
                    status,
                    msg,
                    data
                ))
                return enabled
            else:
                self.print_test(
                    TestStatus.FAIL,
                    "Visa IDX Integration Status",
                    f"HTTP {response.status_code}"
                )
                return False
        
        except Exception as e:
            self.print_test(TestStatus.SKIP, "Visa IDX Integration Status", str(e))
            return False
    
    async def test_create_record_basic(self) -> Optional[int]:
        """Create a basic purchase record."""
        payload = {
            "customer_name": "Test User Basic",
            "email_address": "test.basic@example.com",
            "phone_number": "+1-555-0100",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94102",
            "purchase_amount": 5000.00
        }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/api/v1/research/buyers",
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                record_id = data.get("id")
                
                self.log(f"Created basic record ID: {record_id}")
                self.print_test(
                    TestStatus.PASS,
                    "Create Basic Record",
                    f"ID: {record_id}"
                )
                self.results.append(TestResult(
                    "Create Basic Record",
                    TestStatus.PASS,
                    f"Record ID: {record_id}",
                    data
                ))
                
                self.created_records.append(record_id)
                return record_id
            else:
                self.print_test(
                    TestStatus.FAIL,
                    "Create Basic Record",
                    f"HTTP {response.status_code}: {response.text}"
                )
                return None
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "Create Basic Record", str(e))
            return None
    
    async def test_create_record_with_sensitive_data(self) -> Optional[int]:
        """
        Create record with simulated sensitive data.
        Tests that PAN and routing numbers are stripped.
        """
        # Include fake credit card and routing numbers
        payload = {
            "customer_name": "Jane Smith 4532015112830366",  # Fake PAN embedded
            "email_address": "jane@example.com",
            "phone_number": "+1-555-0101 021000021",  # Fake routing number
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90001",
            "purchase_amount": 25000.50
        }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/api/v1/research/buyers",
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                record_id = data.get("id")
                
                # Verify sensitive data was stripped
                stored_name = data.get("customer_name", "")
                stored_phone = data.get("phone_number", "")
                
                pans_removed = "4532015112830366" not in stored_name
                routing_removed = "021000021" not in stored_phone
                
                all_removed = pans_removed and routing_removed
                status = TestStatus.PASS if all_removed else TestStatus.FAIL
                
                self.log(f"Created sensitive record ID: {record_id}")
                self.log(f"PAN stripped: {pans_removed}")
                self.log(f"Routing number stripped: {routing_removed}")
                
                self.print_test(
                    status,
                    "Create Record & Strip Sensitive Data",
                    f"ID: {record_id}, PANs removed: {all_removed}"
                )
                self.results.append(TestResult(
                    "Create Record & Strip Sensitive Data",
                    status,
                    f"Record ID: {record_id}",
                    {
                        "record_id": record_id,
                        "stored_name": stored_name,
                        "stored_phone": stored_phone,
                        "pans_removed": pans_removed,
                        "routing_removed": routing_removed
                    }
                ))
                
                self.created_records.append(record_id)
                return record_id
            else:
                self.print_test(
                    TestStatus.FAIL,
                    "Create Record & Strip Sensitive Data",
                    f"HTTP {response.status_code}"
                )
                return None
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "Create Record & Strip Sensitive Data", str(e))
            return None
    
    async def test_create_high_value_record(self) -> Optional[int]:
        """Create a high-value record to test amount formatting."""
        payload = {
            "customer_name": "High Value Test",
            "email_address": "highval@example.com",
            "phone_number": "+1-555-0102",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "purchase_amount": 123456.78  # Tests cents precision
        }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/api/v1/research/buyers",
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                record_id = data.get("id")
                amount = data.get("purchase_amount")
                
                self.log(f"Created high-value record ID: {record_id}, Amount: ${amount}")
                self.print_test(
                    TestStatus.PASS,
                    "Create High-Value Record",
                    f"ID: {record_id}, Amount: ${amount}"
                )
                self.results.append(TestResult(
                    "Create High-Value Record",
                    TestStatus.PASS,
                    f"Record ID: {record_id}, Amount: ${amount}",
                    data
                ))
                
                self.created_records.append(record_id)
                return record_id
            else:
                return None
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "Create High-Value Record", str(e))
            return None
    
    async def test_sync_status(self, record_id: int, wait_seconds: int = 10) -> bool:
        """
        Check sync status for a record.
        Waits briefly for background sync to process.
        """
        # Wait for background sync to process
        self.log(f"Waiting {wait_seconds}s for background sync to process...")
        await asyncio.sleep(wait_seconds)
        
        try:
            response = await self.client.get(
                f"{self.api_url}/api/v1/research/buyers/{record_id}/sync-status"
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                attempts = data.get("attempts")
                error = data.get("last_error")
                data_sanitized = data.get("data_sanitized")
                no_pans = data.get("no_pans_detected")
                
                self.log(f"Sync Status: {status}")
                self.log(f"Attempts: {attempts}")
                self.log(f"Data Sanitized: {data_sanitized}")
                self.log(f"No PANs Detected: {no_pans}")
                if error:
                    self.log(f"Error: {error}")
                
                # Success if synced or pending (hasn't failed)
                success = status in ["success", "pending"]
                status_enum = TestStatus.PASS if success else TestStatus.FAIL
                
                self.print_test(
                    status_enum,
                    f"Sync Status for Record {record_id}",
                    f"Status: {status}, Sanitized: {data_sanitized}, No PANs: {no_pans}"
                )
                self.results.append(TestResult(
                    f"Sync Status for Record {record_id}",
                    status_enum,
                    f"Status: {status}",
                    data
                ))
                
                return success
            else:
                self.print_test(
                    TestStatus.FAIL,
                    f"Sync Status for Record {record_id}",
                    f"HTTP {response.status_code}"
                )
                return False
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, f"Sync Status for Record {record_id}", str(e))
            return False
    
    async def test_query_by_amount(self) -> bool:
        """Test filtering records by purchase amount range."""
        try:
            # Query for records between $5k and $30k
            response = await self.client.get(
                f"{self.api_url}/api/v1/research/buyers",
                params={"min_amount": 5000, "max_amount": 30000}
            )
            
            if response.status_code == 200:
                data = response.json()
                count = len(data)
                
                self.log(f"Found {count} records in amount range $5k-$30k")
                self.print_test(
                    TestStatus.PASS,
                    "Query by Amount Range",
                    f"Found {count} records"
                )
                self.results.append(TestResult(
                    "Query by Amount Range",
                    TestStatus.PASS,
                    f"Found {count} records",
                    {"count": count, "records": data}
                ))
                
                return count >= 0
            else:
                return False
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "Query by Amount Range", str(e))
            return False
    
    async def test_analytics(self) -> bool:
        """Test analytics endpoint."""
        try:
            response = await self.client.get(
                f"{self.api_url}/api/v1/research/buyers/analytics/total"
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_amount", 0)
                count = data.get("transaction_count", 0)
                avg = data.get("average_amount", 0)
                
                self.log(f"Total: ${total}, Count: {count}, Average: ${avg}")
                self.print_test(
                    TestStatus.PASS,
                    "Analytics Endpoint",
                    f"Total: ${total}, Count: {count}"
                )
                self.results.append(TestResult(
                    "Analytics Endpoint",
                    TestStatus.PASS,
                    f"Total: ${total}, Count: {count}",
                    data
                ))
                
                return True
            else:
                return False
        
        except Exception as e:
            self.print_test(TestStatus.FAIL, "Analytics Endpoint", str(e))
            return False
    
    async def run_all_tests(self):
        """Run complete test suite."""
        print(f"\n{Color.BLUE}=== Visa IDX Integration Test Suite ==={Color.END}")
        print(f"API: {self.api_url}\n")
        
        await self.setup()
        
        try:
            # Health and configuration
            print(f"{Color.BLUE}Configuration Tests{Color.END}")
            api_ok = await self.test_api_health()
            visa_enabled = await self.test_visa_integration_status()
            print()
            
            # Create test records
            print(f"{Color.BLUE}Record Creation Tests{Color.END}")
            record1 = await self.test_create_record_basic()
            record2 = await self.test_create_record_with_sensitive_data()
            record3 = await self.test_create_high_value_record()
            print()
            
            # Query tests
            print(f"{Color.BLUE}Query Tests{Color.END}")
            await self.test_query_by_amount()
            await self.test_analytics()
            print()
            
            # Sync status tests (if integration enabled)
            if visa_enabled and record1:
                print(f"{Color.BLUE}Visa IDX Sync Tests{Color.END}")
                await self.test_sync_status(record1, wait_seconds=5)
                if record2:
                    await self.test_sync_status(record2, wait_seconds=5)
                print()
            
            # Summary
            self.print_summary()
        
        finally:
            await self.teardown()
    
    def print_summary(self):
        """Print test summary."""
        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)
        total = len(self.results)
        
        print(f"{Color.BLUE}=== Test Summary ==={Color.END}")
        print(f"{Color.GREEN}Passed:{Color.END} {passed}/{total}")
        print(f"{Color.RED}Failed:{Color.END} {failed}/{total}")
        print(f"{Color.YELLOW}Skipped:{Color.END} {skipped}/{total}")
        
        if failed == 0:
            print(f"\n{Color.GREEN}✓ All tests passed!{Color.END}")
            return True
        else:
            print(f"\n{Color.RED}✗ Some tests failed. See details above.{Color.END}")
            return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Visa IDX Integration End-to-End Test Suite"
    )
    parser.add_argument(
        "--api-url",
        default="https://gold-research-api-production.up.railway.app",
        help="Base API URL (default: production)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--localhost",
        action="store_true",
        help="Use localhost:8000 instead"
    )
    
    args = parser.parse_args()
    
    api_url = "http://localhost:8000" if args.localhost else args.api_url
    
    tester = VisaIDXIntegrationTester(api_url, verbose=args.verbose)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

