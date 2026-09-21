import { ArrowRightLeft, Ban, BellRing, Building2, ClipboardCheck, FlaskConical, Pill, RotateCcw, ScanLine, SkipForward, Stethoscope, UserX } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { QueueTable } from '../components/QueueTable'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { QueueItem, Visit } from '../types'

interface Room { id: number; department_id: number; room_number: string; status: string }
interface Consultation { id: number; visit_id: number; diagnosis?: string; clinical_notes?: string; treatment_plan?: string; completed_at?: string }
interface PrescriptionItem { id: number; medication_name: string; dosage: string; frequency: string; duration: string; instructions?: string }
interface Prescription { id: number; visit_id: number; status: string; items: PrescriptionItem[]; created_at: string }
interface DoctorOption { id: number; full_name: string; email: string; department_id: number; department: string; specialization: string; is_active: boolean }

const field = 'w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10'
const emptyNotes = { diagnosis: '', clinical_notes: '', treatment_plan: '' }
const clinicalActionStatuses = ['WITH_DOCTOR', 'WAITING_FOR_LAB', 'WAITING_FOR_RADIOLOGY']

const notesFromConsultation = (consultation: Consultation) => ({
  diagnosis: consultation.diagnosis || '',
  clinical_notes: consultation.clinical_notes || '',
  treatment_plan: consultation.treatment_plan || '',
})

