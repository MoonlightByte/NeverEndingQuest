import { useEffect, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs } from '../../stores'
import type { ClientEvents } from '../../contract/events'

type ProviderValue = ClientEvents['set_model_provider']['provider']

const PROVIDER_OPTIONS: Array<{ value: ProviderValue; label: string }> = [
  { value: 'legacy', label: 'Legacy (GPT-4.1) - Stable baseline' },
  { value: 'openai', label: 'OpenAI (GPT-5.x) - Next-gen, tested per task' },
  { value: 'gemini', label: 'Gemini 3.1 - Alternative provider, tested per task' },
  { value: 'lmstudio', label: 'Local / Custom Server (LM Studio, Ollama, OpenRouter...)' },
]

const PROVIDER_HINTS: Record<ProviderValue, string> = {
  legacy: 'Legacy (GPT-4.1): stable baseline, recommended. Uses your OpenAI API key.',
  openai: 'OpenAI (GPT-5.x): next-gen cloud, tested per task. Uses your OpenAI API key.',
  gemini: 'Gemini 3.1: alternative cloud provider, tested per task. Requires a Google API key.',
  lmstudio:
    'Local / Custom Server: point at any OpenAI-compatible server below. Zero cost when local.',
}

const inputClass = 'neq-settings-select-parity'
const smallButtonClass = 'neq-settings-button-small-parity'
const sectionClass = 'neq-settings-section'
const sectionTitleClass = 'neq-settings-title'

type TestTone = 'pending' | 'ok' | 'fail'
const TONE_COLORS: Record<TestTone, string> = {
  pending: '#888',
  ok: '#2e7d32',
  fail: '#c62828',
}

function isProviderValue(value: string): value is ProviderValue {
  return PROVIDER_OPTIONS.some((o) => o.value === value)
}

