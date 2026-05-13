import { api } from '../../api'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

function fmt(s: number | null) {
  if (s == null) return '0s'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec.toString().padStart(2, '0')}s` : `${sec}s`
}

type Props = { snapshot: KioskSnapshot }

export function Brewing({ snapshot }: Props) {
  const { user, brew_count, elapsed, shot_type, decaf } = snapshot
  const BREW_MAX = 180
  const fill = Math.min(1, (elapsed ?? 0) / BREW_MAX)

  function setShot(v: string) { api.kioskBrewOptions({ shot_type: v, decaf }) }
  function setDecaf(v: boolean) { api.kioskBrewOptions({ shot_type, decaf: v }) }

  return (
    <div className="h-screen bg-bg flex flex-col">
      <div className="h-1 bg-crema-400 flex-shrink-0" />
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8">
        <p className="font-plex text-xs uppercase tracking-[0.18em] text-faint">{user}</p>
        <p className="font-display text-8xl text-ink leading-none">×{brew_count + 1}</p>
        <p className="font-plex text-2xl text-crema-400 tracking-wide">{fmt(elapsed)}</p>
        <div className="w-2/3 h-1.5 bg-border-subtle rounded-full overflow-hidden mt-2">
          <div className="h-full bg-crema-400 rounded-full transition-all duration-1000" style={{ width: `${fill * 100}%` }} />
        </div>
        {/* Brew option toggles (adjustable during brew) */}
        <div className="flex gap-3 mt-3">
          {(['single', 'double'] as const).map(v => (
            <button key={v} onClick={() => setShot(v)}
              className={`px-4 py-2 rounded text-xs font-plex tracking-widest uppercase ${shot_type === v ? 'bg-crema-500 text-surface' : 'bg-surface text-faint border border-border'}`}>
              {v}
            </button>
          ))}
          <button onClick={() => setDecaf(!decaf)}
            className={`px-4 py-2 rounded text-xs font-plex tracking-widest uppercase ${decaf ? 'bg-crema-500 text-surface' : 'bg-surface text-faint border border-border'}`}>
            {decaf ? 'Decaf' : 'Origin'}
          </button>
        </div>
      </div>
      <div className="h-1 bg-crema-400 flex-shrink-0" />
    </div>
  )
}
