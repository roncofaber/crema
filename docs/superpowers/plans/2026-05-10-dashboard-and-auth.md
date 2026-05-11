# CREMA Dashboard and Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bearer token authentication to the FastAPI API and build a React dashboard showing live status, leaderboard, daily chart, stats, and recent brews — served from the same FastAPI process.

**Architecture:** Auth is a FastAPI dependency (`api/auth.py`) applied to all routers; it is disabled when `CREMA_API_TOKEN` env var is unset (safe default for local dev). The dashboard is a Vite + React + TypeScript app in `dashboard/` built to `dashboard/dist/`; FastAPI mounts that directory at `/ui` as static files. In development, Vite proxies API calls to localhost:8000. No frontend unit tests — the API already has full coverage; UI correctness is verified by running the dev server.

**Tech Stack:** FastAPI, Vite, React 18, TypeScript, Tailwind CSS, Recharts, aiofiles

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `api/auth.py` | Create | `verify_token` FastAPI dependency |
| `api/main.py` | Modify | Apply auth dependency to all routers; mount static files |
| `pyproject.toml` | Modify | Add `aiofiles` dependency |
| `tests/test_api.py` | Modify | Add auth tests |
| `dashboard/` | Create | Vite project root |
| `dashboard/vite.config.ts` | Create | Dev proxy config |
| `dashboard/tailwind.config.js` | Create | Tailwind content paths |
| `dashboard/postcss.config.js` | Create | Tailwind + autoprefixer |
| `dashboard/src/index.css` | Modify | Tailwind directives |
| `dashboard/src/types.ts` | Create | TypeScript types matching API schemas |
| `dashboard/src/api.ts` | Create | Typed fetch wrapper |
| `dashboard/src/hooks/usePolling.ts` | Create | Generic polling hook |
| `dashboard/src/components/StatusBadge.tsx` | Create | Live status (polls /status every 5s) |
| `dashboard/src/components/StatsCards.tsx` | Create | Today/all-time stats cards |
| `dashboard/src/components/Leaderboard.tsx` | Create | User table sorted by brew count |
| `dashboard/src/components/DailyChart.tsx` | Create | Recharts bar chart of brews per day |
| `dashboard/src/components/RecentBrews.tsx` | Create | Table of last 20 brews |
| `dashboard/src/App.tsx` | Modify | Main layout composing all components |

---

## Task 1: API token auth

**Files:**
- Create: `api/auth.py`
- Modify: `api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Create `api/auth.py`**

```python
import os
from fastapi import Header, HTTPException

_TOKEN = os.getenv("CREMA_API_TOKEN", "")


async def verify_token(authorization: str | None = Header(None)):
    if not _TOKEN:
        return  # auth disabled when env var not set
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
```

- [ ] **Step 2: Update `api/main.py`** to apply the dependency to all routers

```python
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import verify_token
from api.routers import users, brews, stats, status

