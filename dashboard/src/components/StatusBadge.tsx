import { useElapsed } from "../hooks/useElapsed"
import type { Status } from "../types"

type Props = {
  status: Status | null
  error: string | null
  loading: boolean
  stale: boolean
}

export function StatusBadge({ status, error, loading, stale }: Props) {
  const elapsed = useElapsed(status?.brew_started_at ?? status?.session_started_at ?? null)

  if (error) {
    return (
      <span className="font-plex text-sm text-muted" role="alert" title={error}>
        {stale && status ? "Status update failed. Showing the last known state." : "Status unavailable. Retrying..."}
      </span>
    )
  }
  if (loading || !status) return <span className="font-plex text-sm text-faint" role="status">Loading status...</span>

  if (status.state === "idle")
    return <span className="font-plex text-sm text-muted">idle</span>

  if (status.state === "ready")
    return (
      <span className="font-plex text-sm text-muted">
        {status.user} - ready to brew
      </span>
    )

  return (
    <span className="flex items-center justify-center gap-2 font-plex text-sm text-crema-400">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-crema-400 opacity-60" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-crema-500" />
      </span>
      {status.user} - {elapsed}
    </span>
  )
}
