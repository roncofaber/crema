import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import { SkeletonRow } from "./Skeleton"

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
    <div className="bg-surface rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-muted font-normal w-8">#</th>
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-muted font-normal">Name</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-muted font-normal">Brews</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-muted font-normal">Time</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-muted font-normal">Last</th>
          </tr>
        </thead>
        <tbody>
          {users == null
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} cols={5} />)
            : users.map((u, i) => (
                <tr key={u.id} className="border-b border-border-subtle last:border-0">
                  <td className="px-4 py-3 font-plex text-xs text-faint">{i + 1}</td>
                  <td className="px-4 py-3 text-ink">{u.name}</td>
                  <td className="px-4 py-3 text-right font-plex text-crema-400">{u.total_brews}</td>
                  <td className="px-4 py-3 text-right font-plex text-xs text-muted">{fmt(u.total_time)}</td>
                  <td className="px-4 py-3 text-right font-plex text-xs text-faint">{fmtDate(u.last_brew)}</td>
                </tr>
              ))
          }
        </tbody>
      </table>
    </div>
  )
}
