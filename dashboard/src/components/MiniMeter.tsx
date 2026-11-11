type Props = { label: string; ok: boolean }

export function MiniMeter({ label, ok }: Props) {
  return (
    <span className="inline-flex items-center gap-1.5" title={`${label}: ${ok ? 'ready' : 'degraded'}`}>
      <span className={`h-1.5 w-5 rounded-full ${ok ? 'bg-crema-400' : 'bg-ink'}`} aria-hidden="true" />
      <span>{label}</span>
    </span>
  )
}
