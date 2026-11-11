import { lazy, Suspense, useEffect, useState } from "react"
import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { RecentBrews }  from "./components/RecentBrews"
import { KioskApp }    from "./kiosk/KioskApp"
import { api } from "./api"
import { usePolling } from "./hooks/usePolling"
import { useElapsed } from "./hooks/useElapsed"
import { SkeletonBlock } from "./components/Skeleton"
import { Login } from "./components/Login"

const DailyChart = lazy(() =>
  import("./components/DailyChart").then(module => ({ default: module.DailyChart })),
)

export default function App() {
  const kiosk = window.location.pathname.replace(/^\/ui/, '').startsWith('/kiosk')
  return <AuthGate kiosk={kiosk} />
}

function AuthGate({ kiosk }: { kiosk: boolean }) {
  const [mode, setMode] = useState<string | null>(null)
  const [authenticated, setAuthenticated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    api.authSession(controller.signal).then(result => {
      setMode(result.mode)
      setAuthenticated(result.authenticated)
    }).catch(cause => {
      if (!controller.signal.aborted) setError(String(cause))
    })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    const unauthorized = () => {
      if (mode === 'session') setAuthenticated(false)
    }
    window.addEventListener('crema:unauthorized', unauthorized)
    return () => window.removeEventListener('crema:unauthorized', unauthorized)
  }, [mode])

  if (mode === null) {
    return (
      <main className="min-h-screen bg-bg text-ink flex items-center justify-center px-6">
        <div className="text-center" role="status">
          <p className="font-display italic text-4xl">CREMA</p>
          {error && <p role="alert" className="mt-3 font-plex text-xs">{error}</p>}
          {error
            ? <button onClick={() => { setError(null); setAttempt(value => value + 1) }} className="mt-5 min-h-11 px-5 rounded border border-border font-plex text-xs uppercase tracking-widest">Retry</button>
            : <p className="mt-3 font-plex text-xs text-muted">Loading {kiosk ? 'kiosk' : 'dashboard'}...</p>}
        </div>
      </main>
    )
  }
  if (mode === 'session' && !authenticated) {
    return <Login kiosk={kiosk} onAuthenticated={() => setAuthenticated(true)} />
  }
  if (kiosk) return <KioskApp />
  return <DashboardApp sessionAuth={mode === 'session'} onSignedOut={() => setAuthenticated(false)} />
}

function DashboardApp({ sessionAuth, onSignedOut }: { sessionAuth: boolean; onSignedOut: () => void }) {
  const { data: status, error: statusError, loading: statusLoading, stale: statusStale } = usePolling(api.status, 5000)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const elapsed = useElapsed(status?.brew_started_at ?? null)
  const brewing = status?.state === "brewing" || status?.state === "anon_brew"

  async function signOut() {
    setSignOutError(null)
    try {
      await api.authLogout()
      onSignedOut()
    } catch {
      setSignOutError('Could not sign out. Try again.')
    }
  }

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
            <StatusBadge status={status} error={statusError} loading={statusLoading} stale={statusStale} />
          </div>
        )}
        {brewing && statusError && (
          <p role="alert" className="mt-3 font-plex text-xs text-muted">
            Status update failed. Showing the last known state.
          </p>
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

      <footer className="border-t border-border px-8 py-6 flex flex-wrap gap-4 items-center justify-between">
        <span className="font-plex text-xs text-faint">
          © {new Date().getFullYear()} roncofaber
        </span>
        {sessionAuth && (
          <span className="flex items-center gap-3">
            {signOutError && <span role="alert" className="font-plex text-xs text-ink">{signOutError}</span>}
            <button onClick={() => { void signOut() }} className="min-h-11 px-3 font-plex text-xs text-faint uppercase tracking-widest hover:text-muted">
              Sign out
            </button>
          </span>
        )}
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
