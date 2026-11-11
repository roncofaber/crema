import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api'
import { deferred, makeSnapshot } from '../../test/fixtures'
import { RatingPrompt } from './RatingPrompt'

vi.mock('../../api', () => ({
  api: { kioskRate: vi.fn() },
}))

const rate = vi.mocked(api.kioskRate)

describe('RatingPrompt', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    rate.mockReset()
  })

  it('prevents duplicate submissions and dismisses only after success', async () => {
    const first = deferred<{ ok: boolean }>()
    const retry = deferred<{ ok: boolean }>()
    rate.mockReturnValueOnce(first.promise).mockReturnValueOnce(retry.promise)
    const onDismiss = vi.fn()
    render(<RatingPrompt snapshot={makeSnapshot()} brewId={42} onDismiss={onDismiss} />)

    fireEvent.click(screen.getByRole('button', { name: 'Rate 4 out of 5' }))
    fireEvent.click(screen.getByRole('button', { name: 'Rate 5 out of 5' }))
    expect(rate).toHaveBeenCalledTimes(1)
    expect(rate).toHaveBeenCalledWith(42, 4)
    expect(screen.getByRole('status')).toHaveTextContent('Saving rating')
    expect(onDismiss).not.toHaveBeenCalled()

    await act(async () => {
      first.reject(new Error('offline'))
      await first.promise.catch(() => undefined)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Rating not saved')
    expect(onDismiss).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(20000))
    expect(onDismiss).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Retry rating' }))
    expect(rate).toHaveBeenCalledTimes(2)
    expect(onDismiss).not.toHaveBeenCalled()
    await act(async () => {
      retry.resolve({ ok: true })
      await retry.promise
    })
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('allows an explicit skip after a failed request', async () => {
    const request = deferred<{ ok: boolean }>()
    rate.mockReturnValueOnce(request.promise)
    const onDismiss = vi.fn()
    render(<RatingPrompt snapshot={makeSnapshot()} brewId={42} onDismiss={onDismiss} />)

    fireEvent.click(screen.getByRole('button', { name: 'Rate 3 out of 5' }))
    await act(async () => {
      request.reject(new Error('offline'))
      await request.promise.catch(() => undefined)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Skip rating' }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
