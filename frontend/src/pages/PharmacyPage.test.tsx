import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../store/LanguageContext'
import { PharmacyPage } from './PharmacyPage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))

describe('PharmacyPage cancellation', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.patch.mockReset()
    mocks.get.mockResolvedValue([
      {
        id: 9,
        visit_id: 4,
        status: 'ACTIVE',
        created_at: new Date().toISOString(),
        items: [{ id: 1, medication_name: 'Medicine', dosage: '10 mg', frequency: 'Daily', duration: '3 days' }],
      },
    ])
    mocks.patch.mockResolvedValue({})
  })

  it('cancels an active prescription and reloads the worklist', async () => {
    const user = userEvent.setup()
    render(<LanguageProvider><PharmacyPage/></LanguageProvider>)

    await user.click(await screen.findByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith('/prescriptions/9', { status: 'CANCELLED' }))
    expect(await screen.findByText('Prescription #9 cancelled.')).toBeInTheDocument()
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })
})
