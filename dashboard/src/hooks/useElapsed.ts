import { useEffect, useState } from "react"

export function useElapsed(startTs: number | null): string {
  const [elapsed, setElapsed] = useState<number | null>(null)

  useEffect(() => {
    if (!startTs) return
    const update = () => setElapsed(Math.max(0, Math.floor(Date.now() / 1000 - startTs)))
    const immediate = setTimeout(update, 0)
    const interval = setInterval(update, 1000)
    return () => {
      clearTimeout(immediate)
      clearInterval(interval)
    }
  }, [startTs])

  if (elapsed == null) return ""
  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60
  return minutes ? `${minutes}m ${seconds}s` : `${seconds}s`
}
