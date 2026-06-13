# LM Studio Setup Guide

Run NeverEndingQuest using your local LM Studio instead of OpenAI's API. This
eliminates API costs and lets you run the game completely offline with
open-source models.

## Overview

NeverEndingQuest now talks to LM Studio **directly** through LM Studio's built-in
OpenAI-compatible server. There is no proxy and no library patching -- you simply
select the `lmstudio` provider and the game routes every API call to your local
server.

```
NeverEndingQuest --(MODEL_PROVIDER="lmstudio")--> http://localhost:1234/v1 (LM Studio server)
```

> NOTE: The old proxy-based approach (`openai_patcher.py`, `lmstudio_forwarder.py`,
> `start_lmstudio_proxy.bat`, `run_with_lmstudio.bat`, `launch_lmstudio_mode.bat`,
> mitmproxy) has been **removed**. It is no longer needed.

## Quick Start

1. **Set up LM Studio**
   - Download and install [LM Studio](https://lmstudio.ai/).
   - Load a model (e.g. Mistral 7B, Llama 3.1 8B, or similar).
   - Open the **Local Server** tab and click **Start Server**.
   - Verify it says the server is running on port **1234**.

2. **Select the LM Studio provider**

   Edit `model_config.py` and set:
   ```python
   MODEL_PROVIDER = "lmstudio"
   ```
   (Default is `"legacy"`, which uses the OpenAI GPT-4.1 API.)

3. **Run the game normally**
   ```bash
   python run_web.py      # web interface (recommended)
   # or
   python main.py         # terminal mode
   ```

That's it. All AI calls now go to your local model.

## Optional: custom endpoint / model

By default the game connects to `http://localhost:1234/v1` and lets each callsite
keep its own model name. To override, add a `user_settings.json` at the repo root:

```json
{
  "local_base_url": "http://localhost:1234/v1",
  "local_api_key": "lm-studio",
  "local_model": "your-loaded-model-name"
}
```

- `local_base_url` -- change if LM Studio runs on a different host/port.
- `local_model` -- if set (non-empty), this single model is used for **all**
  callsites. Leave empty (`""`) to keep each callsite's configured model string.

These are read at call time by `model_config.get_local_endpoint()`, so changes
take effect on the next API call.

## Notes & Tips

- **Performance:** local models are slower than the cloud APIs. A GPU with enough
  VRAM for your chosen model is strongly recommended.
- **Quality:** smaller local models may struggle with the strict JSON output the
  game expects. If you see malformed responses, try a larger / more capable model.
- **Switching back:** set `MODEL_PROVIDER = "legacy"` (GPT-4.1) or `"openai"` /
  `"gemini"` to use a cloud provider again.
- **Cost:** running on LM Studio incurs **zero** API cost.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Connection refused / timeouts | Confirm LM Studio's server is started and listening on port 1234. |
| Game still hits OpenAI | Confirm `MODEL_PROVIDER = "lmstudio"` is actually set in `model_config.py`. |
| Garbled / non-JSON responses | Use a larger model; some small models can't hold the output format. |
| Wrong model used | Set `local_model` in `user_settings.json` to your loaded model's name. |
