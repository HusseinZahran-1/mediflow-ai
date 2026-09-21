import { BadgePlus, Ban, Search, TicketCheck, UserRoundPlus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { Department, Patient, Visit } from '../types'

const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10'
const genders = ['MALE', 'FEMALE', 'OTHER']
const identityTypes = ['NATIONAL_ID', 'RESIDENCE_ID', 'PASSPORT', 'TEMPORARY_PERMIT', 'UNKNOWN_EMERGENCY']
const visitTypes = ['WALK_IN', 'EMERGENCY', 'OUTPATIENT', 'FOLLOW_UP', 'REFERRAL', 'AMBULANCE']
const arrivalMethods = ['WALKING', 'WHEELCHAIR', 'AMBULANCE', 'FAMILY_VEHICLE', 'POLICE', 'MILITARY_TRANSPORT', 'OTHER']

export function ReceptionPage() {
  const { language, t, enumLabel, locale } = useLanguage()
  const [query, setQuery] = useState('')
  const [patients, setPatients] = useState<Patient[]>([])
  const [selected, setSelected] = useState<Patient | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [notice, setNotice] = useState('')
  const [issuedTicket, setIssuedTicket] = useState<Visit | null>(null)
  const [busy, setBusy] = useState<'search' | 'register' | 'visit' | 'cancel' | ''>('')
  const [form, setForm] = useState({ full_name: '', phone_number: '', gender: 'MALE', date_of_birth: '', nationality: 'Jordanian', identity_type: 'NATIONAL_ID', identity_number: '', is_military: false, military_number: '' })
  const [visit, setVisit] = useState({ department_id: '', visit_type: 'WALK_IN', arrival_method: 'WALKING' })

  useEffect(() => { api.get<Department[]>('/departments').then(setDepartments).catch(() => undefined) }, [])

  async function search() {
    if (!query.trim() || busy) return
    setBusy('search')
    setSelected(null)
    setIssuedTicket(null)
    setPatients([])
    try {
      const result = await api.get<{ items: Patient[] }>(`/patients/search?q=${encodeURIComponent(query)}`)
      setPatients(result.items)
      if (result.items.length === 1) setSelected(result.items[0])
    } catch (error) {
      setNotice(error instanceof Error ? error.message : t('reception.registrationFailed'))
    } finally {
      setBusy('')
    }
  }

  async function register(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy('register')
    setNotice('')
    try {
      const patient = await api.post<Patient>('/patients', { ...form, date_of_birth: form.date_of_birth || null, phone_number: form.phone_number || null, military_number: form.is_military ? form.military_number : null })
      setSelected(patient)
      setPatients([patient])
      setIssuedTicket(null)
      setNotice(t('reception.registered', { mrn: patient.medical_record_number }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : t('reception.registrationFailed'))
    } finally {
      setBusy('')
    }
  }

  async function createVisit(event: FormEvent) {
    event.preventDefault()
    if (!selected || busy) return
    setBusy('visit')
    try {
      const created = await api.post<Visit>('/visits', { patient_id: selected.id, department_id: Number(visit.department_id), visit_type: visit.visit_type, arrival_method: visit.arrival_method })
      setIssuedTicket(created)
      setVisit((current) => ({ ...current, department_id: '' }))
      setNotice(t('reception.visitCreated', { ticket: created.ticket_code }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : t('reception.visitFailed'))
    } finally {
      setBusy('')
    }
  }

  async function printTicket() {
    if (!issuedTicket) return
    const ticket = await api.get<{hospital:string;ticket_code:string;priority:string;department:string;room?:string;registered_at:string;qr_png_base64:string}>(`/visits/${issuedTicket.id}/ticket`)
    const popup = window.open('', '_blank', 'width=420,height=720')
    if (!popup) { setNotice(t('reception.popup')); return }
    const escape = (value: string) => value.replace(/[&<>'"]/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character] || character))
    popup.document.write(`<html lang="${language}" dir="${language === 'ar' ? 'rtl' : 'ltr'}"><head><title>${escape(ticket.ticket_code)}</title><style>@page{size:80mm auto;margin:4mm}body{width:72mm;margin:0 auto;font-family:Arial,Tahoma,sans-serif;text-align:center;color:#111}h1{font-size:16px;margin:8px 0}h2{font-size:42px;margin:10px 0}.rule{border-top:1px dashed #333;margin:10px 0}.row{display:flex;justify-content:space-between;gap:8px;font-size:12px;margin:6px 0}img{width:120px;height:120px}.notice{font-size:10px;margin-top:10px}</style></head><body><h1>${escape(ticket.hospital)}</h1><div class="rule"></div><h2 dir="ltr">${escape(ticket.ticket_code)}</h2><div class="row"><b>${escape(t('common.department'))}</b><span>${escape(enumLabel(ticket.department))}</span></div><div class="row"><b>${escape(t('common.priority'))}</b><span>${escape(enumLabel(ticket.priority))}</span></div><div class="row"><b>${escape(t('triage.arrival'))}</b><span>${new Date(ticket.registered_at).toLocaleTimeString(locale)}</span></div><div class="rule"></div><img src="data:image/png;base64,${ticket.qr_png_base64}"/><p class="notice">${escape(t('reception.ticketInstruction'))}</p><p class="notice">${escape(t('disclaimer'))}</p><script>window.onload=()=>window.print()<\/script></body></html>`)
    popup.document.close()
  }

  async function cancelIssuedVisit() {
    if (!issuedTicket || busy) return
    const reason = window.prompt(t('reception.cancelReasonPrompt'))?.trim()
    if (!reason) return
    const ticket = issuedTicket
    setBusy('cancel')
    try {
      await api.post('/visits/' + ticket.id + '/closure', {
        status: 'CANCELLED',
        reason,
        expected_status: ticket.status,
      })
      setIssuedTicket(null)
      setNotice(t('reception.visitCancelled', { ticket: ticket.ticket_code }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : t('reception.cancelFailed'))
    } finally {
      setBusy('')
    }
  }

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('reception.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('reception.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('reception.subtitle')}</p></div>
    {notice && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm font-medium text-cyan-800"><span>{notice}</span>{issuedTicket && <div className="flex flex-wrap gap-2"><button type="button" disabled={Boolean(busy)} onClick={cancelIssuedVisit} className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-bold text-red-700 disabled:opacity-40"><Ban className="h-3.5 w-3.5"/>{t('reception.cancelVisit')}</button><button type="button" disabled={Boolean(busy)} onClick={printTicket} className="rounded-lg bg-navy-950 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">{t('reception.print')}</button></div>}</div>}
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="mb-4 flex items-center gap-2"><Search className="h-5 w-5 text-cyan-600"/><h3 className="font-bold text-navy-950">{t('reception.find')}</h3></div><div className="flex gap-2"><input value={query} onChange={(event) => { setQuery(event.target.value); setSelected(null); setIssuedTicket(null); setPatients([]) }} onKeyDown={(event) => event.key === 'Enter' && search()} placeholder={t('reception.searchPlaceholder')} className={inputClass}/><button type="button" disabled={Boolean(busy)} onClick={search} className="rounded-xl bg-navy-950 px-6 font-bold text-white hover:bg-navy-800 disabled:opacity-50">{t('common.search')}</button></div>{patients.length > 0 && <div className="mt-4 grid gap-2">{patients.map((patient) => <button type="button" key={patient.id} onClick={() => { setSelected(patient); setIssuedTicket(null) }} className={`flex items-center justify-between rounded-xl border p-3 text-left transition ${selected?.id === patient.id ? 'border-cyan-400 bg-cyan-50' : 'border-slate-200 hover:bg-slate-50'}`}><div><p className="font-semibold text-slate-800">{patient.full_name}</p><p className="text-xs text-slate-500" dir="ltr">{patient.medical_record_number} • {patient.identity_number}</p></div><span className="text-xs font-bold text-cyan-700">{t('common.select')}</span></button>)}</div>}</section>
    <div className="grid gap-6 xl:grid-cols-2">
      <form onSubmit={register} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card"><div className="mb-5 flex items-center gap-2"><UserRoundPlus className="h-5 w-5 text-cyan-600"/><div><h3 className="font-bold text-navy-950">{t('reception.registerTitle')}</h3><p className="text-xs text-slate-500">{t('reception.permanentRecord')}</p></div></div><div className="grid gap-4 sm:grid-cols-2"><label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.fullName')}</span><input required value={form.full_name} onChange={(e) => setForm({...form, full_name:e.target.value})} className={inputClass}/></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.phone')}</span><input value={form.phone_number} onChange={(e) => setForm({...form, phone_number:e.target.value})} className={inputClass} dir="ltr"/></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.gender')}</span><select value={form.gender} onChange={(e) => setForm({...form, gender:e.target.value})} className={inputClass}>{genders.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.dob')}</span><input type="date" value={form.date_of_birth} onChange={(e) => setForm({...form, date_of_birth:e.target.value})} className={inputClass}/></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.nationality')}</span><input value={form.nationality} onChange={(e) => setForm({...form, nationality:e.target.value})} className={inputClass}/></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.identityType')}</span><select value={form.identity_type} onChange={(e) => setForm({...form, identity_type:e.target.value})} className={inputClass}>{identityTypes.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.identityNumber')}</span><input required value={form.identity_number} onChange={(e) => setForm({...form, identity_number:e.target.value})} className={inputClass} dir="ltr"/></label><label className="sm:col-span-2 flex items-center gap-3 rounded-xl bg-slate-50 p-3"><input type="checkbox" checked={form.is_military} onChange={(e) => setForm({...form, is_military:e.target.checked})} className="h-4 w-4 accent-cyan-600"/><span className="text-sm font-semibold text-slate-700">{t('reception.militaryPatient')}</span></label>{form.is_military && <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.militaryNumber')}</span><input required value={form.military_number} onChange={(e) => setForm({...form, military_number:e.target.value})} className={inputClass} dir="ltr"/></label>}</div><button disabled={Boolean(busy)} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-600 py-3 font-bold text-white hover:bg-cyan-700 disabled:opacity-50"><BadgePlus className="h-4 w-4"/>{t('reception.register')}</button></form>
      <form onSubmit={createVisit} className="h-fit rounded-2xl border border-slate-200 bg-white p-6 shadow-card"><div className="mb-5 flex items-center gap-2"><TicketCheck className="h-5 w-5 text-cyan-600"/><div><h3 className="font-bold text-navy-950">{t('reception.visitTitle')}</h3><p className="text-xs text-slate-500">{t('reception.visitSubtitle')}</p></div></div>{selected ? <div className="mb-5 rounded-xl bg-navy-950 p-4 text-white"><p className="text-xs text-cyan-300">{t('reception.selectedPatient')}</p><p className="mt-1 text-lg font-bold">{selected.full_name}</p><p className="text-xs text-slate-400" dir="ltr">{selected.medical_record_number}</p></div> : <div className="mb-5 rounded-xl border border-dashed border-slate-300 p-7 text-center text-sm text-slate-400">{t('reception.selectFirst')}</div>}<div className="space-y-4"><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('common.department')}</span><select required value={visit.department_id} onChange={(e) => setVisit({...visit, department_id:e.target.value})} className={inputClass}><option value="">{t('reception.chooseDepartment')}</option>{departments.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{enumLabel(d.name)}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.visitType')}</span><select value={visit.visit_type} onChange={(e) => setVisit({...visit, visit_type:e.target.value})} className={inputClass}>{visitTypes.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold text-slate-600">{t('reception.arrivalMethod')}</span><select value={visit.arrival_method} onChange={(e) => setVisit({...visit, arrival_method:e.target.value})} className={inputClass}>{arrivalMethods.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label></div><button disabled={!selected || Boolean(busy)} className="mt-5 w-full rounded-xl bg-navy-950 py-3 font-bold text-white hover:bg-navy-800 disabled:opacity-40">{t('reception.createVisit')}</button></form>
    </div>
  </div>
}
