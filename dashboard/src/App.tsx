import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { DailyChart }   from "./components/DailyChart"
import { RecentBrews }  from "./components/RecentBrews"

export default function App() {
  return (
    <div className="min-h-screen bg-bg text-ink">
      <div className="border-b border-border text-center px-8 py-8">
        <p className="text-xs uppercase tracking-[0.25em] text-muted mb-2">Benvenuti al</p>
        <h1 className="font-display italic text-4xl text-ink tracking-tight">Caffè Cabrini</h1>
        <div className="mt-3 flex items-center justify-center gap-3">
          <span className="h-px w-12 bg-border" />
          <span className="text-xs uppercase tracking-[0.2em] text-crema-400">Crema</span>
          <span className="h-px w-12 bg-border" />
        </div>
      </div>
      <header className="border-b border-border px-8 py-4 flex items-center justify-between">
        <span className="font-plex text-xs text-faint uppercase tracking-widest">Dashboard</span>
        <StatusBadge />
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
