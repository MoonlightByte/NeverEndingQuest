# Ollama Setup Guide

Run NeverEndingQuest using your local [Ollama](https://ollama.com) installation instead of OpenAI's API. No API costs, no network dependency after pulling a model, and full offline play.

**Status: EXPERIMENTAL.** NeverEndingQuest's prompts are tuned for GPT-4/GPT-4.1. Local models may produce malformed JSON or incorrect combat decisions — see *Known Issues* below.

## How It Works

```
NeverEndingQuest -> Ollama (port 11434)
```

Direct connection, zero overhead. The launcher sets `OPENAI_BASE_URL` so the OpenAI Python SDK talks to Ollama's OpenAI-compatible endpoint instead of `api.openai.com`.

The game's source code contains two hardcoded OpenAI model identifiers (`gpt-4.1-2025-04-14` for heavy calls and `gpt-4.1-mini-2025-04-14` for light ones). LM Studio ignores these and serves whatever you've loaded — effectively single-model. Ollama **validates** the identifier, so the launcher creates two Ollama aliases on first run, both pointing at the same user-chosen model. Single model, no VRAM thrashing, LM-Studio-equivalent behavior.

## Prerequisites

1. **`config.py` must exist.** Every API callsite in NeverEndingQuest is coded as `OpenAI(api_key=config.OPENAI_API_KEY)`. If the file is missing, the game crashes on import before talking to Ollama. Ollama ignores the key value, but the file is mandatory:

   ```bash
   cp config_template.py config.py
   ```

   Leave the placeholder key in place or put any non-empty string — it's sent to Ollama and discarded.

2. **Ollama 0.4 or newer.** Earlier versions lack reliable function/tool calling on the OpenAI-compatible endpoint, which silently breaks combat and validation. Check with `ollama --version`.

## 1. Install Ollama

Download from [ollama.com/download](https://ollama.com/download). On macOS/Windows the installer starts the daemon automatically; on Linux, start it with `ollama serve` (as a systemd unit for persistent setups).

Verify:
```bash
curl http://localhost:11434/api/tags
```
Expected: JSON response (possibly `{"models":[]}` if nothing is pulled yet).

## 2. Pull One Model

Pick exactly one model — the same model will handle both the game's heavy and light calls. Recommended:

| Model tag                               | Notes                              |
|-----------------------------------------|------------------------------------|
| `llama3.1:8b-instruct-q4_K_M`           | 128K context, ~5 GB disk/VRAM      |
| `mistral:7b-instruct-q4_K_M`            | 32K context, ~4 GB disk/VRAM       |
| `mistral-nemo:12b-instruct-q4_K_M`      | 128K context, stronger prose       |

Example:
```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

You can pull more than one and pick between them with the `OLLAMA_MODEL` env var (see *Switching models* below). But the **active** game session will always use a single model, just like LM Studio.

## 3. Launch the Game

- **Windows:** double-click `run_with_ollama_direct.bat`
- **macOS / Linux:** `./run_with_ollama_direct.sh`

On **first run** the launcher:
1. Verifies `config.py` and the Ollama daemon
2. Finds your pulled model (or uses `$OLLAMA_MODEL` if set)
3. Creates the aliases `gpt-4.1-2025-04-14` and `gpt-4.1-mini-2025-04-14`, both pointing at your model
4. Starts the web server on `http://localhost:8357`

On **subsequent runs** the launcher sees the aliases already exist and jumps straight to step 4.

If you've pulled more than one model, the launcher refuses to guess and prints the list. Pick one:

```bash
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M ./run_with_ollama_direct.sh
```

## Switching Models

```bash
ollama pull <new-tag>
ollama rm gpt-4.1-2025-04-14 gpt-4.1-mini-2025-04-14
./run_with_ollama_direct.sh   # recreates aliases against whatever is pulled
```

Or force a specific model without deleting aliases first:

```bash
OLLAMA_MODEL=<new-tag> ./run_with_ollama_direct.sh
```

When `OLLAMA_MODEL` is set, the launcher re-points both aliases at the specified model even if they already exist — no `ollama rm` needed.

## Verifying It Works

1. Open `http://localhost:8357`
2. Start a new game and take any action
3. Watch the Ollama log: requests should hit `POST /v1/chat/completions`
4. If you see a 404 for `gpt-4.1-2025-04-14`, the alias didn't land — check `ollama list` and re-run the launcher

## Known Issues

**Ollama-specific (not LM Studio):**
- **Image generation is broken.** Ollama has no `/v1/images/generations` endpoint. NPC/monster portrait generation from the toolkit will 404.
- **Text-to-speech is broken.** Ollama has no `/v1/audio/speech` endpoint. Disable TTS in the UI before starting a session.
- **Function/tool calling requires Ollama 0.4+.** Older versions produce free-form text instead of JSON action structures and break combat silently.

**Shared with LM Studio:**
- JSON parsing errors in combat with smaller models (try `q5_K_M` quantization or a larger model)
- Inconsistent action detection vs GPT-4
- Slow response on CPU-only systems
- `@TAG` compression notation is sometimes ignored

## Troubleshooting

| Symptom                                              | Fix                                                      |
|------------------------------------------------------|----------------------------------------------------------|
| `connection refused: localhost:11434`                | Start Ollama (`ollama serve` / open the app)             |
| `No Ollama models are pulled`                        | `ollama pull <tag>` and re-run the launcher              |
| `Multiple models pulled; can't auto-pick`            | Set `OLLAMA_MODEL=<tag>` and re-run                      |
| `OLLAMA_MODEL='X' is not pulled`                     | Typo or missing pull — check `ollama list`               |
| `model 'gpt-4.1-2025-04-14' not found` at runtime    | Aliases were deleted externally — re-run the launcher    |
| Combat actions fail silently                         | Try a larger quantization or compare with LM Studio      |

## Configuration Reference

- **Endpoint:** `http://localhost:11434/v1` (set by launcher via `OPENAI_BASE_URL`)
- **Aliases:** `gpt-4.1-2025-04-14` and `gpt-4.1-mini-2025-04-14` (both point at your chosen model)
- **Override source model:** set `OLLAMA_MODEL` before running the launcher
- **Compression:** enabled by default in `model_config.py` (`COMPRESSION_ENABLED = True`)
