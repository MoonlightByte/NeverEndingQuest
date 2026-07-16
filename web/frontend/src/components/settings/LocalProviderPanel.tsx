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

const inputClass =
  'w-full rounded border-2 border-card bg-page px-2 py-1 font-chrome text-sm text-primary ' +
  'outline-none focus:border-accent'
const smallButtonClass =
  'cursor-pointer rounded border-2 border-card bg-panel px-3 py-1 font-chrome text-xs ' +
  'text-primary hover:border-soft disabled:cursor-not-allowed disabled:opacity-50'
const sectionClass = 'mt-3 border-t-2 border-card pt-3'
const sectionTitleClass = 'font-display text-xs uppercase tracking-wide text-secondary'

type TestTone = 'pending' | 'ok' | 'fail'
const TONE_COLORS: Record<TestTone, string> = {
  pending: 'var(--text-secondary)',
  ok: 'var(--accent)',
  fail: '#e74c3c',
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
    <div className="font-chrome text-sm">
      <div className={sectionClass}>
        <div className={sectionTitleClass}>AI Provider</div>
        <label htmlFor="model-provider-select" className="mt-2 block text-xs text-secondary">
          Provider
        </label>
        <select
          id="model-provider-select"
          className={`${inputClass} mt-1`}
          value={provider}
          disabled={pendingProvider !== null}
          onChange={(e) => changeProvider(e.target.value)}
        >
          {PROVIDER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-secondary">
          {isProviderValue(provider)
            ? PROVIDER_HINTS[provider]
            : 'Models are selected per-task based on quality testing.'}
        </p>
      </div>

      {provider === 'lmstudio' && (
        <div className={sectionClass}>
          <div className={sectionTitleClass}>Local / Custom Server</div>
          <p className="mt-1 text-xs text-secondary">
            Point at any OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenRouter, or a
            remote host). Leave blank to use the default local server at localhost:1234.
          </p>
          <label htmlFor="local-base-url" className="mt-2 block text-xs text-secondary">
            Server URL
          </label>
          <input
            id="local-base-url"
            type="text"
            className={`${inputClass} mt-1`}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:1234/v1"
          />
          <label htmlFor="local-model" className="mt-2 block text-xs text-secondary">
            Model name (optional)
          </label>
          <input
            id="local-model"
            type="text"
            className={`${inputClass} mt-1`}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g. local-model or an OpenRouter model id"
          />
          <label htmlFor="local-api-key" className="mt-2 block text-xs text-secondary">
            API key (optional)
          </label>
          <input
            id="local-api-key"
            type="password"
            className={`${inputClass} mt-1`}
            value={localApiKey}
            onChange={(e) => setLocalApiKey(e.target.value)}
            placeholder={
              settings.localEndpoint?.has_key
                ? '(saved - leave blank to keep)'
                : 'leave blank for local servers'
            }
            autoComplete="off"
          />
          <div className="mt-2 flex gap-2">
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
              className="mt-2 font-log text-xs"
              style={{ color: TONE_COLORS[testStatus.tone] }}
              role="status"
            >
              {testStatus.text}
            </p>
          )}
        </div>
      )}

      <div className={sectionClass}>
        <div className={sectionTitleClass}>OpenAI API Key</div>
        <p className="mt-1 text-xs text-secondary">
          Needed for the Legacy and OpenAI providers. Stored locally on this machine. Leave
          blank to keep the stored key.
          <span>{keyStatusText(settings.openaiHasKey)}</span>
        </p>
        <input
          type="password"
          aria-label="OpenAI API key"
          className={`${inputClass} mt-2`}
          value={openaiKey}
          onChange={(e) => setOpenaiKey(e.target.value)}
          placeholder="sk-..."
          autoComplete="off"
        />
        <button type="button" className={`${smallButtonClass} mt-2`} onClick={saveOpenaiKey}>
          Save Key
        </button>
      </div>

      {provider === 'gemini' && (
        <div className={sectionClass}>
          <div className={sectionTitleClass}>Gemini API Key</div>
          <p className="mt-1 text-xs text-secondary">
            Needed for the Gemini provider. Stored locally on this machine. Get a key at
            https://aistudio.google.com/apikey. Leave blank to keep the stored key.
            <span>{keyStatusText(settings.geminiHasKey)}</span>
          </p>
          <input
            type="password"
            aria-label="Gemini API key"
            className={`${inputClass} mt-2`}
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder="AIza..."
            autoComplete="off"
          />
          <button type="button" className={`${smallButtonClass} mt-2`} onClick={saveGeminiKey}>
            Save Key
          </button>
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