function LocalProviderPanelBody() {
  const settings = useDialogs((s) => s.settings)

  // Sync all provider state from the server when the panel mounts.
  useEffect(() => {
    emitC('get_model_provider', undefined)
    emitC('get_local_endpoint', undefined)
    emitC('get_openai_key', undefined)
    emitC('get_gemini_key', undefined)
  }, [])

  // ---- provider select (server confirms via provider_changed) ----
  const [pendingProvider, setPendingProvider] = useState<ProviderValue | null>(null)
  useEffect(() => {
    setPendingProvider(null)
  }, [settings.provider])
  useEffect(() => {
    if (pendingProvider === null) return undefined
    // A persistence/validation failure is reported through the global error
    // channel, not provider_changed. Avoid leaving the selector permanently
    // disabled when no confirmation can arrive.
    const timer = window.setTimeout(() => setPendingProvider(null), 10000)
    return () => window.clearTimeout(timer)
  }, [pendingProvider])

  const storedProvider = settings.provider ?? 'legacy'
  const provider: string = pendingProvider ?? storedProvider

  const changeProvider = (value: string) => {
    if (!isProviderValue(value)) return
    setPendingProvider(value)
    emitC('set_model_provider', { provider: value })
  }

  // ---- local endpoint form (blank api_key keeps the stored key) ----
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [localApiKey, setLocalApiKey] = useState('')
  useEffect(() => {
    const ep = settings.localEndpoint
    if (ep) {
      setBaseUrl(ep.base_url)
      setModel(ep.model)
    }
  }, [settings.localEndpoint])

  const saveLocalEndpoint = () => {
    emitC('set_local_endpoint', { base_url: baseUrl, model, api_key: localApiKey })
    setLocalApiKey('') // never keep the secret in the DOM; blank keeps the stored key
  }

  // ---- endpoint test probe ----
  const [testing, setTesting] = useState(false)
  const [testStatus, setTestStatus] = useState<{ text: string; tone: TestTone } | null>(null)
  useEffect(() => {
    if (!testing) return
    const timer = window.setTimeout(() => {
      setTesting(false)
      setTestStatus({ text: 'No test response received. Check your connection and try again.', tone: 'fail' })
    }, 30000)
    return () => window.clearTimeout(timer)
  }, [testing])
  useEffect(() => {
    const res = settings.endpointTest
    if (!res) return
    setTesting(false)
    setTestStatus({ text: `${res.ok ? 'PASS' : 'FAIL'}: ${res.detail}`, tone: res.ok ? 'ok' : 'fail' })
  }, [settings.endpointTest])

  const runEndpointTest = () => {
    if (!baseUrl.trim()) {
      setTestStatus({ text: 'Please enter a Server URL first.', tone: 'fail' })
      return
    }
    setTesting(true)
    setTestStatus({ text: 'Testing connection...', tone: 'pending' })
    emitC('test_local_endpoint', { base_url: baseUrl, model, api_key: localApiKey })
  }

  // ---- API keys (blank submit keeps the stored key server-side) ----
  const [openaiKey, setOpenaiKey] = useState('')
  const [geminiKey, setGeminiKey] = useState('')

  const saveOpenaiKey = () => {
    emitC('set_openai_key', { api_key: openaiKey })
    setOpenaiKey('')
  }
  const saveGeminiKey = () => {
    emitC('set_gemini_key', { api_key: geminiKey })
    setGeminiKey('')
  }

  const keyStatusText = (hasKey: boolean | null) =>
    hasKey === null ? '' : hasKey ? ' (a key is set)' : ' (no key set)'

  return (
    <div>
      <div className={sectionClass}>
        <div className={sectionTitleClass}>AI Provider</div>
        <div className="neq-settings-item neq-settings-provider-item-parity">
          <div className="neq-settings-provider-row-parity">
            <label htmlFor="model-provider-select">Provider</label>
            <select
              id="model-provider-select"
              className={inputClass}
              value={provider}
              disabled={pendingProvider !== null}
              onChange={(e) => changeProvider(e.target.value)}
            >
              {PROVIDER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        <p className="neq-settings-help-parity neq-settings-provider-help-parity">
          {isProviderValue(provider)
            ? PROVIDER_HINTS[provider]
            : 'Models are selected per-task based on quality testing.'}
        </p>
        </div>
      </div>

      {provider === 'lmstudio' && (
        <div className={sectionClass}>
          <div className={sectionTitleClass}>Local / Custom Server</div>
          <p className="neq-settings-help-parity">
            Point at any OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenRouter, or a
            remote host). Leave blank to use the default local server at localhost:1234.
          </p>
          <div className="neq-settings-item neq-settings-stack-parity">
          <label htmlFor="local-base-url">Server URL</label>
          <input
            id="local-base-url"
            type="text"
            className={inputClass}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:1234/v1"
          />
          <label htmlFor="local-model">
            Model name (optional)
          </label>
          <input
            id="local-model"
            type="text"
            className={inputClass}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g. local-model or an OpenRouter model id"
          />
          <label htmlFor="local-api-key">
            API key (optional)
          </label>
          <input
            id="local-api-key"
            type="password"
            className={inputClass}
            value={localApiKey}
            onChange={(e) => setLocalApiKey(e.target.value)}
            placeholder={
              settings.localEndpoint?.has_key
                ? '(saved - leave blank to keep)'
                : 'leave blank for local servers'
            }
            autoComplete="off"
          />
          <div className="neq-settings-button-row-parity">
            <button type="button" className={smallButtonClass} onClick={saveLocalEndpoint}>
              Save
            </button>
            <button
              type="button"
              className={smallButtonClass}
              onClick={runEndpointTest}
              disabled={testing}
            >
              Test Connection
            </button>
          </div>
          {testStatus && (
            <p
              className="neq-settings-status-parity"
              style={{ color: TONE_COLORS[testStatus.tone] }}
              role="status"
            >
              {testStatus.text}
            </p>
          )}
          </div>
        </div>
      )}

      <div className={sectionClass}>
        <div className={sectionTitleClass}>OpenAI API Key</div>
        <p className="neq-settings-help-parity">
          Needed for the Legacy and OpenAI providers. Stored locally on this machine.
          <span>{keyStatusText(settings.openaiHasKey)}</span>
        </p>
        <div className="neq-settings-item neq-settings-stack-parity"><input
          type="password"
          aria-label="OpenAI API key"
          className={inputClass}
          value={openaiKey}
          onChange={(e) => setOpenaiKey(e.target.value)}
          placeholder="sk-..."
          autoComplete="off"
        />
        <button type="button" className={smallButtonClass} onClick={saveOpenaiKey}>
          Save Key
        </button></div>
      </div>

      {provider === 'gemini' && (
        <div className={`${sectionClass} neq-settings-gemini-section-parity`}>
          <div className={sectionTitleClass}>Gemini API Key</div>
          <p className="neq-settings-help-parity">
            Needed for the Gemini provider. Stored locally on this machine. Get a key at
            https://aistudio.google.com/apikey
            <span>{keyStatusText(settings.geminiHasKey)}</span>
          </p>
          <div className="neq-settings-item neq-settings-stack-parity"><input
            type="password"
            aria-label="Gemini API key"
            className={inputClass}
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder="AIza..."
            autoComplete="off"
          />
          <button type="button" className={smallButtonClass} onClick={saveGeminiKey}>
            Save Key
          </button></div>
        </div>
      )}
    </div>
  )
}

/**
 * Local-edition operator settings (plan 4.4f): provider select emitting
 * set_model_provider, endpoint/key forms with blank-keeps-stored semantics, and
 * a test_local_endpoint probe. Hidden entirely in the hosted edition.
 */
export function LocalProviderPanel() {
  if (import.meta.env.VITE_EDITION === 'hosted') return null
  return <LocalProviderPanelBody />
}
