import { afterEach, describe, expect, it, vi } from 'vitest'

async function loadApi(base?: string) {
  vi.resetModules()
  if (base === undefined) vi.stubEnv('VITE_API_URL', '')
  else vi.stubEnv('VITE_API_URL', base)
  return import('./api')
}

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('API URLs', () => {
  it.each([
    ['http://coffee.example/api/', 'ws://coffee.example/api/ws/kiosk'],
    ['https://coffee.example/api', 'wss://coffee.example/api/ws/kiosk'],
    ['ws://coffee.example/api', 'ws://coffee.example/api/ws/kiosk'],
    ['wss://coffee.example/api', 'wss://coffee.example/api/ws/kiosk'],
  ])('converts %s to the matching WebSocket URL', async (base, expected) => {
    const { kioskWebSocketUrl } = await loadApi(base)
    expect(kioskWebSocketUrl()).toBe(expected)
  })

  it('uses the configured base for REST requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'idle',
      user: null,
      session_started_at: null,
      brew_started_at: null,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { api } = await loadApi('https://coffee.example/api/')

    await api.status()
    expect(fetchMock).toHaveBeenCalledOnce()
    const request = fetchMock.mock.calls[0][0] as Request
    expect(request.url).toBe('https://coffee.example/api/status')
    expect(request.credentials).toBe('include')
  })

  it('uses the current origin by default', async () => {
    const { kioskWebSocketUrl } = await loadApi()
    expect(kioskWebSocketUrl()).toBe(`${window.location.origin.replace(/^http/, 'ws')}/ws/kiosk`)
  })
})
