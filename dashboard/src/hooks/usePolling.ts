import { useEffect, useState } from "react"

type PollingResult<T> = {
  data: T | null
  error: string | null
  loading: boolean
  stale: boolean
}

export function usePolling<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  deps: unknown[] = [],
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)

  useEffect(() => {
    let active = true
    let hasData = data !== null
    let retry: ReturnType<typeof setTimeout> | null = null
    const controller = new AbortController()

    async function tick() {
      try {
        const result = await fn(controller.signal)
        if (!active) return
        hasData = true
        setData(result)
        setError(null)
        setLoading(false)
        setStale(false)
      } catch (e) {
        if (!active || controller.signal.aborted) return
        setError(e instanceof Error ? e.message : String(e))
        setLoading(false)
        setStale(hasData)
      } finally {
        if (active && !controller.signal.aborted) {
          retry = setTimeout(() => { void tick() }, intervalMs)
        }
      }
    }

    void tick()
    return () => {
      active = false
      controller.abort()
      if (retry !== null) clearTimeout(retry)
    }
  // fn changes identity every render; callers use deps[] for explicit re-triggers
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps])

  return { data, error, loading, stale }
}
