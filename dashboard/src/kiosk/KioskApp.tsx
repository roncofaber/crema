import { useState, useEffect, useRef } from 'react'
import { useKioskSocket } from './hooks/useKioskSocket'
import { Idle } from './screens/Idle'
import { Armed } from './screens/Armed'
import { Brewing } from './screens/Brewing'
import { AnonBrewing } from './screens/AnonBrewing'
import { Summary } from './screens/Summary'
import { RatingPrompt } from './overlays/RatingPrompt'
import { Reconnecting } from './overlays/Reconnecting'

export function KioskApp() {
  const { snapshot, connected } = useKioskSocket()
  const [showRating, setShowRating] = useState(false)
  const prevBrewId = useRef<number | null>(null)
  const prevState = useRef<string>('')

  // Show rating prompt when a brew completes (brewing → armed with new last_brew_id)
  useEffect(() => {
    if (
      prevState.current === 'brewing' &&
      snapshot.state === 'armed' &&
      snapshot.last_brew_id != null &&
      snapshot.last_brew_id !== prevBrewId.current
    ) {
      setShowRating(true)
      prevBrewId.current = snapshot.last_brew_id
    }
    prevState.current = snapshot.state
  }, [snapshot.state, snapshot.last_brew_id])

  function renderScreen() {
    switch (snapshot.state) {
      case 'idle':      return <Idle />
      case 'armed':     return <Armed snapshot={snapshot} />
      case 'brewing':   return <Brewing snapshot={snapshot} />
      case 'anon_brew': return <AnonBrewing snapshot={snapshot} />
      case 'summary':   return <Summary snapshot={snapshot} />
      default:          return <Idle />
    }
  }

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {renderScreen()}
      {showRating && snapshot.state === 'armed' && (
        <RatingPrompt snapshot={snapshot} onDismiss={() => setShowRating(false)} />
      )}
      {!connected && <Reconnecting />}
    </div>
  )
}
