import type { KioskSnapshot } from '../hooks/useKioskSocket'

function fmt(s: number | null) {
  if (s == null) return '0s'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec.toString().padStart(2, '0')}s` : `${sec}s`
}

type Props = { snapshot: KioskSnapshot }

export function AnonBrewing({ snapshot }: Props) {
  const { elapsed } = snapshot
  const BREW_MAX = 180
  const fill = Math.min(1, (elapsed ?? 0) / BREW_MAX)

  return (
    <div className="h-screen bg-bg flex flex-col">
      <div className="h-1 bg-border flex-shrink-0" />
      <div className="flex-1 flex flex-col items-center justify-center gap-3">
        <p className="font-plex text-xs uppercase tracking-[0.18em] text-faint">Anonymous</p>
        <p className="font-display text-8xl text-ink leading-none">×1</p>
        <p className="font-plex text-2xl text-crema-400 tracking-wide">{fmt(elapsed)}</p>
        <div className="w-2/3 h-1.5 bg-border-subtle rounded-full overflow-hidden mt-2">
          <div className="h-full bg-crema-400 rounded-full transition-all duration-1000" style={{ width: `${fill * 100}%` }} />
        </div>
      </div>
      <div className="h-1 bg-border flex-shrink-0" />
    </div>
  )
}
