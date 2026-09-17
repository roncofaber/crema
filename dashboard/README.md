# CREMA frontend

This Vite, React, and TypeScript application builds two interfaces from one bundle:

- `/ui` is the responsive operations dashboard.
- `/kiosk` is the dedicated 800 x 480 Raspberry Pi touchscreen interface.

FastAPI serves the production build from `dashboard/dist/`.

## Setup

```bash
npm ci
```

Supported Node.js versions are 20.19.x, or 22.12 or newer, as declared in `package.json`.

## Development

Start the API on port 8000 first, then run:

```bash
npm run dev
```

Open:

- Dashboard: `http://localhost:5173/ui/`
- Kiosk: `http://localhost:5173/ui/kiosk`

The Vite server proxies REST and WebSocket requests to `http://localhost:8000`. See `../dev/development.md` for API-only startup and database isolation.

## Production build

```bash
npm run build
```

The build runs TypeScript project compilation and writes static assets to `dist/`. Do not edit that directory directly.

If API authentication is enabled, provide the browser token at build time:

```bash
VITE_API_TOKEN=your-secret-token npm run build
```

The value is embedded in client assets and is suitable only for a trusted local network.

## Checks

```bash
npm run lint
npm run build
npm audit --audit-level=high
```

For kiosk changes, also inspect affected states at exactly 800 x 480 and confirm there is no page overflow or control overlap.

## Source layout

```text
src/
  App.tsx                  Route selection and dashboard layout
  api.ts                   REST client
  components/              Dashboard cards, tables, charts, and status
  hooks/                   Dashboard polling hooks
  kiosk/
    KioskApp.tsx           Kiosk state screen selection and overlays
    hooks/                 WebSocket state client
    overlays/              Rating, reconnecting, and hardware alerts
    screens/               Idle, armed, brewing, anonymous, and summary screens
```
