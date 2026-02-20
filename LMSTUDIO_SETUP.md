# LM Studio Setup Guide

Run NeverEndingQuest using your local LM Studio instead of OpenAI's API. This eliminates API costs and allows you to run the game completely offline with open-source models!

## Overview

NeverEndingQuest supports two connection methods:

### Method 1: Direct Connection (Recommended - Simple & Fast)
```
NeverEndingQuest → LM Studio (port 1234)
```
Direct connection with zero overhead. This is the easiest and fastest method.

### Method 2: Proxy Connection (Advanced - For Debugging)
```
NeverEndingQuest → mitmproxy (port 8080) → LM Studio (port 1234)
```
Routes through a proxy for request/response logging. Use this for troubleshooting.

## Quick Start (Windows)

### ✨ Method 1: Direct Connection (RECOMMENDED)

1. **Setup LM Studio:**
   - Download and install [LM Studio](https://lmstudio.ai/)
   - Load a model (recommended: Mistral 7B, Llama 3.1 8B, or similar)
   - Click "Start Server" in the Local Server tab (bottom-right)
   - Verify it says "Server running on port 1234"

2. **Launch the game:**
   - Double-click `run_with_lmstudio_direct.bat`
   - Start playing!

**That's it!** No proxy setup, no mitmproxy installation. Just LM Studio + the game.

---

### Method 2: Proxy Connection (Advanced)

**Use this method if you need to:**
- Debug API calls
- Log requests and responses
- Troubleshoot model compatibility issues

**Setup:**

1. **Setup LM Studio** (same as Method 1 above)

2. **Install mitmproxy:**
   ```bash
   pip install mitmproxy
   ```

3. **Choose your launch style:**

   **Option A: One-Click Launch**
   - Double-click `launch_lmstudio_mode.bat`
   - Two windows will open automatically
   - Logs saved to `lmstudio_logs/`

   **Option B: Manual Launch**
   - Terminal 1: Run `start_lmstudio_proxy.bat` (starts proxy)
   - Terminal 2: Run `run_with_lmstudio.bat` (starts game)

## Prerequisites

### Method 1 (Direct) - Required Software

1. **LM Studio** - [Download here](https://lmstudio.ai/)
   - Free local LLM runtime
   - Windows, Mac, or Linux

2. **Python 3.8+** - Already installed if you can run NeverEndingQuest

### Method 2 (Proxy) - Additional Requirements

3. **mitmproxy** - Install via:
   ```bash
   pip install mitmproxy
   ```
   Only needed for the advanced proxy method.

### Recommended Models for NeverEndingQuest

Good models to try (available in LM Studio's model browser):

| Model | Size | Context | Performance | Notes |
|-------|------|---------|-------------|-------|
| **Mistral 7B Instruct** | 7B | 32K | Excellent | Best all-around choice |
| **Llama 3.1 8B Instruct** | 8B | 128K | Excellent | Great for long sessions |
| **Phi-3 Medium** | 14B | 128K | Very Good | Good balance |
| **Mistral Nemo** | 12B | 128K | Excellent | Great storytelling |

**Minimum Requirements:**
- 16GB RAM for 7B models
- 32GB RAM for 13B+ models
- GPU recommended but not required

## Configuration

### Changing LM Studio Port

If your LM Studio runs on a different port (default is 1234):

1. Open `lmstudio_forwarder.py`
2. Find line 20: `LM_STUDIO_PORT = 1234`
3. Change to your port number
4. Save and restart the forwarder

### Disable Logging

To disable request/response logging:

1. Open `lmstudio_forwarder.py`
2. Find line 21: `CAPTURE_LOGS = True`
3. Change to `CAPTURE_LOGS = False`
4. Save and restart

### Advanced: Different LM Studio Host

If running LM Studio on a different machine:

1. Open `lmstudio_forwarder.py`
2. Line 19: Change `LM_STUDIO_HOST = "localhost"` to your IP address
3. Make sure LM Studio's server is set to listen on `0.0.0.0` instead of `localhost`

## How It Works

### Component Breakdown

**1. openai_patcher.py**
- Monkey-patches the OpenAI Python library
- Redirects all API calls to `http://localhost:8080`
- No changes to game code needed!

**2. lmstudio_forwarder.py**
- mitmproxy addon that runs on port 8080
- Intercepts redirected calls
- Forwards them to LM Studio on port 1234
- Optionally logs requests/responses

**3. LM Studio**
- Runs the actual AI model locally
- Provides OpenAI-compatible API on port 1234
- Processes all game prompts

## Troubleshooting

### "mitmproxy is not installed"

**Solution:**
```bash
pip install mitmproxy
```

### "The forwarder proxy does not appear to be running"

**Causes:**
- Forwarder proxy window was closed
- Port 8080 is in use by another application

**Solution:**
1. Make sure `start_lmstudio_proxy.bat` is running in a separate window
2. Check if another program is using port 8080:
   ```bash
   netstat -ano | findstr :8080
   ```

### "Connection refused" or "Cannot connect to LM Studio"

**Causes:**
- LM Studio server is not started
- LM Studio is using a different port
- No model is loaded in LM Studio

**Solution:**
1. Open LM Studio
2. Go to the "Local Server" tab (bottom-right icon)
3. Make sure a model is loaded
4. Click "Start Server"
5. Verify it says "Server running on port 1234"

### Game is slow or responses are weird

**Causes:**
- Model is too small (< 7B parameters)
- Model doesn't follow instructions well
- System prompt is too large for model's context

**Solutions:**
1. Try a different model (Mistral 7B Instruct recommended)
2. Enable compression in NeverEndingQuest's `config.py`
3. Use a model with larger context window (32K+)

### SSL/Certificate errors

**Cause:**
- mitmproxy certificates not trusted

**Solution:**
The forwarder uses `--ssl-insecure` flag, so this shouldn't happen. If it does:
1. Check that `mitm_config/` directory exists
2. Restart the forwarder

## Performance Tips

1. **GPU Acceleration:**
   - LM Studio automatically uses your GPU if available
   - NVIDIA GPUs work best (CUDA support)
   - AMD GPUs work via ROCm
   - Apple Silicon Macs work great with Metal

2. **Model Selection:**
   - Larger models = better quality but slower
   - Smaller models = faster but less creative
   - 7B-8B models are the sweet spot

3. **Context Length:**
   - Enable NeverEndingQuest's compression system
   - Use models with 32K+ context for longer sessions
   - Compression reduces token usage by 70-90%

4. **LM Studio Settings:**
   - In LM Studio's server settings, increase "Max Tokens" to 2048+
   - Adjust temperature (0.7-0.9 works well for D&D)
   - Enable prompt caching if available

## Cost Savings

Running locally with LM Studio eliminates all API costs:

- **OpenAI GPT-4:** ~$0.03-0.06 per 1K tokens
- **LM Studio:** $0.00 (free!)

**Typical Session Costs:**
- 4-hour game session with GPT-4: $5-15
- Same session with LM Studio: $0

**Hardware Investment:**
- One-time cost of GPU (if not already owned)
- RTX 3060 12GB: ~$300 (runs 7B models well)
- RTX 4060 Ti 16GB: ~$500 (runs 13B models well)
- Pays for itself after 20-100 hours of gameplay vs GPT-4

## Logs and Debugging

### Request Logs

If `CAPTURE_LOGS = True` in `lmstudio_forwarder.py`:

- Requests/responses saved to: `lmstudio_logs/lmstudio_capture_TIMESTAMP.jsonl`
- Forwarder activity logged to: `lmstudio_logs/lmstudio_forwarder.log`

### Viewing Logs

```bash
# View latest capture (Windows)
type lmstudio_logs\lmstudio_forwarder.log

# View latest capture (Linux/Mac)
tail -f lmstudio_logs/lmstudio_forwarder.log
```

## Switching Back to OpenAI

To switch back to using OpenAI's API:

1. Close both LM Studio windows (forwarder and game)
2. Run the game normally:
   ```bash
   python run_web.py
   ```

Your `config.py` OpenAI API key will be used automatically.

## Support and Community

- **LM Studio Discord:** [discord.gg/lmstudio](https://discord.gg/lmstudio)
- **NeverEndingQuest Issues:** [GitHub Issues](https://github.com/yourusername/neverendingquest/issues)
- **Model Recommendations:** Check LM Studio's community models

## File Reference

| File | Purpose |
|------|---------|
| `lmstudio_forwarder.py` | Proxy that forwards to LM Studio |
| `openai_patcher.py` | Patches OpenAI library to use proxy |
| `launch_lmstudio_mode.bat` | Master launcher (one-click) |
| `start_lmstudio_proxy.bat` | Start forwarder only |
| `run_with_lmstudio.bat` | Run game only |
| `LMSTUDIO_SETUP.md` | This file |

## Advanced: Linux/Mac Usage

For Linux or Mac users:

**Start the forwarder:**
```bash
chmod +x start_lmstudio_forwarder.sh
./start_lmstudio_forwarder.sh
```

**Run the game:**
```bash
python openai_patcher.py
```

**Create Linux/Mac launcher script:**
```bash
#!/bin/bash
# Terminal 1
gnome-terminal -- bash -c "./start_lmstudio_forwarder.sh; exec bash"
# Terminal 2 (wait 3 seconds)
sleep 3
gnome-terminal -- bash -c "python openai_patcher.py; exec bash"
```

## Credits

This proxy system is based on the `conductor.py` pattern and uses:
- [mitmproxy](https://mitmproxy.org/) - MIT License
- [LM Studio](https://lmstudio.ai/) - Free for personal use
