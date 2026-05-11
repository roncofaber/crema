import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

const LABELS = ["Today", "All time", "Users", "Total brew time", "Top brewer"]

export function StatsCards() {
  const { data: stats } = usePolling(api.stats, 30_000)

  const cards = stats
    ? [
        { label: "Today",           value: stats.today_brews },
        { label: "All time",        value: stats.total_brews },
        { label: "Users",           value: stats.total_users },
        { label: "Total brew time", value: fmt(stats.total_brew_time) },
        { label: "Top brewer",      value: stats.top_brewer ?? "—" },
      ]
    : LABELS.map(label => ({ label, value: "—" }))

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map(c => (
        <div key={c.label} className="bg-surface rounded p-5 border-t-2 border-crema-500">
          <div className="font-plex text-3xl font-medium text-ink">{c.value}</div>
          <div className="text-xs uppercase tracking-widest text-muted mt-2">{c.label}</div>
        </div>
      ))}
    </div>
  )
}
