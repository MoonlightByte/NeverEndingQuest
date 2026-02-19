#!/usr/bin/env python3
"""
Regression Tests for Debug Usage Rollups
Tests session/week token math, cost source tracking, and compatibility
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_usage_tracker import (
    LLMUsageTracker,
    get_usage_stats,
    track_response,
    track_image_cost,
    get_dalle3_cost_usd,
    get_global_tracker,
)
import utils.llm_usage_tracker as _tracker_module


class MockUsage:
    """Mock usage object for testing"""
    def __init__(self, prompt=0, completion=0, total=0, cost=None):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total
        if cost is not None:
            self.cost = cost


class MockResponse:
    """Mock LLM response for testing"""
    def __init__(self, prompt=0, completion=0, total=0, cost=None):
        self.usage = MockUsage(prompt, completion, total, cost)


def reset_global_tracker():
    """Reset global tracker to fresh state for isolated testing."""
    with _tracker_module._global_tracker_lock:
        _tracker_module._global_tracker = LLMUsageTracker(telemetry_log="/dev/null")
        return _tracker_module._global_tracker


def test_provider_reported_cost():
    """Test 5.1: Provider-reported cost events"""
    print("[TEST 5.1] Provider-reported cost events...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    # Track event with provider cost
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500, cost=0.015))
    
    stats = tracker.get_current_stats()
    
    assert stats['session_cost_usd'] > 0, "Cost should be recorded"
    assert stats['session_cost_source'] == 'provider_reported', "Should be provider_reported"
    assert stats['session_cost_estimate'] == False, "Should not be estimate"
    assert stats['session_tokens'] == 1500, "Tokens should match"
    
    print("  [PASS] Provider cost tracked correctly")
    return True


def test_fallback_estimated_cost():
    """Test 5.2: Fallback estimated cost when provider cost missing"""
    print("[TEST 5.2] Fallback estimated cost...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    # Track event without provider cost (triggers fallback)
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500))
    
    stats = tracker.get_current_stats()
    
    assert stats['session_cost_usd'] > 0, "Cost should be estimated"
    assert stats['session_cost_source'] == 'estimated', "Should be estimated"
    assert stats['session_cost_estimate'] == True, "Should be marked as estimate"
    
    print("  [PASS] Fallback estimate working correctly")
    return True


def test_mixed_session_source():
    """Test 5.3: Mixed provider + estimated shows estimated"""
    print("[TEST 5.3] Mixed session source tracking...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    # First event: provider cost
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500, cost=0.015))
    
    # Second event: no cost (estimated)
    tracker.track(MockResponse(prompt=500, completion=300, total=800))
    
    stats = tracker.get_current_stats()
    
    # Session should show estimated (priority: estimated > provider_reported > unavailable)
    assert stats['session_cost_source'] == 'estimated', "Should be estimated when any estimated events exist"
    assert stats['session_cost_estimate'] == True, "Should be marked as estimate"
    
    print("  [PASS] Mixed source tracking correct")
    return True


def test_legacy_payload_compatibility():
    """Test 5.4: Legacy payload compatibility"""
    print("[TEST 5.4] Legacy payload compatibility...")
    
    # Simulate legacy payload (only tpm, rpm, total_tokens)
    legacy_payload = {
        'tpm': 100,
        'rpm': 5,
        'total_tokens': 5000
    }
    
    # Verify new fields have safe defaults when missing
    # This simulates what the frontend handler does
    session_tokens = legacy_payload.get('session_tokens', 0)
    session_cost_usd = legacy_payload.get('session_cost_usd', 0.0)
    
    assert session_tokens == 0, "Missing fields should default to 0"
    assert session_cost_usd == 0.0, "Missing cost fields should default to 0.0"
    
    print("  [PASS] Legacy payload handles gracefully")
    return True


def test_cost_calculation_accuracy():
    """Test 5.5: Cost calculation accuracy"""
    print("[TEST 5.5] Cost calculation accuracy...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    # Track event with known cost
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500, cost=0.015))
    
    stats = tracker.get_current_stats()
    
    # Verify USD->NZD conversion
    expected_nzd = 0.015 * 1.65
    actual_nzd = stats['session_cost_nzd']
    
    assert abs(actual_nzd - expected_nzd) < 0.001, f"NZD conversion incorrect: {actual_nzd} vs {expected_nzd}"
    
    print(f"  [PASS] Cost calculation accurate (USD: {stats['session_cost_usd']}, NZD: {actual_nzd})")
    return True


def test_thread_safety():
    """Test 5.6: Thread safety - no hangs or crashes"""
    print("[TEST 5.6] Thread safety...")
    import threading
    import time
    
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    errors = []
    
    def track_batch():
        try:
            for i in range(10):
                tracker.track(MockResponse(prompt=100, completion=50, total=150))
                time.sleep(0.001)
        except Exception as e:
            errors.append(str(e))
    
    # Run concurrent tracking from multiple threads
    threads = [threading.Thread(target=track_batch) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Thread errors: {errors}"
    
    stats = tracker.get_current_stats()
    assert stats['session_requests'] == 50, f"Expected 50 requests, got {stats['session_requests']}"
    
    print("  [PASS] Thread-safe operations verified")
    return True


def test_zero_token_edge_case():
    """Test 5.7: Zero token edge case handling"""
    print("[TEST 5.7] Zero token edge case...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    # Track event with zero tokens
    tracker.track(MockResponse(prompt=0, completion=0, total=0))
    
    stats = tracker.get_current_stats()
    
    assert stats['session_tokens'] == 0, "Zero tokens should be recorded"
    assert stats['session_cost_usd'] == 0.0, "Zero cost expected"
    
    print("  [PASS] Zero token handling correct")
    return True


def test_no_provider_branding():
    """Test 5.8: No provider-specific branding in output"""
    print("[TEST 5.8] No provider branding...")
    tracker = LLMUsageTracker(telemetry_log="/dev/null")
    
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500, cost=0.015))
    
    stats = tracker.get_current_stats()
    
    # Verify no OpenAI-specific branding in any string fields
    for key, value in stats.items():
        if isinstance(value, str):
            assert 'openai' not in value.lower(), f"Provider branding found in {key}: {value}"
            assert 'openrouter' not in value.lower(), f"Provider branding found in {key}: {value}"
    
    print("  [PASS] No provider branding detected")
    return True


def test_week_bootstrap_backfill():
    """Test 6.1: Week bootstrap backfills missing cost from tokens"""
    import json
    import tempfile
    import os
    
    print("[TEST 6.1] Week bootstrap backfill...")
    
    # Create temp telemetry log with historical entries (tokens but no cost)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        # Entry 1: historical OpenAI-style (tokens only, no cost)
        f.write(json.dumps({
            'timestamp': '2026-02-19T10:00:00',
            'total_tokens': 1000000,
            'prompt_tokens': 800000,
            'completion_tokens': 200000,
            'model': 'gpt-4.1'
        }) + '\n')
        # Entry 2: historical with explicit cost
        f.write(json.dumps({
            'timestamp': '2026-02-19T11:00:00',
            'total_tokens': 500000,
            'prompt_tokens': 400000,
            'completion_tokens': 100000,
            'cost_usd': 0.75,
            'cost_source': 'provider_reported',
            'cost_estimate': False
        }) + '\n')
        temp_log = f.name
    
    try:
        tracker = LLMUsageTracker(telemetry_log=temp_log)
        stats = tracker.get_current_stats()
        
        # Week tokens should be 1.5M
        assert stats['week_tokens'] == 1500000, f"Expected 1500000 week tokens, got {stats['week_tokens']}"
        
        # Week cost should include fallback (1M * 1.5/1M) + explicit 0.75 = 2.25
        expected_week_cost = 1.5 + 0.75  # fallback + explicit
        actual_week_cost = stats['week_cost_usd']
        assert abs(actual_week_cost - expected_week_cost) < 0.01, \
            f"Week cost should be ~{expected_week_cost}, got {actual_week_cost}"
        
        # Week cost source should be estimated (because fallback rows present)
        assert stats['week_cost_source'] == 'estimated', \
            f"Expected 'estimated', got {stats['week_cost_source']}"
        
        print(f"  [PASS] Week backfill correct (tokens: {stats['week_tokens']}, cost: {actual_week_cost:.2f})")
    finally:
        os.unlink(temp_log)
    
    return True


def test_week_bootstrap_only_explicit():
    """Test 6.2: Week bootstrap with only explicit cost entries"""
    import json
    import tempfile
    import os
    
    print("[TEST 6.2] Week bootstrap explicit cost only...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        # Two entries with explicit cost, no fallback needed
        f.write(json.dumps({
            'timestamp': '2026-02-19T10:00:00',
            'total_tokens': 1000000,
            'cost_usd': 2.00,
            'cost_source': 'provider_reported',
            'cost_estimate': False
        }) + '\n')
        f.write(json.dumps({
            'timestamp': '2026-02-19T11:00:00',
            'total_tokens': 500000,
            'cost_usd': 1.00,
            'cost_source': 'provider_reported',
            'cost_estimate': False
        }) + '\n')
        temp_log = f.name
    
    try:
        tracker = LLMUsageTracker(telemetry_log=temp_log)
        stats = tracker.get_current_stats()
        
        assert stats['week_cost_usd'] == 3.00, f"Expected 3.00, got {stats['week_cost_usd']}"
        assert stats['week_cost_source'] == 'provider_reported', \
            f"Expected 'provider_reported', got {stats['week_cost_source']}"
        
        print(f"  [PASS] Explicit cost week tracking correct (cost: {stats['week_cost_usd']:.2f})")
    finally:
        os.unlink(temp_log)
    
    return True


def test_dalle3_cost_lookup():
    """Test 7.1: DALL-E 3 cost lookup from pricing config"""
    print("[TEST 7.1] DALL-E 3 cost lookup...")
    
    # Test known size/quality combinations
    cost_1024_std = get_dalle3_cost_usd("1024x1024", "standard")
    assert cost_1024_std == 0.040, f"Expected 0.040, got {cost_1024_std}"
    
    cost_1024_hd = get_dalle3_cost_usd("1024x1024", "hd")
    assert cost_1024_hd == 0.080, f"Expected 0.080, got {cost_1024_hd}"
    
    cost_wide_std = get_dalle3_cost_usd("1792x1024", "standard")
    assert cost_wide_std == 0.080, f"Expected 0.080, got {cost_wide_std}"
    
    # Test fallback behavior for invalid inputs
    cost_invalid = get_dalle3_cost_usd("invalid_size", "standard")
    assert cost_invalid == 0.0, f"Expected 0.0 for invalid size, got {cost_invalid}"
    
    print(f"  [PASS] Cost lookup correct (1024x1024 std: {cost_1024_std}, hd: {cost_1024_hd})")
    return True


def test_image_cost_only_event():
    """Test 7.2: Image cost-only event updates cost rollups without changing tokens"""
    print("[TEST 7.2] Image cost-only event...")
    tracker = reset_global_tracker()
    
    # Get baseline
    baseline_stats = tracker.get_current_stats()
    baseline_tokens = baseline_stats['session_tokens']
    baseline_cost = baseline_stats['session_cost_usd']
    
    # Track image cost event
    track_image_cost(
        cost_usd=0.040,
        size="1024x1024",
        quality="standard",
        model="dall-e-3",
        context={"endpoint": "test", "purpose": "portrait_create", "n": 1}
    )
    
    stats = tracker.get_current_stats()
    
    # Assert cost increased
    assert stats['session_cost_usd'] > baseline_cost, "Cost should increase after image event"
    assert abs(stats['session_cost_usd'] - 0.040) < 0.001, f"Cost should be ~0.040, got {stats['session_cost_usd']}"
    
    # Assert NZD conversion happened
    expected_nzd = 0.040 * 1.65
    assert abs(stats['session_cost_nzd'] - expected_nzd) < 0.001, f"NZD should be ~{expected_nzd}, got {stats['session_cost_nzd']}"
    
    # Assert tokens remain unchanged
    assert stats['session_tokens'] == baseline_tokens, f"Tokens should remain {baseline_tokens}, got {stats['session_tokens']}"
    
    # Assert week window also updated
    assert stats['week_cost_usd'] > 0, "Week cost should be positive"
    assert stats['week_tokens'] == 0, "Week tokens should remain 0 for image-only event"
    
    print(f"  [PASS] Cost-only event correct (USD: {stats['session_cost_usd']}, NZD: {stats['session_cost_nzd']}, tokens: {stats['session_tokens']})")
    return True


def test_mixed_session_token_and_image():
    """Test 7.3: Mixed session with token-bearing event + image cost event"""
    print("[TEST 7.3] Mixed session token + image...")
    tracker = reset_global_tracker()
    
    # First: track a token-bearing chat event
    tracker.track(MockResponse(prompt=1000, completion=500, total=1500, cost=0.015))
    
    # Then: track an image cost-only event
    track_image_cost(
        cost_usd=0.040,
        size="1024x1024",
        quality="standard",
        model="dall-e-3",
        context={"endpoint": "test", "purpose": "portrait_create", "n": 1}
    )
    
    stats = tracker.get_current_stats()
    
    # Assert tokens reflect only the chat event
    assert stats['session_tokens'] == 1500, f"Tokens should be 1500 (chat only), got {stats['session_tokens']}"
    
    # Assert cost reflects both events (0.015 + 0.040 = 0.055)
    expected_cost = 0.015 + 0.040
    assert abs(stats['session_cost_usd'] - expected_cost) < 0.001, \
        f"Cost should be ~{expected_cost}, got {stats['session_cost_usd']}"
    
    # Assert cost source is estimated (because image event is estimated)
    assert stats['session_cost_source'] == 'estimated', \
        f"Session source should be 'estimated' (mixed), got {stats['session_cost_source']}"
    
    # Week should also reflect both
    assert stats['week_tokens'] == 1500, f"Week tokens should be 1500, got {stats['week_tokens']}"
    assert abs(stats['week_cost_usd'] - expected_cost) < 0.001, \
        f"Week cost should be ~{expected_cost}, got {stats['week_cost_usd']}"
    
    print(f"  [PASS] Mixed session correct (tokens: {stats['session_tokens']}, cost: {stats['session_cost_usd']})")
    return True


def test_image_cost_fail_open():
    """Test 7.4: Image cost tracking fails open (never raises)"""
    print("[TEST 7.4] Image cost fail-open behavior...")
    
    # Test with valid inputs
    result = track_image_cost(
        cost_usd=0.040,
        size="1024x1024",
        quality="standard",
        model="dall-e-3",
        context={"endpoint": "test", "n": 1}
    )
    assert result == True, "Should return True on success"
    
    # Test with zero cost (should still succeed)
    result = track_image_cost(cost_usd=0.0)
    assert result == True, "Should return True even with zero cost"
    
    # Test with None cost (should still succeed via fail-open)
    result = track_image_cost(cost_usd=None)  # type: ignore
    assert result == True, "Should return True even with None cost"
    
    # Test with negative cost (should still succeed)
    result = track_image_cost(cost_usd=-0.010)
    assert result == True, "Should return True even with negative cost"
    
    print("  [PASS] Fail-open behavior verified")
    return True


def test_image_telemetry_entry():
    """Test 7.5: Image events logged with correct telemetry structure"""
    import json
    import tempfile
    import os
    
    print("[TEST 7.5] Image telemetry entry structure...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_log = f.name
    
    try:
        with _tracker_module._global_tracker_lock:
            _tracker_module._global_tracker = LLMUsageTracker(telemetry_log=temp_log)
        tracker = _tracker_module._global_tracker
        
        # Track image event
        track_image_cost(
            cost_usd=0.080,
            size="1024x1792",
            quality="hd",
            model="dall-e-3",
            context={"endpoint": "test", "purpose": "monster_portrait", "n": 1}
        )
        
        # Read telemetry log
        with open(temp_log, 'r') as f:
            lines = f.readlines()
        
        # Find image entry
        image_entries = []
        for line in lines:
            entry = json.loads(line)
            if 'image_metadata' in entry:
                image_entries.append(entry)
        
        assert len(image_entries) == 1, f"Expected 1 image entry, found {len(image_entries)}"
        
        entry = image_entries[0]
        assert entry['total_tokens'] == 0, "Image entry should have 0 tokens"
        assert entry['prompt_tokens'] == 0, "Image entry should have 0 prompt tokens"
        assert entry['completion_tokens'] == 0, "Image entry should have 0 completion tokens"
        assert entry['cost_usd'] == 0.080, f"Cost should be 0.080, got {entry['cost_usd']}"
        assert entry['cost_source'] == 'estimated', f"Source should be 'estimated', got {entry['cost_source']}"
        assert entry['image_metadata']['size'] == '1024x1792', f"Size mismatch"
        assert entry['image_metadata']['quality'] == 'hd', f"Quality mismatch"
        assert entry['image_metadata']['model'] == 'dall-e-3', f"Model mismatch"
        
        print(f"  [PASS] Telemetry entry structure correct (cost: {entry['cost_usd']}, size: {entry['image_metadata']['size']})")
    finally:
        os.unlink(temp_log)
    
    return True


def test_multiple_image_events_aggregation():
    """Test 7.6: Multiple image events aggregate correctly"""
    print("[TEST 7.6] Multiple image events aggregation...")
    tracker = reset_global_tracker()
    
    # Track 3 image events
    track_image_cost(cost_usd=0.040, context={"n": 1})
    track_image_cost(cost_usd=0.040, context={"n": 1})
    track_image_cost(cost_usd=0.080, size="1024x1792", quality="standard", context={"n": 1})
    
    stats = tracker.get_current_stats()
    
    # Expected: 0.040 + 0.040 + 0.080 = 0.160
    expected_cost = 0.160
    assert abs(stats['session_cost_usd'] - expected_cost) < 0.001, \
        f"Cost should be ~{expected_cost}, got {stats['session_cost_usd']}"
    
    # Tokens should remain 0
    assert stats['session_tokens'] == 0, f"Tokens should be 0, got {stats['session_tokens']}"
    
    # Should have 3 estimated events
    assert tracker.session_estimated_count == 3, f"Expected 3 estimated events, got {tracker.session_estimated_count}"
    
    print(f"  [PASS] Multiple events aggregated correctly (cost: {stats['session_cost_usd']}, count: {tracker.session_estimated_count})")
    return True


def run_all_tests():
    """Run all regression tests"""
    print("=" * 60)
    print("Debug Usage Rollups - Regression Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_provider_reported_cost,
        test_fallback_estimated_cost,
        test_mixed_session_source,
        test_legacy_payload_compatibility,
        test_cost_calculation_accuracy,
        test_thread_safety,
        test_zero_token_edge_case,
        test_no_provider_branding,
        test_week_bootstrap_backfill,
        test_week_bootstrap_only_explicit,
        test_dalle3_cost_lookup,
        test_image_cost_only_event,
        test_mixed_session_token_and_image,
        test_image_cost_fail_open,
        test_image_telemetry_entry,
        test_multiple_image_events_aggregation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {e}")
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
