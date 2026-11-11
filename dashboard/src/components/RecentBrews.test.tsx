import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { RecentBrews } from './RecentBrews'

vi.mock('../api', () => ({ api: { brews: vi.fn() } }))
const brews = vi.mocked(api.brews)
const record = {
  id: 1,
  user: 'alice',
  started_at: 100,
  ended_at: 125,
  duration: 25,
  kind: 'brew' as const,
  shot_type: 'single' as const,
  decaf: true,
  rating: 5,
}

beforeEach(() => {
  brews.mockReset()
  brews.mockResolvedValue([record])
})

describe('RecentBrews filters', () => {
  it('requests brews only by default', async () => {
    render(<RecentBrews />)
    expect(await screen.findByText('alice')).toBeInTheDocument()
    expect(brews).toHaveBeenLastCalledWith({ limit: 100, kind: 'brew' }, expect.any(AbortSignal))
    expect(screen.getByText('single decaf', { selector: 'span' })).toBeInTheDocument()
  })

  it('combines user, record, shot, decaf, and date filters', async () => {
    render(<RecentBrews />)
    await screen.findByText('alice')
    fireEvent.change(screen.getByLabelText('User'), { target: { value: ' alice ' } })
    fireEvent.change(screen.getByLabelText('Records'), { target: { value: 'all' } })
    fireEvent.change(screen.getByLabelText('Shot'), { target: { value: 'single' } })
    fireEvent.change(screen.getByLabelText('Decaf'), { target: { value: 'yes' } })
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-01' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-11' } })

    const expectedStart = new Date('2026-11-01T00:00:00').getTime() / 1000
    const nextDay = new Date('2026-11-11T00:00:00')
    nextDay.setDate(nextDay.getDate() + 1)
    const expectedEnd = nextDay.getTime() / 1000 - 0.001
    expect(brews).toHaveBeenLastCalledWith({
      limit: 100,
      user: 'alice',
      shot_type: 'single',
      decaf: true,
      from_ts: expectedStart,
      to_ts: expectedEnd,
    }, expect.any(AbortSignal))
  })

  it('ends a date range at the next local midnight across DST', async () => {
    vi.stubEnv('TZ', 'America/Los_Angeles')
    try {
      render(<RecentBrews />)
      await screen.findByText('alice')
      fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-01' } })

      const start = new Date('2026-11-01T00:00:00').getTime()
      const end = new Date('2026-11-02T00:00:00').getTime()
      const filters = brews.mock.lastCall?.[0]
      expect(filters?.to_ts).toBe(end / 1000 - 0.001)
      expect(end - start).toBe(90_000_000)
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('resets filters and presents an empty result', async () => {
    brews.mockResolvedValue([])
    render(<RecentBrews />)
    expect(await screen.findByText('No records match these filters.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Records'), { target: { value: 'noise' } })
    fireEvent.click(screen.getByRole('button', { name: 'Reset filters' }))
    expect(brews).toHaveBeenLastCalledWith({ limit: 100, kind: 'brew' }, expect.any(AbortSignal))
    expect(screen.getByLabelText('Records')).toHaveValue('brew')
  })
})
