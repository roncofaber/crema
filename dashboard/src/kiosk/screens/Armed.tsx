import { api } from '../../api'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { snapshot: KioskSnapshot }

function ToggleRow({ label, options, value, onChange }: {
  label: string
  options: [string, string][]  // [value, label]
  value: string | boolean
  onChange: (v: string | boolean) => void
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-faint mb-2">{label}</p>
      <div className="flex gap-3">
        {options.map(([v, l]) => (
          <button
            key={v}
            onClick={() => onChange(v === 'true' ? true : v === 'false' ? false : v)}
            className={`flex-1 py-4 rounded text-sm font-plex tracking-widest uppercase transition-colors ${
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
  const { user, brew_count, time_remaining, timeout, shot_type, decaf } = snapshot
  const frac = time_remaining != null && timeout ? Math.max(0, time_remaining / timeout) : 1

  function setShot(v: string | boolean) { api.kioskBrewOptions({ shot_type: String(v), decaf }) }
  function setDecaf(v: string | boolean) { api.kioskBrewOptions({ shot_type, decaf: v === true || v === 'true' }) }

  return (
    <div className="h-screen bg-bg flex flex-col">
      <div className="h-1 bg-crema-500 flex-shrink-0" />
      <div className="flex-1 flex min-h-0">
        {/* Left: user info */}
        <div className="flex-[2] flex flex-col justify-center px-10 border-r border-border-subtle">
          <p className="text-base uppercase tracking-[0.2em] text-faint mb-1">Ciao,</p>
          <h1 className="font-display italic text-6xl text-ink mb-3 truncate">{user}</h1>
          <p className="text-base text-muted">
            {brew_count === 0
              ? 'Start the machine when ready'
              : `${brew_count} coffee${brew_count === 1 ? '' : 's'} this session`}
          </p>
        </div>
        {/* Right: controls */}
        <div className="flex-[3] flex flex-col justify-center gap-5 px-10">
          <ToggleRow
            label="Shot type"
            options={[['single', 'Single'], ['double', 'Double']]}
            value={shot_type}
            onChange={setShot}
          />
          <ToggleRow
            label="Decaf"
            options={[['false', 'Off'], ['true', 'On']]}
            value={String(decaf)}
            onChange={setDecaf}
          />
          <button
            onClick={() => api.kioskLogout()}
            className="py-4 rounded text-sm uppercase tracking-[0.16em] text-faint border border-border bg-transparent"
          >
            Logout
          </button>
        </div>
      </div>
      {/* Bottom timeout bar */}
      <div className="h-1 bg-border-subtle flex-shrink-0 relative overflow-hidden">
        <div
          className="absolute left-0 top-0 bottom-0 bg-crema-400 transition-all duration-1000"
          style={{ width: `${frac * 100}%` }}
        />
      </div>
    </div>
  )
}
