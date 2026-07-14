# Import Execution Guide - Step by Step

**Status:** Ready to execute on your local machine  
**Date:** July 14, 2026

---

## **🚀 Command to Run**

```bash
python3 import_transactions.py --source sample_data.csv --format csv
```

---

## **📋 Prerequisites**

Before running, ensure you have:

1. **Python 3.7+**
   ```bash
   python3 --version
   # Should output: Python 3.x.x
   ```

2. **psycopg2 installed**
   ```bash
   pip3 install psycopg2-binary
   ```

3. **PostgreSQL database running and accessible**
   ```bash
   psql -h localhost -U postgres -d gold_research -c "SELECT 1"
   # Should connect successfully
   ```

4. **Database credentials**
   - Host: localhost (or your Railway database host)
   - Port: 5432
   - User: postgres
   - Database: gold_research

---

## **🔧 Setup (First Time Only)**

### **Option A: Local PostgreSQL**

```bash
# On your machine (macOS/Linux)
cd /path/to/gold-research-api

# Install dependencies
pip3 install psycopg2-binary

# Ensure PostgreSQL is running
psql -U postgres -d gold_research -c "SELECT 1"

# Run the import
python3 import_transactions.py --source sample_data.csv --format csv
```

### **Option B: Railway PostgreSQL (Remote)**

```bash
# Get credentials from Railway dashboard
# Then set environment variables
export PGHOST=your-railway-host.railway.app
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=your-password
export PGDATABASE=gold_research

# Run the import
python3 import_transactions.py --source sample_data.csv --format csv
```

---

## **▶️ What Will Happen When You Run It**

### **Timeline of Execution**

```
1. Script starts
   ↓
2. Database connection attempt
   ↓
3. CSV file reading
   ↓
4. Data validation (15 rows)
   ↓
5. Sanitization (PAN/routing removal)
   ↓
6. Duplicate detection
   ↓
7. Database inserts (15 transactions)
   ↓
8. Report generation
   ↓
9. Success!
```

---

## **📊 Expected Output**

### **Console Output (Real Time)**

```
2026-07-14 23:30:15,123 - INFO - 🚀 Starting transaction import (csv format)
2026-07-14 23:30:15,124 - INFO - ✓ Connected to database
2026-07-14 23:30:15,125 - INFO - Reading CSV file: sample_data.csv
2026-07-14 23:30:15,127 - INFO - ✓ Loaded 15 rows from CSV
2026-07-14 23:30:15,128 - INFO - Importing 15 rows...
2026-07-14 23:30:15,135 - INFO -   Imported 10 rows...
2026-07-14 23:30:15,142 - INFO - ✓ Import completed successfully!

============================================================
IMPORT REPORT - 2026-07-14 23:30:15
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
```

---

## **✅ Success Indicators**

You'll know the import succeeded when:

- ✅ No errors printed to console
- ✅ "✓ Import completed successfully!" message appears
- ✅ All 15 records show in "Successfully imported"
- ✅ "INSERTED RECORD IDs: 1, 2, 3, ..." lists the IDs
- ✅ Exit code is 0 (no error)

---

## **🔍 Verify the Import Worked**

After the script completes successfully:

### **Check Row Count**

```bash
psql -h localhost -U postgres -d gold_research -c "SELECT COUNT(*) FROM gold_purchases"
```

**Expected output:** `15` (or your previous count + 15)

### **View Imported Records**

```bash
psql -h localhost -U postgres -d gold_research -c "SELECT id, customer_name, email_address, purchase_amount FROM gold_purchases ORDER BY id DESC LIMIT 5"
```

**Expected output:**
```
 id |   customer_name    |         email_address         | purchase_amount
----+--------------------+-------------------------------+-----------------
 15 | Daniel White       | daniel.white@example.com      |        24000.25
 14 | Nicole Harris      | nicole.harris@example.com     |        29750.75
 13 | Kevin Thompson     | kevin.t@example.com           |        38500.00
 12 | Amanda Brown       | amanda.brown@example.com      |        21000.50
 11 | Christopher Taylor | chris.taylor@example.com      |        26500.00
(5 rows)
```

### **Check All Imported States**

```bash
psql -h localhost -U postgres -d gold_research -c "SELECT DISTINCT state FROM gold_purchases ORDER BY state"
```

**Expected output:**
```
 state
-------
 AZ
 CA
 FL
 IL
 NC
 NY
 OH
 PA
 TX
(9 states)
```

### **Calculate Total Amount**

```bash
psql -h localhost -U postgres -d gold_research -c "SELECT SUM(purchase_amount) as total FROM gold_purchases"
```

**Expected output:**
```
    total
-----------
 422750.50
```

---

## **📝 Log File**

The script automatically creates a log file:

```
import_YYYYMMDD_HHMMSS.log
```

Example: `import_20260714_233015.log`

**View it:**
```bash
cat import_20260714_233015.log
```

This log contains:
- All operations performed
- Any errors encountered
- Timestamps for each action
- Full audit trail

---

## **❌ If Something Goes Wrong**

### **Error: "Failed to connect to database"**

```
✗ Failed to connect to database: connection refused
```

**Fix:**
```bash
# Check database is running
psql -h localhost -U postgres -d gold_research -c "SELECT 1"

# If that fails, start PostgreSQL
# On macOS: brew services start postgresql
# On Linux: sudo systemctl start postgresql
```

### **Error: "File not found"**

```
✗ File not found: sample_data.csv
```

