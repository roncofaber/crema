import { useBrewOptions } from '../hooks/useBrewOptions'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

function fmt(s: number | null) {
  if (s == null) return '0s'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec.toString().padStart(2, '0')}s` : `${sec}s`
}

type Props = { snapshot: KioskSnapshot }

export function Brewing({ snapshot }: Props) {
  const { user, brew_count, elapsed } = snapshot
  const brewOptions = useBrewOptions(snapshot)
  const BREW_MAX = 180
  const fill = Math.min(1, (elapsed ?? 0) / BREW_MAX)

  return (
    <div className="relative h-full min-h-0 overflow-hidden bg-bg flex flex-col">
      <div className="h-1 bg-crema-400 flex-shrink-0" />
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-3 px-8 py-3">
        <p className="font-plex text-sm uppercase tracking-[0.18em] text-faint">{user}</p>
        <p className="font-display text-8xl text-ink leading-none">×{brew_count + 1}</p>
        <p className="font-plex text-2xl text-crema-400 tracking-wide">{fmt(elapsed)}</p>
        <div className="w-2/3 h-1.5 bg-border-subtle rounded-full overflow-hidden mt-2">
          <div className="h-full bg-crema-400 rounded-full transition-all duration-1000" style={{ width: `${fill * 100}%` }} />
        </div>
        <div className="flex gap-3 mt-2">
          {(['single', 'double'] as const).map(v => (
            <button
              key={v}
              disabled={brewOptions.pending}
              onClick={() => brewOptions.setShotType(v)}
              className={`min-h-12 px-5 py-2 rounded text-sm font-plex tracking-widest uppercase disabled:cursor-wait disabled:opacity-60 ${brewOptions.shot_type === v ? 'bg-crema-500 text-surface' : 'bg-surface text-faint border border-border'}`}
            >
              {v}
            </button>
          ))}
          <button
            disabled={brewOptions.pending}
            onClick={() => brewOptions.setDecaf(!brewOptions.decaf)}
            className={`min-h-12 px-5 py-2 rounded text-sm font-plex tracking-widest uppercase disabled:cursor-wait disabled:opacity-60 ${brewOptions.decaf ? 'bg-crema-500 text-surface' : 'bg-surface text-faint border border-border'}`}
          >
            {brewOptions.decaf ? 'Decaf' : 'Origin'}
          </button>
        </div>
        <div className="min-h-8 max-w-full text-center font-plex text-xs leading-4" aria-live="polite">
          {brewOptions.pending && <p role="status">Saving brew options...</p>}
          {!brewOptions.pending && brewOptions.error && <p role="alert">{brewOptions.error}</p>}
        </div>
      </div>
      <div className="h-1 bg-crema-400 flex-shrink-0" />
    </div>
  )
}
