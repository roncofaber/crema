import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { snapshot: KioskSnapshot }

function fmtDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.round(seconds % 60)
  return minutes ? `${minutes}m ${remainder.toString().padStart(2, '0')}s` : `${remainder}s`
}

export function Summary({ snapshot }: Props) {
  const { user, brew_count, avg_rating, session_brew_time } = snapshot

  return (
    <div className="h-screen bg-bg flex flex-col items-center justify-center gap-3">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="font-plex text-sm uppercase tracking-[0.18em] text-faint">Grazie,</p>
      <h1 className="font-display italic text-6xl text-ink">{user}</h1>
      <div className="h-px w-24 bg-border my-2" />
      <div className="flex items-center gap-8 font-plex text-sm text-muted">
        <span>{brew_count} coffee{brew_count === 1 ? '' : 's'}</span>
        <span className="text-border">/</span>
        <span>{fmtDuration(session_brew_time)} brewing</span>
      </div>
      {avg_rating != null && (
        <p className="font-plex text-base text-crema-400">
          {'★'.repeat(Math.round(avg_rating))}{'☆'.repeat(5 - Math.round(avg_rating))} avg {avg_rating.toFixed(1)}
        </p>
      )}
      <p className="font-plex text-sm text-faint mt-2 tracking-widest">alla prossima!</p>
      <div className="h-1 w-full bg-crema-500 absolute bottom-0" />
    </div>
  )
}
