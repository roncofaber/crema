import { useEffect, useState } from "react"

export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = [],
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
  // fn changes identity every render; callers use deps[] for explicit re-triggers
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps])

  return { data, error }
}
