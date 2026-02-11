# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""
NeverEndingQuest Core Engine - World Observer
Copyright (c) 2024 MoonlightByte

The "World Observer" is the surveillance layer that records verified game events
into an immutable "Block Universe" ledger (SQLite). It serves as the source of truth
for the EGO System (Evaluator/Guardian Observer) to detect hallucinations.
"""

import sqlite3
import threading
import queue
import json
import os
import time
from datetime import datetime
from utils.enhanced_logger import debug, info, warning, error, set_script_name

set_script_name(__name__)

class WorldObserver:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WorldObserver, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db_path = "data/world_surveillance.db"
        self.event_queue = queue.Queue()
        self.running = True
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._init_db()
        
        # Start background worker
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
        self._initialized = True
        info("WorldObserver initialized - Surveillance System Online", category="world_observer")

    def _init_db(self):
        """Initialize the SQLite database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Track A: The Block Universe (Mechanical Truth)
            # Stores every verified state change in the system
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    turn_id INTEGER,
                    track TEXT,           -- 'MECHANICAL' or 'NARRATIVE'
                    event_type TEXT,      -- 'COMBAT', 'MOVEMENT', 'INVENTORY', 'NARRATIVE_EMIT'
                    actor TEXT,
                    action TEXT,
                    value TEXT,
                    raw_content TEXT,
                    metadata JSON
                )
            ''')
            
            # Indices for performance queries by EGO Analyst
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_timestamp ON event_log(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_actor ON event_log(actor)')
            
            # Surveillance Log (EGO Output)
            # Where the Analyst records Divergence reports
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS surveillance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    severity TEXT,        -- 'DRIFT', 'DISTORTION', 'HALLUCINATION'
                    analysis TEXT,
                    correction_vector TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            error(f"Failed to initialize database: {e}", category="world_observer")

    def record_event(self, track, event_type, actor, action, value=None, raw_content=None, metadata=None):
        """
        Public API to record an event.
        Non-blocking: pushes to queue to avoid impacting game loop performance.
        
        Args:
            track (str): 'MECHANICAL' (Hard Truth) or 'NARRATIVE' (Soft Truth)
            event_type (str): Category of event
            actor (str): Who performed the action
            action (str): What happened
            value (str, optional): Quantitative value (damage amount, gold count)
            raw_content (str, optional): Full text description
            metadata (dict, optional): Additional context
        """
        try:
            event = {
                'track': track,
                'event_type': event_type,
                'actor': actor,
                'action': action,
                'value': str(value) if value is not None else None,
                'raw_content': raw_content,
                'metadata': json.dumps(metadata) if metadata else None,
                'timestamp': datetime.now().isoformat()
            }
            self.event_queue.put(event)
        except Exception as e:
            error(f"Failed to queue event: {e}", category="world_observer")

    def _process_queue(self):
        """Background worker to write events to DB."""
        while self.running:
            try:
                # Get event with timeout to allow checking self.running
                event = self.event_queue.get(timeout=1.0)
                self._write_event(event)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                error(f"Error in WorldObserver worker thread: {e}", category="world_observer")

    def _write_event(self, event):
        """Write a single event to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO event_log (timestamp, track, event_type, actor, action, value, raw_content, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event['timestamp'],
                event['track'],
                event['event_type'],
                event['actor'],
                event['action'],
                event['value'],
                event['raw_content'],
                event['metadata']
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            error(f"Failed to write event to DB: {e}", category="world_observer")

    def shutdown(self):
        """Clean shutdown of the worker thread."""
        self.running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
            info("WorldObserver shutdown complete", category="world_observer")

# Global accessor pattern
_observer = None

def get_world_observer():
    """Get the singleton instance of WorldObserver"""
    global _observer
    if _observer is None:
        _observer = WorldObserver()
    return _observer
