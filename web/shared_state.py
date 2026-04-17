#!/usr/bin/env python3
"""
Shared State Module - Centralized location for cross-module shared objects.
This prevents circular dependencies and ensures single instances.
"""

import queue

# Single, shared queue for module creation progress
module_progress_queue = queue.Queue()

print("[SHARED STATE] Module progress queue initialized")