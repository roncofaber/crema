export function Idle() {
  return (
    <div className="h-screen bg-bg flex flex-col items-center justify-center gap-4">
      <div className="h-1 w-full bg-crema-500 absolute top-0" />
      <p className="text-xs uppercase tracking-[0.25em] text-faint">Caffè Cabrini</p>
      <h1 className="font-display italic text-5xl text-ink">C R E M A</h1>
      <p className="font-plex text-sm text-faint tracking-widest">scan to brew</p>
      <div className="h-1 w-full bg-crema-500 absolute bottom-0" />
    </div>
  )
}
