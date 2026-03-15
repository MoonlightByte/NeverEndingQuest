#!/usr/bin/env python3
"""
OpenAI Library Patcher
Monkey-patches the OpenAI library to redirect all API calls through a local proxy
No game code changes needed!
"""

import sys
import os

# Patch OpenAI to use our local proxy
os.environ['OPENAI_BASE_URL'] = 'http://localhost:8080/v1'

# Import and patch the openai module before anything else uses it
import openai

# Store the original base URL
original_base_url = "https://api.openai.com/v1"

# Monkey patch the client initialization
original_init = openai.OpenAI.__init__

def patched_init(self, *args, **kwargs):
    # Force base_url to our proxy
    kwargs['base_url'] = 'http://localhost:8080/v1'
    # Remove any httpx_client to avoid SSL issues
    kwargs.pop('httpx_client', None)
    kwargs.pop('http_client', None)
    original_init(self, *args, **kwargs)

openai.OpenAI.__init__ = patched_init

# Also patch the module-level client if it exists
if hasattr(openai, 'api_base'):
    openai.api_base = 'http://localhost:8080/v1'

print("[OpenAI Patcher] OpenAI library patched to use localhost:8080")
print("[OpenAI Patcher] All API calls will be redirected through the local proxy")

# Now import and run the actual game
if __name__ == "__main__":
    # Import the game's main module
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from run_web import main
    # Run the game with patched OpenAI
    main()