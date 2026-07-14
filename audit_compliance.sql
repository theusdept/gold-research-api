-- Visa IDX Integration Compliance Audit Queries
-- Use these to verify that PANs and routing numbers are being properly stripped

-- 1. Overall Sync Status Summary
SELECT 
  status,
  COUNT(*) as count,
  ROUND(AVG(attempts), 2) as avg_attempts,
  MAX(created_at) as latest_sync,
  COUNT(CASE WHEN data_sanitized = true THEN 1 END) as sanitized_count
FROM visa_idx_sync_log
GROUP BY status
ORDER BY count DESC;

-- 2. Recently Synced Records (Last 24 Hours)
SELECT 
  psl.id,
  psl.purchase_record_id,
  gp.customer_name,
  gp.email_address,
  gp.purchase_amount,
  psl.status,
  psl.synced_at,
  psl.data_sanitized,
  psl.no_pans_detected,
  psl.attempts
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY psl.created_at DESC;

-- 3. Check for Failed Syncs Requiring Manual Review
SELECT 
  psl.id,
  psl.purchase_record_id,
  gp.customer_name,
  gp.purchase_amount,
  psl.status,
  psl.attempts,
  psl.last_error,
  psl.last_attempted_at
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.status IN ('failed_max_retries', 'failed')
  AND psl.last_attempted_at >= NOW() - INTERVAL '7 days'
ORDER BY psl.last_attempted_at DESC;

-- 4. Compliance Audit: Verify All Synced Records Had Data Sanitized
SELECT 
  COUNT(*) as total_synced,
  COUNT(CASE WHEN data_sanitized = true THEN 1 END) as properly_sanitized,
  COUNT(CASE WHEN no_pans_detected = true THEN 1 END) as no_pans_found,
  COUNT(CASE WHEN data_sanitized = false THEN 1 END) as sanitization_failures,
  100.0 * COUNT(CASE WHEN data_sanitized = true THEN 1 END) / COUNT(*) as sanitization_percentage
FROM visa_idx_sync_log
WHERE status = 'success';

-- 5. Records Still Pending Sync (After 10 Minutes)
SELECT 
  psl.id,
  psl.purchase_record_id,
  gp.customer_name,
  gp.purchase_amount,
  psl.created_at,
  EXTRACT(EPOCH FROM (NOW() - psl.created_at)) / 60 as minutes_pending
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.status = 'pending'
  AND psl.created_at < NOW() - INTERVAL '10 minutes'
ORDER BY psl.created_at ASC;

-- 6. Success Rate by Day (for trending)
SELECT 
  DATE_TRUNC('day', psl.synced_at) as sync_date,
  COUNT(*) as total_syncs,
  COUNT(CASE WHEN psl.status = 'success' THEN 1 END) as successful,
  COUNT(CASE WHEN psl.status != 'success' THEN 1 END) as failed,
  ROUND(100.0 * COUNT(CASE WHEN psl.status = 'success' THEN 1 END) / COUNT(*), 2) as success_rate
FROM visa_idx_sync_log psl
WHERE psl.synced_at IS NOT NULL
GROUP BY DATE_TRUNC('day', psl.synced_at)
ORDER BY sync_date DESC;

-- 7. High-Value Transactions Synced (>$50,000)
SELECT 
  psl.purchase_record_id,
  gp.customer_name,
  gp.city,
  gp.state,
  gp.purchase_amount,
  psl.status,
  psl.synced_at,
  psl.data_sanitized,
  psl.no_pans_detected
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE gp.purchase_amount > 50000
  AND psl.status = 'success'
ORDER BY gp.purchase_amount DESC;

-- 8. Retry Analysis (which records needed multiple attempts)
SELECT 
  psl.purchase_record_id,
  gp.customer_name,
  gp.purchase_amount,
  psl.attempts,
  psl.status,
  psl.last_error,
  psl.created_at,
  psl.synced_at,
  EXTRACT(EPOCH FROM (psl.synced_at - psl.created_at)) / 60 as minutes_to_sync
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.attempts > 1
ORDER BY psl.attempts DESC;

