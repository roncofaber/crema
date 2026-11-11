import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api'
import { deferred, makeSnapshot } from '../../test/fixtures'
import { useBrewOptions } from './useBrewOptions'

vi.mock('../../api', () => ({
  api: { kioskBrewOptions: vi.fn() },
}))

const request = vi.mocked(api.kioskBrewOptions)

describe('useBrewOptions', () => {
  beforeEach(() => {
    request.mockReset()
  })

  it('keeps optimistic updates through stale snapshots and sends complete options', async () => {
    const first = deferred<{ ok: boolean }>()
    request.mockReturnValueOnce(first.promise)
    const snapshot = makeSnapshot()
    const { result, rerender } = renderHook(
      ({ value }) => useBrewOptions(value),
      { initialProps: { value: snapshot } },
    )

    act(() => result.current.setShotType('single'))
    expect(result.current).toMatchObject({ shot_type: 'single', decaf: false, pending: true })
    expect(request).toHaveBeenCalledWith({
      shot_type: 'single',
      decaf: false,
      session_started_at: 1000,
    })

    rerender({ value: makeSnapshot() })
    expect(result.current.shot_type).toBe('single')

    await act(async () => {
      first.resolve({ ok: true })
      await first.promise
    })
    expect(result.current.pending).toBe(false)

    rerender({ value: makeSnapshot({ shot_type: 'single' }) })
    expect(result.current).toMatchObject({ shot_type: 'single', decaf: false })
  })

  it('rolls back to the last confirmed options after failure', async () => {
    const update = deferred<{ ok: boolean }>()
    request.mockReturnValueOnce(update.promise)
    const { result } = renderHook(() => useBrewOptions(makeSnapshot()))

    act(() => result.current.setDecaf(true))
    expect(result.current.decaf).toBe(true)
    await act(async () => {
      update.reject(new Error('request failed'))
      await update.promise.catch(() => undefined)
    })

    expect(result.current).toMatchObject({
      shot_type: 'double',
      decaf: false,
      pending: false,
    })
    expect(result.current.error).toContain('Tap an option to retry')

    const retry = deferred<{ ok: boolean }>()
    request.mockReturnValueOnce(retry.promise)
    act(() => result.current.setDecaf(true))
    expect(request).toHaveBeenLastCalledWith({
      shot_type: 'double',
      decaf: true,
      session_started_at: 1000,
    })
    await act(async () => {
      retry.resolve({ ok: true })
      await retry.promise
    })
    expect(result.current.error).toBeNull()
  })

  it('accepts an authoritative server snapshot after an uncertain failure', async () => {
    const update = deferred<{ ok: boolean }>()
    request.mockReturnValueOnce(update.promise)
    const { result, rerender } = renderHook(
      ({ value }) => useBrewOptions(value),
      { initialProps: { value: makeSnapshot() } },
    )

    act(() => result.current.setShotType('single'))
    await act(async () => {
      update.reject(new Error('response lost'))
      await update.promise.catch(() => undefined)
    })
    expect(result.current.shot_type).toBe('double')

    rerender({ value: makeSnapshot({ shot_type: 'single' }) })
    expect(result.current.shot_type).toBe('single')
  })

  it('scopes overlapping requests and callbacks to their original sessions', async () => {
    const aliceUpdate = deferred<{ ok: boolean }>()
    const bobUpdate = deferred<{ ok: boolean }>()
    request.mockReturnValueOnce(aliceUpdate.promise).mockReturnValueOnce(bobUpdate.promise)
    const { result, rerender } = renderHook(
      ({ value }) => useBrewOptions(value),
      { initialProps: { value: makeSnapshot() } },
    )

    act(() => result.current.setShotType('single'))
    rerender({
      value: makeSnapshot({
        user: 'bob',
        session_started_at: 2000,
        shot_type: 'double',
        decaf: true,
      }),
    })
    act(() => result.current.setDecaf(false))

    expect(request).toHaveBeenCalledTimes(2)
    expect(request.mock.calls).toEqual([
      [{ shot_type: 'single', decaf: false, session_started_at: 1000 }],
      [{ shot_type: 'double', decaf: false, session_started_at: 2000 }],
    ])

    await act(async () => {
      bobUpdate.resolve({ ok: true })
      await bobUpdate.promise
    })
    await act(async () => {
      aliceUpdate.resolve({ ok: true })
      await aliceUpdate.promise
    })
    expect(result.current).toMatchObject({
      shot_type: 'double',
      decaf: false,
      pending: false,
    })
    expect(result.current.error).toBeNull()
  })
})
