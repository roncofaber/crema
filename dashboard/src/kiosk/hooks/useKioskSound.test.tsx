import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { isQuietTime, useKioskSound } from './useKioskSound'
import type { KioskSnapshot } from './useKioskSocket'

function snapshot(state: KioskSnapshot['state'], user: string | null = null): KioskSnapshot {
  return {
    state,
    user,
    brew_count: 0,
    session_brew_time: 0,
    time_remaining: null,
    timeout: null,
    elapsed: null,
    shot_type: 'double',
    decaf: false,
    last_brew_id: null,
    avg_rating: null,
    session_started_at: user ? 100 : null,
    brew_started_at: null,
    hardware: null,
  }
}

const oscillator = {
  type: 'sine',
  frequency: { setValueAtTime: vi.fn() },
  connect: vi.fn(),
  disconnect: vi.fn(),
  start: vi.fn(),
  stop: vi.fn(),
  onended: null,
}
const gain = {
  gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
  connect: vi.fn(),
  disconnect: vi.fn(),
}
const context = {
  state: 'running',
  currentTime: 1,
  destination: {},
  resume: vi.fn().mockResolvedValue(undefined),
  close: vi.fn().mockResolvedValue(undefined),
  createOscillator: vi.fn(() => oscillator),
  createGain: vi.fn(() => gain),
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 10, 10, 12, 0))
  context.state = 'running'
  window.localStorage.clear()
  vi.clearAllMocks()
  vi.stubGlobal('AudioContext', vi.fn(function AudioContext() { return context }))
})

describe('useKioskSound', () => {
  it('defaults off and persists opt-in without replaying the current snapshot', () => {
    const { result, rerender } = renderHook(({ value }) => useKioskSound(value), {
      initialProps: { value: snapshot('idle') },
    })
    expect(result.current.enabled).toBe(false)
    act(() => result.current.toggle())
    expect(JSON.parse(window.localStorage.getItem('crema.kiosk.sound')!).enabled).toBe(true)
    rerender({ value: snapshot('idle') })
    expect(oscillator.start).not.toHaveBeenCalled()
    rerender({ value: snapshot('armed', 'alice') })
    expect(oscillator.start).toHaveBeenCalledOnce()
  })

  it('retries a suspended context when sound is enabled again', () => {
    context.state = 'suspended'
    const { result } = renderHook(({ value }) => useKioskSound(value), {
      initialProps: { value: snapshot('idle') },
    })

    act(() => result.current.toggle())
    expect(context.resume).toHaveBeenCalledOnce()
    act(() => result.current.toggle())
    act(() => result.current.toggle())

    expect(AudioContext).toHaveBeenCalledOnce()
    expect(context.resume).toHaveBeenCalledTimes(2)
  })

  it('supports overnight quiet hours and treats equal boundaries as unscheduled', () => {
    const quiet = { enabled: true, start: '22:00', end: '07:00' }
    expect(isQuietTime(new Date(2026, 10, 10, 22, 0), quiet)).toBe(true)
    expect(isQuietTime(new Date(2026, 10, 11, 6, 59), quiet)).toBe(true)
    expect(isQuietTime(new Date(2026, 10, 11, 7, 0), quiet)).toBe(false)
    expect(isQuietTime(new Date(2026, 10, 10, 12, 0), quiet)).toBe(false)
    expect(isQuietTime(new Date(2026, 10, 10, 23, 0), { ...quiet, end: '22:00' })).toBe(false)
  })

  it('suppresses new cues during quiet hours and persists schedule changes', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 10, 23, 0))
    const { result, rerender } = renderHook(({ value }) => useKioskSound(value), {
      initialProps: { value: snapshot('idle') },
    })
    act(() => result.current.toggle())
    rerender({ value: snapshot('armed', 'alice') })
    expect(oscillator.start).not.toHaveBeenCalled()

    act(() => result.current.setQuietHours({ enabled: false, start: '01:00', end: '03:00' }))
    expect(JSON.parse(window.localStorage.getItem('crema.kiosk.sound')!).quietHours).toEqual({
      enabled: false, start: '01:00', end: '03:00',
    })
    rerender({ value: snapshot('idle') })
    rerender({ value: snapshot('armed', 'alice') })
    expect(oscillator.start).toHaveBeenCalledOnce()
  })

  it('restores the preference, cues a new brew, and closes audio on unmount', () => {
    window.localStorage.setItem('crema.kiosk.sound', 'on')
    const brewing = { ...snapshot('brewing', 'alice'), last_brew_id: null }
    const completed = { ...snapshot('armed', 'alice'), last_brew_id: 4 }
    const { unmount, rerender } = renderHook(({ value }) => useKioskSound(value), {
      initialProps: { value: brewing },
    })
    rerender({ value: completed })
    expect(context.createOscillator).toHaveBeenCalledOnce()
    unmount()
    expect(context.close).toHaveBeenCalledOnce()
  })
})
