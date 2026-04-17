#!/usr/bin/env python3
"""
Module Toolkit Launcher
Launches the web interface with the module toolkit enabled
"""

import os
import sys
import webbrowser
import time
import subprocess
import socket
from pathlib import Path

def check_port(port=5000):
    """Check if a port is available"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except:
            return False

def main():
    """Launch the module toolkit web interface"""
    print("=" * 60)
    print("NeverEndingQuest Module Toolkit")
    print("=" * 60)
    print()
    
    # The web interface runs on port 8357 by default
    # We'll just open the toolkit page on the existing server
    port = 8357
    
    # Check if the main game server is already running
    if not check_port(port):
        # Server is running (port is in use), just open the toolkit page
        print(f"[INFO] Game server is already running on port {port}")
        print(f"[INFO] Opening toolkit interface at: http://localhost:{port}/toolkit")
        webbrowser.open(f'http://localhost:{port}/toolkit')
        return
    
    # If server is not running, we need to start it
    print("[INFO] Game server not running. Starting web interface...")
    
    # Ensure required directories exist
    dirs_to_create = [
        'graphic_packs',
        'graphic_packs/default_photorealistic/monsters/images',
        'graphic_packs/default_photorealistic/monsters/videos', 
        'graphic_packs/default_photorealistic/monsters/thumbnails',
        'data/bestiary',
        'data/styles',
        'templates'
    ]
    
    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Check for required files
    if not Path('data/bestiary/monster_compendium.json').exists():
        print("[WARNING] Monster compendium not found. Some features may be limited.")
    
    if not Path('data/styles/style_templates.json').exists():
        print("[WARNING] Style templates not found. Using default styles.")
    
    print("[INFO] Starting web server on port 8357...")
    print(f"[INFO] The toolkit will be available at: http://localhost:{port}/toolkit")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    # Start the web interface
    try:
        # Launch in subprocess so we can control it better
        process = subprocess.Popen(
            [sys.executable, 'web/web_interface.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Open browser to toolkit page
        print(f"[INFO] Opening browser to http://localhost:{port}/toolkit")
        webbrowser.open(f'http://localhost:{port}/toolkit')
        
        # Stream output from the process
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down toolkit server...")
        if 'process' in locals():
            process.terminate()
            process.wait()
        print("[INFO] Server stopped.")
    except Exception as e:
        print(f"[ERROR] Failed to start toolkit: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())