# CREMA - Kiosk UI

The kiosk UI runs at `/kiosk` in Chromium, full-screen on the 5" DSI touchscreen (800×480).

## Routing

`dashboard/src/App.tsx` checks `window.location.pathname`:

```tsx
const kiosk = window.location.pathname.replace(/^\/ui/, '').startsWith('/kiosk')
return <AuthGate kiosk={kiosk} />
```

No router library is needed because path selection is simple. The shared gate checks `/auth/session` before mounting either application. In session mode, the kiosk presents a compact sign-in view before enabling protected actions; a 401 from an expired or revoked session returns it to that view. Token mode retains the existing embedded-token behavior.

## File layout

```
dashboard/src/kiosk/
  KioskApp.tsx              Top-level router: picks screen, shows overlays
  hooks/
    useKioskSocket.ts       WebSocket hook with reconnect and snapshot retention
    useKioskSound.ts        Opt-in cues and browser-local quiet hours
  screens/
    Idle.tsx                Waiting for QR scan
    Armed.tsx               User logged in, awaiting brew
    Brewing.tsx             Brew in progress
    AnonBrewing.tsx         Brew without a user
    Summary.tsx             End-of-session summary
  overlays/
    AudioControls.tsx       Opt-in sound toggle and quiet-hours settings
    HardwareWarning.tsx     Non-blocking scanner and sensor status
    LivePanel.tsx           Compact connection and hardware readiness indicators
    RatingPrompt.tsx        1-5 star rating (auto-dismiss 15 s)
    Reconnecting.tsx        Full-screen state before the first valid snapshot
    StatusToast.tsx         Stale-data notice while reconnecting
```

## WebSocket hook (`useKioskSocket.ts`)

```ts
const { snapshot, connected } = useKioskSocket()
```

- Connects to `ws://<host>/ws/kiosk`, or the WebSocket equivalent of `VITE_API_URL` when configured
- Receives `KioskSnapshot` JSON on every server push
- Starts with no snapshot and becomes live only after receiving state on the current connection
- Retries when the server has no state or the connection closes, and treats stale message streams as disconnected
- Retains the last valid snapshot after disconnect, but marks it stale and pauses screen controls until a fresh valid snapshot arrives
- Uses `<Reconnecting />` only before any valid snapshot and `<StatusToast />` while a retained snapshot is stale
- Shows `<LivePanel />` connection and readiness indicators; connected snapshots with unavailable hardware also trigger `<HardwareWarning />`

`KioskSnapshot` type:
```ts
{
  state: "idle" | "armed" | "brewing" | "anon_brew" | "summary"
  user: string | null
  brew_count: number
  session_brew_time: number
  time_remaining: number | null   // null except in ARMED
  timeout: number | null          // null except in ARMED
  elapsed: number | null          // null except in BREWING/ANON_BREW
  shot_type: "single" | "double"
  decaf: boolean
  last_brew_id: number | null
  avg_rating: number | null       // non-null in SUMMARY
  session_started_at: number | null
  brew_started_at: number | null
  hardware: KioskHardware | null
}
```

## Screen: Armed

Most complex screen. Layout:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Left 40%                          Right 60%                              │
│  ─────────────────────────         ─────────────────────────              │
│  [Playfair italic] alice           [SINGLE] [DOUBLE]                      │
│  2 coffees this session            [OFF] [ON]                             │
│                                    [Finish session]                       │
├──────────────────────────────────────────────────────────────────────────┤
│  ████████████████░░░░░░░░  timeout bar (animated, ARMED_TIMEOUT / SESSION)│
└──────────────────────────────────────────────────────────────────────────┘
```

Toggle active state: `bg-crema-500 text-surface` / inactive: `bg-surface text-faint border-border`.

Brew options (shot type, decaf) are adjustable during `BREWING` as well.

## Overlay: RatingPrompt

Triggered in `KioskApp.tsx` when:
1. State transitions from `brewing` or `anon_brew` to `armed`
2. `last_brew_id` changes (new brew completed)

Behaviour:
- 5 tappable stars
- 15 s countdown → auto-dismiss
- On tap: awaits `api.kioskRate(last_brew_id, rating)` and dismisses only after success
- Failed requests preserve the prompt with an error and retry path
- The prompt is bound to its brew ID and dismissed on user handoff or when that brew disappears

## Overlay: AudioControls

Sound feedback is opt-in and off by default. Enabling it from a touch gesture creates or resumes the browser `AudioContext`. Cues follow scan, brew, and hardware-error changes; reconnecting alone does not replay the current snapshot as a new event.

`Audio settings` exposes feedback and quiet-hours controls. The settings live only in this browser's `crema.kiosk.sound` localStorage key, not in SQLite or server metrics. The legacy `on` and `off` values still load correctly.

Quiet hours default to enabled from 22:00 through 07:00 local browser time, including overnight schedules. They suppress new output only and do not change kiosk state. Equal start and end times mean no scheduled suppression. Clear or corrupt preferences safely return to sound off.

## Overlay: HardwareWarning

The top-right warning lists the scanner, sensor, or both when they are unavailable. It uses a lower stacking layer than reconnecting and rating overlays, and it must not cover controls at 800 x 480.

## Design tokens

Matches the dashboard:
- **Font display**: Playfair Display (italic for user names)
- **Font mono**: IBM Plex Mono (times, counters)
- **Font body**: DM Sans
- **Palette**: warm cream from `crema-50` through `crema-900`, plus `surface`, `border`, and `faint`

All defined in `dashboard/tailwind.config.js`.

## Brew options API calls

```ts
api.kioskBrewOptions({ shot_type: "single", decaf: true })
```

Options are sticky per session. The server resets them to `shot_type="double"`, `decaf=false` on every new user login.