export function DoctorPage() {
  const { t, enumLabel } = useLanguage()
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [selected, setSelected] = useState<QueueItem | null>(null)
  const [rooms, setRooms] = useState<Room[]>([])
  const [roomId, setRoomId] = useState('')
  const [consultationStarted, setConsultationStarted] = useState(false)
  const [notes, setNotes] = useState(emptyNotes)
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([])
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState('')
  const [completionError, setCompletionError] = useState('')
  const [adminDoctors, setAdminDoctors] = useState<DoctorOption[] | null | undefined>(undefined)
  const [actingDoctorId, setActingDoctorId] = useState<number | null>(null)
  const selectionVersion = useRef(0)

  const doctorPath = (path: string, doctorId = actingDoctorId) => doctorId ? `${path}${path.includes('?') ? '&' : '?'}doctor_id=${doctorId}` : path

  const load = (doctorId = actingDoctorId) => Promise.all([
    api.get<QueueItem[]>(doctorPath('/doctors/me/queue', doctorId)),
    api.get<Room[]>('/admin/rooms'),
  ]).then(([nextQueue, nextRooms]) => {
    setQueue(nextQueue)
    setRooms(nextRooms)
    setSelected((current) => {
      if (!current) return null
      const updated = nextQueue.find((item) => item.visit_id === current.visit_id)
      if (updated) return updated
      return ['WAITING_FOR_LAB', 'WAITING_FOR_RADIOLOGY', 'RESULTS_READY'].includes(current.status) ? current : null
    })
  })

  useEffect(() => {
    let active = true
    api.get<DoctorOption[]>('/admin/doctors')
      .then((doctors) => {
        if (!active) return
        const available = doctors.filter((doctor) => doctor.is_active)
        setAdminDoctors(available)
        setActingDoctorId(available[0]?.id ?? null)
        if (!available.length) setMessage(t('doctor.adminNoDoctors'))
      })
      .catch(() => {
        if (!active) return
        setAdminDoctors(null)
        setActingDoctorId(null)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (adminDoctors === undefined) return
    if (Array.isArray(adminDoctors) && !actingDoctorId) return
    const doctorId = Array.isArray(adminDoctors) ? actingDoctorId : null
    load(doctorId).catch((error) => setMessage(error instanceof Error ? error.message : t('doctor.loadFailed')))
    const timer = window.setInterval(() => load(doctorId).catch(() => undefined), 5000)
    return () => window.clearInterval(timer)
  }, [adminDoctors, actingDoctorId])

  async function selectPatient(item: QueueItem) {
    const requestVersion = ++selectionVersion.current
    setSelected(item)
    setRoomId(item.room ? String(rooms.find((room) => room.room_number === item.room)?.id || '') : '')
    setConsultationStarted(item.status === 'WITH_DOCTOR')
    setNotes(emptyNotes)
    setPrescriptions([])
    setMessage('')
    setCompletionError('')
    const [consultationResult, prescriptionsResult] = await Promise.allSettled([
      api.get<Consultation>(doctorPath('/visits/' + item.visit_id + '/consultation')),
      api.get<Prescription[]>(doctorPath('/visits/' + item.visit_id + '/prescriptions')),
    ])
    if (requestVersion !== selectionVersion.current) return
    if (consultationResult.status === 'fulfilled') setNotes(notesFromConsultation(consultationResult.value))
    if (prescriptionsResult.status === 'fulfilled') setPrescriptions(prescriptionsResult.value)
  }

  async function loadPrescriptions(visitId: number, requestVersion = selectionVersion.current) {
    const next = await api.get<Prescription[]>(doctorPath('/visits/' + visitId + '/prescriptions'))
    if (requestVersion === selectionVersion.current) setPrescriptions(next)
  }

  async function callPatient() {
    if (!selected || !roomId || pending) return
    setPending('call')
    try {
      const visit = await api.post<Visit>(doctorPath('/queue/' + selected.visit_id + '/call'), { room_id: Number(roomId) })
      const room = rooms.find((candidate) => candidate.id === Number(roomId))
      setSelected({...selected, status: visit.status, room: room?.room_number})
      setMessage(t('doctor.called', { ticket: selected.ticket_code, room: room?.room_number || '' }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.callFailed'))
    } finally {
      setPending('')
    }
  }

  async function recallPatient() {
    if (!selected || pending) return
    setPending('recall')
    try {
      await api.post(doctorPath('/queue/' + selected.visit_id + '/recall'))
      setMessage(t('doctor.recalled', { ticket: selected.ticket_code }))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.callFailed'))
    } finally {
      setPending('')
    }
  }

  async function skipPatient() {
    if (!selected || pending) return
    setPending('skip')
    try {
      const visit = await api.post<Visit>(doctorPath('/queue/' + selected.visit_id + '/skip'))
      setSelected({...selected, status: visit.status, room: undefined})
      setRoomId('')
      setMessage(t('doctor.skipped', { ticket: selected.ticket_code }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.callFailed'))
    } finally {
      setPending('')
    }
  }

  async function start() {
    if (!selected || pending) return
    setPending('start')
    try {
      const consultation = await api.post<Consultation>(doctorPath('/visits/' + selected.visit_id + '/start-consultation'))
      setSelected({...selected, status: 'WITH_DOCTOR'})
      setConsultationStarted(true)
      setNotes(notesFromConsultation(consultation))
      setCompletionError('')
      setMessage(t('doctor.started'))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.startFailed'))
    } finally {
      setPending('')
    }
  }

  async function saveDraft(visitId = selected?.visit_id) {
    if (!visitId) return
    await api.patch(doctorPath('/visits/' + visitId + '/consultation'), notes)
  }

  async function saveAndComplete(event: FormEvent) {
    event.preventDefault()
    if (!selected || pending) return
    setCompletionError('')
    setMessage('')
    if (selected.status !== 'WITH_DOCTOR') {
      setCompletionError(t('doctor.completeWrongStatus'))
      return
    }
    if (!notes.diagnosis.trim() && !notes.clinical_notes.trim()) {
      setCompletionError(t('doctor.completeValidation'))
      return
    }
    setPending('complete')
    try {
      await saveDraft()
      await api.post(doctorPath('/visits/' + selected.visit_id + '/complete-consultation'))
      setMessage(t('doctor.completed'))
      setCompletionError('')
      setSelected(null)
      setConsultationStarted(false)
      setNotes(emptyNotes)
      setPrescriptions([])
      setRoomId('')
      await load()
    } catch (error) {
      setCompletionError(error instanceof Error ? error.message : t('doctor.completeFailed'))
    } finally {
      setPending('')
    }
  }

  async function orderDiagnostic(type: 'lab' | 'radiology') {
    if (!selected || pending || !clinicalActionStatuses.includes(selected.status)) return
    const visitItem = selected
    setPending(type)
    try {
      await saveDraft(visitItem.visit_id)
      if (type === 'lab') {
        await api.post(doctorPath('/visits/' + visitItem.visit_id + '/lab-orders'), { test_name: 'Complete Blood Count', priority: visitItem.priority })
      } else {
        await api.post(doctorPath('/visits/' + visitItem.visit_id + '/radiology-orders'), { scan_type: 'X-Ray', body_area: 'As clinically indicated', priority: visitItem.priority })
      }
      const visit = await api.get<Visit>('/visits/' + visitItem.visit_id)
      setSelected((current) => current?.visit_id === visitItem.visit_id ? {...current, status: visit.status, room: undefined} : current)
      setRoomId('')
      setMessage(t(type === 'lab' ? 'doctor.labOrdered' : 'doctor.imagingOrdered'))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.orderFailed'))
    } finally {
      setPending('')
    }
  }

  async function createPrescription() {
    if (!selected || pending || !clinicalActionStatuses.includes(selected.status)) return
    const visit = selected
    const requestVersion = selectionVersion.current
    const medicationName = window.prompt(t('doctor.medicationPrompt'))?.trim()
    if (!medicationName) return
    const dosage = window.prompt(t('doctor.dosagePrompt'), '10 mg')?.trim()
    const frequency = window.prompt(t('doctor.frequencyPrompt'), 'Once daily')?.trim()
    const duration = window.prompt(t('doctor.durationPrompt'), '3 days')?.trim()
    if (!dosage || !frequency || !duration) return
    setPending('prescription')
    try {
      await saveDraft(visit.visit_id)
      await api.post(doctorPath('/visits/' + visit.visit_id + '/prescriptions'), { items: [{ medication_name: medicationName, dosage, frequency, duration }] })
      await loadPrescriptions(visit.visit_id, requestVersion)
      setMessage(t('doctor.prescriptionCreated'))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.orderFailed'))
    } finally {
      setPending('')
    }
  }

  async function cancelPrescription(prescription: Prescription) {
    if (!selected || pending || prescription.status !== 'ACTIVE') return
    const visitId = selected.visit_id
    const requestVersion = selectionVersion.current
    const reason = window.prompt(t('doctor.prescriptionCancelReasonPrompt'))?.trim()
    if (!reason) return
    setPending('cancel-prescription-' + prescription.id)
    try {
      await api.post(doctorPath('/prescriptions/' + prescription.id + '/cancel-by-doctor'), { reason })
      await loadPrescriptions(visitId, requestVersion)
      setMessage(t('doctor.prescriptionCancelled', { id: prescription.id }))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.prescriptionCancelFailed'))
    } finally {
      setPending('')
    }
  }

  async function closeVisit(status: 'CANCELLED' | 'LEFT_WITHOUT_BEING_SEEN') {
    if (!selected || pending || !['WAITING_FOR_DOCTOR', 'CALLED'].includes(selected.status)) return
    const visit = selected
    const promptKey = status === 'CANCELLED' ? 'doctor.cancelReasonPrompt' : 'doctor.lwbsReasonPrompt'
    const reason = window.prompt(t(promptKey))?.trim()
    if (!reason) return
    setPending('closure')
    try {
      await api.post('/visits/' + visit.visit_id + '/closure', {
        status,
        reason,
        expected_status: visit.status,
      })
      selectionVersion.current += 1
      setSelected(null)
      setConsultationStarted(false)
      setNotes(emptyNotes)
      setPrescriptions([])
      setRoomId('')
      setMessage(t(status === 'CANCELLED' ? 'doctor.cancelled' : 'doctor.lwbsRecorded', { ticket: visit.ticket_code }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.closureFailed'))
    } finally {
      setPending('')
    }
  }

  async function setDisposition(status: 'ADMITTED' | 'TRANSFERRED') {
    if (!selected || pending || selected.status !== 'WITH_DOCTOR') return
    const visit = selected
    setPending(status.toLowerCase())
    try {
      await saveDraft(visit.visit_id)
      const reasonKey = status === 'ADMITTED' ? 'doctor.admissionReasonPrompt' : 'doctor.transferReasonPrompt'
      const reason = window.prompt(t(reasonKey))?.trim()
      if (!reason) return
      const destination = status === 'TRANSFERRED'
        ? window.prompt(t('doctor.transferDestinationPrompt'))?.trim()
        : undefined
      if (status === 'TRANSFERRED' && !destination) return
      await api.post(doctorPath('/visits/' + visit.visit_id + '/disposition'), {
        status,
        reason,
        ...(destination ? { destination } : {}),
      })
      selectionVersion.current += 1
      setSelected(null)
      setConsultationStarted(false)
      setNotes(emptyNotes)
      setPrescriptions([])
      setRoomId('')
      setMessage(t(status === 'ADMITTED' ? 'doctor.admitted' : 'doctor.transferred', { ticket: visit.ticket_code }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('doctor.dispositionFailed'))
    } finally {
      setPending('')
    }
  }

  const availableRooms = rooms.filter((room) => room.status === 'AVAILABLE' && (!selected || room.department_id === selected.department_id))
  const clinicalActionsAllowed = Boolean(selected && clinicalActionStatuses.includes(selected.status))

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('doctor.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('doctor.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('doctor.subtitle')}</p></div>
    {Array.isArray(adminDoctors) && adminDoctors.length > 0 && <section className="rounded-2xl border border-violet-200 bg-violet-50 p-4"><div className="grid gap-3 md:grid-cols-[1fr_1.4fr] md:items-center"><div><p className="text-xs font-black uppercase tracking-wider text-violet-700">{t('doctor.adminDemo')}</p><p className="mt-1 text-sm text-violet-900">{t('doctor.adminDemoHelp')}</p></div><select value={actingDoctorId ?? ''} onChange={(e) => { selectionVersion.current += 1; setSelected(null); setConsultationStarted(false); setNotes(emptyNotes); setPrescriptions([]); setRoomId(''); setCompletionError(''); setActingDoctorId(Number(e.target.value)) }} className={field}>{adminDoctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.full_name} — {doctor.specialization} — {doctor.department}</option>)}</select></div></section>}
    <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <section><QueueTable items={queue} onSelect={(item) => void selectPatient(item)}/></section>
      <section className="h-fit rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-50 p-3 text-cyan-600"><Stethoscope className="h-5 w-5"/></div><div><h3 className="font-bold text-navy-950">{t('doctor.control')}</h3><p className="text-xs text-slate-500">{selected ? selected.ticket_code + ' • ' + selected.patient_name : t('doctor.select')}</p></div></div>
        {message && <p className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm font-medium text-cyan-800">{message}</p>}
        {selected && <>
          <div className="mt-5 grid grid-cols-[1fr_auto] gap-2">
            <select value={roomId} onChange={(e) => setRoomId(e.target.value)} disabled={selected.status !== 'WAITING_FOR_DOCTOR'} className={field}><option value="">{t('doctor.selectRoom')}</option>{availableRooms.map((room) => <option key={room.id} value={room.id}>{room.room_number}</option>)}</select>
            <button type="button" onClick={callPatient} disabled={Boolean(pending) || !roomId || selected.status !== 'WAITING_FOR_DOCTOR'} className="flex items-center gap-2 rounded-xl bg-orange-500 px-4 font-bold text-white disabled:opacity-40"><BellRing className="h-4 w-4"/>{t('doctor.call')}</button>
          </div>
          <button type="button" onClick={start} disabled={Boolean(pending) || selected.status !== 'CALLED'} className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-navy-950 py-3 font-bold text-white disabled:opacity-40"><ClipboardCheck className="h-4 w-4"/>{t('doctor.start')}</button>
          {selected.status === 'CALLED' && <div className="mt-2 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(pending)} onClick={recallPatient} className="flex items-center justify-center gap-2 rounded-xl border border-cyan-200 py-2.5 text-sm font-bold text-cyan-700 disabled:opacity-40"><RotateCcw className="h-4 w-4"/>{t('doctor.recall')}</button><button type="button" disabled={Boolean(pending)} onClick={skipPatient} className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 py-2.5 text-sm font-bold text-slate-600 disabled:opacity-40"><SkipForward className="h-4 w-4"/>{t('doctor.skip')}</button></div>}
          {['WAITING_FOR_DOCTOR', 'CALLED'].includes(selected.status) && <div className="mt-2 grid grid-cols-2 gap-2"><button type="button" disabled={Boolean(pending)} onClick={() => closeVisit('CANCELLED')} className="flex items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 py-2.5 text-sm font-bold text-red-700 disabled:opacity-40"><Ban className="h-4 w-4"/>{t('doctor.cancelVisit')}</button><button type="button" disabled={Boolean(pending)} onClick={() => closeVisit('LEFT_WITHOUT_BEING_SEEN')} className="flex items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 py-2.5 text-sm font-bold text-amber-800 disabled:opacity-40"><UserX className="h-4 w-4"/>{t('doctor.markLwbs')}</button></div>}
          <p className="mt-2 text-xs text-slate-400">{enumLabel(selected.status)}</p>
        </>}
        {consultationStarted && selected && <form onSubmit={saveAndComplete} className="mt-6 space-y-4 border-t border-slate-100 pt-6">
          <label><span className="mb-1.5 block text-xs font-semibold">{t('doctor.diagnosis')}</span><textarea value={notes.diagnosis} onChange={(e) => setNotes({...notes, diagnosis: e.target.value})} className={field + ' min-h-20'}/></label>
          <label><span className="mb-1.5 block text-xs font-semibold">{t('doctor.notes')}</span><textarea value={notes.clinical_notes} onChange={(e) => setNotes({...notes, clinical_notes: e.target.value})} className={field + ' min-h-24'}/></label>
          <label><span className="mb-1.5 block text-xs font-semibold">{t('doctor.treatment')}</span><textarea value={notes.treatment_plan} onChange={(e) => setNotes({...notes, treatment_plan: e.target.value})} className={field + ' min-h-20'}/></label>
          {selected.status === 'WITH_DOCTOR' && <div className="grid grid-cols-2 gap-2"><button disabled={Boolean(pending)} type="button" onClick={() => setDisposition('ADMITTED')} className="flex items-center justify-center gap-2 rounded-xl border border-violet-200 bg-violet-50 p-3 text-xs font-bold text-violet-700 disabled:opacity-40"><Building2 className="h-4 w-4"/>{t('doctor.admit')}</button><button disabled={Boolean(pending)} type="button" onClick={() => setDisposition('TRANSFERRED')} className="flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs font-bold text-blue-700 disabled:opacity-40"><ArrowRightLeft className="h-4 w-4"/>{t('doctor.transfer')}</button></div>}
          <div className="grid grid-cols-3 gap-2"><button disabled={Boolean(pending) || !clinicalActionsAllowed} type="button" onClick={() => orderDiagnostic('lab')} className="rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-40"><FlaskConical className="mx-auto mb-1 h-4 w-4"/>{t('doctor.lab')}</button><button disabled={Boolean(pending) || !clinicalActionsAllowed} type="button" onClick={() => orderDiagnostic('radiology')} className="rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-40"><ScanLine className="mx-auto mb-1 h-4 w-4"/>{t('doctor.imaging')}</button><button disabled={Boolean(pending) || !clinicalActionsAllowed} type="button" onClick={createPrescription} className="rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-40"><Pill className="mx-auto mb-1 h-4 w-4"/>{t('doctor.rx')}</button></div>
          <section className="rounded-xl border border-slate-100 bg-slate-50/70 p-3"><div className="mb-2 flex items-center justify-between"><h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">{t('doctor.prescriptions')}</h4><span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-slate-500">{prescriptions.length}</span></div>{prescriptions.length === 0 ? <p className="py-2 text-xs text-slate-400">{t('doctor.noPrescriptions')}</p> : <div className="space-y-2">{prescriptions.map((prescription) => <article key={prescription.id} className="rounded-lg border border-slate-200 bg-white p-3"><div className="flex items-center justify-between gap-2"><p className="text-sm font-bold text-navy-950">{t('doctor.prescriptionNumber', { id: prescription.id })}</p><span className="text-xs font-bold text-slate-500">{enumLabel(prescription.status)}</span></div><div className="mt-2 space-y-1">{prescription.items.map((item) => <p key={item.id} className="text-xs text-slate-600"><span className="font-semibold">{item.medication_name}</span> · {item.dosage} · {item.frequency} · {item.duration}</p>)}</div>{prescription.status === 'ACTIVE' && <button type="button" disabled={Boolean(pending)} onClick={() => cancelPrescription(prescription)} className="mt-3 flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-700 disabled:opacity-40"><Ban className="h-3.5 w-3.5"/>{t('doctor.cancelPrescription')}</button>}</article>)}</div>}</section>
          {selected.status !== 'WITH_DOCTOR' && <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{t(selected.status === 'WAITING_FOR_DOCTOR' ? 'doctor.recallAfterResults' : 'doctor.awaitingReturn')}</p>}
          {completionError && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{completionError}</p>}
          <button type="submit" disabled={Boolean(pending)} aria-busy={pending === 'complete'} className="w-full rounded-xl bg-emerald-600 py-3 font-bold text-white hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60">{pending === 'complete' ? t('doctor.completing') : t('doctor.complete')}</button>
        </form>}
      </section>
    </div>
  </div>
}
