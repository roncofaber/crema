import { useState } from "react"
import { api } from "../api"
import type { BrewFilters } from "../api"
import { usePolling } from "../hooks/usePolling"
import { SkeletonRow } from "./Skeleton"

function relTime(ts: number): string {
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 60) return `${s}s ago`
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

function timestamp(date: string, end = false): number | undefined {
  if (!date) return undefined
  const value = new Date(`${date}T00:00:00`)
  if (end) value.setDate(value.getDate() + 1)
  return value.getTime() / 1000 - (end ? 0.001 : 0)
}

type KindFilter = "brew" | "noise" | "all"
type ChoiceFilter = "all" | "single" | "double"
type DecafFilter = "all" | "yes" | "no"

export function RecentBrews() {
  const [user, setUser] = useState("")
  const [kind, setKind] = useState<KindFilter>("brew")
  const [shotType, setShotType] = useState<ChoiceFilter>("all")
  const [decaf, setDecaf] = useState<DecafFilter>("all")
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const trimmedUser = user.trim()
  const filters: BrewFilters = {
    limit: 100,
    ...(kind !== "all" && { kind }),
    ...(trimmedUser && { user: trimmedUser }),
    ...(shotType !== "all" && { shot_type: shotType }),
    ...(decaf !== "all" && { decaf: decaf === "yes" }),
    ...(fromDate && { from_ts: timestamp(fromDate) }),
    ...(toDate && { to_ts: timestamp(toDate, true) }),
  }
  const { data: brews, error, loading, stale } = usePolling(
    signal => api.brews(filters, signal),
    15_000,
    [trimmedUser, kind, shotType, decaf, fromDate, toDate],
  )
  const filtered = kind !== "brew" || shotType !== "all" || decaf !== "all" || !!trimmedUser || !!fromDate || !!toDate
  const showKind = kind !== "brew"
  const columns = showKind ? 6 : 5

  function reset() {
    setUser("")
    setKind("brew")
    setShotType("all")
    setDecaf("all")
    setFromDate("")
    setToDate("")
  }

  return (
    <section className="bg-surface rounded overflow-hidden" aria-labelledby="recent-brews-title">
      <div className="px-4 py-3 border-b border-border flex flex-wrap gap-3 items-center justify-between">
        <span id="recent-brews-title" className="font-display italic text-muted text-base">Recent brews</span>
        {filtered && (
          <button onClick={reset} className="min-h-9 px-3 rounded font-plex text-xs uppercase tracking-widest text-faint hover:text-muted">
            Reset filters
          </button>
        )}
      </div>
      <div role="region" aria-label="Brew filters" tabIndex={0} className="overflow-x-auto border-b border-border-subtle">
        <div className="flex w-max gap-3 px-4 py-3">
        <label className="w-40 shrink-0 font-plex text-xs text-muted">User
          <input value={user} onChange={event => setUser(event.target.value)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink" placeholder="Exact name" />
        </label>
        <label className="w-40 shrink-0 font-plex text-xs text-muted">Records
          <select value={kind} onChange={event => setKind(event.target.value as KindFilter)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink">
            <option value="brew">Brews only</option>
            <option value="noise">Noise only</option>
            <option value="all">All records</option>
          </select>
        </label>
        <label className="w-40 shrink-0 font-plex text-xs text-muted">Shot
          <select value={shotType} onChange={event => setShotType(event.target.value as ChoiceFilter)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink">
            <option value="all">Any shot</option>
            <option value="single">Single</option>
            <option value="double">Double</option>
          </select>
        </label>
        <label className="w-40 shrink-0 font-plex text-xs text-muted">Decaf
          <select value={decaf} onChange={event => setDecaf(event.target.value as DecafFilter)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink">
            <option value="all">Any</option>
            <option value="yes">Decaf only</option>
            <option value="no">Non-decaf</option>
          </select>
        </label>
        <label className="w-40 shrink-0 font-plex text-xs text-muted">From
          <input type="date" value={fromDate} max={toDate || undefined} onChange={event => setFromDate(event.target.value)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink" />
        </label>
        <label className="w-40 shrink-0 font-plex text-xs text-muted">To
          <input type="date" value={toDate} min={fromDate || undefined} onChange={event => setToDate(event.target.value)} className="mt-1 w-full min-h-10 rounded border border-border bg-bg px-2 text-sm text-ink" />
        </label>
        </div>
      </div>
      {error && stale && brews && (
        <p role="alert" className="px-4 py-2 border-b border-border font-plex text-xs text-muted" title={error}>
          Brew list update failed. Showing the last update.
        </p>
      )}
      <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] md:min-w-0 text-sm" aria-busy={loading}>
        <thead>
          <tr className="border-b border-border-subtle">
            <th className="text-left px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">User</th>
            <th className="text-left px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">When</th>
            <th className="text-right px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">Duration</th>
            <th className="hidden md:table-cell text-right px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">Shot</th>
            <th className="hidden md:table-cell text-right px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">Rating</th>
            {showKind && <th className="text-right px-4 py-2 text-xs uppercase tracking-widest text-faint font-normal">Kind</th>}
          </tr>
        </thead>
        <tbody>
          {brews == null
            ? error
              ? <tr><td colSpan={columns} role="alert" title={error} className="px-4 py-8 text-center font-plex text-xs text-muted">Recent brews unavailable. Retrying...</td></tr>
              : Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={columns} />)
            : brews.length === 0
              ? <tr><td colSpan={columns} className="px-4 py-8 text-center font-plex text-xs text-muted">No records match these filters.</td></tr>
              : brews.map(b => (
                <tr key={b.id} className={`border-b border-border-subtle last:border-0 ${b.kind === "noise" ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3 text-ink font-medium">
                    {b.user}
                    {b.shot_type && (
                      <span className="mt-1 block font-plex text-xs font-normal text-muted md:hidden">
                        {b.shot_type}{b.decaf ? " decaf" : ""}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-plex text-xs text-faint">{relTime(b.started_at)}</td>
                  <td className="px-4 py-3 text-right font-plex text-xs text-muted">{fmtDuration(b.duration)}</td>
                  <td className="hidden md:table-cell px-4 py-3 text-right font-plex text-xs text-muted">{b.shot_type ? `${b.shot_type}${b.decaf ? " decaf" : ""}` : "-"}</td>
                  <td className="hidden md:table-cell px-4 py-3 text-right font-plex text-xs text-crema-400">{b.rating == null ? "-" : `${b.rating} / 5`}</td>
                  {showKind && <td className={`px-4 py-3 text-right font-plex text-xs ${b.kind === "brew" ? "text-crema-400" : "text-faint"}`}>{b.kind}</td>}
                </tr>
              ))}
        </tbody>
      </table>
      </div>
    </section>
  )
}
