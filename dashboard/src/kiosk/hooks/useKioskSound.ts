import { useCallback, useEffect, useRef, useState } from 'react'
import type { KioskSnapshot } from './useKioskSocket'

const STORAGE_KEY = 'crema.kiosk.sound'
type Cue = 'scan' | 'brew' | 'error'
type AudioContextWithState = AudioContext

export type QuietHours = {
  enabled: boolean
  start: string
  end: string
}

export type SoundPreferences = {
  enabled: boolean
  quietHours: QuietHours
}

const DEFAULT_PREFERENCES: SoundPreferences = {
  enabled: false,
  quietHours: { enabled: true, start: '22:00', end: '07:00' },
}

function validTime(value: unknown): value is string {
  return typeof value === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(value)
}

function readPreferences(): SoundPreferences {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored || stored === 'on' || stored === 'off') {
      return { ...DEFAULT_PREFERENCES, enabled: stored === 'on' }
    }
    const value = JSON.parse(stored) as Partial<SoundPreferences>
    const quiet = value.quietHours as Partial<QuietHours> | undefined
    return {
      enabled: typeof value.enabled === 'boolean' ? value.enabled : false,
      quietHours: {
        enabled: typeof quiet?.enabled === 'boolean' ? quiet.enabled : true,
        start: validTime(quiet?.start) ? quiet.start : '22:00',
        end: validTime(quiet?.end) ? quiet.end : '07:00',
      },
    }
  } catch {
    return { ...DEFAULT_PREFERENCES, quietHours: { ...DEFAULT_PREFERENCES.quietHours } }
  }
}

export function isQuietTime(date: Date, quiet: QuietHours): boolean {
  if (!quiet.enabled || !validTime(quiet.start) || !validTime(quiet.end) || quiet.start === quiet.end) {
    return false
  }
  const minutes = date.getHours() * 60 + date.getMinutes()
  const start = Number(quiet.start.slice(0, 2)) * 60 + Number(quiet.start.slice(3))
  const end = Number(quiet.end.slice(0, 2)) * 60 + Number(quiet.end.slice(3))
  return start < end
    ? minutes >= start && minutes < end
    : minutes >= start || minutes < end
}

function hardwareIssue(snapshot: KioskSnapshot): boolean {
  const hardware = snapshot.hardware
  if (!hardware) return false
  return !hardware.running || !hardware.scanner.connected || !hardware.sensor.connected ||
    hardware.sensor.last_read_at === null || hardware.sensor.stale_age === null || hardware.sensor.stale_age > 5
}

export function useKioskSound(snapshot: KioskSnapshot | null) {
  const [preferences, setPreferences] = useState<SoundPreferences>(readPreferences)
  const preferencesRef = useRef(preferences)
  const { enabled } = preferences
  const contextRef = useRef<AudioContextWithState | null>(null)
  const previousRef = useRef<KioskSnapshot | null>(null)

  const ensureContext = useCallback((): AudioContextWithState | null => {
    let context = contextRef.current
    if (!context || context.state === 'closed') {
      if (typeof AudioContext === 'undefined') return null
      context = new AudioContext()
      contextRef.current = context
    }
    if (context.state === 'suspended') {
      void context.resume().catch(() => undefined)
    }
    return context
  }, [])

  const play = useCallback((cue: Cue) => {
    const context = ensureContext()
    if (!context) return
    const oscillator = context.createOscillator()
    const gain = context.createGain()
    const now = context.currentTime
    oscillator.type = cue === 'error' ? 'square' : 'sine'
    oscillator.frequency.setValueAtTime(cue === 'scan' ? 660 : cue === 'brew' ? 880 : 180, now)
    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(0.08, now + 0.015)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.14)
    oscillator.connect(gain)
    gain.connect(context.destination)
    oscillator.start(now)
    oscillator.stop(now + 0.15)
    oscillator.onended = () => {
      oscillator.disconnect()
      gain.disconnect()
    }
  }, [ensureContext])

  useEffect(() => {
    const previous = previousRef.current
    previousRef.current = snapshot
    if (!snapshot) {
      previousRef.current = null
      return
    }
    if (!enabled || !previous || isQuietTime(new Date(), preferences.quietHours)) return
    const newBrew = (previous.state === 'brewing' || previous.state === 'anon_brew') &&
      snapshot.last_brew_id !== null && snapshot.last_brew_id !== previous.last_brew_id
    const scan = snapshot.state === 'armed' && snapshot.user !== null && snapshot.user !== previous.user
    if (newBrew) play('brew')
    else if (scan) play('scan')
    else if (!hardwareIssue(previous) && hardwareIssue(snapshot)) play('error')
  }, [enabled, play, preferences.quietHours, snapshot])

  useEffect(() => () => {
    if (contextRef.current && contextRef.current.state !== 'closed') {
      void contextRef.current.close().catch(() => undefined)
    }
    contextRef.current = null
  }, [])

  const toggle = useCallback(() => {
    const next = { ...preferencesRef.current, enabled: !preferencesRef.current.enabled }
    if (next.enabled) ensureContext()
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      return
    }
    preferencesRef.current = next
    setPreferences(next)
  }, [ensureContext])

  const setQuietHours = useCallback((quietHours: QuietHours) => {
    const next = { ...preferencesRef.current, quietHours }
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      return
    }
    preferencesRef.current = next
    setPreferences(next)
  }, [])

  return { enabled, toggle, quietHours: preferences.quietHours, setQuietHours }
}
