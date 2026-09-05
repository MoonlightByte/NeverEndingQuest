// Test-only settings protocol. Real persistence is covered by the Python suite.
// Store presence flags only: never retain keys entered into this mock process.
export function createProviderFixture() {
  let provider, endpoint, openai, gemini, rejectNext
  const reset = () => {
    provider = 'legacy'
    endpoint = { base_url: 'http://localhost:1234/v1', model: '', has_key: false }
    openai = false
    gemini = false
    rejectNext = false
  }
  reset()
  return {
    reset,
    reject: () => { rejectNext = true },
    attach(socket) {
      socket.on('get_model_provider', () => socket.emit('provider_changed', { provider }))
      socket.on('set_model_provider', data => {
        if (rejectNext) { rejectNext = false; socket.emit('error', { message: 'Fixture: settings write rejected' }); return }
        if (!['legacy', 'openai', 'gemini', 'lmstudio'].includes(data.provider)) {
          socket.emit('error', { message: 'Fixture: invalid provider' }); return
        }
        provider = data.provider
        socket.emit('provider_changed', { provider })
      })
      socket.on('get_local_endpoint', () => socket.emit('local_endpoint_changed', endpoint))
      socket.on('set_local_endpoint', data => {
        endpoint = { base_url: data.base_url || 'http://localhost:1234/v1', model: data.model || '', has_key: endpoint.has_key || Boolean(data.api_key?.trim()) }
        socket.emit('local_endpoint_changed', endpoint)
      })
      socket.on('get_openai_key', () => socket.emit('openai_key_status', { has_key: openai }))
      socket.on('set_openai_key', data => { openai ||= Boolean(data.api_key?.trim()); socket.emit('openai_key_status', { has_key: openai }) })
      socket.on('get_gemini_key', () => socket.emit('gemini_key_status', { has_key: gemini }))
      socket.on('set_gemini_key', data => { gemini ||= Boolean(data.api_key?.trim()); socket.emit('gemini_key_status', { has_key: gemini }) })
      socket.on('test_local_endpoint', data => {
        const ok = data.base_url === 'http://127.0.0.1:9999/v1'
        socket.emit('local_endpoint_test_result', { ok, detail: ok ? 'Fixture endpoint responded.' : 'Fixture endpoint unavailable.' })
      })
    },
  }
}
