import type { User, Brew, OverallStats, DailyStats, Status } from "./types"

const BASE = import.meta.env.VITE_API_URL ?? ""
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ""

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (TOKEN) headers.set("Authorization", `Bearer ${TOKEN}`)
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  status:     ()           => request<Status>("/status"),
  stats:      ()           => request<OverallStats>("/stats/"),
  dailyStats: (days = 30)  => request<DailyStats[]>(`/stats/daily?days=${days}`),
  users:      ()           => request<User[]>("/users/"),
  brews:      (limit = 20, kind: string | null = "brew") =>
    request<Brew[]>(`/brews/?limit=${limit}${kind ? `&kind=${kind}` : ""}`),
  kioskLogout: () => request<{ ok: boolean }>("/kiosk/logout", { method: "POST" }),
  kioskBrewOptions: (opts: { shot_type: string; decaf: boolean }) =>
    request<{ ok: boolean }>("/kiosk/brew-options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    }),
  kioskRate: (brew_id: number, rating: number) =>
    request<{ ok: boolean }>("/kiosk/rate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brew_id, rating }),
    }),
}
