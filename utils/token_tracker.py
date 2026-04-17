#!/usr/bin/env python3
"""
Token and Request Tracking System for OpenAI API Usage
Tracks TPM (Tokens Per Minute) and RPM (Requests Per Minute)
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import deque
import threading

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    # Don't print warning here as it might interfere with web output capture
    pass

class TokenTracker:
    """Track OpenAI API token usage with TPM and RPM calculations"""
    
    def __init__(self):
        # Token tracking
        self.total_tokens_sent = 0
        self.total_tokens_received = 0
        self.total_tokens = 0
        
        # TPM/RPM tracking with sliding window (last 60 seconds)
        self.token_history = deque()  # List of (timestamp, tokens) tuples
        self.request_history = deque()  # List of timestamps
        self.window_size = 60  # 60 seconds for per-minute calculations
        
        # Session tracking
        self.session_start = datetime.now()
        self.total_requests = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Initialize tiktoken encoder if available
        self.encoder = None
        if TIKTOKEN_AVAILABLE:
            try:
                # Use cl100k_base encoding (GPT-4 and newer models)
                self.encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # Silently handle encoder initialization failures
                # Don't print warnings that might interfere with web output capture
                pass
    
    def track_request(self):
        """Track a request being made"""
        with self.lock:
            now = datetime.now()
            self.request_history.append(now)
            self.total_requests += 1
            self._clean_history()
    
    def track_response(self, response_data: Dict) -> Dict:
        """Track tokens from OpenAI response"""
        with self.lock:
            usage = {}
            
            if isinstance(response_data, dict):
                # Extract usage data from response
                if "usage" in response_data:
                    usage = response_data["usage"]
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    
                    # Update totals
                    self.total_tokens_sent += prompt_tokens
                    self.total_tokens_received += completion_tokens
                    self.total_tokens += total_tokens
                    
                    # Add to history for TPM calculation
                    now = datetime.now()
                    self.token_history.append((now, total_tokens))
                    
                    # Clean old entries
                    self._clean_history()
            
            return usage
    
    def _clean_history(self):
        """Remove entries older than window_size seconds"""
        cutoff = datetime.now() - timedelta(seconds=self.window_size)
        
        # Clean token history
        while self.token_history and self.token_history[0][0] < cutoff:
            self.token_history.popleft()
        
        # Clean request history
        while self.request_history and self.request_history[0] < cutoff:
            self.request_history.popleft()
    
    def get_current_tpm(self) -> int:
        """Calculate current tokens per minute rate"""
        with self.lock:
            self._clean_history()
            
            if not self.token_history:
                return 0
            
            # Sum tokens in the window
            total_tokens = sum(tokens for _, tokens in self.token_history)
            
            # Calculate time span
            if len(self.token_history) == 1:
                # Only one entry, extrapolate
                return int(total_tokens * (60.0 / self.window_size))
            
            time_span = (self.token_history[-1][0] - self.token_history[0][0]).total_seconds()
            if time_span == 0:
                return 0
            
            # Calculate TPM
            return int((total_tokens / time_span) * 60.0)
    
    def get_current_rpm(self) -> int:
        """Calculate current requests per minute rate"""
        with self.lock:
            self._clean_history()
            
            if not self.request_history:
                return 0
            
            # Count requests in window
            request_count = len(self.request_history)
            
            if request_count == 1:
                # Only one entry, extrapolate
                return int(request_count * (60.0 / self.window_size))
            
            time_span = (self.request_history[-1] - self.request_history[0]).total_seconds()
            if time_span == 0:
                return 0
            
            # Calculate RPM
            return int((request_count / time_span) * 60.0)
    
    def get_stats(self) -> Dict:
        """Get current usage statistics"""
        with self.lock:
            runtime = (datetime.now() - self.session_start).total_seconds()
            
            return {
                "tpm": self.get_current_tpm(),
                "rpm": self.get_current_rpm(),
                "total_tokens": self.total_tokens,
                "total_requests": self.total_requests,
                "tokens_sent": self.total_tokens_sent,
                "tokens_received": self.total_tokens_received,
                "session_minutes": int(runtime / 60)
            }
    
    def get_display_string(self) -> str:
        """Get formatted string for display"""
        stats = self.get_stats()
        return f"TPM: {stats['tpm']:,} | RPM: {stats['rpm']} | Total: {stats['total_tokens']:,} tokens"


# Global tracker instance
_tracker = None

def get_tracker() -> TokenTracker:
    """Get or create the global token tracker"""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker

def track_openai_request():
    """Track an OpenAI request"""
    tracker = get_tracker()
    tracker.track_request()

def track_openai_response(response) -> Dict:
    """Track OpenAI response and return usage data"""
    tracker = get_tracker()
    
    # Handle both raw dict and OpenAI response objects
    if hasattr(response, 'model_dump'):
        response_dict = response.model_dump()
    elif hasattr(response, 'to_dict'):
        response_dict = response.to_dict()
    elif hasattr(response, '__dict__'):
        response_dict = response.__dict__
    else:
        response_dict = response
    
    return tracker.track_response(response_dict)

def get_usage_display() -> str:
    """Get usage display string for UI"""
    tracker = get_tracker()
    return tracker.get_display_string()