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

  if (!status) return <span className="text-gray-500 text-sm">connecting...</span>

  const active = status.state === "active"
  return (
    <span className={`text-sm font-medium ${active ? "text-green-400" : "text-gray-500"}`}>
      {active ? `${status.user} is brewing (${elapsed})` : "idle"}
    </span>
  )
}
