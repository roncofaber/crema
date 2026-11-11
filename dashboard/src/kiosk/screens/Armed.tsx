import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { useBrewOptions } from '../hooks/useBrewOptions'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { snapshot: KioskSnapshot }

function ToggleRow({ label, options, value, disabled, onChange }: {
  label: string
  options: [string, string][]
  value: string | boolean
  disabled: boolean
  onChange: (v: string | boolean) => void
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-faint mb-2">{label}</p>
      <div className="flex gap-3">
        {options.map(([v, l]) => (
          <button
            key={v}
            disabled={disabled}
            onClick={() => onChange(v === 'true' ? true : v === 'false' ? false : v)}
            className={`flex-1 min-h-[52px] py-3 rounded text-sm font-plex tracking-widest uppercase transition-colors disabled:cursor-wait disabled:opacity-60 ${
              String(value) === v
                ? 'bg-crema-500 text-surface'
                : 'bg-surface text-faint border border-border'
            }`}
          >
            {l}
          </button>
        ))}
      </div>
    </div>
  )
}

export function Armed({ snapshot }: Props) {
  return <ArmedSession key={snapshot.session_started_at ?? 'anonymous'} snapshot={snapshot} />
}

function ArmedSession({ snapshot }: Props) {
  const { user, brew_count, time_remaining, timeout } = snapshot
  const brewOptions = useBrewOptions(snapshot)
  const [logoutPending, setLogoutPending] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const logoutInFlight = useRef(false)
  const logoutRequest = useRef(0)
  const frac = time_remaining != null && timeout ? Math.max(0, time_remaining / timeout) : 1
  const actionPending = brewOptions.pending || logoutPending
  const actionError = brewOptions.error ?? logoutError

  useEffect(() => () => {
    logoutRequest.current += 1
  }, [])

  async function logout() {
    if (logoutInFlight.current || brewOptions.pending) return
    const sessionStartedAt = snapshot.session_started_at
    if (sessionStartedAt === null) return
    const requestId = ++logoutRequest.current
    logoutInFlight.current = true
    brewOptions.clearError()
    setLogoutPending(true)
    setLogoutError(null)
    try {
      await api.kioskLogout(sessionStartedAt)
    } catch (error) {
      if (logoutRequest.current !== requestId) return
      logoutInFlight.current = false
      setLogoutPending(false)
      setLogoutError(`Could not end the session. Tap to retry. ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  return (
    <div className="relative h-full min-h-0 overflow-hidden bg-bg flex flex-col">
      <div className="h-1 bg-crema-500 flex-shrink-0" />
      <div className="flex-1 flex min-h-0">
        <div className="flex-[2] min-w-0 flex flex-col justify-center px-10 border-r border-border-subtle">
          <p className="text-base uppercase tracking-[0.2em] text-faint mb-1">Ciao,</p>
          <h1 className="font-display italic text-6xl text-ink mb-3 break-words leading-tight">{user}</h1>
          <p className="text-base text-muted">
            {brew_count === 0
              ? 'Start the machine when ready'
              : `${brew_count} coffee${brew_count === 1 ? '' : 's'} this session`}
          </p>
        </div>
        <div className="flex-[3] min-w-0 flex flex-col justify-center gap-4 px-10 py-4">
          <ToggleRow
            label="Shot type"
            options={[['single', 'Single'], ['double', 'Double']]}
            value={brewOptions.shot_type}
            disabled={actionPending}
            onChange={v => {
              setLogoutError(null)
              brewOptions.setShotType(v === 'single' ? 'single' : 'double')
            }}
          />
          <ToggleRow
            label="Decaf"
            options={[['false', 'Off'], ['true', 'On']]}
            value={String(brewOptions.decaf)}
            disabled={actionPending}
            onChange={v => {
              setLogoutError(null)
              brewOptions.setDecaf(v === true || v === 'true')
            }}
          />
          <button
            onClick={() => { void logout() }}
            disabled={actionPending}
            className="min-h-[52px] py-3 rounded text-sm uppercase tracking-[0.16em] text-faint border border-border bg-transparent disabled:cursor-wait disabled:opacity-60"
          >
            {logoutPending
              ? 'Ending session...'
              : brew_count ? 'Finish session' : 'Cancel session'}
          </button>
          <div className="min-h-8 text-center font-plex text-xs leading-4" aria-live="polite">
            {brewOptions.pending && <p role="status">Saving brew options...</p>}
            {!brewOptions.pending && actionError && <p role="alert" className="text-ink">{actionError}</p>}
          </div>
        </div>
      </div>
      <div className="h-1 bg-border-subtle flex-shrink-0 relative overflow-hidden">
        <div
          className="absolute left-0 top-0 bottom-0 bg-crema-400 transition-all duration-1000"
          style={{ width: `${frac * 100}%` }}
        />
      </div>
    </div>
  )
}
