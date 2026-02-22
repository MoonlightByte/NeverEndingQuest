"""Verify OpenAI and Gemini model access before capture testing.

Tests each model variant with a simple prompt to ensure:
1. Model names are correct
2. API keys work
3. Reasoning effort levels are valid
4. Temperature compatibility is correct
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
import config

print("=" * 70)
print("MODEL VERIFICATION TEST")
print("=" * 70)
print()

client = OpenAI(api_key=config.OPENAI_API_KEY)
test_messages = [{"role": "user", "content": "Say OK"}]

# Test 1: GPT-4.1 baseline (current production)
print("[1/8] Testing gpt-4.1-2025-04-14 (baseline)...")
try:
    response = client.chat.completions.create(
        model="gpt-4.1-2025-04-14",
        messages=test_messages,
        temperature=0.7
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 2: GPT-5.2 with reasoning_effort="none" + temperature
print("[2/8] Testing gpt-5.2 with reasoning_effort='none' + temperature...")
try:
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=test_messages,
        reasoning_effort="none",
        temperature=0.7
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 3: GPT-5.2 with reasoning_effort="low" (no temperature)
print("[3/8] Testing gpt-5.2 with reasoning_effort='low' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=test_messages,
        reasoning_effort="low"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 4: GPT-5.2 with reasoning_effort="medium" (no temperature)
print("[4/10] Testing gpt-5.2 with reasoning_effort='medium' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=test_messages,
        reasoning_effort="medium"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 5: GPT-5.2 with reasoning_effort="high" (no temperature)
print("[5/10] Testing gpt-5.2 with reasoning_effort='high' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=test_messages,
        reasoning_effort="high"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 6: GPT-4.1-mini baseline (current production)
print("[6/10] Testing gpt-4.1-mini-2025-04-14 (baseline)...")
try:
    response = client.chat.completions.create(
        model="gpt-4.1-mini-2025-04-14",
        messages=test_messages
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 7: GPT-5-mini with reasoning_effort="minimal" (no temperature)
print("[7/10] Testing gpt-5-mini with reasoning_effort='minimal' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=test_messages,
        reasoning_effort="minimal"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 8: GPT-5-mini with reasoning_effort="low" (no temperature)
print("[8/10] Testing gpt-5-mini with reasoning_effort='low' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=test_messages,
        reasoning_effort="low"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 9: GPT-5-mini with reasoning_effort="medium" (no temperature)
print("[9/10] Testing gpt-5-mini with reasoning_effort='medium' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=test_messages,
        reasoning_effort="medium"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 10: GPT-5-mini with reasoning_effort="high" (no temperature)
print("[10/10] Testing gpt-5-mini with reasoning_effort='high' (no temp)...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=test_messages,
        reasoning_effort="high"
    )
    print(f"  [OK] Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

# Test 11: Gemini (if API key available)
print("[11/11] Testing gemini-3-flash-preview...")
try:
    if os.path.exists("google_api.pi"):
        from google import genai
        with open("google_api.pi", 'r') as f:
            content = f.read().strip()
            if 'api_key=' in content:
                api_key = content.split('api_key=')[1].strip()
            else:
                api_key = content
        os.environ['GEMINI_API_KEY'] = api_key
        gemini_client = genai.Client()

        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Say OK"
        )
        print(f"  [OK] Response: {response.text}")
    else:
        print("  [SKIP] google_api.pi not found")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
print()

print("=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
