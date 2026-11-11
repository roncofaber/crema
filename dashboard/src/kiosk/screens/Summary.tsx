import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { snapshot: KioskSnapshot }

function fmtDuration(seconds: number) {
  const totalSeconds = Math.round(seconds)
  const minutes = Math.floor(totalSeconds / 60)
  const remainder = totalSeconds % 60
  return minutes ? `${minutes}m ${remainder.toString().padStart(2, '0')}s` : `${remainder}s`
}

export function Summary({ snapshot }: Props) {
  const { user, brew_count, avg_rating, session_brew_time } = snapshot

  return (
    <div className="relative h-full min-h-0 overflow-hidden bg-bg flex flex-col items-center justify-center gap-3 px-8 py-4 text-center">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="font-plex text-sm uppercase tracking-[0.18em] text-faint">Grazie,</p>
      <h1 className="max-w-full break-words font-display italic text-6xl leading-tight text-ink">{user}</h1>
      <div className="h-px w-24 bg-border my-2 flex-shrink-0" />
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
