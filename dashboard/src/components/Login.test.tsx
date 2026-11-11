import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { Login } from './Login'

vi.mock('../api', () => ({ api: { authLogin: vi.fn() } }))

const login = vi.mocked(api.authLogin)

describe('Login', () => {
  it('authenticates the entered password without displaying it', async () => {
    login.mockResolvedValue({ authenticated: true, expires_at: 2000 })
    const authenticated = vi.fn()
    render(<Login onAuthenticated={authenticated} />)
    fireEvent.change(screen.getByLabelText('Administrator password'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith('secret')
    expect(authenticated).toHaveBeenCalledOnce()
    expect(screen.getByLabelText('Administrator password')).toHaveValue('')
  })

  it('uses a compact kiosk presentation', () => {
    render(<Login kiosk onAuthenticated={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Kiosk sign in' })).toBeInTheDocument()
    expect(screen.getByText('Sign in to enable kiosk controls.')).toBeInTheDocument()
    expect(screen.getByLabelText('Administrator password')).toHaveAttribute('id', 'kiosk-password')
  })

  it('keeps the form available after a failed login', async () => {
    login.mockRejectedValue(new Error('401'))
    render(<Login onAuthenticated={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Administrator password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign-in failed')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
  })
})
