import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../store/LanguageContext'
import { DoctorPage } from './DoctorPage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))

describe('DoctorPage consultation isolation', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.post.mockReset()
    mocks.patch.mockReset()
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([
        { visit_id: 1, ticket_code: 'A001', patient_name: 'Patient One', department_id: 1, department: 'Emergency', priority: 'URGENT', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 4, room: 'ER-101' },
        { visit_id: 2, ticket_code: 'A002', patient_name: 'Patient Two', department_id: 1, department: 'Emergency', priority: 'NORMAL', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 2, room: 'ER-102' },
      ])
      if (path === '/admin/rooms') return Promise.resolve([
        { id: 1, department_id: 1, room_number: 'ER-101', status: 'OCCUPIED' },
        { id: 2, department_id: 1, room_number: 'ER-102', status: 'OCCUPIED' },
      ])
      if (path === '/visits/1/consultation') return Promise.resolve({ id: 1, visit_id: 1, diagnosis: 'Diagnosis for patient one' })
      if (path === '/visits/2/consultation') return Promise.resolve({ id: 2, visit_id: 2, diagnosis: 'Diagnosis for patient two' })
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
  })

  it('loads notes for the selected visit instead of carrying notes from the previous patient', async () => {
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Diagnosis for patient one'))

    await user.click(screen.getByText('A002'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Diagnosis for patient two'))
  })

  it('ignores a stale consultation response after another patient is selected', async () => {
    let resolveFirst!: (value: { id: number; visit_id: number; diagnosis: string }) => void
    let resolveSecond!: (value: { id: number; visit_id: number; diagnosis: string }) => void
    const first = new Promise<{ id: number; visit_id: number; diagnosis: string }>((resolve) => { resolveFirst = resolve })
    const second = new Promise<{ id: number; visit_id: number; diagnosis: string }>((resolve) => { resolveSecond = resolve })
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([
        { visit_id: 1, ticket_code: 'A001', patient_name: 'Patient One', department_id: 1, department: 'Emergency', priority: 'URGENT', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 4, room: 'ER-101' },
        { visit_id: 2, ticket_code: 'A002', patient_name: 'Patient Two', department_id: 1, department: 'Emergency', priority: 'NORMAL', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 2, room: 'ER-102' },
      ])
      if (path === '/admin/rooms') return Promise.resolve([])
      if (path === '/visits/1/consultation') return first
      if (path === '/visits/2/consultation') return second
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await user.click(screen.getByText('A002'))
    resolveSecond({ id: 2, visit_id: 2, diagnosis: 'Current patient diagnosis' })
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Current patient diagnosis'))
    await act(async () => {
      resolveFirst({ id: 1, visit_id: 1, diagnosis: 'Stale patient diagnosis' })
      await first
    })

    expect(screen.getByLabelText('Diagnosis')).toHaveValue('Current patient diagnosis')
  })

  it('reconciles the selected visit when diagnostic results return during refresh', async () => {
    const returned = { visit_id: 1, ticket_code: 'A001', patient_name: 'Patient One', department_id: 1, department: 'Emergency', priority: 'URGENT', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 4, room: undefined }
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([returned])
      if (path === '/admin/rooms') return Promise.resolve([])
      if (path === '/visits/1/consultation') return Promise.resolve({ id: 1, visit_id: 1, diagnosis: 'Saved diagnosis' })
      if (path === '/visits/1') return Promise.resolve({ id: 1, status: 'WAITING_FOR_LAB' })
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    mocks.patch.mockResolvedValue({})
    mocks.post.mockResolvedValue({})
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Saved diagnosis'))
    await user.click(screen.getByRole('button', { name: 'Lab' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Save & complete visit' })).toBeEnabled())
  })

  it('closes a waiting visit with the expected status', async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([
        { visit_id: 4, ticket_code: 'A004', patient_name: 'Waiting Patient', department_id: 1, department: 'Emergency', priority: 'NORMAL', status: 'WAITING_FOR_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 3 },
      ])
      if (path === '/admin/rooms') return Promise.resolve([])
      return Promise.reject(new Error('No consultation yet'))
    })
    mocks.post.mockResolvedValue({})
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Patient left the department')
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A004'))
    await user.click(screen.getByRole('button', { name: 'Left without being seen' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/4/closure', {
      status: 'LEFT_WITHOUT_BEING_SEEN',
      reason: 'Patient left the department',
      expected_status: 'WAITING_FOR_DOCTOR',
    }))
    prompt.mockRestore()
  })

  it('saves the draft before transferring a patient with a destination', async () => {
    mocks.patch.mockResolvedValue({})
    mocks.post.mockResolvedValue({})
    const prompt = vi.spyOn(window, 'prompt')
      .mockReturnValueOnce('Needs specialist care')
      .mockReturnValueOnce('Regional cardiac centre')
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A001'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Diagnosis for patient one'))
    await user.click(screen.getByRole('button', { name: 'Transfer patient' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/1/disposition', {
      status: 'TRANSFERRED',
      reason: 'Needs specialist care',
      destination: 'Regional cardiac centre',
    }))
    expect(mocks.patch).toHaveBeenCalledWith('/visits/1/consultation', {
      diagnosis: 'Diagnosis for patient one',
      clinical_notes: '',
      treatment_plan: '',
    })
    expect(mocks.patch.mock.invocationCallOrder[0]).toBeLessThan(mocks.post.mock.invocationCallOrder[0])
    prompt.mockRestore()
  })

  it('saves the draft before admitting a patient without a transfer destination', async () => {
    mocks.patch.mockResolvedValue({})
    mocks.post.mockResolvedValue({})
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('Requires inpatient monitoring')
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A002'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Diagnosis for patient two'))
    await user.click(screen.getByRole('button', { name: 'Admit patient' }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/visits/2/disposition', {
      status: 'ADMITTED',
      reason: 'Requires inpatient monitoring',
    }))
    expect(mocks.patch.mock.invocationCallOrder[0]).toBeLessThan(mocks.post.mock.invocationCallOrder[0])
    prompt.mockRestore()
  })
})

