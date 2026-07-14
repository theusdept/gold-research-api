# Transaction Import Guide

Complete guide for manually importing transaction data into the Gold Research API.

---

## **🚀 Quick Start**

### **Step 1: Prepare Your Data**

You can import from:
- **CSV file** - Flat transaction data
- **JSON file** - Structured transaction data
- **PostgreSQL database** - Direct database-to-database copy

### **Step 2: Run the Import Script**

```bash
# Preview CSV import (no data written)
python import_transactions.py --source data.csv --format csv --preview

# Actually import CSV
python import_transactions.py --source data.csv --format csv

# Import JSON
python import_transactions.py --source transactions.json --format json

# Import from another PostgreSQL database
python import_transactions.py --format postgres \
  --source-host source.db.example.com \
  --source-user postgres \
  --source-password secret \
  --source-db transactions
```

### **Step 3: Review the Report**

The script will print a detailed report showing:
- How many records were imported
- How many were duplicates
- Any validation errors
- The inserted record IDs

---

## **📋 Data Format**

### **CSV Format**

**Required columns:**
```
customer_name,email_address,purchase_amount,transaction_date
```

**Optional columns:**
```
phone_number,city,state,zip_code
```

**Example:**
```csv
customer_name,email_address,phone_number,city,state,zip_code,purchase_amount,transaction_date
John Smith,john@example.com,+1-555-0100,New York,NY,10001,25000.00,2026-04-15
Jane Doe,jane@example.com,+1-555-0101,Los Angeles,CA,90001,35500.50,2026-04-16
```

### **JSON Format**

**Structure:**
```json
{
  "transactions": [
    {
      "customer_name": "John Smith",
      "email_address": "john@example.com",
      "phone_number": "+1-555-0100",
      "city": "New York",
      "state": "NY",
      "zip_code": "10001",
      "purchase_amount": 25000.00,
      "transaction_date": "2026-04-15"
    }
  ]
}
```

### **PostgreSQL Format**

Query the source database:

```sql
SELECT 
  customer_name,
  email_address,
  phone_number,
  city,
  state,
  zip_code,
  purchase_amount,
  transaction_date
FROM transactions
WHERE transaction_date >= NOW() - INTERVAL '90 days'
```

---

## **🧪 Testing the Script**

### **Step 1: Preview Sample CSV Data**

```bash
cd /path/to/gold-research-api
python import_transactions.py --source sample_data.csv --format csv --preview
```

**Expected output:**
```
INFO - Reading CSV file: sample_data.csv
INFO - ✓ Loaded 15 rows from CSV

=== PREVIEW MODE ===
Would import 15 rows

First row example:
{
  "customer_name": "John Smith",
  "email_address": "john.smith@example.com",
  ...
}
```

### **Step 2: Test Actual Import (CSV)**

```bash
python import_transactions.py --source sample_data.csv --format csv
```

**Expected output:**
```
INFO - 🚀 Starting transaction import (csv format)
INFO - ✓ Connected to database
INFO - Reading CSV file: sample_data.csv
INFO - ✓ Loaded 15 rows from CSV
INFO - Imported 10 rows...

============================================================
IMPORT REPORT - 2026-07-14 15:30:45
============================================================

STATISTICS:
  Total rows processed:     15
  Successfully imported:    15 ✓
  Duplicates skipped:       0 ⊘
  Validation errors:        0 ✗
  Import errors:            0 ✗

INSERTED RECORD IDs:
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15

============================================================

✓ Import completed successfully!
```

### **Step 3: Test with JSON**

```bash
python import_transactions.py --source sample_data.json --format json --preview
```

### **Step 4: Verify in Database**

```bash
# Connect to your local database
psql -h localhost -U postgres -d gold_research

# Count imported records
SELECT COUNT(*) FROM gold_purchases;

# View imported data
SELECT id, customer_name, email_address, purchase_amount, transaction_date 
FROM gold_purchases 
ORDER BY id DESC 
LIMIT 10;

# Test enrichment with one record
SELECT id FROM gold_purchases ORDER BY id DESC LIMIT 1;
```

---

## **⚙️ Command Line Options**

### **Target Database Connection**

