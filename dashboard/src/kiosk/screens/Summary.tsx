import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { snapshot: KioskSnapshot }

export function Summary({ snapshot }: Props) {
  const { user, brew_count, avg_rating } = snapshot

  return (
    <div className="h-screen bg-bg flex flex-col items-center justify-center gap-3">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="font-plex text-sm uppercase tracking-[0.18em] text-faint">Grazie,</p>
      <h1 className="font-display italic text-6xl text-ink">{user}</h1>
      <div className="h-px w-24 bg-border my-2" />
      <p className="text-base text-muted">
        {brew_count} coffee{brew_count === 1 ? '' : 's'}
      </p>
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
