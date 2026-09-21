import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../store/LanguageContext'
import { OrdersPage } from './OrdersPage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))

describe('OrdersPage cancellation', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.patch.mockReset()
    mocks.get.mockResolvedValue([
      { id: 7, visit_id: 3, status: 'REQUESTED', priority: 'URGENT', test_name: 'CBC', requested_at: new Date().toISOString() },
    ])
    mocks.patch.mockResolvedValue({})
  })

  it('cancels a non-terminal order once while the request is pending', async () => {
    let resolvePatch!: (value: unknown) => void
    mocks.patch.mockImplementation(() => new Promise((resolve) => { resolvePatch = resolve }))
    const user = userEvent.setup()
    render(<LanguageProvider><OrdersPage type="lab"/></LanguageProvider>)

    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    await user.click(cancel)
    await user.click(cancel)

    expect(mocks.patch).toHaveBeenCalledTimes(1)
    expect(mocks.patch).toHaveBeenCalledWith('/lab-orders/7', { status: 'CANCELLED' })
    resolvePatch({})
    expect(await screen.findByText('Order #7 cancelled.')).toBeInTheDocument()
  })
})
