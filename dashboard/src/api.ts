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
  brews:      (limit = 20) => get<Brew[]>(`/brews/?limit=${limit}`),
}
