import { useEffect, useState } from "react"
import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

function useElapsed(startTs: number | null): string {
  const [, setTick] = useState(0)

  useEffect(() => {
    if (!startTs) return
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [startTs])

  if (!startTs) return ""
  const s = Math.floor(Date.now() / 1000 - startTs)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m ? `${m}m ${sec}s` : `${sec}s`
}

export function StatusBadge() {
  const { data: status } = usePolling(api.status, 5000)
  const elapsed = useElapsed(status?.session_started_at ?? null)

  if (!status) return <span className="font-plex text-sm text-parchment-700">—</span>

  const active = status.state === "active"

  if (!active) return <span className="font-plex text-sm text-parchment-600">idle</span>

  return (
    <span className="flex items-center gap-2 font-plex text-sm text-crema-400">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-crema-400 opacity-60" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-crema-500" />
      </span>
      {status.user} — {elapsed}
    </span>
  )
}
