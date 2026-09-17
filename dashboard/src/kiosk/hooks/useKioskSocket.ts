import { useEffect, useRef, useState } from 'react'

export type KioskSnapshot = {
  state: 'idle' | 'armed' | 'brewing' | 'anon_brew' | 'summary'
  user: string | null
  brew_count: number
  time_remaining: number | null
  timeout: number | null
  elapsed: number | null
  shot_type: 'single' | 'double'
  decaf: boolean
  last_brew_id: number | null
  avg_rating: number | null
  session_started_at: number | null
  brew_started_at: number | null
}

const DEFAULT_SNAPSHOT: KioskSnapshot = {
  state: 'idle',
  user: null,
  brew_count: 0,
  time_remaining: null,
  timeout: null,
  elapsed: null,
  shot_type: 'double',
  decaf: false,
  last_brew_id: null,
  avg_rating: null,
  session_started_at: null,
  brew_started_at: null,
}

export function useKioskSocket() {
  const [snapshot, setSnapshot] = useState<KioskSnapshot>(DEFAULT_SNAPSHOT)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryDelay = useRef(2000)

  useEffect(() => {
    let disposed = false

    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/kiosk`)
      wsRef.current = ws

      ws.onopen = () => {
        if (disposed) return
        setConnected(true)
        retryDelay.current = 2000
      }

      ws.onmessage = (e) => {
        if (disposed) return
        try {
          setSnapshot(JSON.parse(e.data))
        } catch (err) {
          console.error('Failed to parse kiosk snapshot:', err, e.data)
        }
      }

      ws.onclose = () => {
        if (disposed) return
        setConnected(false)
        retryRef.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 1.5, 15000)
          connect()
        }, retryDelay.current)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      disposed = true
      if (retryRef.current) clearTimeout(retryRef.current)
      if (wsRef.current) wsRef.current.onclose = null
      wsRef.current?.close()
    }
  }, [])

  return { snapshot, connected }
}
