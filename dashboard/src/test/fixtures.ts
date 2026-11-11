import type { KioskSnapshot } from '../kiosk/hooks/useKioskSocket'

export function makeSnapshot(overrides: Partial<KioskSnapshot> = {}): KioskSnapshot {
  return {
    state: 'armed',
    user: 'alice',
    brew_count: 0,
    session_brew_time: 0,
    time_remaining: 120,
    timeout: 120,
    elapsed: null,
    shot_type: 'double',
    decaf: false,
    last_brew_id: null,
    avg_rating: null,
    session_started_at: 1000,
    brew_started_at: null,
    hardware: {
      running: true,
      scanner: { connected: true, error: null, last_scan_at: null },
      sensor: { connected: true, error: null, last_read_at: 1000, stale_age: 0.1 },
    },
    ...overrides,
  }
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}
