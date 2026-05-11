import { useEffect, useState } from "react"
import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { DailyChart }   from "./components/DailyChart"
import { RecentBrews }  from "./components/RecentBrews"
import { api } from "./api"
import { usePolling } from "./hooks/usePolling"

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

export default function App() {
  const { data: status } = usePolling(api.status, 5000)
  const elapsed = useElapsed(status?.session_started_at ?? null)
  const brewing = status?.state === "active"

  return (
    <div className="min-h-screen bg-bg text-ink">
      {/* Welcome banner */}
      <div className="border-b border-border text-center px-8 py-8">
        <p className="text-xs uppercase tracking-[0.25em] text-faint mb-2">Benvenuti al</p>
        <h1 className="font-display italic text-4xl text-ink tracking-tight">Caffè Cabrini</h1>
        <div className="mt-3 flex items-center justify-center gap-3">
          <span className="h-px w-12 bg-border" />
          <span className="text-xs uppercase tracking-[0.2em] text-crema-400">Crema</span>
          <span className="h-px w-12 bg-border" />
        </div>
      </div>

      {/* Brewing now strip */}
      {brewing && (
        <div className="bg-crema-500 px-8 py-3 flex items-center justify-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-surface opacity-70" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-surface" />
          </span>
          <span className="font-plex text-sm text-surface tracking-wide">
            {status?.user} is brewing — {elapsed}
          </span>
        </div>
      )}

      {/* Dashboard bar */}
      <header className="border-b border-border px-8 py-4 flex items-center justify-between">
        <span className="font-plex text-xs text-faint uppercase tracking-widest">Dashboard</span>
        {!brewing && <StatusBadge />}
      </header>

      <main className="max-w-5xl mx-auto px-8 py-10 space-y-10">
        <StatsCards />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <h2 className="font-display italic text-muted text-base mb-4">Leaderboard</h2>
            <Leaderboard />
          </div>
          <DailyChart />
        </div>
        <div>
          <h2 className="font-display italic text-muted text-base mb-4">Recent brews</h2>
          <RecentBrews />
        </div>
      </main>
    </div>
  )
}
