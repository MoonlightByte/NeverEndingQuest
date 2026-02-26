#!/usr/bin/env python3
"""Clean up stale SESSION RESUME RECAP messages from conversation history."""
import json
from pathlib import Path

def clean_history(filepath):
    """Remove all messages containing 'SESSION RESUME RECAP ONLY' from a JSON file."""
    p = Path(filepath)
    if not p.exists():
        print(f"[INFO] File not found: {filepath}")
        return
    
    data = json.loads(p.read_text(encoding='utf-8'))
    clean_data = [m for m in data if "SESSION RESUME RECAP ONLY" not in m.get("content", "")]
    
    removed = len(data) - len(clean_data)
    if removed > 0:
        p.write_text(json.dumps(clean_data, indent=2), encoding='utf-8')
        print(f"[CLEANED] {filepath}: {len(data)} -> {len(clean_data)} messages (removed {removed} stale recaps)")
    else:
        print(f"[OK] {filepath}: No stale recap messages found")

if __name__ == "__main__":
    # Clean both conversation_history and chat_history
    clean_history('/Users/zeug/Projects/NeverEndingQuest/modules/conversation_history/conversation_history.json')
    clean_history('/Users/zeug/Projects/NeverEndingQuest/modules/conversation_history/chat_history.json')
