import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

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
    <div className="bg-espresso-800 rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-espresso-600">
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">User</th>
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Time</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Duration</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Kind</th>
          </tr>
        </thead>
        <tbody>
          {(brews ?? []).map(b => (
            <tr key={b.id} className="border-b border-espresso-700 last:border-0">
              <td className="px-4 py-3 text-parchment-100">{b.user}</td>
              <td className="px-4 py-3 font-plex text-xs text-parchment-600">{fmtTime(b.started_at)}</td>
              <td className="px-4 py-3 text-right font-plex text-xs text-parchment-400">{fmtDuration(b.duration)}</td>
              <td className={`px-4 py-3 text-right font-plex text-xs ${b.kind === "brew" ? "text-crema-400" : "text-parchment-600"}`}>
                {b.kind}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
