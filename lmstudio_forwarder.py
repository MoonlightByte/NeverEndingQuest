#!/usr/bin/env python3
"""
LM Studio API Forwarder Proxy
Redirects OpenAI API calls from the game to your local LM Studio server

CONFIGURATION:
1. Make sure LM Studio is running with a loaded model
2. Check LM Studio's server port (default: 1234)
3. Adjust LM_STUDIO_PORT below if needed
4. Run this script in one terminal, then run the game in another
"""

import json
import time
from datetime import datetime
from pathlib import Path
from mitmproxy import http

# ============================================================================
# CONFIGURATION - Adjust these settings for your setup
# ============================================================================
LM_STUDIO_HOST = "localhost"
LM_STUDIO_PORT = 1234  # LM Studio's default port - change if different
CAPTURE_LOGS = True    # Set to False to disable logging
LOG_DIRECTORY = "lmstudio_logs"

# ============================================================================

class LMStudioForwarder:
    def __init__(self):
        self.lm_studio_url = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}/v1/"

        if CAPTURE_LOGS:
            self.capture_dir = Path(LOG_DIRECTORY)
            self.capture_dir.mkdir(exist_ok=True)

            # Create new capture file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.capture_file = self.capture_dir / f"lmstudio_capture_{timestamp}.jsonl"
            self.log_file = self.capture_dir / "lmstudio_forwarder.log"
        else:
            self.capture_file = None
            self.log_file = None

        print("=" * 70)
        print("LM STUDIO FORWARDER - Ready")
        print("=" * 70)
        print(f"Forwarding to: {self.lm_studio_url}")
        print(f"Listening on:  http://localhost:8080")
        if CAPTURE_LOGS:
            print(f"Logging to:    {self.capture_file}")
        print("=" * 70)
        print()
        print("Waiting for game requests...")
        print()

        if self.log_file:
            self._log(f"LM Studio Forwarder started - {timestamp}")
            self._log(f"Target: {self.lm_studio_url}")

    def request(self, flow: http.HTTPFlow) -> None:
        """Intercept requests to localhost:8080 and forward to LM Studio"""
        if flow.request.url.startswith("http://localhost:8080/v1/"):
            # Change the request to go to LM Studio
            flow.request.url = flow.request.url.replace(
                "http://localhost:8080/v1/",
                self.lm_studio_url
            )
            flow.request.host = LM_STUDIO_HOST
            flow.request.port = LM_STUDIO_PORT
            flow.request.scheme = "http"

            print(f"[>>] Forwarding to LM Studio: {flow.request.path}")
            if self.log_file:
                self._log(f"Forwarding request to LM Studio: {flow.request.path}")

    def response(self, flow: http.HTTPFlow) -> None:
        """Capture responses from LM Studio"""
        if LM_STUDIO_HOST in flow.request.host:
            try:
                print(f"[<<] Response from LM Studio: {flow.response.status_code}")

                # Only capture if logging is enabled
                if not CAPTURE_LOGS or not self.capture_file:
                    return

                # Build capture entry
                capture_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request": {
                        "method": flow.request.method,
                        "url": flow.request.url,
                        "path": flow.request.path,
                        "headers": dict(flow.request.headers),
                        "body": None
                    },
                    "response": {
                        "status_code": flow.response.status_code,
                        "headers": dict(flow.response.headers),
                        "body": None
                    }
                }

                # Parse request body
                if flow.request.content:
                    try:
                        capture_entry["request"]["body"] = json.loads(flow.request.content.decode('utf-8'))
                    except:
                        capture_entry["request"]["body"] = flow.request.content.decode('utf-8', errors='ignore')

                # Parse response body
                if flow.response.content:
                    try:
                        capture_entry["response"]["body"] = json.loads(flow.response.content.decode('utf-8'))
                    except:
                        capture_entry["response"]["body"] = flow.response.content.decode('utf-8', errors='ignore')

                # Write to JSONL file
                with open(self.capture_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(capture_entry) + '\n')

                # Log key info
                if flow.request.path.startswith("/v1/chat/completions"):
                    req_body = capture_entry["request"]["body"]
                    resp_body = capture_entry["response"]["body"]

                    model = req_body.get("model", "unknown") if isinstance(req_body, dict) else "unknown"

                    # LM Studio responses may have different structure than OpenAI
                    if isinstance(resp_body, dict):
                        tokens = resp_body.get("usage", {}).get("total_tokens", 0)
                        if tokens == 0:
                            # Some models don't report tokens
                            tokens = "unknown"
                    else:
                        tokens = "unknown"

                    self._log(f"Captured chat completion - Model: {model}, Tokens: {tokens}")

            except Exception as e:
                error_msg = f"Error capturing response: {e}"
                print(f"[ERROR] {error_msg}")
                if self.log_file:
                    self._log(error_msg)

    def _log(self, message: str):
        """Write to log file"""
        if not self.log_file:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} - {message}\n"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)


# Create addon instance
addons = [LMStudioForwarder()]
