import { useEffect, useRef, useState } from 'react'
import { kioskWebSocketUrl } from '../../api'

export type KioskSnapshot = {
  state: 'idle' | 'armed' | 'brewing' | 'anon_brew' | 'summary'
  user: string | null
  brew_count: number
  session_brew_time: number
  time_remaining: number | null
  timeout: number | null
  elapsed: number | null
  shot_type: 'single' | 'double'
  decaf: boolean
  last_brew_id: number | null
  avg_rating: number | null
  session_started_at: number | null
  brew_started_at: number | null
  hardware: {
    running: boolean
    scanner: { connected: boolean; error: string | null; last_scan_at: number | null }
    sensor: {
      connected: boolean
      error: string | null
      last_read_at: number | null
      stale_age?: number | null
    }
  } | null
}

const STALE_AFTER_MS = 5000
const STATES = new Set(['idle', 'armed', 'brewing', 'anon_brew', 'summary'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isNumber(value)
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isDeviceHealth(value: unknown, timestampKey: 'last_scan_at' | 'last_read_at'): value is Record<string, unknown> {
  return isRecord(value) &&
    typeof value.connected === 'boolean' &&
    isNullableString(value.error) &&
    isNullableNumber(value[timestampKey])
}

export function isKioskSnapshot(value: unknown): value is KioskSnapshot {
  if (!isRecord(value)) return false
  const snapshot = value
  if (
    typeof snapshot.state !== 'string' || !STATES.has(snapshot.state) ||
    !isNullableString(snapshot.user) ||
    !isNumber(snapshot.brew_count) ||
    !isNumber(snapshot.session_brew_time) ||
    !isNullableNumber(snapshot.time_remaining) ||
    !isNullableNumber(snapshot.timeout) ||
    !isNullableNumber(snapshot.elapsed) ||
    (snapshot.shot_type !== 'single' && snapshot.shot_type !== 'double') ||
    typeof snapshot.decaf !== 'boolean' ||
    !isNullableNumber(snapshot.last_brew_id) ||
    !isNullableNumber(snapshot.avg_rating) ||
    !isNullableNumber(snapshot.session_started_at) ||
    !isNullableNumber(snapshot.brew_started_at)
  ) return false

  if (snapshot.hardware === null) return true
  const hardware = snapshot.hardware
  if (
    !isRecord(hardware) ||
    typeof hardware.running !== 'boolean' ||
    !isDeviceHealth(hardware.scanner, 'last_scan_at')
  ) return false
  const sensor = hardware.sensor
  return isDeviceHealth(sensor, 'last_read_at') &&
    (!('stale_age' in sensor) || isNullableNumber(sensor.stale_age))
}

export function useKioskSocket() {
  const [snapshot, setSnapshot] = useState<KioskSnapshot | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryDelay = useRef(2000)

  useEffect(() => {
    let disposed = false

    function clearWatchdog() {
      if (watchdogRef.current !== null) {
        clearTimeout(watchdogRef.current)
        watchdogRef.current = null
      }
    }

    function isCurrent(ws: WebSocket) {
      return !disposed && wsRef.current === ws
    }

    function makeUnavailable(ws: WebSocket) {
      if (!isCurrent(ws)) return
      clearWatchdog()
      setConnected(false)
    }

    function watch(ws: WebSocket) {
      clearWatchdog()
      watchdogRef.current = setTimeout(() => {
        if (!isCurrent(ws)) return
        makeUnavailable(ws)
        ws.close()
      }, STALE_AFTER_MS)
    }

    function scheduleReconnect() {
      if (disposed || retryRef.current !== null) return
      const delay = retryDelay.current
      retryDelay.current = Math.min(delay * 1.5, 15000)
      retryRef.current = setTimeout(() => {
        retryRef.current = null
        connect()
      }, delay)
    }

    function connect() {
      if (disposed) return
      let ws: WebSocket
      try {
        ws = new WebSocket(kioskWebSocketUrl())
      } catch (error) {
        console.error('Failed to open kiosk WebSocket:', error)
        scheduleReconnect()
        return
      }
      wsRef.current = ws
      setConnected(false)
      watch(ws)

      ws.onmessage = (event) => {
        if (!isCurrent(ws) || typeof event.data !== 'string') return
        try {
          const parsed: unknown = JSON.parse(event.data)
          if (!isKioskSnapshot(parsed)) {
            console.error('Invalid kiosk snapshot:', event.data)
            return
          }
          retryDelay.current = 2000
          setSnapshot(parsed)
          setConnected(true)
          watch(ws)
        } catch (error) {
          console.error('Failed to parse kiosk snapshot:', error, event.data)
        }
      }

      ws.onclose = () => {
        if (!isCurrent(ws)) return
        makeUnavailable(ws)
        wsRef.current = null
        scheduleReconnect()
      }

      ws.onerror = () => {
        if (!isCurrent(ws)) return
        makeUnavailable(ws)
        ws.close()
      }
    }

    connect()
    return () => {
      disposed = true
      clearWatchdog()
      if (retryRef.current !== null) clearTimeout(retryRef.current)
      retryRef.current = null
      const ws = wsRef.current
      wsRef.current = null
      if (ws) {
        ws.onclose = null
        ws.onerror = null
        ws.onmessage = null
        ws.close()
      }
    }
  }, [])

  return { snapshot, connected }
}
