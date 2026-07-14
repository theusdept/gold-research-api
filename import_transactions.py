"""
Gold Research API - Manual Transaction Import Script

Usage:
    python import_transactions.py --source data.csv --format csv
    python import_transactions.py --source transactions.json --format json
    python import_transactions.py --source postgres --db-host localhost --db-name source_db

Features:
    - Validates data before import
    - Sanitizes sensitive information
    - Detects and skips duplicates
    - Logs all operations with audit trail
    - Easy rollback if needed
    - Detailed reporting
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


class TransactionImporter:
    """Handles transaction import with validation, sanitization, and audit logging."""
    
    def __init__(self, db_host: str, db_port: int, db_user: str, db_password: str, db_name: str):
        """Initialize database connection."""
        self.db_params = {
            "host": db_host,
            "port": db_port,
            "user": db_user,
            "password": db_password,
            "database": db_name
        }
        self.stats = {
            "total_rows": 0,
            "valid_rows": 0,
            "duplicates_skipped": 0,
            "validation_errors": 0,
            "import_errors": 0,
            "successful_inserts": 0
        }
        self.errors: List[Dict[str, Any]] = []
        self.inserted_ids: List[int] = []
    
    def connect(self) -> psycopg2.extensions.connection:
        """Create database connection."""
        try:
            conn = psycopg2.connect(**self.db_params)
            logger.info("✓ Connected to database")
            return conn
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            sys.exit(1)
    
    def validate_row(self, row: Dict[str, Any], row_number: int) -> Tuple[bool, Optional[str]]:
        """
        Validate a transaction row.
        
        Returns: (is_valid, error_message)
        """
        # Check required fields
        required_fields = ['customer_name', 'email_address', 'purchase_amount']
        for field in required_fields:
            if field not in row or not row[field]:
                return False, f"Missing required field: {field}"
        
        # Validate customer name (non-empty string)
        if not str(row['customer_name']).strip():
            return False, "customer_name cannot be empty"
        
        # Validate email format
        email = str(row['email_address']).strip().lower()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, f"Invalid email format: {email}"
        
        # Validate purchase_amount (positive number)
        try:
            amount = float(row['purchase_amount'])
            if amount <= 0:
                return False, "purchase_amount must be positive"
        except (ValueError, TypeError):
            return False, f"Invalid purchase_amount: {row['purchase_amount']}"
        
        # Validate state (2-letter code if provided)
        if 'state' in row and row['state']:
            state = str(row['state']).strip().upper()
            if len(state) != 2 or not state.isalpha():
                return False, f"Invalid state code: {state}"
        
        # Validate transaction_date format if provided
        if 'transaction_date' in row and row['transaction_date']:
            try:
                date_str = str(row['transaction_date']).strip()
                # Try common formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%m/%d/%Y %H:%M:%S']:
                    try:
                        datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return False, f"Invalid date format: {date_str} (try YYYY-MM-DD or MM/DD/YYYY)"
            except Exception as e:
                return False, f"Date parsing error: {e}"
        
        return True, None
    
    def sanitize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize row by removing sensitive data (PANs, routing numbers, etc).
        
        Returns: Sanitized row
        """
        sanitized = {}
        
        for key, value in row.items():
            if value is None:
                sanitized[key] = None
            elif isinstance(value, str):
                # Strip whitespace
                value = value.strip()
                
                # Remove credit card numbers (13-19 digits)
                value = re.sub(r'\b\d{13,19}\b', '', value)
                
                # Remove routing numbers (9 digits)
                value = re.sub(r'\b\d{9}\b', '', value)
                
                # Clean up multiple spaces
                value = re.sub(r'\s+', ' ', value)
                
                sanitized[key] = value if value else None
            else:
                sanitized[key] = value
        
        return sanitized
    
    def check_duplicate(self, conn, row: Dict[str, Any]) -> bool:
        """
        Check if transaction already exists (by email + date + amount).
        
        Returns: True if duplicate exists
        """
        cursor = conn.cursor()
        
        email = row['email_address'].lower()
        amount = float(row['purchase_amount'])
        
        # Try to match by email + amount + date (if date provided)
        if 'transaction_date' in row and row['transaction_date']:
            try:
                date_str = str(row['transaction_date']).strip()
                # Parse date
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%m/%d/%Y %H:%M:%S']:
                    try:
                        tx_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                cursor.execute("""
                    SELECT id FROM gold_purchases
                    WHERE LOWER(email_address) = %s
                      AND purchase_amount = %s
                      AND DATE(transaction_date) = %s
                    LIMIT 1
                """, (email, amount, tx_date.date()))
            except Exception as e:
                logger.debug(f"Date parsing in duplicate check failed: {e}")
                # Fall back to email + amount only
                cursor.execute("""
                    SELECT id FROM gold_purchases
                    WHERE LOWER(email_address) = %s
                      AND purchase_amount = %s
                    LIMIT 1
                """, (email, amount))
        else:
            # Match by email + amount only
            cursor.execute("""
                SELECT id FROM gold_purchases
                WHERE LOWER(email_address) = %s
                  AND purchase_amount = %s
                LIMIT 1
            """, (email, amount))
        
        return cursor.fetchone() is not None
    
    def import_row(self, conn, row: Dict[str, Any], row_number: int) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Import a single row.
        
        Returns: (success, inserted_id, error_message)
        """
        # Validate
        is_valid, error_msg = self.validate_row(row, row_number)
        if not is_valid:
            self.stats['validation_errors'] += 1
            self.errors.append({
                'row': row_number,
                'email': row.get('email_address', 'N/A'),
                'error': error_msg
            })
            return False, None, error_msg
        
        # Sanitize
        row = self.sanitize_row(row)
        
        # Check for duplicate
        if self.check_duplicate(conn, row):
            self.stats['duplicates_skipped'] += 1
            return False, None, "Duplicate record (skipped)"
        
        # Insert
        try:
            cursor = conn.cursor()
            
            # Prepare values
            customer_name = row['customer_name']
            email = row['email_address'].lower()
            phone = row.get('phone_number')
            city = row.get('city')
            state = row.get('state', '').upper() if row.get('state') else None
            zip_code = row.get('zip_code')
            amount = float(row['purchase_amount'])
            
            # Parse transaction date
            tx_date = None
            if 'transaction_date' in row and row['transaction_date']:
                try:
                    date_str = str(row['transaction_date']).strip()
                    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%m/%d/%Y %H:%M:%S']:
                        try:
                            tx_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Failed to parse date for row {row_number}: {e}, using current time")
                    tx_date = datetime.now()
            else:
                tx_date = datetime.now()
            
            cursor.execute("""
                INSERT INTO gold_purchases
                (customer_name, email_address, phone_number, city, state, zip_code, purchase_amount, transaction_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (customer_name, email, phone, city, state, zip_code, amount, tx_date))
            
            inserted_id = cursor.fetchone()[0]
            conn.commit()
            
            self.stats['successful_inserts'] += 1
            self.inserted_ids.append(inserted_id)
            
            return True, inserted_id, None
        
        except psycopg2.Error as e:
            conn.rollback()
            self.stats['import_errors'] += 1
            self.errors.append({
                'row': row_number,
                'email': row.get('email_address', 'N/A'),
                'error': str(e)
            })
            return False, None, str(e)
    
    def import_from_csv(self, filename: str, preview: bool = False) -> int:
        """Import transactions from CSV file."""
        logger.info(f"Reading CSV file: {filename}")
        
        if not os.path.exists(filename):
            logger.error(f"✗ File not found: {filename}")
            return 0
        
        rows_to_import = []
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_number, row in enumerate(reader, start=2):  # Start at 2 (skip header)
                    # Convert empty strings to None
                    row = {k: v if v else None for k, v in row.items()}
                    rows_to_import.append((row_number, row))
                    self.stats['total_rows'] += 1
        
        except Exception as e:
            logger.error(f"✗ Failed to read CSV: {e}")
            return 0
        
        logger.info(f"✓ Loaded {len(rows_to_import)} rows from CSV")
        
        # Preview mode: just show what would be imported
        if preview:
            logger.info("\n=== PREVIEW MODE ===")
            logger.info(f"Would import {len(rows_to_import)} rows")
            if rows_to_import:
                logger.info("\nFirst row example:")
                logger.info(json.dumps(rows_to_import[0][1], indent=2, default=str))
            return 0
        
        # Import rows
        return self._import_rows(rows_to_import)
    
    def import_from_json(self, filename: str, preview: bool = False) -> int:
        """Import transactions from JSON file."""
        logger.info(f"Reading JSON file: {filename}")
        
        if not os.path.exists(filename):
            logger.error(f"✗ File not found: {filename}")
            return 0
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"✗ Failed to read JSON: {e}")
            return 0
        
        # Handle both array and object with 'transactions' key
        if isinstance(data, list):
            rows_data = data
        elif isinstance(data, dict) and 'transactions' in data:
            rows_data = data['transactions']
        else:
            logger.error("✗ JSON must be array of objects or {transactions: [...]}")
            return 0
        
        rows_to_import = [(i + 2, row) for i, row in enumerate(rows_data)]
        self.stats['total_rows'] = len(rows_to_import)
        
        logger.info(f"✓ Loaded {len(rows_to_import)} rows from JSON")
        
        # Preview mode
        if preview:
            logger.info("\n=== PREVIEW MODE ===")
            logger.info(f"Would import {len(rows_to_import)} rows")
            if rows_to_import:
                logger.info("\nFirst row example:")
                logger.info(json.dumps(rows_to_import[0][1], indent=2, default=str))
            return 0
        
        # Import rows
        return self._import_rows(rows_to_import)
    
    def import_from_postgres(self, source_host: str, source_port: int, source_user: str, 
                            source_password: str, source_db: str, query: str, preview: bool = False) -> int:
        """Import transactions from another PostgreSQL database."""
        logger.info(f"Connecting to source database: {source_host}:{source_port}/{source_db}")
        
        try:
            source_conn = psycopg2.connect(
                host=source_host,
                port=source_port,
                user=source_user,
                password=source_password,
                database=source_db
            )
            cursor = source_conn.cursor(cursor_factory=RealDictCursor)
            
            # If no query provided, use default
            if not query:
                query = """
                    SELECT 
                        customer_name,
                        email_address,
                        phone_number,
                        city,
                        state,
                        zip_code,
                        purchase_amount,
                        transaction_date
                    FROM gold_purchases
                    WHERE transaction_date >= NOW() - INTERVAL '90 days'
                """
            
            logger.info(f"Executing query...")
            cursor.execute(query)
            
            rows_data = cursor.fetchall()
            source_conn.close()
            
            rows_to_import = [(i + 1, dict(row)) for i, row in enumerate(rows_data)]
            self.stats['total_rows'] = len(rows_to_import)
            
            logger.info(f"✓ Loaded {len(rows_to_import)} rows from source database")
            
            # Preview mode
            if preview:
                logger.info("\n=== PREVIEW MODE ===")
                logger.info(f"Would import {len(rows_to_import)} rows")
                if rows_to_import:
                    logger.info("\nFirst row example:")
                    logger.info(json.dumps(rows_to_import[0][1], indent=2, default=str))
                return 0
            
            # Import rows
            return self._import_rows(rows_to_import)
        
        except Exception as e:
            logger.error(f"✗ Failed to import from source database: {e}")
            return 0
    
    def _import_rows(self, rows_to_import: List[Tuple[int, Dict]]) -> int:
        """Internal method to import a list of rows."""
        conn = self.connect()
        
        try:
            for row_number, row in rows_to_import:
                success, inserted_id, error = self.import_row(conn, row, row_number)
                
                if success:
                    if row_number % 10 == 0:
                        logger.info(f"  Imported {row_number} rows...")
            
            return self.stats['successful_inserts']
        
        finally:
            conn.close()
    
    def report(self) -> str:
        """Generate import report."""
        report = f"""
{'='*60}
IMPORT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

STATISTICS:
  Total rows processed:     {self.stats['total_rows']}
  Successfully imported:    {self.stats['successful_inserts']} ✓
  Duplicates skipped:       {self.stats['duplicates_skipped']} ⊘
  Validation errors:        {self.stats['validation_errors']} ✗
  Import errors:            {self.stats['import_errors']} ✗

INSERTED RECORD IDs:
  {', '.join(map(str, self.inserted_ids)) if self.inserted_ids else 'None'}

{'='*60}
"""
        
        if self.errors:
            report += f"\nERROR DETAILS:\n"
            for error in self.errors[:10]:  # Show first 10 errors
                report += f"\n  Row {error['row']} ({error['email']}):\n    → {error['error']}\n"
            
            if len(self.errors) > 10:
                report += f"\n  ... and {len(self.errors) - 10} more errors\n"
        
        report += f"\n{'='*60}\n"
        
        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Import transactions into Gold Research API database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CSV import
  python import_transactions.py --source data.csv --format csv
  
  # Preview before importing
  python import_transactions.py --source data.csv --format csv --preview
  
  # JSON import
  python import_transactions.py --source transactions.json --format json
  
  # Import from another PostgreSQL database
  python import_transactions.py --format postgres \\
    --source-host source.db.server \\
    --source-user postgres \\
    --source-password secret \\
    --source-db transactions_db
        """
    )
    
    # Database arguments
    parser.add_argument('--db-host', default='localhost', help='Target database host')
    parser.add_argument('--db-port', type=int, default=5432, help='Target database port')
    parser.add_argument('--db-user', default='postgres', help='Target database user')
    parser.add_argument('--db-password', default='', help='Target database password')
    parser.add_argument('--db-name', default='gold_research', help='Target database name')
    
    # Source arguments
    parser.add_argument('--source', help='Source file (CSV/JSON) or empty for environment config')
    parser.add_argument('--format', choices=['csv', 'json', 'postgres'], required=True, help='Source format')
    parser.add_argument('--preview', action='store_true', help='Preview import without actually importing')
    
    # PostgreSQL source arguments
    parser.add_argument('--source-host', help='Source PostgreSQL host')
    parser.add_argument('--source-port', type=int, default=5432, help='Source PostgreSQL port')
    parser.add_argument('--source-user', help='Source PostgreSQL user')
    parser.add_argument('--source-password', help='Source PostgreSQL password')
    parser.add_argument('--source-db', help='Source PostgreSQL database')
    parser.add_argument('--source-query', help='Custom SQL query for PostgreSQL import')
    
    args = parser.parse_args()
    
    # Use environment variables as defaults
    if not args.db_password:
        args.db_password = os.getenv('PGPASSWORD', '')
    if not args.db_host:
        args.db_host = os.getenv('PGHOST', 'localhost')
    if not args.db_user:
        args.db_user = os.getenv('PGUSER', 'postgres')
    if not args.db_name:
        args.db_name = os.getenv('PGDATABASE', 'gold_research')
    
    if args.format == 'postgres':
        if not args.source_host:
            args.source_host = os.getenv('SOURCE_PGHOST')
        if not args.source_user:
            args.source_user = os.getenv('SOURCE_PGUSER')
        if not args.source_password:
            args.source_password = os.getenv('SOURCE_PGPASSWORD')
        if not args.source_db:
            args.source_db = os.getenv('SOURCE_PGDATABASE')
    
    # Initialize importer
    importer = TransactionImporter(
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_password=args.db_password,
        db_name=args.db_name
    )
    
    # Import based on format
    logger.info(f"🚀 Starting transaction import ({args.format} format)")
    
    if args.format == 'csv':
        if not args.source:
            logger.error("✗ --source argument required for CSV format")
            sys.exit(1)
        importer.import_from_csv(args.source, preview=args.preview)
    
    elif args.format == 'json':
        if not args.source:
            logger.error("✗ --source argument required for JSON format")
            sys.exit(1)
        importer.import_from_json(args.source, preview=args.preview)
    
    elif args.format == 'postgres':
        if not all([args.source_host, args.source_user, args.source_password, args.source_db]):
            logger.error("✗ Missing PostgreSQL source credentials")
            sys.exit(1)
        importer.import_from_postgres(
            args.source_host,
            args.source_port,
            args.source_user,
            args.source_password,
            args.source_db,
            args.source_query,
            preview=args.preview
        )
    
    # Print report
    report = importer.report()
    print(report)
    logger.info(report)
    
    # Exit with appropriate code
    if importer.stats['successful_inserts'] > 0:
        logger.info(f"✓ Import completed successfully!")
        sys.exit(0)
    else:
        logger.error(f"✗ No records were imported")
        sys.exit(1)


if __name__ == '__main__':
    main()

