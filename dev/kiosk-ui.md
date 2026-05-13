# CREMA — Kiosk UI

The kiosk UI runs at `/kiosk` in Chromium, full-screen on the 5" DSI touchscreen (800×480).

## Routing

`dashboard/src/App.tsx` checks `window.location.pathname`:

```tsx
if (window.location.pathname.startsWith('/kiosk')) return <KioskApp />
// else: dashboard
```

No router library — simple path check.

## File layout

```
dashboard/src/kiosk/
  KioskApp.tsx              Top-level router: picks screen, shows overlays
  hooks/
    useKioskSocket.ts       WebSocket hook with auto-reconnect
  screens/
    Idle.tsx                Waiting for QR scan
    Armed.tsx               User logged in, awaiting brew
    Brewing.tsx             Brew in progress
    AnonBrewing.tsx         Brew without a user
    Summary.tsx             End-of-session summary
  overlays/
    RatingPrompt.tsx        1–5 star rating (auto-dismiss 15 s)
    Reconnecting.tsx        Shown when WebSocket is disconnected
```

## WebSocket hook (`useKioskSocket.ts`)

```ts
const { snapshot, connected } = useKioskSocket()
```

- Connects to `ws://<host>/ws/kiosk`
- Receives `KioskSnapshot` JSON on every server push
- Exponential backoff reconnect: 2 s → ×1.5 → 15 s cap
- `connected: false` triggers `<Reconnecting />` overlay

`KioskSnapshot` type:
```ts
{
  state: "idle" | "armed" | "brewing" | "anon_brew" | "summary"
  user: string | null
  brew_count: number
  time_remaining: number | null   // null except in ARMED
  timeout: number | null          // null except in ARMED
  elapsed: number | null          // null except in BREWING/ANON_BREW
  shot_type: "single" | "double"
  decaf: boolean
  last_brew_id: number | null
  avg_rating: number | null       // non-null in SUMMARY
}
```

## Screen: Armed

Most complex screen. Layout:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Left 60%                          Right 40%                              │
│  ─────────────────────────         ─────────────────────────              │
│  [Playfair italic] alice           [SINGLE] [DOUBLE]                      │
│  2 brews · start the machine       [REGULAR] [DECAF]                      │
│                                    [Logout]                               │
├──────────────────────────────────────────────────────────────────────────┤
│  ████████████████░░░░░░░░  timeout bar (animated, ARMED_TIMEOUT / SESSION)│
└──────────────────────────────────────────────────────────────────────────┘
```

Toggle active state: `bg-crema-500 text-surface` / inactive: `bg-surface text-faint border-border`.

Brew options (shot type, decaf) are adjustable during `BREWING` as well.

## Overlay: RatingPrompt

Triggered in `KioskApp.tsx` when:
1. State transitions from `brewing` → `armed`
2. `last_brew_id` changes (new brew completed)

Behaviour:
- 5 tappable stars
- 15 s countdown → auto-dismiss
- On tap: calls `api.kioskRate(last_brew_id, rating)` → dismiss

## Design tokens

Matches the dashboard:
- **Font display**: Playfair Display (italic for user names)
- **Font mono**: IBM Plex Mono (times, counters)
- **Font body**: DM Sans
- **Palette**: warm cream — `crema-50` … `crema-900`, `surface`, `border`, `faint`

All defined in `dashboard/tailwind.config.js`.

## Brew options API calls

```ts
api.kioskBrewOptions({ shot_type: "single", decaf: true })
```

Options are sticky per session. The server resets them to `shot_type="double"`, `decaf=false` on every new user login.