// Completion UX regression tests: the action must never appear to do nothing.
describe('DoctorPage save and complete feedback', () => {
  beforeEach(() => {
    localStorage.setItem('mediflow_language', 'en')
    mocks.get.mockReset()
    mocks.post.mockReset()
    mocks.patch.mockReset()
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([
        { visit_id: 11, ticket_code: 'A011', patient_name: 'Completion Patient', department_id: 1, department: 'Emergency', priority: 'URGENT', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 1, room: 'ER-101' },
      ])
      if (path === '/admin/rooms') return Promise.resolve([])
      if (path === '/visits/11/consultation') return Promise.resolve({ id: 11, visit_id: 11, diagnosis: 'Viral syndrome', clinical_notes: '', treatment_plan: '' })
      if (path === '/visits/11/prescriptions') return Promise.resolve([])
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
  })

  it('saves the draft, completes the consultation, and shows success beside the workspace', async () => {
    mocks.patch.mockResolvedValue({})
    mocks.post.mockResolvedValue({})
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A011'))
    await waitFor(() => expect(screen.getByLabelText('Diagnosis')).toHaveValue('Viral syndrome'))
    await user.click(screen.getByRole('button', { name: 'Save & complete visit' }))

    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith('/visits/11/consultation', {
      diagnosis: 'Viral syndrome',
      clinical_notes: '',
      treatment_plan: '',
    }))
    expect(mocks.post).toHaveBeenCalledWith('/visits/11/complete-consultation')
    await screen.findByText('Consultation completed and visit closed.')
  })

  it('shows an inline validation message instead of silently refusing an empty consultation', async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path === '/doctors/me/queue') return Promise.resolve([
        { visit_id: 12, ticket_code: 'A012', patient_name: 'Empty Notes Patient', department_id: 1, department: 'Emergency', priority: 'NORMAL', status: 'WITH_DOCTOR', arrival_time: new Date().toISOString(), wait_minutes: 1, room: 'ER-102' },
      ])
      if (path === '/admin/rooms') return Promise.resolve([])
      if (path === '/visits/12/consultation') return Promise.resolve({ id: 12, visit_id: 12, diagnosis: '', clinical_notes: '', treatment_plan: '' })
      if (path === '/visits/12/prescriptions') return Promise.resolve([])
      return Promise.reject(new Error('Unexpected path: ' + path))
    })
    const user = userEvent.setup()
    render(<LanguageProvider><DoctorPage/></LanguageProvider>)

    await user.click(await screen.findByText('A012'))
    await user.click(screen.getByRole('button', { name: 'Save & complete visit' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a diagnosis or clinical notes before completing the visit.')
    expect(mocks.patch).not.toHaveBeenCalled()
    expect(mocks.post).not.toHaveBeenCalled()
  })
})
