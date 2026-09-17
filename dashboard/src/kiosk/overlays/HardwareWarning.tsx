import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { hardware: KioskSnapshot['hardware'] }

export function HardwareWarning({ hardware }: Props) {
  if (!hardware) return null
  const missing = [
    !hardware.scanner.connected && 'Scanner',
    !hardware.sensor.connected && 'Sensor',
  ].filter(Boolean)
  if (!missing.length) return null

  return (
    <div
      className="absolute top-3 right-3 z-40 rounded bg-ink/90 px-4 py-2 font-plex text-xs uppercase tracking-widest text-surface shadow-lg"
      role="status"
      aria-live="polite"
    >
      {missing.join(' + ')} offline
    </div>
  )
}
