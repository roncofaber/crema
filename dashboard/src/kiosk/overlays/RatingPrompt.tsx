import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = {
  snapshot: KioskSnapshot
  brewId: number
  onDismiss: () => void
}

export function RatingPrompt({ snapshot, brewId, onDismiss }: Props) {
  const [countdown, setCountdown] = useState(15)
  const [submitting, setSubmitting] = useState<number | null>(null)
  const [failedRating, setFailedRating] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const submittingRef = useRef(false)
  const { shot_type, decaf } = snapshot
  const pending = submitting !== null

  useEffect(() => {
    if (pending || failedRating !== null) return
    const id = setTimeout(() => {
      if (countdown <= 1) onDismiss()
      else setCountdown(value => value - 1)
    }, 1000)
    return () => clearTimeout(id)
  }, [countdown, failedRating, onDismiss, pending])

  async function rate(n: number) {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(n)
    setFailedRating(null)
    setError(null)
    try {
      await api.kioskRate(brewId, n)
      submittingRef.current = false
      onDismiss()
    } catch (cause) {
      submittingRef.current = false
      setSubmitting(null)
      setFailedRating(n)
      setError(`Rating not saved. ${cause instanceof Error ? cause.message : String(cause)}`)
    }
  }

  return (
    <div className="absolute inset-0 overflow-hidden bg-bg flex flex-col items-center justify-center gap-3 px-6 py-4 z-50">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="font-plex text-xs uppercase tracking-[0.22em] text-faint">Brew complete</p>
      <h2 className="font-display italic text-5xl text-ink text-center">How was that one?</h2>
      <p className="font-plex text-sm text-faint tracking-wide">
        {shot_type} {decaf ? '· decaf' : ''}
      </p>
      <div className="flex gap-3 my-1" aria-busy={pending}>
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n}
            aria-label={`Rate ${n} out of 5`}
            disabled={pending}
            onClick={() => { void rate(n) }}
            className={`h-16 w-16 text-6xl leading-none text-crema-400 active:text-crema-300 active:scale-110 transition-all disabled:cursor-wait disabled:active:scale-100 ${submitting === n ? 'animate-pulse' : 'disabled:opacity-60'}`}
          >
            ★
          </button>
        ))}
      </div>
      <div className="min-h-8 max-w-full text-center font-plex text-xs leading-4" aria-live="polite">
        {pending && <p role="status">Saving rating...</p>}
        {!pending && error && (
          <div role="alert" className="flex flex-col items-center gap-1">
            <p>{error} Retry when ready.</p>
            {failedRating !== null && (
              <button
                onClick={() => { void rate(failedRating) }}
                className="min-h-12 px-4 uppercase tracking-widest text-crema-500 border border-crema-500 rounded"
              >
                Retry rating
              </button>
            )}
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        disabled={pending}
        className="min-h-8 font-plex text-sm text-faint uppercase tracking-widest border-b border-border pb-px disabled:cursor-wait disabled:opacity-60"
      >
        {failedRating !== null ? 'Skip rating' : `Skip · auto-dismiss in ${countdown}s`}
      </button>
      <div className="h-1 w-full bg-crema-500 absolute bottom-0" />
    </div>
  )
}