```bash
--db-host localhost          # Database host (default: localhost)
--db-port 5432             # Database port (default: 5432)
--db-user postgres         # Database user (default: postgres)
--db-password secret       # Database password (default: empty)
--db-name gold_research    # Database name (default: gold_research)
```

**Or use environment variables:**
```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=secret
export PGDATABASE=gold_research

python import_transactions.py --source data.csv --format csv
```

### **Source Options (CSV/JSON)**

```bash
--source data.csv          # Source file path (required)
--format csv              # csv, json, or postgres (required)
--preview                 # Preview without importing (optional)
```

### **Source Options (PostgreSQL)**

```bash
--format postgres                    # Required
--source-host source.db.example.com  # Source database host
--source-port 5432                   # Source database port (default: 5432)
--source-user postgres               # Source database user
--source-password secret             # Source database password
--source-db transactions             # Source database name
--source-query "SELECT ..."          # Optional: custom SQL query
```

**Or use environment variables:**
```bash
export SOURCE_PGHOST=source.db.example.com
export SOURCE_PGUSER=postgres
export SOURCE_PGPASSWORD=secret
export SOURCE_PGDATABASE=transactions

python import_transactions.py --format postgres
```

---

## **✅ Validation Rules**

The import script validates each row:

| Field | Required | Rules |
|-------|----------|-------|
| `customer_name` | ✓ | Non-empty string |
| `email_address` | ✓ | Valid email format |
| `purchase_amount` | ✓ | Positive number |
| `transaction_date` | ✗ | ISO 8601 or MM/DD/YYYY format |
| `state` | ✗ | 2-letter code (A-Z) |
| `phone_number` | ✗ | Any format (stripped of whitespace) |
| `city` | ✗ | Any text |
| `zip_code` | ✗ | Any format |

**Validation Errors:**
- Missing required fields → Skipped
- Invalid email format → Skipped
- Negative purchase amount → Skipped
- Invalid date format → Uses current timestamp, logs warning
- Invalid state code → Skipped

---

## **🛡️ Data Sanitization**

The script automatically sanitizes all data:

1. **Remove credit card numbers** (13-19 digit patterns)
2. **Remove routing numbers** (9 digit patterns)
3. **Strip whitespace** (leading/trailing)
4. **Normalize state codes** (convert to uppercase)
5. **Normalize emails** (convert to lowercase)

---

## **🔍 Duplicate Detection**

Records are considered duplicates if:
- Same email address
- Same purchase amount
- Same transaction date (if provided)

**Action:** Duplicate records are skipped with a warning.

---

## **📊 Import Report**

After import, the script generates a report showing:

```
STATISTICS:
  Total rows processed:     15
  Successfully imported:    15 ✓
  Duplicates skipped:       0 ⊘
  Validation errors:        0 ✗
  Import errors:            0 ✗

INSERTED RECORD IDs:
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15

ERROR DETAILS:
  Row 5 (invalid@example):
    → Invalid email format: invalid@example
```

**Log file:** `import_YYYYMMDD_HHMMSS.log`

---

## **🚨 Error Handling**

### **Connection Errors**

```
✗ Failed to connect to database: connection refused
```

**Fix:** Verify database is running and connection parameters are correct.

### **Validation Errors**

```
Row 3 (john@example.com):
  → Invalid email format: john@example
```

**Fix:** Fix the data in your source file and re-import.

### **Duplicate Detection**

```
Duplicates skipped: 2 ⊘
```

**Behavior:** Duplicates are silently skipped. No error is raised.

### **Parse Errors**

```
Row 5:
  → Invalid date format: 2026/13/45 (try YYYY-MM-DD or MM/DD/YYYY)
```

**Fix:** Format dates as YYYY-MM-DD or MM/DD/YYYY.

---

## **🔄 Rollback**

If you need to undo an import:

### **Option 1: Delete All Imported Records**

```sql
-- If you imported all at once, delete by date
DELETE FROM gold_purchases 
WHERE created_at >= NOW() - INTERVAL '1 hour';
```

### **Option 2: Delete Specific Records**

```sql
-- If you have the insert IDs from the report
DELETE FROM gold_purchases 
WHERE id IN (1, 2, 3, 4, 5);
```

### **Option 3: Restore from Backup**

```bash
# Railway manages backups automatically
# Contact support to restore
```

---