-- 9. Data Sanitization Verification - Spot Check
-- Returns sample of synced records to manually verify names/phones are properly formatted
SELECT 
  psl.purchase_record_id,
  gp.customer_name,
  gp.phone_number,
  gp.email_address,
  LENGTH(gp.customer_name) as name_length,
  LENGTH(gp.phone_number) as phone_length,
  CASE 
    WHEN gp.customer_name ~ '\d{13,19}' THEN 'WARNING: PAN-like pattern detected'
    WHEN gp.phone_number ~ '\d{9}' THEN 'WARNING: Routing-like pattern detected'
    ELSE 'OK'
  END as sanitization_check,
  psl.data_sanitized,
  psl.no_pans_detected
FROM visa_idx_sync_log psl
JOIN gold_purchases gp ON psl.purchase_record_id = gp.id
WHERE psl.status = 'success'
  AND psl.created_at >= NOW() - INTERVAL '1 day'
ORDER BY psl.synced_at DESC
LIMIT 20;

-- 10. Sync Pipeline Health Check
SELECT 
  'Total Records in System' as metric,
  COUNT(*) as value
FROM gold_purchases
UNION ALL
SELECT 
  'Total Sync Attempts',
  COUNT(*)
FROM visa_idx_sync_log
UNION ALL
SELECT 
  'Successful Syncs',
  COUNT(*)
FROM visa_idx_sync_log
WHERE status = 'success'
UNION ALL
SELECT 
  'Failed Syncs (Max Retries)',
  COUNT(*)
FROM visa_idx_sync_log
WHERE status = 'failed_max_retries'
UNION ALL
SELECT 
  'Pending Syncs',
  COUNT(*)
FROM visa_idx_sync_log
WHERE status = 'pending'
UNION ALL
SELECT 
  'Average Sync Time (seconds)',
  ROUND(EXTRACT(EPOCH FROM AVG(psl.synced_at - psl.created_at)))
FROM visa_idx_sync_log psl
WHERE psl.synced_at IS NOT NULL;

-- 11. Certificate/Integration Issues - Error Log Analysis
SELECT 
  last_error,
  COUNT(*) as occurrences,
  MAX(last_attempted_at) as most_recent,
  ARRAY_AGG(DISTINCT purchase_record_id ORDER BY purchase_record_id) as affected_records
FROM visa_idx_sync_log
WHERE status IN ('failed', 'failed_max_retries')
  AND last_error IS NOT NULL
GROUP BY last_error
ORDER BY occurrences DESC;

-- 12. Compliance Report for Audit (summary)
SELECT 
  NOW() as report_timestamp,
  (SELECT COUNT(*) FROM gold_purchases) as total_purchase_records,
  (SELECT COUNT(*) FROM visa_idx_sync_log WHERE status = 'success') as successfully_synced,
  (SELECT COUNT(*) FROM visa_idx_sync_log WHERE status IN ('failed', 'failed_max_retries')) as failed_syncs,
  (SELECT COUNT(*) FROM visa_idx_sync_log WHERE data_sanitized = true AND status = 'success') as sanitized_successful,
  (SELECT COUNT(*) FROM visa_idx_sync_log WHERE no_pans_detected = true AND status = 'success') as no_pans_successful,
  (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE data_sanitized = true) / NULLIF(COUNT(*), 0), 2)
   FROM visa_idx_sync_log WHERE status = 'success') as sanitization_compliance_rate,
  (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE no_pans_detected = true) / NULLIF(COUNT(*), 0), 2)
   FROM visa_idx_sync_log WHERE status = 'success') as no_pans_compliance_rate;

-- 13. Timeline of Recent Activity
SELECT 
  'Purchase Created' as event_type,
  id as event_id,
  customer_name as details,
  purchase_amount as amount,
  created_at as timestamp
FROM gold_purchases
WHERE created_at >= NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 
  'Sync Status: ' || status,
  purchase_record_id,
  CASE WHEN status = 'success' THEN 'Synced to Visa' ELSE last_error END,
  NULL,
  updated_at
FROM visa_idx_sync_log
WHERE updated_at >= NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

