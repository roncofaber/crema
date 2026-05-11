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
