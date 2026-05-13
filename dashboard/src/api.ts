import type { User, Brew, OverallStats, DailyStats, Status } from "./types"

const BASE  = import.meta.env.VITE_API_URL  ?? ""
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ""

async function get<T>(path: string): Promise<T> {
  const headers: HeadersInit = TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}
  const res = await fetch(`${BASE}${path}`, { headers })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export const api = {
  status:     ()           => get<Status>("/status"),
  stats:      ()           => get<OverallStats>("/stats/"),
  dailyStats: (days = 30)  => get<DailyStats[]>(`/stats/daily?days=${days}`),
  users:      ()           => get<User[]>("/users/"),
  brews:      (limit = 20, kind: string | null = "brew") =>
    get<Brew[]>(`/brews/?limit=${limit}${kind ? `&kind=${kind}` : ""}`),
  kioskLogout: () => {
    const headers: HeadersInit = TOKEN ? { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
    return fetch(`${BASE}/kiosk/logout`, { method: 'POST', headers })
  },
  kioskBrewOptions: (opts: { shot_type: string; decaf: boolean }) => {
    const headers: HeadersInit = TOKEN ? { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
    return fetch(`${BASE}/kiosk/brew-options`, { method: 'POST', headers, body: JSON.stringify(opts) })
  },
  kioskRate: (brew_id: number, rating: number) => {
    const headers: HeadersInit = TOKEN ? { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
    return fetch(`${BASE}/kiosk/rate`, { method: 'POST', headers, body: JSON.stringify({ brew_id, rating }) })
  },
}
