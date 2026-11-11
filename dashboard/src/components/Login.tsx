import { useState } from 'react'
import { api } from '../api'

type Props = { onAuthenticated: () => void; kiosk?: boolean }

export function Login({ onAuthenticated, kiosk = false }: Props) {
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (pending || !password) return
    setPending(true)
    setError(null)
    try {
      await api.authLogin(password)
      setPassword('')
      onAuthenticated()
    } catch {
      setError('Sign-in failed. Check your password or wait before retrying.')
    } finally {
      setPending(false)
    }
  }

  return (
    <main className={`${kiosk ? 'fixed inset-0 overflow-hidden py-4' : 'min-h-screen py-10'} bg-bg text-ink flex items-center justify-center px-6`}>
      <form onSubmit={submit} className={`w-full max-w-sm bg-surface border border-border rounded ${kiosk ? 'p-5 space-y-4' : 'p-8 space-y-6'}`}>
        <div className="text-center">
          <p className="text-xs uppercase tracking-[0.25em] text-faint mb-3">Caffè Cabrini</p>
          <h1 className="font-display italic text-4xl">{kiosk ? 'Kiosk sign in' : 'Dashboard sign in'}</h1>
          {kiosk && <p className="mt-2 font-plex text-xs text-muted">Sign in to enable kiosk controls.</p>}
        </div>
        <div>
          <label htmlFor={kiosk ? 'kiosk-password' : 'dashboard-password'} className="block mb-2 font-plex text-xs uppercase tracking-widest text-muted">
            Administrator password
          </label>
          <input
            id={kiosk ? 'kiosk-password' : 'dashboard-password'}
            type="password"
            value={password}
            onChange={event => setPassword(event.target.value)}
            autoComplete="current-password"
            autoFocus
            required
            disabled={pending}
            className="w-full min-h-12 rounded border border-border bg-bg px-3 text-ink disabled:opacity-60"
          />
        </div>
        <div className="min-h-5" aria-live="polite">
          {error && <p role="alert" className="font-plex text-xs text-ink">{error}</p>}
        </div>
        <button
          type="submit"
          disabled={pending || !password}
          className="w-full min-h-12 rounded bg-crema-500 text-surface font-plex text-sm uppercase tracking-widest disabled:cursor-wait disabled:opacity-60"
        >
          {pending ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
