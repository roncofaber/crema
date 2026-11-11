import { MiniMeter } from '../../components/MiniMeter'
import type { KioskSnapshot } from '../hooks/useKioskSocket'


type Props = { snapshot: KioskSnapshot; connected: boolean }

export function LivePanel({ snapshot, connected }: Props) {
  const scannerReady = snapshot.hardware?.scanner.connected ?? false
  const sensorReady = snapshot.hardware?.sensor.connected && (snapshot.hardware?.sensor.stale_age ?? 6) <= 5

  return (
    <div
      aria-live="polite"
      data-connection-state={connected ? 'live' : 'reconnecting'}
      className="absolute bottom-3 right-3 z-30 rounded border border-border bg-surface/95 px-3 py-2 font-plex text-[10px] uppercase tracking-wider text-muted"
    >
      <p className="mb-1.5 text-right">{connected ? 'Live updates' : 'Reconnecting'}</p>
      <div className="flex gap-3">
        <MiniMeter label="Scanner" ok={connected && scannerReady} />
        <MiniMeter label="Sensor" ok={connected && sensorReady === true} />
      </div>
    </div>
  )
}
