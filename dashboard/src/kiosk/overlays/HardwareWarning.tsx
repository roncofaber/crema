import type { KioskSnapshot } from '../hooks/useKioskSocket'

type Props = { hardware: KioskSnapshot['hardware'] }

const SENSOR_STALE_AFTER_SECONDS = 5

export function HardwareWarning({ hardware }: Props) {
  if (!hardware) return null
  const sensorStale = hardware.sensor.last_read_at === null ||
    hardware.sensor.stale_age === null ||
    (hardware.sensor.stale_age ?? 0) > SENSOR_STALE_AFTER_SECONDS
  const issues = [
    !hardware.running && 'Kiosk loop stopped',
    !hardware.scanner.connected && 'Scanner offline',
    (!hardware.sensor.connected || sensorStale) &&
      `Sensor ${hardware.sensor.connected && sensorStale ? 'stale' : 'offline'}`,
  ].filter(Boolean)
  if (!issues.length) return null

  return (
    <div
      className="absolute top-3 left-1/2 -translate-x-1/2 max-w-[calc(100%-2rem)] z-40 rounded bg-ink/90 px-4 py-2 text-center font-plex text-xs uppercase tracking-widest text-surface shadow-lg"
      role="status"
      aria-live="polite"
    >
      {issues.join(' · ')}
    </div>
  )
}
