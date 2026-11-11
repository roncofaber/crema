import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeSnapshot } from '../../test/fixtures'
import { HardwareWarning } from './HardwareWarning'

describe('HardwareWarning', () => {
  it('warns when a connected sensor has never produced a sample', () => {
    const hardware = makeSnapshot().hardware!
    hardware.sensor.last_read_at = null
    hardware.sensor.stale_age = null

    render(<HardwareWarning hardware={hardware} />)
    expect(screen.getByRole('status')).toHaveTextContent('Sensor stale')
  })

  it('warns when sensor samples become stale', () => {
    const hardware = makeSnapshot().hardware!
    hardware.sensor.stale_age = 6

    render(<HardwareWarning hardware={hardware} />)
    expect(screen.getByRole('status')).toHaveTextContent('Sensor stale')
  })
})
