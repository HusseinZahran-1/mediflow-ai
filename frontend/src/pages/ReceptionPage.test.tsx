import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../store/LanguageContext'
import { ReceptionPage } from './ReceptionPage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))

describe('ReceptionPage issued visit', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.post.mockReset()
    mocks.get.mockImplementation((path: string) => {
      if (path === '/departments') return Promise.resolve([
        { id: 1, name: 'Emergency', code: 'ER', ticket_prefix: 'A', is_active: true },
      ])
      if (path.startsWith('/patients/search')) return Promise.resolve({ items: [
        { id: 1, medical_record_number: 'MRN-1', full_name: 'Patient One', identity_number: 'ID-1' },
      ] })
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    mocks.post.mockImplementation((path: string) => {
      if (path === '/visits') return Promise.resolve({
        id: 7,
        patient_id: 1,
        department_id: 1,
        ticket_code: 'A001',
        ticket_sequence: 1,
        status: 'WAITING_FOR_TRIAGE',
        visit_type: 'WALK_IN',
        arrival_method: 'WALKING',
        arrival_time: new Date().toISOString(),
      })
      if (path === '/visits/7/closure') return Promise.resolve({})
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
  })

  it('lets reception cancel the visit it just issued with stale-state protection', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Registered in error')
    const user = userEvent.setup()
    render(<LanguageProvider><ReceptionPage/></LanguageProvider>)

    await user.type(screen.getByPlaceholderText('Identity number, MRN, name, or phone'), 'Patient One')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await screen.findAllByText('Patient One')
    await user.selectOptions(screen.getByLabelText('Department'), '1')
    await user.click(screen.getByRole('button', { name: 'Create visit & issue ticket' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel issued visit' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/7/closure', {
      status: 'CANCELLED',
      reason: 'Registered in error',
      expected_status: 'WAITING_FOR_TRIAGE',
    }))
    expect(await screen.findByText('Visit A001 cancelled.')).toBeInTheDocument()
    prompt.mockRestore()
  })
})
