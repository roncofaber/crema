import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { deferred, makeSnapshot } from '../test/fixtures'
import { useKioskSocket } from './hooks/useKioskSocket'
import { KioskApp } from './KioskApp'

vi.mock('./hooks/useKioskSocket', async importOriginal => {
  const actual = await importOriginal<typeof import('./hooks/useKioskSocket')>()
  return { ...actual, useKioskSocket: vi.fn() }
})

const socket = vi.mocked(useKioskSocket)

function show(snapshot: ReturnType<typeof makeSnapshot>) {
  socket.mockReturnValue({ snapshot, connected: true })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('KioskApp rating lifecycle', () => {
  it('does not let an old rating completion dismiss a newer session prompt', async () => {
    const request = deferred<{ ok: boolean }>()
    vi.spyOn(api, 'kioskRate').mockReturnValue(request.promise)
    show(makeSnapshot({ state: 'brewing', last_brew_id: null }))
    const { rerender } = render(<KioskApp />)

    show(makeSnapshot({ state: 'armed', last_brew_id: 1 }))
    rerender(<KioskApp />)
    fireEvent.click(screen.getByRole('button', { name: 'Rate 4 out of 5' }))

    show(makeSnapshot({
      state: 'brewing',
      user: 'bob',
      session_started_at: 2000,
      last_brew_id: null,
    }))
    rerender(<KioskApp />)
    show(makeSnapshot({
      state: 'armed',
      user: 'bob',
      session_started_at: 2000,
      last_brew_id: 2,
    }))
    rerender(<KioskApp />)
    expect(screen.getByRole('heading', { name: 'How was that one?' })).toBeInTheDocument()

    await act(async () => {
      request.resolve({ ok: true })
      await request.promise
    })
    expect(screen.getByRole('heading', { name: 'How was that one?' })).toBeInTheDocument()
  })

  it('pauses stale-screen controls while retaining the last snapshot', () => {
    const snapshot = makeSnapshot({ state: 'armed', last_brew_id: null })
    show(snapshot)
    const { rerender } = render(<KioskApp />)
    expect(screen.getByRole('button', { name: 'Cancel session' })).toBeInTheDocument()

    socket.mockReturnValue({ snapshot, connected: false })
    rerender(<KioskApp />)
    expect(screen.getByRole('alert')).toHaveTextContent('Kiosk unavailable')
    expect(document.querySelector('[inert]')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('button', { name: 'Cancel session' })).not.toBeInTheDocument()

    show(snapshot)
    rerender(<KioskApp />)
    expect(screen.getByRole('button', { name: 'Cancel session' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a rating prompt when a scan claims an anonymous brew', () => {
    show(makeSnapshot({
      state: 'anon_brew',
      user: null,
      session_started_at: null,
      last_brew_id: null,
    }))
    const { rerender } = render(<KioskApp />)
    expect(screen.queryByRole('heading', { name: 'How was that one?' })).not.toBeInTheDocument()

    show(makeSnapshot({ state: 'armed', last_brew_id: 7 }))
    rerender(<KioskApp />)
    expect(screen.getByRole('heading', { name: 'How was that one?' })).toBeInTheDocument()
  })
})