## **🔗 Testing the Enrichment**

Once you've imported records, test the enrichment:

```bash
# Get a purchase ID from the import (e.g., ID=1)

# Enrich with merchant search
curl -X POST "https://gold-research-api-production.up.railway.app/api/v1/merchants/enrich/directory-search?purchase_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_name": "Tiffany",
    "merchant_city": "New York",
    "merchant_state": "NY"
  }'

# Check enrichment status
curl "https://gold-research-api-production.up.railway.app/api/v1/merchants/enrichment-status/1"

# Get merchant profiles
curl "https://gold-research-api-production.up.railway.app/api/v1/merchants/merchant-profiles/1"
```

---

## **💡 Pro Tips**

### **1. Always Preview First**

```bash
python import_transactions.py --source data.csv --format csv --preview
```

Ensure the script can read your file and show the expected data.

### **2. Start Small**

Test with 10-20 records before importing 1000s.

### **3. Validate After Import**

```sql
-- Check imported count
SELECT COUNT(*) FROM gold_purchases WHERE created_at >= NOW() - INTERVAL '1 hour';

-- Spot check some records
SELECT * FROM gold_purchases ORDER BY id DESC LIMIT 5;
```

### **4. Monitor Enrichment**

```sql
-- See how many records have been enriched
SELECT 
  COUNT(DISTINCT purchase_record_id) as enriched_count
FROM purchase_merchants;

-- Check enrichment success rate
SELECT 
  search_type,
  COUNT(*) as total,
  COUNT(CASE WHEN success THEN 1 END) as successful,
  ROUND(100.0 * COUNT(CASE WHEN success THEN 1 END) / COUNT(*), 1) as success_rate
FROM merchant_enrichment_history
GROUP BY search_type;
```

### **5. Batch Large Imports**

For 10,000+ records, split into batches:

```bash
# Import batch 1
python import_transactions.py --source data_part1.csv --format csv

# Wait a minute, check logs
sleep 60

# Import batch 2
python import_transactions.py --source data_part2.csv --format csv
```

---

## **📝 Example: Full Workflow**

### **Step 1: Prepare CSV**

Create `transactions.csv`:
```csv
customer_name,email_address,phone_number,city,state,zip_code,purchase_amount,transaction_date
...
```

### **Step 2: Preview**

```bash
python import_transactions.py --source transactions.csv --format csv --preview
```

### **Step 3: Import**

```bash
python import_transactions.py --source transactions.csv --format csv
```

### **Step 4: Verify**

```bash
psql -c "SELECT COUNT(*) FROM gold_purchases"
```

### **Step 5: Enrich**

```bash
# Get a purchase ID
PURCHASE_ID=$(psql -t -c "SELECT id FROM gold_purchases ORDER BY id DESC LIMIT 1")

# Enrich it
curl -X POST "https://your-api/api/v1/merchants/enrich/directory-search?purchase_id=$PURCHASE_ID" \
  -H "Content-Type: application/json" \
  -d '{"merchant_name": "Tiffany", "merchant_city": "New York", "merchant_state": "NY"}'

# Check status
curl "https://your-api/api/v1/merchants/enrichment-status/$PURCHASE_ID"
```

---

## **❓ FAQ**

**Q: Can I import the same data twice?**  
A: No, the script detects duplicates and skips them.

**Q: What happens if a row has missing optional fields?**  
A: It's imported with NULL values for missing optional fields.

**Q: Can I use a different date format?**  
A: Yes, the script supports YYYY-MM-DD and MM/DD/YYYY with optional time.

**Q: How do I import from a live database?**  
A: Use `--format postgres` with source database credentials.

**Q: Can I rollback an import?**  
A: Yes, use SQL `DELETE` or restore from backup.

**Q: What's the maximum file size?**  
A: The script can handle files with millions of rows, but import speed depends on database performance.

---

## **Next Steps**

1. ✅ Prepare your transaction data (CSV or JSON)
2. ✅ Run `--preview` to validate
3. ✅ Run import script
4. ✅ Verify in database
5. ✅ Test enrichment endpoints
6. ✅ Monitor in `merchant_enrichment_history` table

---

**Ready to import?** Start with:

```bash
python import_transactions.py --source sample_data.csv --format csv --preview
```

Then test the real data!

