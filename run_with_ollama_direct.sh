#!/usr/bin/env bash
# Run NeverEndingQuest with Ollama (Direct Connection - No Proxy)
#
# The game sends hardcoded OpenAI model names in every request. LM Studio
# ignores them; Ollama validates them and 404s unknown tags. This launcher
# creates two Ollama aliases on first run that both point at a single
# user-chosen model -- matching LM Studio's single-model behavior and
# avoiding VRAM thrashing between tiers.

set -euo pipefail
cd "$(dirname "$0")"

readonly ALIAS_FULL="gpt-4.1-2025-04-14"
readonly ALIAS_MINI="gpt-4.1-mini-2025-04-14"

echo
echo "========================================================================"
echo "NEVERENDINGQUEST - OLLAMA MODE (DIRECT)"
echo "========================================================================"
echo

# --- Prerequisite 1: config.py must exist ------------------------------------
# Every callsite does OpenAI(api_key=config.OPENAI_API_KEY). Import fails
# before any Ollama request if config.py is missing.
if [ ! -f config.py ]; then
    echo "[ERROR] config.py not found. Copy the template first:"
    echo "    cp config_template.py config.py"
    echo "Ollama ignores the OPENAI_API_KEY value, but the file must exist."
    exit 1
fi

# --- Prerequisite 2: Ollama CLI + daemon --------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
    echo "[ERROR] ollama CLI not found on PATH. Install from https://ollama.com/download"
    exit 1
fi
if ! curl -sf --connect-timeout 3 --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "[ERROR] Ollama daemon is not reachable on localhost:11434."
    echo "Start it with 'ollama serve' (Linux) or open the Ollama app (macOS)."
    exit 1
fi

# --- Helper: match a model name in `ollama list` ------------------------------
# `ollama list` prints names as either "name" or "name:tag". Use awk equality
# (not regex) to avoid metacharacter pitfalls with dots/colons in user tags.
_ollama_has_model() {
    local target="$1"
    ollama list | awk -v t="$target" '
        NR > 1 {
            if ($1 == t) { found = 1; exit }
            if ($1 == t ":latest") { found = 1; exit }
            if (index($1, t ":") == 1) { found = 1; exit }
        }
        END { exit !found }
    '
}

# --- Alias setup -------------------------------------------------------------
# Normally: create aliases only if missing. If OLLAMA_MODEL is set, treat it
# as an explicit override and (re)point the aliases to that model even if
# they already exist.
_aliases_present() {
    _ollama_has_model "$ALIAS_FULL" && _ollama_has_model "$ALIAS_MINI"
}

if [ -n "${OLLAMA_MODEL:-}" ]; then
    source_model="$OLLAMA_MODEL"
    if ! _ollama_has_model "$source_model"; then
        echo "[ERROR] OLLAMA_MODEL='$source_model' is not pulled."
        echo "Run: ollama pull $source_model"
        exit 1
    fi
    echo "[INFO] OLLAMA_MODEL set; re-pointing aliases at '$source_model'."
    ollama cp "$source_model" "$ALIAS_FULL"
    ollama cp "$source_model" "$ALIAS_MINI"
    echo "[INFO] Aliases updated."
elif _aliases_present; then
    echo "[INFO] Aliases already present; skipping setup."
else
    echo "[INFO] Ollama aliases missing. Creating them now..."

    # Candidates = column 1 of `ollama list`, excluding header and the
    # two alias names themselves (so re-runs don't count them).
    # Portable to bash 3.2 (macOS default) -- no `mapfile`.
    candidates=()
    while IFS= read -r _name; do
        [ -n "$_name" ] && candidates+=("$_name")
    done < <(ollama list | awk -v a="$ALIAS_FULL" -v b="$ALIAS_MINI" '
        NR > 1 {
            name = $1
            # Strip :latest suffix for dedupe comparisons only
            base = name
            sub(/:latest$/, "", base)
            if (base == a || name == a) next
            if (base == b || name == b) next
            print name
        }')
    if [ "${#candidates[@]}" -eq 0 ]; then
        echo "[ERROR] No Ollama models are pulled."
        echo "Pull one first, e.g.: ollama pull llama3.1:8b-instruct-q4_K_M"
        exit 1
    elif [ "${#candidates[@]}" -gt 1 ]; then
        echo "[ERROR] Multiple models pulled; can't auto-pick."
        echo "Set OLLAMA_MODEL to one of the following and re-run:"
        printf "  %s\n" "${candidates[@]}"
        exit 1
    fi
    source_model="${candidates[0]}"

    echo "[INFO] Using '$source_model' for both full and mini tiers."
    ollama cp "$source_model" "$ALIAS_FULL"
    ollama cp "$source_model" "$ALIAS_MINI"
    echo "[INFO] Aliases created."
fi

# --- Launch ------------------------------------------------------------------
echo "[INFO] Redirecting OpenAI SDK to Ollama (localhost:11434)..."
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"

PYTHON_BIN="${PYTHON:-python3}"
"$PYTHON_BIN" run_web.py
