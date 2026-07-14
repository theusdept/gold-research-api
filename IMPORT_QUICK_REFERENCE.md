# Transaction Import - Quick Reference Card

## **The Import Script**

**File:** `import_transactions.py`

**Purpose:** Manually import transaction data into Gold Research API

**Status:** ✅ Ready to test

---

## **Quick Commands**

### **Test with Sample Data**

```bash
# Preview (don't actually import)
python import_transactions.py --source sample_data.csv --format csv --preview

# Actually import sample data
python import_transactions.py --source sample_data.csv --format csv

# View what was imported
psql -h localhost -U postgres -d gold_research -c "SELECT COUNT(*) FROM gold_purchases"
```

### **Import Your Own Data**

**CSV:**
```bash
python import_transactions.py --source your_data.csv --format csv --preview
python import_transactions.py --source your_data.csv --format csv
```

**JSON:**
```bash
python import_transactions.py --source your_data.json --format json
```

**PostgreSQL Database:**
```bash
python import_transactions.py --format postgres \
  --source-host source.db.example.com \
  --source-user postgres \
  --source-password secret \
  --source-db transactions
```

---

## **Data Format Required**

### **CSV Columns**

**Minimum (required):**
```
customer_name,email_address,purchase_amount
```

**Full (recommended):**
```
customer_name,email_address,phone_number,city,state,zip_code,purchase_amount,transaction_date
```

### **JSON Structure**

```json
{
  "transactions": [
    {
      "customer_name": "Name",
      "email_address": "email@example.com",
      "purchase_amount": 25000.00,
      "transaction_date": "2026-04-15"
    }
  ]
}
```

---

## **What Happens During Import**

1. ✅ **Validation** - Checks required fields, email format, amounts
2. ✅ **Sanitization** - Strips credit card numbers, routing numbers
3. ✅ **Duplicate Detection** - Skips records already imported
4. ✅ **Import** - Inserts into `gold_purchases` table
5. ✅ **Reporting** - Prints summary with inserted IDs

---

## **Testing Workflow**

### **Step 1: Preview**
```bash
python import_transactions.py --source sample_data.csv --format csv --preview
```
Expected: Shows what would be imported, doesn't write anything

### **Step 2: Import Sample**
```bash
python import_transactions.py --source sample_data.csv --format csv
```
Expected: "✓ Import completed successfully!" + report

### **Step 3: Verify**
```bash
psql -c "SELECT COUNT(*) FROM gold_purchases"
psql -c "SELECT id, customer_name, purchase_amount FROM gold_purchases LIMIT 5"
```
Expected: 15 rows (from sample_data.csv)

### **Step 4: Test Enrichment**
```bash
# Get the ID of last imported record
PURCHASE_ID=$(psql -t -c "SELECT id FROM gold_purchases ORDER BY id DESC LIMIT 1")

# Enrich it
curl -X POST "https://gold-research-api-production.up.railway.app/api/v1/merchants/enrich/directory-search?purchase_id=$PURCHASE_ID" \
  -H "Content-Type: application/json" \
  -d '{"merchant_name": "Tiffany", "merchant_city": "New York", "merchant_state": "NY"}'
```
Expected: Returns merchant profiles with logos and confidence scores

---

## **Sample Data Files Included**

### **sample_data.csv** (15 rows)
- Pre-formatted CSV with test transactions
- Ready to import
- Use to test the script

### **sample_data.json** (8 rows)
- Pre-formatted JSON with test transactions
- Different test data than CSV
- Use to test JSON import

---

## **Database Connection**

### **Local Testing**

```bash
# Using default local PostgreSQL
python import_transactions.py --source data.csv --format csv

# Using environment variables
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=secret
export PGDATABASE=gold_research

python import_transactions.py --source data.csv --format csv
```

### **Railway Database**

```bash
# Get credentials from Railway dashboard
python import_transactions.py \
  --source data.csv \
  --format csv \
  --db-host your-railway-host.railway.app \
  --db-user postgres \
  --db-password your-password \
  --db-name gold_research
```

---

## **What Gets Imported**

**Into:** `gold_purchases` table

**Fields:**
- `id` - Auto-generated
- `customer_name` - From data
- `email_address` - From data (normalized to lowercase)
- `phone_number` - From data (optional)
- `city` - From data (optional)
- `state` - From data (normalized to uppercase, optional)
- `zip_code` - From data (optional)
- `purchase_amount` - From data (numeric)
- `transaction_date` - From data or current timestamp
- `created_at` - Auto-timestamp

---

## **Validation Rules**

| Field | Required? | Must Be Valid |
|-------|-----------|---------------|
| customer_name | ✓ | Non-empty |
| email_address | ✓ | Valid email (user@domain.com) |
| purchase_amount | ✓ | Positive number |
| transaction_date | ✗ | YYYY-MM-DD or MM/DD/YYYY format |
| state | ✗ | 2-letter code (A-Z) |
| phone_number | ✗ | Any format |
| city | ✗ | Any text |
| zip_code | ✗ | Any format |

---

## **Data Sanitization**

The script automatically removes:
- ❌ Credit card numbers (13-19 digit sequences)
- ❌ Bank routing numbers (9 digit sequences)

And normalizes:
- 📧 Email addresses → lowercase
- 🗺️ State codes → UPPERCASE
- 🔤 Whitespace → trimmed

---

## **Duplicate Detection**

Records with same:
- Email address
- Purchase amount
- Transaction date

Are automatically **skipped** (no error, just logged)

---

## **Import Report**

After import, you get:

```
STATISTICS:
  Total rows processed:     15
  Successfully imported:    15 ✓
  Duplicates skipped:       0 ⊘
  Validation errors:        0 ✗
  Import errors:            0 ✗

INSERTED RECORD IDs:
  1, 2, 3, 4, 5, ...
```

**Log file:** `import_YYYYMMDD_HHMMSS.log` (in current directory)

---

## **Common Issues & Fixes**

| Issue | Fix |
|-------|-----|
| `File not found` | Check file path, use full path if needed |
| `Failed to connect` | Verify database is running, check credentials |
| `Invalid email format` | Fix email in CSV/JSON (must have @domain) |
| `Negative purchase_amount` | Change amount to positive number |
| `Duplicates skipped: 5` | Normal - these records already exist |
| `Validation errors: 3` | Check error details in report, fix and re-import |

---

## **Next Steps**

1. **Test with samples:**
   ```bash
   python import_transactions.py --source sample_data.csv --format csv --preview
   python import_transactions.py --source sample_data.csv --format csv
   ```

2. **Verify import:**
   ```bash
   psql -c "SELECT COUNT(*) FROM gold_purchases"
   ```

3. **Test enrichment:**
   - Use the purchase_id from import report
   - Call `/api/v1/merchants/enrich/directory-search` endpoint

4. **Import your real data:**
   - Prepare CSV or JSON with your transactions
   - Run preview first to validate
   - Run actual import
   - Monitor enrichment results

5. **Automate (later):**
   - Schedule import script via cron
   - Or create REST endpoint wrapper

---

## **Full Documentation**

See `IMPORT_GUIDE.md` for:
- Detailed command reference
- Advanced usage (PostgreSQL source)
- Error handling
- Rollback procedures
- Pro tips and workflows

---

## **Status**

✅ Script created  
✅ Sample data provided  
✅ Documentation complete  
✅ Ready to test  

**Next:** Run the test!

```bash
python import_transactions.py --source sample_data.csv --format csv --preview
```

