import { useEffect, useState } from "react"
import { api } from "../api"
import type { OverallStats } from "../types"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

export function StatsCards() {
  const [stats, setStats] = useState<OverallStats | null>(null)
  useEffect(() => { api.stats().then(setStats).catch(() => {}) }, [])

  if (!stats) return null

  const cards = [
    { label: "Today",           value: stats.today_brews },
    { label: "All time",        value: stats.total_brews },
    { label: "Users",           value: stats.total_users },
    { label: "Total brew time", value: fmt(stats.total_brew_time) },
    { label: "Top brewer",      value: stats.top_brewer ?? "-" },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map(c => (
        <div key={c.label} className="bg-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold">{c.value}</div>
          <div className="text-sm text-gray-400 mt-1">{c.label}</div>
        </div>
      ))}
    </div>
  )
}
