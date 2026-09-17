import { lazy, Suspense } from "react"
import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { RecentBrews }  from "./components/RecentBrews"
import { KioskApp }    from "./kiosk/KioskApp"
import { api } from "./api"
import { usePolling } from "./hooks/usePolling"
import { useElapsed } from "./hooks/useElapsed"
import { SkeletonBlock } from "./components/Skeleton"

const DailyChart = lazy(() =>
  import("./components/DailyChart").then(module => ({ default: module.DailyChart })),
)

export default function App() {
  if (window.location.pathname.replace(/^\/ui/, '').startsWith('/kiosk')) {
    return <KioskApp />
  }

  return <DashboardApp />
}

function DashboardApp() {
  const { data: status } = usePolling(api.status, 5000)
  const elapsed = useElapsed(status?.brew_started_at ?? null)
  const brewing = status?.state === "brewing" || status?.state === "anon_brew"

  return (
    <div className="min-h-screen bg-bg text-ink flex flex-col">

      {/* Unified hero block */}
      <div className="border-b border-border text-center px-8 pt-10 pb-6">
        <p className="text-xs uppercase tracking-[0.25em] text-faint mb-3">Benvenuti al</p>
        <h1 className="font-display italic text-6xl text-ink tracking-tight">Caffè Cabrini</h1>
        <div className="mt-3 flex items-center justify-center gap-3">
          <span className="h-px w-12 bg-border" />
          <span className="text-xs uppercase tracking-[0.2em] text-crema-400">Crema</span>
          <span className="h-px w-12 bg-border" />
        </div>
        {!brewing && (
          <div className="mt-4">
            <StatusBadge />
          </div>
        )}
      </div>

      {/* Brewing now strip */}
      {brewing && (
        <div className="bg-crema-500 px-8 py-3 flex items-center justify-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-surface opacity-70" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-surface" />
          </span>
          <span className="font-plex text-sm text-surface tracking-wide">
            {status?.user ?? "Anonymous"} is brewing - {elapsed}
          </span>
        </div>
      )}

      <main className="flex-1 max-w-5xl mx-auto w-full px-8 py-10 space-y-10">
        <StatsCards />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <h2 className="font-display italic text-muted text-base mb-4">Leaderboard</h2>
            <Leaderboard />
          </div>
          <Suspense fallback={<SkeletonBlock className="h-[250px]" />}>
            <DailyChart />
          </Suspense>
        </div>
        <RecentBrews />
      </main>

      <footer className="border-t border-border px-8 py-6 flex items-center justify-between">
        <span className="font-plex text-xs text-faint">
          © {new Date().getFullYear()} roncofaber
        </span>
        <span className="font-plex text-xs text-faint uppercase tracking-widest">CREMA</span>
        <a
          href="https://github.com/roncofaber/crema"
          target="_blank"
          rel="noopener noreferrer"
          className="font-plex text-xs text-faint hover:text-muted transition-colors"
        >
          github.com/roncofaber/crema
        </a>
      </footer>

    </div>
  )
}
