import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = {
  snapshot: KioskSnapshot
  onDismiss: () => void
}

export function RatingPrompt({ snapshot, onDismiss }: Props) {
  const [countdown, setCountdown] = useState(15)
  const { last_brew_id, shot_type, decaf } = snapshot

  useEffect(() => {
    const id = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { clearInterval(id); onDismiss(); return 0 }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [onDismiss])

  function rate(n: number) {
    if (last_brew_id != null) api.kioskRate(last_brew_id, n).catch(console.error)
    onDismiss()
  }

  return (
    <div className="absolute inset-0 bg-bg flex flex-col items-center justify-center gap-4 z-50">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="font-plex text-xs uppercase tracking-[0.22em] text-faint">Brew complete</p>
      <h2 className="font-display italic text-5xl text-ink">How was that one?</h2>
      <p className="font-plex text-sm text-faint tracking-wide">
        {shot_type} {decaf ? '· decaf' : ''}
      </p>
      <div className="flex gap-5 my-2">
        {[1, 2, 3, 4, 5].map(n => (
          <button key={n} onClick={() => rate(n)}
            className="text-6xl leading-none text-crema-400 active:text-crema-300 active:scale-110 transition-all">
            ★
          </button>
        ))}
      </div>
      <button onClick={onDismiss}
        className="font-plex text-sm text-faint uppercase tracking-widest border-b border-border pb-px">
        Skip · auto-dismiss in {countdown}s
      </button>
      <div className="h-1 w-full bg-crema-500 absolute bottom-0" />
    </div>
  )
}
