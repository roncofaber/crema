import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { isKioskSnapshot, useKioskSocket } from './useKioskSocket'
import { makeSnapshot } from '../../test/fixtures'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  readonly url: string

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  close = vi.fn(() => {
    this.onclose?.()
  })

  emit(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent)
  }
}

describe('useKioskSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  it('becomes live only after a valid snapshot', () => {
    const { result } = renderHook(() => useKioskSocket())
    const socket = FakeWebSocket.instances[0]

    expect(result.current).toEqual({ snapshot: null, connected: false })
    act(() => socket.emit(null))
    expect(result.current).toEqual({ snapshot: null, connected: false })

    const snapshot = makeSnapshot()
    act(() => socket.emit(snapshot))
    expect(result.current).toEqual({ snapshot, connected: true })
    expect(isKioskSnapshot(snapshot)).toBe(true)
  })

  it('closes stale streams and discards messages from the previous socket', () => {
    const { result } = renderHook(() => useKioskSocket())
    const first = FakeWebSocket.instances[0]
    const firstSnapshot = makeSnapshot()
    act(() => first.emit(firstSnapshot))
    expect(result.current.connected).toBe(true)

    act(() => vi.advanceTimersByTime(5000))
    expect(first.close).toHaveBeenCalledOnce()
    expect(result.current).toEqual({ snapshot: firstSnapshot, connected: false })

    act(() => vi.advanceTimersByTime(2000))
    const second = FakeWebSocket.instances[1]
    expect(second).toBeDefined()
    act(() => first.emit(makeSnapshot()))
    expect(result.current.snapshot).toEqual(firstSnapshot)

    const current = makeSnapshot({ state: 'idle', user: null })
    act(() => second.emit(current))
    expect(result.current).toEqual({ snapshot: current, connected: true })
  })

  it('retries after the server closes an unavailable connection', () => {
    const { result } = renderHook(() => useKioskSocket())
    const first = FakeWebSocket.instances[0]

    act(() => first.onerror?.())
    expect(result.current).toEqual({ snapshot: null, connected: false })
    act(() => vi.advanceTimersByTime(1999))
    expect(FakeWebSocket.instances).toHaveLength(1)
    act(() => vi.advanceTimersByTime(1))
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
