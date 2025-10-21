#!/usr/bin/env python3
"""
Results Store - Unified Data Persistence for Flask + FastAPI

Provides a unified interface for storing and retrieving processing results
from both Flask web UI and FastAPI analytics API.

Uses DuckDB as the single source of truth for all data:
- Pipeline execution metadata (existing)
- Processing results and legal events (new)
- Session tracking and analytics (enhanced)
"""

import duckdb
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import threading

class ResultsStore:
    """Unified results storage using DuckDB"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        # Default database path
        if db_path is None:
            # Try to get from FastAPI settings, fallback to default
            try:
                from src.api.config import settings
                db_path = settings.runs_db_path
            except Exception:
                # Fallback to default DuckDB file
                db_path = "runs.duckdb"

        self.db_path = Path(db_path)
        self._conn = None
        self._initialized = True

    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup"""
        conn = None
        try:
            if self._conn is None:
                self._conn = duckdb.connect(str(self.db_path))
                self._ensure_schema()
            conn = self._conn
            yield conn
        except Exception as e:
            print(f"Database error: {e}")
            raise

    def _ensure_schema(self):
        """Ensure all required tables exist"""
        with self.get_connection() as conn:
            # Pipeline runs table (existing, enhanced)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP,
                    parser_name VARCHAR,
                    parser_version VARCHAR,
                    provider_name VARCHAR,
                    provider_model VARCHAR,
                    ocr_engine VARCHAR,
                    table_mode VARCHAR,
                    environment VARCHAR,
                    session_label VARCHAR,
                    input_filename VARCHAR,
                    input_size_bytes INTEGER,
                    input_pages INTEGER,
                    output_path VARCHAR,
                    docling_seconds DOUBLE,
                    extractor_seconds DOUBLE,
                    total_seconds DOUBLE,
                    events_extracted INTEGER,
                    citations_found INTEGER,
                    avg_detail_length DOUBLE,
                    status VARCHAR,
                    error_message VARCHAR,
                    config_snapshot JSON,
                    cost_usd DOUBLE,
                    tokens_input INTEGER,
                    tokens_output INTEGER,
                    -- New Flask-specific fields
                    enable_classification BOOLEAN DEFAULT FALSE,
                    classification_model VARCHAR,
                    document_types_extracted INTEGER DEFAULT 0,
                    session_id VARCHAR,
                    user_agent VARCHAR,
                    ip_address VARCHAR
                )
            """)

            # Legal events results table (new)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS legal_events (
                    id INTEGER PRIMARY KEY,
                    run_id VARCHAR NOT NULL,
                    event_number INTEGER,
                    event_date VARCHAR,
                    event_particulars VARCHAR,
                    citation VARCHAR,
                    document_reference VARCHAR,
                    document_type VARCHAR,  -- From classification
                    confidence_score DOUBLE, -- From classification
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
                )
            """)

            # Document processing sessions (new)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_sessions (
                    session_id VARCHAR PRIMARY KEY,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_runs INTEGER DEFAULT 0,
                    total_events INTEGER DEFAULT 0,
                    user_agent VARCHAR,
                    ip_address VARCHAR,
                    status VARCHAR DEFAULT 'active'  -- 'active', 'completed', 'expired'
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_legal_events_run_id ON legal_events(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_timestamp ON pipeline_runs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON processing_sessions(last_activity)")

    def store_processing_result(self, run_id: str, metadata: Dict[str, Any],
                               results_df=None, session_info: Dict[str, Any] = None):
        """Store a complete processing result"""
        with self.get_connection() as conn:
            try:
                # Store enhanced pipeline metadata
                pipeline_data = {
                    'run_id': run_id,
                    'timestamp': metadata.get('timestamp', datetime.now()),
                    'parser_name': metadata.get('extractor', 'docling'),
                    'provider_name': metadata.get('provider', 'langextract'),
                    'provider_model': metadata.get('model'),
                    'input_filename': metadata.get('filename', 'unknown'),
                    'input_size_bytes': metadata.get('file_size'),
                    'events_extracted': metadata.get('events_found', 0),
                    'total_seconds': metadata.get('processing_time'),
                    'status': 'success',
                    'enable_classification': metadata.get('enable_classification', False),
                    'classification_model': metadata.get('classification_model'),
                    'document_types_extracted': metadata.get('document_types_found', 0),
                    'session_id': session_info.get('session_id') if session_info else None,
                    'user_agent': session_info.get('user_agent') if session_info else None,
                    'ip_address': session_info.get('ip_address') if session_info else None,
                }

                # Insert/update pipeline run
                conn.execute("""
                    INSERT OR REPLACE INTO pipeline_runs
                    (run_id, timestamp, parser_name, provider_name, provider_model,
                     input_filename, input_size_bytes, events_extracted, total_seconds,
                     status, enable_classification, classification_model,
                     document_types_extracted, session_id, user_agent, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, list(pipeline_data.values()))

                # Store legal events if provided
                if results_df is not None and not results_df.empty:
                    # Convert DataFrame to records
                    records = results_df.to_dict('records')

                    for record in records:
                        event_data = {
                            'run_id': run_id,
                            'event_number': record.get('No', record.get('number')),
                            'event_date': record.get('Date'),
                            'event_particulars': record.get('Event Particulars'),
                            'citation': record.get('Citation'),
                            'document_reference': record.get('Document Reference'),
                            'document_type': record.get('Document Type'),
                        }

                        conn.execute("""
                            INSERT INTO legal_events
                            (run_id, event_number, event_date, event_particulars,
                             citation, document_reference, document_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, list(event_data.values()))

                # Update session tracking
                if session_info and session_info.get('session_id'):
                    conn.execute("""
                        INSERT OR REPLACE INTO processing_sessions
                        (session_id, last_activity, total_runs, total_events, user_agent, ip_address)
                        VALUES (?, CURRENT_TIMESTAMP,
                               COALESCE((SELECT total_runs FROM processing_sessions WHERE session_id = ?), 0) + 1,
                               COALESCE((SELECT total_events FROM processing_sessions WHERE session_id = ?), 0) + ?,
                               ?, ?)
                    """, [
                        session_info['session_id'],
                        session_info['session_id'],
                        session_info['session_id'],
                        metadata.get('events_found', 0),
                        session_info.get('user_agent'),
                        session_info.get('ip_address')
                    ])

                conn.commit()
                return True

            except Exception as e:
                print(f"Error storing result: {e}")
                conn.rollback()
                return False

    def get_processing_result(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a processing result by run ID"""
        with self.get_connection() as conn:
            try:
                # Get pipeline metadata
                pipeline_result = conn.execute("""
                    SELECT * FROM pipeline_runs WHERE run_id = ?
                """, [run_id]).fetchone()

                if not pipeline_result:
                    return None

                # Get legal events
                events_result = conn.execute("""
                    SELECT * FROM legal_events
                    WHERE run_id = ?
                    ORDER BY event_number
                """, [run_id]).fetchall()

                return {
                    'metadata': dict(pipeline_result),
                    'events': [dict(row) for row in events_result]
                }

            except Exception as e:
                print(f"Error retrieving result: {e}")
                return None

    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics"""
        with self.get_connection() as conn:
            try:
                result = conn.execute("""
                    SELECT * FROM processing_sessions WHERE session_id = ?
                """, [session_id]).fetchone()

                return dict(result) if result else None

            except Exception as e:
                print(f"Error getting session stats: {e}")
                return None

    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """Clean up old sessions and their associated data"""
        with self.get_connection() as conn:
            try:
                # Mark old sessions as expired
                conn.execute("""
                    UPDATE processing_sessions
                    SET status = 'expired'
                    WHERE last_activity < (CURRENT_TIMESTAMP - INTERVAL ? HOURS)
                    AND status = 'active'
                """, [max_age_hours])

                # Optionally delete expired data (uncomment if needed)
                # conn.execute("""
                #     DELETE FROM legal_events
                #     WHERE run_id IN (
                #         SELECT pr.run_id FROM pipeline_runs pr
                #         JOIN processing_sessions ps ON pr.session_id = ps.session_id
                #         WHERE ps.status = 'expired'
                #     )
                # """)

                conn.commit()
                return True

            except Exception as e:
                print(f"Error cleaning up sessions: {e}")
                return False

# Global instance
results_store = ResultsStore()

def get_results_store() -> ResultsStore:
    """Get the global results store instance"""
    return results_store
