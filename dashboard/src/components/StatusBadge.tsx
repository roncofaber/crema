import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

export function StatusBadge() {
  const { data: status } = usePolling(api.status, 5000)

  if (!status) return <span className="text-gray-500 text-sm">connecting...</span>

  const active = status.state === "active"
  return (
    <span className={`text-sm font-medium ${active ? "text-green-400" : "text-gray-500"}`}>
      {active ? `${status.user} is brewing` : "idle"}
    </span>
  )
}
