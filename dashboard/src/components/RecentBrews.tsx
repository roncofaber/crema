import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import type { Brew } from "../types"

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

function fmtDuration(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec}s` : `${sec}s`
}

export function RecentBrews() {
  const { data: brews } = usePolling(api.brews, 15_000)

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left px-4 py-3">User</th>
            <th className="text-left px-4 py-3">Time</th>
            <th className="text-right px-4 py-3">Duration</th>
            <th className="text-right px-4 py-3">Kind</th>
          </tr>
        </thead>
        <tbody>
          {(brews ?? []).map(b => (
            <tr key={b.id} className="border-b border-gray-700 last:border-0">
              <td className="px-4 py-3">{b.user}</td>
              <td className="px-4 py-3 text-gray-400">{fmtTime(b.started_at)}</td>
              <td className="px-4 py-3 text-right text-gray-300">{fmtDuration(b.duration)}</td>
              <td className={`px-4 py-3 text-right ${b.kind === "brew" ? "text-amber-400" : "text-gray-500"}`}>
                {b.kind}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
