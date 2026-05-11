import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

function fmtDate(ts: number | null): string {
  if (!ts) return "—"
  return new Date(ts * 1000).toLocaleDateString()
}

export function Leaderboard() {
  const { data: users } = usePolling(api.users, 30_000)

  return (
    <div className="bg-espresso-800 rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-espresso-600">
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal w-8">#</th>
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Name</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Brews</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Time</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-parchment-600 font-normal">Last</th>
          </tr>
        </thead>
        <tbody>
          {(users ?? []).map((u, i) => (
            <tr key={u.id} className="border-b border-espresso-700 last:border-0">
              <td className="px-4 py-3 font-plex text-xs text-parchment-600">{i + 1}</td>
              <td className="px-4 py-3 text-parchment-100">{u.name}</td>
              <td className="px-4 py-3 text-right font-plex text-crema-400">{u.total_brews}</td>
              <td className="px-4 py-3 text-right font-plex text-xs text-parchment-400">{fmt(u.total_time)}</td>
              <td className="px-4 py-3 text-right font-plex text-xs text-parchment-600">{fmtDate(u.last_brew)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
