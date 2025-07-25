# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Configuration for chunked conversation compression
"""

# Chunked compression settings
COMPRESSION_TRIGGER = 12  # Number of location summaries to trigger compression
CHUNK_SIZE = 6           # Number of transitions to compress in each chunk
ENABLE_AUTO_COMPRESSION = True  # Enable automatic compression on location transitions

# Backup settings
CREATE_BACKUPS = True    # Create backups before compression
BACKUP_RETENTION_DAYS = 30  # How long to keep old backups

# File settings
CONVERSATION_FILE = "modules/conversation_history/conversation_history.json"  # Main conversation history file