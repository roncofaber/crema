import createClient from "openapi-fetch"
import type { components, paths } from "./generated/api"

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "")
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ""

const client = createClient<paths>({
  baseUrl: BASE,
  credentials: "include",
  headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : undefined,
})

type ApiResult<T> = {
  data?: T
  error?: unknown
  response: Response
}

async function unwrap<T>(result: Promise<ApiResult<T>>, path: string): Promise<T> {
  const { data, response } = await result
  if (response.status === 401 && !path.startsWith("/auth/")) {
    window.dispatchEvent(new Event("crema:unauthorized"))
  }
  if (!response.ok || data === undefined) throw new Error(`${response.status} ${path}`)
  return data
}

export type BrewOptions = components["schemas"]["BrewOptions"]
export type BrewFilters = NonNullable<paths["/brews/"]["get"]["parameters"]["query"]>

export function kioskWebSocketUrl(): string {
  const url = new URL(`${BASE || window.location.origin}/ws/kiosk`, window.location.origin)
  if (url.protocol === "http:") url.protocol = "ws:"
  else if (url.protocol === "https:") url.protocol = "wss:"
  else if (url.protocol !== "ws:" && url.protocol !== "wss:") {
    throw new Error(`Unsupported API protocol: ${url.protocol}`)
  }
  return url.toString()
}

export const api = {
  authSession: (signal?: AbortSignal) =>
    unwrap(client.GET("/auth/session", { signal }), "/auth/session"),
  authLogin: (password: string) =>
    unwrap(client.POST("/auth/login", { body: { password } }), "/auth/login"),
  authLogout: () => unwrap(client.POST("/auth/logout"), "/auth/logout"),
  status: (signal?: AbortSignal) => unwrap(client.GET("/status", { signal }), "/status"),
  stats: (signal?: AbortSignal) => unwrap(client.GET("/stats/", { signal }), "/stats/"),
  dailyStats: (days = 30, signal?: AbortSignal) =>
    unwrap(client.GET("/stats/daily", { params: { query: { days } }, signal }), "/stats/daily"),
  users: (signal?: AbortSignal) => unwrap(client.GET("/users/", { signal }), "/users/"),
  brews: (filters: BrewFilters = {}, signal?: AbortSignal) =>
    unwrap(client.GET("/brews/", { params: { query: filters }, signal }), "/brews/"),
  kioskLogout: (session_started_at: number) =>
    unwrap(client.POST("/kiosk/logout", { body: { session_started_at } }), "/kiosk/logout"),
  kioskBrewOptions: (options: BrewOptions) =>
    unwrap(client.POST("/kiosk/brew-options", { body: options }), "/kiosk/brew-options"),
  kioskRate: (brew_id: number, rating: number) =>
    unwrap(client.POST("/kiosk/rate", { body: { brew_id, rating } }), "/kiosk/rate"),
}
