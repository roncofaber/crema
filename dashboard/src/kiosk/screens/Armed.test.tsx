import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api'
import { deferred, makeSnapshot } from '../../test/fixtures'
import { Armed } from './Armed'

vi.mock('../../api', () => ({
  api: {
    kioskBrewOptions: vi.fn(),
    kioskLogout: vi.fn(),
  },
}))

const optionsRequest = vi.mocked(api.kioskBrewOptions)
const logoutRequest = vi.mocked(api.kioskLogout)

describe('Armed actions', () => {
  beforeEach(() => {
    optionsRequest.mockReset()
    logoutRequest.mockReset()
  })

  it('shows the latest action error instead of hiding it behind an older one', async () => {
    const optionFailure = deferred<{ ok: boolean }>()
    const logoutFailure = deferred<{ ok: boolean }>()
    optionsRequest.mockReturnValueOnce(optionFailure.promise)
    logoutRequest.mockReturnValueOnce(logoutFailure.promise)
    render(<Armed snapshot={makeSnapshot()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Single' }))
    await act(async () => {
      optionFailure.reject(new Error('options offline'))
      await optionFailure.promise.catch(() => undefined)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Could not save brew options')

    fireEvent.click(screen.getByRole('button', { name: 'Cancel session' }))
    expect(logoutRequest).toHaveBeenCalledWith(1000)
    await act(async () => {
      logoutFailure.reject(new Error('logout offline'))
      await logoutFailure.promise.catch(() => undefined)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Could not end the session')
    expect(screen.getByRole('alert')).not.toHaveTextContent('Could not save brew options')
  })

  it('scopes delayed logout requests and callbacks to their original session', async () => {
    const aliceLogout = deferred<{ ok: boolean }>()
    const bobLogout = deferred<{ ok: boolean }>()
    logoutRequest
      .mockReturnValueOnce(aliceLogout.promise)
      .mockReturnValueOnce(bobLogout.promise)
    const { rerender } = render(<Armed snapshot={makeSnapshot()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel session' }))
    rerender(<Armed snapshot={makeSnapshot({ user: 'bob', session_started_at: 2000 })} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel session' }))

    expect(logoutRequest.mock.calls).toEqual([[1000], [2000]])
    await act(async () => {
      aliceLogout.reject(new Error('late Alice failure'))
      await aliceLogout.promise.catch(() => undefined)
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ending session...' })).toBeDisabled()

    await act(async () => {
      bobLogout.resolve({ ok: true })
      await bobLogout.promise
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