app = FastAPI(title="CREMA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_token)]

app.include_router(users.router,  prefix="/users",  tags=["users"],  dependencies=_auth)
app.include_router(brews.router,  prefix="/brews",  tags=["brews"],  dependencies=_auth)
app.include_router(stats.router,  prefix="/stats",  tags=["stats"],  dependencies=_auth)
app.include_router(status.router,                   tags=["status"], dependencies=_auth)


@app.get("/")
def root():
    return {"status": "ok"}
```

- [ ] **Step 3: Add auth tests** — append to `tests/test_api.py`:

```python
def test_auth_disabled_by_default(client):
    resp = client.get("/users/")
    assert resp.status_code == 200


def test_auth_required_when_token_set(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/")
    assert resp.status_code == 401


def test_auth_valid_token(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200


def test_auth_invalid_token(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_api.py -v
```

Expected: all tests pass (existing tests unaffected because `_TOKEN` is empty by default).

- [ ] **Step 5: Commit**

```bash
git add api/auth.py api/main.py tests/test_api.py
git commit -m "feat: add bearer token auth to API"
```

---

## Task 2: Dashboard project scaffold

**Files:**
- Create: `dashboard/` (entire Vite project)
- Modify: `dashboard/vite.config.ts`
- Modify: `dashboard/tailwind.config.js`
- Create: `dashboard/postcss.config.js`

- [ ] **Step 1: Scaffold the Vite project**

```bash
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install
npm install recharts
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: Replace `dashboard/vite.config.ts`**

```typescript
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/users": "http://localhost:8000",
      "/brews": "http://localhost:8000",
      "/stats": "http://localhost:8000",
      "/status": "http://localhost:8000",
    },
  },
})
```

- [ ] **Step 3: Replace `dashboard/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 4: Replace `dashboard/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 5: Replace `dashboard/src/App.tsx`** with a minimal placeholder

```tsx
export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <p className="text-gray-400">CREMA dashboard loading...</p>
    </div>
  )
}
```

- [ ] **Step 6: Verify build succeeds**

```bash
cd dashboard && npm run build
```

Expected: `dashboard/dist/` created with no errors.

- [ ] **Step 7: Commit**

```bash
cd ..
git add dashboard/
git commit -m "feat: scaffold Vite + React + Tailwind dashboard"
```

---

## Task 3: API client, types, polling hook

**Files:**
- Create: `dashboard/src/types.ts`
- Create: `dashboard/src/api.ts`
- Create: `dashboard/src/hooks/usePolling.ts`

- [ ] **Step 1: Create `dashboard/src/types.ts`**

```typescript
export interface User {
  id: number
  name: string
  token: string
  total_brews: number
  total_time: number
  last_brew: number | null
}

export interface Brew {
  id: number
  user: string
  started_at: number
  ended_at: number
  duration: number
  kind: string
}

export interface OverallStats {
  total_brews: number
  total_users: number
  total_brew_time: number
  today_brews: number
  top_brewer: string | null
}

export interface DailyStats {
  date: string
  brews: number
  total_duration: number
}

export interface Status {
  state: string
  user: string | null
  session_started_at: number | null
}
```

- [ ] **Step 2: Create `dashboard/src/api.ts`**

```typescript
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
```

- [ ] **Step 3: Create `dashboard/src/hooks/usePolling.ts`**

```typescript
import { useEffect, useState } from "react"

export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs: number,
): { data: T | null; error: string | null } {
  const [data, setData]   = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function tick() {
      try {
        const result = await fn()
        if (!cancelled) setData(result)
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }

    tick()
    const id = setInterval(tick, intervalMs)
    return () => { cancelled = true; clearInterval(id) }
  // fn changes identity every render; interval and fn logic are stable
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs])

  return { data, error }
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard/src/types.ts dashboard/src/api.ts dashboard/src/hooks/
git commit -m "feat: add API client, types, polling hook"
```

---

## Task 4: App layout and StatusBadge

**Files:**
- Create: `dashboard/src/components/StatusBadge.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Create `dashboard/src/components/StatusBadge.tsx`**

```tsx
import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

export function StatusBadge() {
  const { data: status } = usePolling(api.status, 5000)

  if (!status) return <span className="text-gray-500 text-sm">connecting...</span>

  const active = status.state === "active"
  return (
    <span className={`text-sm font-medium ${active ? "text-green-400" : "text-gray-500"}`}>
      {active ? `${status.user} is brewing` : "idle"}
    </span>
  )
}
```

- [ ] **Step 2: Replace `dashboard/src/App.tsx`** with the full layout shell

```tsx
import { StatusBadge } from "./components/StatusBadge"

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">CREMA</h1>
        <StatusBadge />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <p className="text-gray-500 text-sm">Components loading...</p>
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Start dev server and verify**

In one terminal:
```bash
crema serve
```

In another:
```bash
cd dashboard && npm run dev
```

Open `http://localhost:5173` — should show the header with "CREMA" and the status badge (idle or active depending on whether the Pi is running).

- [ ] **Step 4: Commit**

```bash
cd ..
git add dashboard/src/components/StatusBadge.tsx dashboard/src/App.tsx
git commit -m "feat: add app layout and live status badge"
```

---

## Task 5: Stats cards and Leaderboard

**Files:**
- Create: `dashboard/src/components/StatsCards.tsx`
- Create: `dashboard/src/components/Leaderboard.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Create `dashboard/src/components/StatsCards.tsx`**

```tsx
import { useEffect, useState } from "react"
import { api } from "../api"
import type { OverallStats } from "../types"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

export function StatsCards() {
  const [stats, setStats] = useState<OverallStats | null>(null)
  useEffect(() => { api.stats().then(setStats).catch(() => {}) }, [])

  if (!stats) return null

  const cards = [
    { label: "Today",           value: stats.today_brews },
    { label: "All time",        value: stats.total_brews },
    { label: "Users",           value: stats.total_users },
    { label: "Total brew time", value: fmt(stats.total_brew_time) },
    { label: "Top brewer",      value: stats.top_brewer ?? "-" },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map(c => (
        <div key={c.label} className="bg-gray-800 rounded-lg p-4">
          <div className="text-2xl font-bold">{c.value}</div>
          <div className="text-sm text-gray-400 mt-1">{c.label}</div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create `dashboard/src/components/Leaderboard.tsx`**

```tsx
import { useEffect, useState } from "react"
import { api } from "../api"
import type { User } from "../types"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

function fmtDate(ts: number | null): string {
  if (!ts) return "-"
  return new Date(ts * 1000).toLocaleDateString()
}

export function Leaderboard() {
  const [users, setUsers] = useState<User[]>([])
  useEffect(() => { api.users().then(setUsers).catch(() => {}) }, [])

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left px-4 py-3">#</th>
            <th className="text-left px-4 py-3">Name</th>
            <th className="text-right px-4 py-3">Brews</th>
            <th className="text-right px-4 py-3">Time</th>
            <th className="text-right px-4 py-3">Last brew</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u, i) => (
            <tr key={u.id} className="border-b border-gray-700 last:border-0 hover:bg-gray-750">
              <td className="px-4 py-3 text-gray-500">{i + 1}</td>
              <td className="px-4 py-3 font-medium">{u.name}</td>
              <td className="px-4 py-3 text-right">{u.total_brews}</td>
              <td className="px-4 py-3 text-right text-gray-300">{fmt(u.total_time)}</td>
              <td className="px-4 py-3 text-right text-gray-400">{fmtDate(u.last_brew)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Update `dashboard/src/App.tsx`**

```tsx
import { StatusBadge } from "./components/StatusBadge"
import { StatsCards }  from "./components/StatsCards"
import { Leaderboard } from "./components/Leaderboard"

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">CREMA</h1>
        <StatusBadge />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <StatsCards />
        <div>
          <h2 className="text-sm text-gray-400 mb-3">Leaderboard</h2>
          <Leaderboard />
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Verify in browser**

With `crema serve` and `npm run dev` running, open `http://localhost:5173` — stats cards and leaderboard should appear with real data.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/StatsCards.tsx dashboard/src/components/Leaderboard.tsx dashboard/src/App.tsx
git commit -m "feat: add stats cards and leaderboard"
```

---

## Task 6: Daily chart and Recent brews

**Files:**
- Create: `dashboard/src/components/DailyChart.tsx`
- Create: `dashboard/src/components/RecentBrews.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Create `dashboard/src/components/DailyChart.tsx`**

```tsx
import { useEffect, useState } from "react"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts"
import { api } from "../api"
import type { DailyStats } from "../types"

export function DailyChart() {
  const [data, setData] = useState<DailyStats[]>([])
  useEffect(() => { api.dailyStats(30).then(setData).catch(() => {}) }, [])

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-sm text-gray-400 mb-4">Brews per day (last 30 days)</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={d => d.slice(5)}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "none", borderRadius: "8px" }}
            labelStyle={{ color: "#f3f4f6" }}
            itemStyle={{ color: "#d1d5db" }}
          />
          <Bar dataKey="brews" fill="#f59e0b" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 2: Create `dashboard/src/components/RecentBrews.tsx`**

```tsx
import { useEffect, useState } from "react"
import { api } from "../api"
import type { Brew } from "../types"

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

function fmtDuration(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m ? `${m}m ${sec}s` : `${sec}s`
}

export function RecentBrews() {
  const [brews, setBrews] = useState<Brew[]>([])
  useEffect(() => { api.brews(20).then(setBrews).catch(() => {}) }, [])

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left px-4 py-3">User</th>
            <th className="text-left px-4 py-3">Time</th>
            <th className="text-right px-4 py-3">Duration</th>
            <th className="text-right px-4 py-3">Kind</th>
          </tr>
        </thead>
        <tbody>
          {brews.map(b => (
            <tr key={b.id} className="border-b border-gray-700 last:border-0">
              <td className="px-4 py-3">{b.user}</td>
              <td className="px-4 py-3 text-gray-400">{fmtTime(b.started_at)}</td>
              <td className="px-4 py-3 text-right text-gray-300">{fmtDuration(b.duration)}</td>
              <td className={`px-4 py-3 text-right ${b.kind === "brew" ? "text-amber-400" : "text-gray-500"}`}>
                {b.kind}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Replace `dashboard/src/App.tsx`** with the complete final layout

```tsx
import { StatusBadge }  from "./components/StatusBadge"
import { StatsCards }   from "./components/StatsCards"
import { Leaderboard }  from "./components/Leaderboard"
import { DailyChart }   from "./components/DailyChart"
import { RecentBrews }  from "./components/RecentBrews"

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">CREMA</h1>
        <StatusBadge />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <StatsCards />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <h2 className="text-sm text-gray-400 mb-3">Leaderboard</h2>
            <Leaderboard />
          </div>
          <DailyChart />
        </div>
        <div>
          <h2 className="text-sm text-gray-400 mb-3">Recent brews</h2>
          <RecentBrews />
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Verify in browser**

With `crema serve` and `npm run dev` running, open `http://localhost:5173` — the full dashboard should render: stats cards, leaderboard, bar chart, and recent brews table.

- [ ] **Step 5: Build and confirm no TS errors**

```bash
cd dashboard && npm run build
```

Expected: no TypeScript errors, `dist/` created.

- [ ] **Step 6: Commit**

```bash
cd ..
git add dashboard/src/components/DailyChart.tsx dashboard/src/components/RecentBrews.tsx dashboard/src/App.tsx
git commit -m "feat: add daily chart and recent brews"
```

---

## Task 7: FastAPI static file serving

**Files:**
- Modify: `api/main.py`
- Modify: `pyproject.toml`

The dashboard is served at `/ui`. FastAPI's `StaticFiles` with `html=True` means any unknown path under `/ui` falls back to `index.html` (needed for React client-side routing, if ever added).

- [ ] **Step 1: Add `aiofiles` to `pyproject.toml`** (required by FastAPI's StaticFiles)

Read the file first, then add `"aiofiles"` to the dependencies list:

```toml
[project]
name = "crema"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "RPi.GPIO",
    "evdev",
    "adafruit-circuitpython-rgb-display",
    "Pillow",
    "click",
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "aiofiles",
]

[project.scripts]
crema = "cli.main:cli"

[tool.setuptools]
py-modules = ["config", "main"]
packages   = ["core", "hardware", "cli", "api", "api.routers"]
```

- [ ] **Step 2: Install aiofiles**

```bash
pip install aiofiles
```

- [ ] **Step 3: Update `api/main.py`** to mount the dashboard at `/ui`

```python
import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.auth import verify_token
from api.routers import users, brews, stats, status

app = FastAPI(title="CREMA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_token)]

app.include_router(users.router,  prefix="/users",  tags=["users"],  dependencies=_auth)
app.include_router(brews.router,  prefix="/brews",  tags=["brews"],  dependencies=_auth)
app.include_router(stats.router,  prefix="/stats",  tags=["stats"],  dependencies=_auth)
app.include_router(status.router,                   tags=["status"], dependencies=_auth)


@app.get("/")
def root():
    return {"status": "ok"}


_DIST = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.isdir(_DIST):
    app.mount("/ui", StaticFiles(directory=_DIST, html=True), name="dashboard")
```

- [ ] **Step 4: Build the dashboard**

```bash
cd dashboard && npm run build && cd ..
```

- [ ] **Step 5: Start the API and verify the dashboard is served**

```bash
crema serve
```

Open `http://localhost:8000/ui` — the full dashboard should load.

Open `http://localhost:8000/users/` — API still works.

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add api/main.py pyproject.toml
git commit -m "feat: serve dashboard from FastAPI at /ui"
git push
```
