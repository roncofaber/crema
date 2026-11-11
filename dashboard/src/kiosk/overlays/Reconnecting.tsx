export function Reconnecting() {
  return (
    <div className="absolute inset-0 bg-bg flex flex-col items-center justify-center gap-4 z-50" role="status" aria-live="polite">
      <p className="font-display italic text-5xl text-ink">Kiosk unavailable</p>
      <p className="font-plex text-sm text-faint tracking-widest uppercase">Reconnecting...</p>
    </div>
  )
}
