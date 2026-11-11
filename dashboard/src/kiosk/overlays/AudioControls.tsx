import { useState } from 'react'
import type { useKioskSound } from '../hooks/useKioskSound'


type Props = { sound: ReturnType<typeof useKioskSound> }

export function AudioControls({ sound }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <div className="absolute bottom-3 left-3 z-30 flex items-center gap-2">
        <button
          type="button"
          onClick={sound.toggle}
          aria-pressed={sound.enabled}
          className="min-h-11 px-3 rounded border border-border bg-surface/95 font-plex text-xs uppercase tracking-widest text-muted"
        >
          {sound.enabled ? 'Sound on' : 'Sound off'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-expanded={open}
          className="min-h-11 px-3 rounded border border-border bg-surface/95 font-plex text-xs uppercase tracking-widest text-muted"
        >
          Audio settings
        </button>
      </div>
      {open && (
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="audio-settings-title"
          className="absolute inset-0 z-[60] flex items-center justify-center bg-ink/35 p-4"
        >
          <div className="w-full max-w-md rounded border border-border bg-surface p-5 shadow-xl">
            <h2 id="audio-settings-title" className="font-display italic text-3xl text-ink">Audio feedback</h2>
            <p className="mt-1 font-plex text-xs text-muted">Local to this display. Sound is off by default.</p>
            <label className="mt-5 flex min-h-11 items-center gap-3 font-plex text-sm text-ink">
              <input type="checkbox" checked={sound.enabled} onChange={sound.toggle} className="h-5 w-5" />
              Enable feedback cues
            </label>
            <label className="mt-2 flex min-h-11 items-center gap-3 font-plex text-sm text-ink">
              <input
                type="checkbox"
                checked={sound.quietHours.enabled}
                onChange={event => sound.setQuietHours({ ...sound.quietHours, enabled: event.target.checked })}
                className="h-5 w-5"
              />
              Use quiet hours
            </label>
            <div className="mt-2 flex gap-4">
              <label className="flex-1 font-plex text-xs text-muted">From
                <input
                  type="time"
                  aria-label="Quiet hours start"
                  value={sound.quietHours.start}
                  disabled={!sound.quietHours.enabled}
                  onChange={event => sound.setQuietHours({...sound.quietHours,start:event.target.value})}
                  className="mt-1 min-h-11 w-full rounded border border-border bg-bg px-2 text-base text-ink disabled:opacity-50"
                />
              </label>
              <label className="flex-1 font-plex text-xs text-muted">Until
                <input
                  type="time"
                  aria-label="Quiet hours end"
                  value={sound.quietHours.end}
                  disabled={!sound.quietHours.enabled}
                  onChange={event => sound.setQuietHours({...sound.quietHours,end:event.target.value})}
                  className="mt-1 min-h-11 w-full rounded border border-border bg-bg px-2 text-base text-ink disabled:opacity-50"
                />
              </label>
            </div>
            <p className="mt-3 font-plex text-xs text-muted">Overnight schedules are supported. Equal start and end times disable suppression.</p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mt-5 min-h-11 w-full rounded bg-crema-500 px-4 font-plex text-sm uppercase tracking-widest text-surface"
            >
              Done
            </button>
          </div>
        </section>
      )}
    </>
  )
}