**Fix:**
```bash
# Verify file exists
ls -la sample_data.csv

# If not, download from GitHub
# https://github.com/theusdept/gold-research-api/blob/main/sample_data.csv
```

### **Error: "Invalid email format"**

```
Row 5 (john@example):
  → Invalid email format: john@example
```

**Fix:** The CSV has bad data. Use the provided `sample_data.csv` which is verified.

### **Error: "psycopg2 not installed"**

```
ModuleNotFoundError: No module named 'psycopg2'
```

**Fix:**
```bash
pip3 install psycopg2-binary
```

---

## **🔄 Run It Again (Testing)**

You can run the import script multiple times:

### **First Run**
```bash
python3 import_transactions.py --source sample_data.csv --format csv
```
Result: 15 records imported (IDs 1-15)

### **Second Run**
```bash
python3 import_transactions.py --source sample_data.csv --format csv
```
Result: 0 records imported (all detected as duplicates)

**Why?** The script detects duplicates by matching:
- Email address
- Purchase amount
- Transaction date

So running the same file twice won't create duplicates!

---

## **🧪 Testing Enrichment After Import**

Once import completes, test the enrichment endpoints:

### **Get the Import Report**

From the console output or log file, note some Purchase IDs. Example: 1, 5, 10

### **Enrich a Record**

```bash
curl -X POST "https://gold-research-api-production.up.railway.app/api/v1/merchants/enrich/directory-search?purchase_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_name": "Tiffany",
    "merchant_city": "New York",
    "merchant_state": "NY"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "purchase_id": 1,
  "merchant_name": "Tiffany",
  "merchants_found": 3,
  "merchants": [
    {
      "name": "Tiffany & Co",
      "mcc": "5944",
      "category": "Jewelry Stores",
      "confidence_score": 0.95,
      "logo_url": "https://...",
      "address": "..."
    }
  ]
}
```

### **Check Enrichment Status**

```bash
curl "https://gold-research-api-production.up.railway.app/api/v1/merchants/enrichment-status/1"
```

### **View Merchant Profiles**

```bash
curl "https://gold-research-api-production.up.railway.app/api/v1/merchants/merchant-profiles/1"
```

---

## **⏱️ Performance**

**Expected execution time:** 2-5 seconds

Breakdown:
- Database connection: ~100ms
- CSV parsing: ~50ms
- Validation (15 rows): ~100ms
- Sanitization: ~50ms
- Duplicate detection: ~100ms
- Inserts (15 rows): ~1000ms
- Report generation: ~100ms
- **Total: ~1.5 seconds**

---

## **📊 Database State After Import**

### **gold_purchases Table**

```
CREATE TABLE gold_purchases (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255),
    email_address VARCHAR(255),
    phone_number VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    purchase_amount NUMERIC(12, 2),
    transaction_date TIMESTAMP,
    created_at TIMESTAMP
)
```

**After import:**
- 15 new rows
- All fields populated from sample_data.csv
- PII sanitized (if any existed)
- Timestamps set to import time

### **Indexes Created**

```sql
idx_state            (state)
idx_zip_code         (zip_code)
idx_transaction_date (transaction_date)
idx_purchase_amount  (purchase_amount)
```

These enable fast filtering for:
```sql
SELECT * FROM gold_purchases WHERE state = 'NY'
SELECT * FROM gold_purchases WHERE purchase_amount > 30000
```

---

## **🎯 Next Steps After Import**

1. **✅ Verify import succeeded**
   ```bash
   psql -c "SELECT COUNT(*) FROM gold_purchases"
   ```

2. **✅ Test enrichment**
   ```bash
   # Use a purchase_id from the import report
   curl https://your-api/api/v1/merchants/merchant-profiles/1
   ```

3. **✅ Check enrichment status**
   ```bash
   curl https://your-api/api/v1/merchants/enrichment-status/1
   ```

4. **✅ Query the data**
   ```bash
   psql -c "SELECT * FROM gold_purchases WHERE state = 'CA' LIMIT 5"
   psql -c "SELECT AVG(purchase_amount) FROM gold_purchases"
   ```

5. **✅ Import your real data**
   ```bash
   python3 import_transactions.py --source your_data.csv --format csv
   ```

---

## **📚 Related Documents**

- **IMPORT_GUIDE.md** - Complete reference
- **IMPORT_QUICK_REFERENCE.md** - Quick commands
- **IMPORT_TESTING_REPORT.md** - Test results
- **README.md** - API overview
- **VISA_MERCHANT_SEARCH.md** - Enrichment endpoints

---

## **✅ Checklist**

Before running the import:

- [ ] Python 3.7+ installed
- [ ] psycopg2 installed (`pip3 install psycopg2-binary`)
- [ ] PostgreSQL accessible
- [ ] `sample_data.csv` exists in current directory
- [ ] `import_transactions.py` exists in current directory
- [ ] Database credentials available

After running the import:

- [ ] Console shows "✓ Import completed successfully!"
- [ ] 15 records inserted
- [ ] No validation errors
- [ ] No import errors
- [ ] Log file created
- [ ] Database query confirms 15 rows added

---

## **🎉 You're Ready!**

You have everything needed to run the import. Just run:

```bash
python3 import_transactions.py --source sample_data.csv --format csv
```

And watch the magic happen! ✨

---

**Expected Result:** 15 test records imported into your Gold Research API database, ready for enrichment testing!

If you have any issues, check the error messages and refer to the "If Something Goes Wrong" section above.

Good luck! 🚀

