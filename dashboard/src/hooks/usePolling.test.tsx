import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deferred } from '../test/fixtures'
import { usePolling } from './usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('does not overlap requests and aborts on cleanup', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const fn = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const { result, unmount } = renderHook(() => usePolling(fn, 1000))

    expect(fn).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(5000))
    expect(fn).toHaveBeenCalledTimes(1)

    await act(async () => {
      first.resolve('current')
      await first.promise
    })
    expect(result.current).toEqual({
      data: 'current',
      error: null,
      loading: false,
      stale: false,
    })

    act(() => vi.advanceTimersByTime(1000))
    expect(fn).toHaveBeenCalledTimes(2)
    const signal = fn.mock.calls[1][0] as AbortSignal
    unmount()
    expect(signal.aborted).toBe(true)

    await act(async () => {
      second.resolve('late')
      await second.promise
    })
    expect(result.current.data).toBe('current')
  })

  it('retains stale data on failure and clears errors after recovery', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const third = deferred<string>()
    const fn = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
      .mockReturnValueOnce(third.promise)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      first.resolve('cached')
      await first.promise
    })
    act(() => vi.advanceTimersByTime(1000))
    await act(async () => {
      second.reject(new Error('offline'))
      await second.promise.catch(() => undefined)
    })
    expect(result.current).toEqual({
      data: 'cached',
      error: 'offline',
      loading: false,
      stale: true,
    })

    act(() => vi.advanceTimersByTime(1000))
    await act(async () => {
      third.resolve('fresh')
      await third.promise
    })
    expect(result.current).toEqual({
      data: 'fresh',
      error: null,
      loading: false,
      stale: false,
    })
  })

  it('finishes initial loading after a failure', async () => {
    const request = deferred<string>()
    const fn = vi.fn().mockReturnValueOnce(request.promise)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      request.reject(new Error('unavailable'))
      await request.promise.catch(() => undefined)
    })
    expect(result.current).toEqual({
      data: null,
      error: 'unavailable',
      loading: false,
      stale: false,
    })
  })
})
