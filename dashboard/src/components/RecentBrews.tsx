import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import { SkeletonRow } from "./Skeleton"

function relTime(ts: number): string {
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 60)  return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  const d = Math.floor(s / 86400)
  return d === 1 ? "yesterday" : `${d}d ago`
}

function fmtDuration(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec}s` : `${sec}s`
}

export function RecentBrews() {
  const { data: brews } = usePolling(api.brews, 15_000)

  return (
    <div className="bg-surface rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-faint font-normal">User</th>
            <th className="text-left px-4 py-3 text-xs uppercase tracking-widest text-faint font-normal">When</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-faint font-normal">Duration</th>
            <th className="text-right px-4 py-3 text-xs uppercase tracking-widest text-faint font-normal">Kind</th>
          </tr>
        </thead>
        <tbody>
          {brews == null
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={4} />)
            : brews.map(b => (
                <tr key={b.id} className="border-b border-border-subtle last:border-0">
                  <td className="px-4 py-3 text-ink font-medium">{b.user}</td>
                  <td className="px-4 py-3 font-plex text-xs text-faint">{relTime(b.started_at)}</td>
                  <td className="px-4 py-3 text-right font-plex text-xs text-muted">{fmtDuration(b.duration)}</td>
                  <td className={`px-4 py-3 text-right font-plex text-xs ${b.kind === "brew" ? "text-crema-400" : "text-faint"}`}>
                    {b.kind}
                  </td>
                </tr>
              ))
          }
        </tbody>
      </table>
    </div>
  )
}
