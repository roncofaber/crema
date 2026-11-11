import { useState, useCallback } from 'react'
import type { ReactNode } from 'react'
import { useKioskSocket } from './hooks/useKioskSocket'
import { useKioskSound } from './hooks/useKioskSound'
import type { KioskSnapshot } from './hooks/useKioskSocket'
import { Idle } from './screens/Idle'
import { Armed } from './screens/Armed'
import { Brewing } from './screens/Brewing'
import { AnonBrewing } from './screens/AnonBrewing'
import { Summary } from './screens/Summary'
import { RatingPrompt } from './overlays/RatingPrompt'
import { Reconnecting } from './overlays/Reconnecting'
import { HardwareWarning } from './overlays/HardwareWarning'
import { AudioControls } from './overlays/AudioControls'
import { LivePanel } from './overlays/LivePanel'
import { StatusToast } from './overlays/StatusToast'

type RatingTarget = {
  brewId: number
  sessionKey: string
}

function KioskFrame({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-raised text-ink">
      <div data-kiosk-stage className="kiosk-stage relative overflow-hidden bg-bg">
        {children}
      </div>
    </div>
  )
}

function sessionKey(snapshot: KioskSnapshot) {
  return `${snapshot.session_started_at ?? 'none'}:${snapshot.user ?? 'anonymous'}`
}

export function KioskApp() {
  const { snapshot, connected } = useKioskSocket()
  const sound = useKioskSound(snapshot)
  const [ratingTarget, setRatingTarget] = useState<RatingTarget | null>(null)
  const [previousSnapshot, setPreviousSnapshot] = useState<KioskSnapshot | null>(null)
  const dismissRating = useCallback(() => {
    const dismissed = ratingTarget
    setRatingTarget(current => {
      if (!current || !dismissed) return current
      return current.brewId === dismissed.brewId && current.sessionKey === dismissed.sessionKey
        ? null
        : current
    })
  }, [ratingTarget])

  if (snapshot !== previousSnapshot) {
    const prev = previousSnapshot
    const currentKey = snapshot ? sessionKey(snapshot) : null
    const sameSession = prev !== null && snapshot !== null && sessionKey(prev) === currentKey
    setPreviousSnapshot(snapshot)

    if (!snapshot || snapshot.state !== 'armed' || snapshot.last_brew_id == null) {
      setRatingTarget(null)
    } else if (
      prev &&
      (prev.state === 'brewing' || prev.state === 'anon_brew') &&
      snapshot.last_brew_id !== prev.last_brew_id &&
      (sameSession || (prev.state === 'anon_brew' && snapshot.user !== null))
    ) {
      setRatingTarget({ brewId: snapshot.last_brew_id, sessionKey: sessionKey(snapshot) })
    } else if (prev && !sameSession) {
      setRatingTarget(null)
    }
  }

  if (!snapshot) {
    return (
      <KioskFrame>
        <Reconnecting />
      </KioskFrame>
    )
  }

  function renderScreen() {
    if (!snapshot) return null
    switch (snapshot.state) {
      case 'idle':      return <Idle />
      case 'armed':     return <Armed snapshot={snapshot} />
      case 'brewing':   return <Brewing snapshot={snapshot} />
      case 'anon_brew': return <AnonBrewing snapshot={snapshot} />
      case 'summary':   return <Summary snapshot={snapshot} />
    }
  }

  const showRating = connected && ratingTarget !== null &&
    snapshot.state === 'armed' &&
    snapshot.last_brew_id === ratingTarget.brewId &&
    sessionKey(snapshot) === ratingTarget.sessionKey

  return (
    <KioskFrame>
      <div inert={!connected} aria-hidden={!connected} className="h-full">
        {renderScreen()}
      </div>
      <AudioControls sound={sound} />
      <LivePanel snapshot={snapshot} connected={connected} />
      <StatusToast disconnected={!connected} />
      {showRating && (
        <RatingPrompt
          key={`${ratingTarget.sessionKey}:${ratingTarget.brewId}`}
          snapshot={snapshot}
          brewId={ratingTarget.brewId}
          onDismiss={dismissRating}
        />
      )}
      {connected && <HardwareWarning hardware={snapshot.hardware} />}
    </KioskFrame>
  )
}
