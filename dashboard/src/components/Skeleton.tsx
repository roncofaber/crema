export function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="border-b border-border-subtle last:border-0">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 rounded bg-raised animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`rounded bg-raised animate-pulse ${className}`} />
}
