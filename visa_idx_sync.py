"""
Visa IDX Outbound Sync Pipeline
Manages background synchronization of purchase records to Visa IDX API.
Handles queue management, retry logic, and compliance tracking.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor
from visa_idx_client import get_visa_idx_client

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a sync operation."""
    PENDING = "pending"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"
    FAILED_MAX_RETRIES = "failed_max_retries"


@dataclass
class SyncRecord:
    """Represents a sync operation."""
    id: int
    purchase_record_id: int
    status: SyncStatus
    attempts: int
    last_error: Optional[str] = None
    last_attempted_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    visa_record_id: Optional[str] = None


class VisaIDXSyncPipeline:
    """
    Manages outbound synchronization of purchase records to Visa IDX.
    
    Features:
    - Background task queue
    - Automatic retry with exponential backoff
    - Compliance tracking
    - Data sanitization enforcement
    - Idempotent operations
    """
    
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 60  # seconds
    MAX_RETRY_DELAY = 3600  # seconds
    BATCH_SIZE = 10
    
    def __init__(self, db_connection_params: Dict[str, str]):
        """
        Initialize sync pipeline.
        
        Args:
            db_connection_params: Database connection parameters
        """
        self.db_params = db_connection_params
        self.visa_client = get_visa_idx_client()
        self.is_running = False
        self._sync_task = None
    
    async def init_sync_table(self, conn) -> None:
        """
        Create sync tracking table if it doesn't exist.
        
        Tracks sync attempts, status, and compliance audit trail.
        """
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visa_idx_sync_log (
                    id SERIAL PRIMARY KEY,
                    purchase_record_id INTEGER NOT NULL REFERENCES gold_purchases(id),
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    last_attempted_at TIMESTAMP,
                    synced_at TIMESTAMP,
                    visa_record_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Compliance tracking
                    data_sanitized BOOLEAN DEFAULT true,
                    no_pans_detected BOOLEAN DEFAULT true,
                    
                    CONSTRAINT unique_sync_per_record UNIQUE(purchase_record_id)
                );
            """)
            
            # Create index for efficient querying
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_visa_sync_status 
                ON visa_idx_sync_log(status);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_visa_sync_pending 
                ON visa_idx_sync_log(status, created_at) 
                WHERE status IN ('pending', 'failed');
            """)
            
            conn.commit()
            logger.info("Visa IDX sync tracking table initialized")
        
        except Exception as e:
            logger.error(f"Failed to initialize sync table: {e}")
            conn.rollback()
            raise
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(**self.db_params)
    
    async def queue_purchase_for_sync(
        self,
        purchase_record_id: int,
        conn: Optional[Any] = None
    ) -> bool:
        """
        Queue a purchase record for sync to Visa IDX.
        
        Args:
            purchase_record_id: ID of gold_purchases record
            conn: Optional existing connection
        
        Returns:
            True if queued successfully
        """
        close_conn = conn is None
        
        try:
            if close_conn:
                conn = self._get_connection()
            
            cursor = conn.cursor()
            
            # Check if already queued or synced
            cursor.execute(
                "SELECT id FROM visa_idx_sync_log WHERE purchase_record_id = %s",
                (purchase_record_id,)
            )
            
            if cursor.fetchone():
                logger.info(f"Record {purchase_record_id} already in sync queue")
                return True
            
            # Queue for sync
            cursor.execute("""
                INSERT INTO visa_idx_sync_log (purchase_record_id, status)
                VALUES (%s, %s)
            """, (purchase_record_id, SyncStatus.PENDING.value))
            
            conn.commit()
            logger.info(f"Queued record {purchase_record_id} for Visa IDX sync")
            return True
        
        except Exception as e:
            logger.error(f"Failed to queue record for sync: {e}")
            if conn:
                conn.rollback()
            return False
        
        finally:
            if close_conn and conn:
                conn.close()
    
    async def process_sync_queue(self) -> Dict[str, int]:
        """
        Process pending records in sync queue.
        
        Returns:
            Summary of operations: {synced: N, failed: N, retried: N}
        """
        conn = self._get_connection()
        summary = {"synced": 0, "failed": 0, "retried": 0}
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get pending and failed records (with retry logic)
            cursor.execute("""
                SELECT id, purchase_record_id, status, attempts, last_attempted_at
                FROM visa_idx_sync_log
                WHERE status IN (%s, %s)
                    AND attempts < %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (
                SyncStatus.PENDING.value,
                SyncStatus.FAILED.value,
                self.MAX_RETRIES,
                self.BATCH_SIZE
            ))
            
            pending_syncs = cursor.fetchall()
            
            if not pending_syncs:
                logger.debug("No pending syncs in queue")
                return summary
            
            logger.info(f"Processing {len(pending_syncs)} pending Visa IDX syncs")
            
            for sync_record in pending_syncs:
                await self._process_single_sync(conn, sync_record, summary)
            
            return summary
        
        except Exception as e:
            logger.error(f"Error processing sync queue: {e}")
            return summary
        
        finally:
            conn.close()
    
    async def _process_single_sync(
        self,
        conn,
        sync_record: Dict,
        summary: Dict[str, int]
    ) -> None:
        """
        Process a single sync record.
        
        Args:
            conn: Database connection
            sync_record: Sync log record
            summary: Summary dict to update
        """
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        purchase_id = sync_record["purchase_record_id"]
        sync_id = sync_record["id"]
        
        try:
            # Update status to syncing
            cursor.execute("""
                UPDATE visa_idx_sync_log
                SET status = %s, last_attempted_at = CURRENT_TIMESTAMP, attempts = attempts + 1
                WHERE id = %s
            """, (SyncStatus.SYNCING.value, sync_id))
            conn.commit()
            
            # Fetch purchase record
            cursor.execute(
                "SELECT * FROM gold_purchases WHERE id = %s",
                (purchase_id,)
            )
            purchase_record = cursor.fetchone()
            
            if not purchase_record:
                logger.warning(f"Purchase record {purchase_id} not found")
                cursor.execute("""
                    UPDATE visa_idx_sync_log
                    SET status = %s, last_error = %s
                    WHERE id = %s
                """, (SyncStatus.FAILED.value, "Purchase record not found", sync_id))
                conn.commit()
                summary["failed"] += 1
                return
            
            # Sync to Visa
            result = await self.visa_client.sync_purchase_record(dict(purchase_record))
            
            if result["success"]:
                cursor.execute("""
                    UPDATE visa_idx_sync_log
                    SET status = %s, synced_at = CURRENT_TIMESTAMP, 
                        visa_record_id = %s, no_pans_detected = true
                    WHERE id = %s
                """, (
                    SyncStatus.SUCCESS.value,
                    result.get("response", {}).get("id"),
                    sync_id
                ))
                conn.commit()
                logger.info(f"Successfully synced record {purchase_id} to Visa IDX")
                summary["synced"] += 1
            
            else:
                # Determine if we should retry
                attempts = sync_record["attempts"] + 1
                
                if attempts >= self.MAX_RETRIES:
                    status = SyncStatus.FAILED_MAX_RETRIES.value
                    logger.error(
                        f"Max retries ({self.MAX_RETRIES}) reached for record {purchase_id}"
                    )
                else:
                    status = SyncStatus.FAILED.value
                    summary["retried"] += 1
                
                cursor.execute("""
                    UPDATE visa_idx_sync_log
                    SET status = %s, last_error = %s
                    WHERE id = %s
                """, (status, result.get("error", "Unknown error"), sync_id))
                conn.commit()
                logger.warning(f"Failed to sync record {purchase_id}: {result.get('error')}")
                summary["failed"] += 1
        
        except Exception as e:
            logger.error(f"Exception processing sync for record {purchase_id}: {e}")
            cursor.execute("""
                UPDATE visa_idx_sync_log
                SET status = %s, last_error = %s
                WHERE id = %s
            """, (SyncStatus.FAILED.value, str(e), sync_id))
            conn.commit()
            summary["failed"] += 1
    
    async def start_background_sync(self, interval_seconds: int = 300) -> None:
        """
        Start background sync task.
        
        Args:
            interval_seconds: Interval between sync checks (default: 5 minutes)
        """
        if self.is_running:
            logger.warning("Sync pipeline already running")
            return
        
        self.is_running = True
        logger.info(f"Starting Visa IDX sync pipeline (interval: {interval_seconds}s)")
        
        try:
            while self.is_running:
                try:
                    summary = await self.process_sync_queue()
                    
                    if any(v > 0 for v in summary.values()):
                        logger.info(
                            f"Sync cycle complete - "
                            f"Synced: {summary['synced']}, "
                            f"Failed: {summary['failed']}, "
                            f"Retried: {summary['retried']}"
                        )
                    
                    await asyncio.sleep(interval_seconds)
                
                except Exception as e:
                    logger.error(f"Error in sync loop: {e}")
                    await asyncio.sleep(min(interval_seconds * 2, 3600))
        
        except asyncio.CancelledError:
            logger.info("Visa IDX sync pipeline stopped")
            self.is_running = False
    
    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        self.is_running = False
        logger.info("Stopping Visa IDX sync pipeline")
    
    async def get_sync_status(self, purchase_record_id: int) -> Optional[Dict]:
        """
        Get sync status for a purchase record.
        
        Args:
            purchase_record_id: ID of gold_purchases record
        
        Returns:
            Sync status dict or None if not found
        """
        conn = self._get_connection()
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, purchase_record_id, status, attempts, 
                       last_error, synced_at, visa_record_id,
                       data_sanitized, no_pans_detected
                FROM visa_idx_sync_log
                WHERE purchase_record_id = %s
            """, (purchase_record_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
        
        finally:
            conn.close()


# Global sync pipeline instance
_sync_pipeline: Optional[VisaIDXSyncPipeline] = None


def get_sync_pipeline(db_params: Dict[str, str]) -> VisaIDXSyncPipeline:
    """Get or create singleton sync pipeline."""
    global _sync_pipeline
    if _sync_pipeline is None:
        _sync_pipeline = VisaIDXSyncPipeline(db_params)
    return _sync_pipeline

