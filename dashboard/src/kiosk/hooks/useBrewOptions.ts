import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import type { KioskSnapshot } from './useKioskSocket'

type BrewOptions = Pick<KioskSnapshot, 'shot_type' | 'decaf'>

function sameOptions(a: BrewOptions, b: BrewOptions) {
  return a.shot_type === b.shot_type && a.decaf === b.decaf
}

export function useBrewOptions(snapshot: KioskSnapshot) {
  const sessionKey = `${snapshot.session_started_at ?? 'none'}:${snapshot.user ?? 'anonymous'}`
  const initial = { shot_type: snapshot.shot_type, decaf: snapshot.decaf }
  const [options, setOptions] = useState<BrewOptions>(initial)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const optionsRef = useRef(initial)
  const confirmedRef = useRef(initial)
  const expectedRef = useRef<BrewOptions | null>(null)
  const sessionRef = useRef(sessionKey)
  const sessionStartedAtRef = useRef(snapshot.session_started_at)
  const requestRef = useRef(0)
  const inFlightRef = useRef(false)

  useEffect(() => {
    sessionStartedAtRef.current = snapshot.session_started_at
    const server = { shot_type: snapshot.shot_type, decaf: snapshot.decaf }
    if (sessionRef.current !== sessionKey) {
      sessionRef.current = sessionKey
      requestRef.current += 1
      inFlightRef.current = false
      expectedRef.current = null
      confirmedRef.current = server
      optionsRef.current = server
      setOptions(server)
      setPending(false)
      setError(null)
      return
    }

    if (expectedRef.current) {
      if (sameOptions(expectedRef.current, server)) {
        expectedRef.current = null
        confirmedRef.current = server
        optionsRef.current = server
        setOptions(server)
      }
      return
    }

    confirmedRef.current = server
    optionsRef.current = server
    setOptions(server)
  }, [sessionKey, snapshot.shot_type, snapshot.decaf, snapshot.session_started_at])

  useEffect(() => () => {
    requestRef.current += 1
  }, [])

  const update = useCallback((patch: Partial<BrewOptions>) => {
    if (inFlightRef.current) return
    const session_started_at = sessionStartedAtRef.current
    if (session_started_at === null) {
      setError('Brew options are unavailable for an anonymous session.')
      return
    }
    inFlightRef.current = true
    const next = { ...optionsRef.current, ...patch }
    const requestId = ++requestRef.current
    optionsRef.current = next
    expectedRef.current = next
    setOptions(next)
    setPending(true)
    setError(null)

    void api.kioskBrewOptions({ ...next, session_started_at }).then(() => {
      if (requestRef.current !== requestId) return
      confirmedRef.current = next
      inFlightRef.current = false
      setPending(false)
    }).catch((cause: unknown) => {
      if (requestRef.current !== requestId) return
      const confirmed = confirmedRef.current
      inFlightRef.current = false
      optionsRef.current = confirmed
      expectedRef.current = null
      setOptions(confirmed)
      setPending(false)
      setError(`Could not save brew options. Tap an option to retry. ${cause instanceof Error ? cause.message : String(cause)}`)
    })
  }, [])

  const setShotType = useCallback((shot_type: BrewOptions['shot_type']) => {
    update({ shot_type })
  }, [update])
  const setDecaf = useCallback((decaf: boolean) => update({ decaf }), [update])
  const clearError = useCallback(() => setError(null), [])

  return { ...options, pending, error, setShotType, setDecaf, clearError }
}
