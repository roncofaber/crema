import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { DailyChart }   from "./components/DailyChart"
import { RecentBrews }  from "./components/RecentBrews"

export default function App() {
  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="border-b border-border px-8 py-5 flex items-center justify-between">
        <h1 className="font-display italic text-2xl text-crema-400 tracking-tight">Crema</h1>
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
