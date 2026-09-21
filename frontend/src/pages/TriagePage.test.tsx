import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../store/LanguageContext'
import { TriagePage } from './TriagePage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))

describe('TriagePage patient isolation', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.post.mockReset()
    mocks.patch.mockReset()
    mocks.get.mockResolvedValue([
      { id: 1, patient_id: 1, department_id: 1, ticket_code: 'A001', ticket_sequence: 1, arrival_time: new Date().toISOString(), status: 'WAITING_FOR_TRIAGE', visit_type: 'EMERGENCY', arrival_method: 'WALKING' },
      { id: 2, patient_id: 2, department_id: 1, ticket_code: 'A002', ticket_sequence: 2, arrival_time: new Date().toISOString(), status: 'WAITING_FOR_TRIAGE', visit_type: 'EMERGENCY', arrival_method: 'WALKING' },
    ])
  })

  it('clears assessment fields when a different patient is selected', async () => {
    const user = userEvent.setup()
    render(<LanguageProvider><TriagePage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    const complaint = screen.getByLabelText('Chief complaint')
    await user.type(complaint, 'First patient complaint')
    expect(complaint).toHaveValue('First patient complaint')

    await user.click(screen.getByText('A002'))
    expect(screen.getByLabelText('Chief complaint')).toHaveValue('')
  })

  it('ignores a stale triage response after another visit is selected', async () => {
    let resolveFirst!: (value: Record<string, unknown>) => void
    let resolveSecond!: (value: Record<string, unknown>) => void
    const first = new Promise<Record<string, unknown>>((resolve) => { resolveFirst = resolve })
    const second = new Promise<Record<string, unknown>>((resolve) => { resolveSecond = resolve })
    mocks.get.mockImplementation((path: string) => {
      if (path === '/visits/active') return Promise.resolve([
        { id: 1, patient_id: 1, department_id: 1, ticket_code: 'A001', ticket_sequence: 1, arrival_time: new Date().toISOString(), status: 'IN_TRIAGE', visit_type: 'EMERGENCY', arrival_method: 'WALKING' },
        { id: 2, patient_id: 2, department_id: 1, ticket_code: 'A002', ticket_sequence: 2, arrival_time: new Date().toISOString(), status: 'IN_TRIAGE', visit_type: 'EMERGENCY', arrival_method: 'WALKING' },
      ])
      if (path === '/visits/1/triage') return first
      if (path === '/visits/2/triage') return second
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    const user = userEvent.setup()
    render(<LanguageProvider><TriagePage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await user.click(screen.getByText('A002'))
    resolveSecond({ id: 2, visit_id: 2, chief_complaint: 'Current patient complaint', human_priority: 'NORMAL' })
    await waitFor(() => expect(screen.getByLabelText('Chief complaint')).toHaveValue('Current patient complaint'))
    await act(async () => {
      resolveFirst({ id: 1, visit_id: 1, chief_complaint: 'Stale patient complaint', human_priority: 'URGENT' })
      await first
    })

    expect(screen.getByLabelText('Chief complaint')).toHaveValue('Current patient complaint')
  })

  it('cancels the selected visit with its current status and documented reason', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Duplicate visit')
    mocks.post.mockResolvedValue({})
    const user = userEvent.setup()
    render(<LanguageProvider><TriagePage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await user.click(screen.getByRole('button', { name: 'Cancel visit' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/1/closure', {
      status: 'CANCELLED',
      reason: 'Duplicate visit',
      expected_status: 'WAITING_FOR_TRIAGE',
    }))
    expect(await screen.findByText('Visit A001 cancelled.')).toBeInTheDocument()
    prompt.mockRestore()
  })

  it('uses IN_TRIAGE as the expected status after an assessment is saved', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Patient left during assessment')
    let activeLoads = 0
    mocks.get.mockImplementation((path: string) => {
      if (path === '/visits/active') {
        activeLoads += 1
        return Promise.resolve([{
          id: 1, patient_id: 1, department_id: 1, ticket_code: 'A001', ticket_sequence: 1,
          arrival_time: new Date().toISOString(), status: activeLoads === 1 ? 'WAITING_FOR_TRIAGE' : 'IN_TRIAGE',
          visit_type: 'EMERGENCY', arrival_method: 'WALKING',
        }])
      }
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    mocks.post.mockImplementation((path: string) => {
      if (path === '/visits/1/triage') return Promise.resolve({
        id: 10, visit_id: 1, chief_complaint: 'Assessment in progress', human_priority: 'NORMAL',
        ai_priority: 'NORMAL', ai_confidence: 0.7,
      })
      if (path === '/visits/1/closure') return Promise.resolve({})
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    const user = userEvent.setup()
    render(<LanguageProvider><TriagePage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await user.type(screen.getByLabelText('Chief complaint'), 'Assessment in progress')
    await user.selectOptions(screen.getByLabelText('Human priority'), 'NORMAL')
    await user.click(screen.getByRole('button', { name: 'Save assessment & run AI' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Left without being seen' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Left without being seen' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/1/closure', {
      status: 'LEFT_WITHOUT_BEING_SEEN',
      reason: 'Patient left during assessment',
      expected_status: 'IN_TRIAGE',
    }))
    prompt.mockRestore()
  })

  it('records left without being seen before triage starts', async () => {
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Patient chose to leave')
    mocks.post.mockResolvedValue({})
    const user = userEvent.setup()
    render(<LanguageProvider><TriagePage/></LanguageProvider>)

    await user.click(await screen.findByText('A002'))
    await user.click(screen.getByRole('button', { name: 'Left without being seen' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/2/closure', {
      status: 'LEFT_WITHOUT_BEING_SEEN',
      reason: 'Patient chose to leave',
      expected_status: 'WAITING_FOR_TRIAGE',
    }))
    prompt.mockRestore()
  })
})
