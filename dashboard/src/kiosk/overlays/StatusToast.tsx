type Props = { disconnected: boolean }

export function StatusToast({ disconnected }: Props) {
  if (!disconnected) return null
  return (
    <div role="alert" className="absolute top-3 left-1/2 z-40 w-max max-w-[calc(100%-2rem)] -translate-x-1/2 rounded bg-ink/95 px-4 py-2 text-center shadow-lg">
      <p className="font-plex text-xs uppercase tracking-widest text-surface">Kiosk unavailable</p>
      <p className="mt-1 font-plex text-[10px] text-surface">Reconnecting. Showing the last snapshot; controls are paused.</p>
    </div>
  )
}
