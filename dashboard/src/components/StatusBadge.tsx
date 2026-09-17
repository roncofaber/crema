import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import { useElapsed } from "../hooks/useElapsed"

export function StatusBadge() {
  const { data: status } = usePolling(api.status, 5000)
  const elapsed = useElapsed(status?.brew_started_at ?? status?.session_started_at ?? null)

  if (!status) return <span className="font-plex text-sm text-faint">—</span>

  if (status.state === "idle")
    return <span className="font-plex text-sm text-muted">idle</span>

  if (status.state === "ready")
    return (
      <span className="font-plex text-sm text-muted">
        {status.user} — ready to brew
      </span>
    )

  return (
    <span className="flex items-center justify-center gap-2 font-plex text-sm text-crema-400">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-crema-400 opacity-60" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-crema-500" />
      </span>
      {status.user} — {elapsed}
    </span>
  )
}
