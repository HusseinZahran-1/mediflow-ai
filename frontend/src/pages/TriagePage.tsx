import { Activity, Ban, BrainCircuit, CheckCircle2, HeartPulse, UserX } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { PriorityBadge } from '../components/PriorityBadge'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { Priority, Triage, Visit } from '../types'

const fieldClass = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10'
const priorities: Priority[] = ['NORMAL', 'URGENT', 'CRITICAL']
const consciousnessLevels = ['ALERT', 'RESPONDS_TO_VOICE', 'RESPONDS_TO_PAIN', 'UNRESPONSIVE']

const emptyForm = () => ({
  chief_complaint: '',
  symptoms: '',
  symptom_start_time: '',
  pain_level: '',
  temperature: '',
  systolic_bp: '',
  diastolic_bp: '',
  heart_rate: '',
  respiratory_rate: '',
  oxygen_saturation: '',
  blood_glucose: '',
  weight: '',
  height: '',
  consciousness_level: '',
  severe_bleeding: false,
  difficulty_breathing: false,
  chest_pain: false,
  seizure: false,
  loss_of_consciousness: false,
  severe_allergy: false,
  pregnancy: false,
  recent_surgery: false,
  chronic_diseases: '',
  medications: '',
  human_priority: '' as Priority | '',
  nurse_notes: '',
})

type TriageForm = ReturnType<typeof emptyForm>

const textValue = (value: unknown) => value == null ? '' : String(value)
const optionalNumber = (value: string) => value === '' ? null : Number(value)

function formFromTriage(triage: Triage): TriageForm {
  return {
    chief_complaint: triage.chief_complaint || '',
    symptoms: triage.symptoms || '',
    symptom_start_time: triage.symptom_start_time ? triage.symptom_start_time.slice(0, 16) : '',
    pain_level: textValue(triage.pain_level),
    temperature: textValue(triage.temperature),
    systolic_bp: textValue(triage.systolic_bp),
    diastolic_bp: textValue(triage.diastolic_bp),
    heart_rate: textValue(triage.heart_rate),
    respiratory_rate: textValue(triage.respiratory_rate),
    oxygen_saturation: textValue(triage.oxygen_saturation),
    blood_glucose: textValue(triage.blood_glucose),
    weight: textValue(triage.weight),
    height: textValue(triage.height),
    consciousness_level: triage.consciousness_level || '',
    severe_bleeding: Boolean(triage.severe_bleeding),
    difficulty_breathing: Boolean(triage.difficulty_breathing),
    chest_pain: Boolean(triage.chest_pain),
    seizure: Boolean(triage.seizure),
    loss_of_consciousness: Boolean(triage.loss_of_consciousness),
    severe_allergy: Boolean(triage.severe_allergy),
    pregnancy: Boolean(triage.pregnancy),
    recent_surgery: Boolean(triage.recent_surgery),
    chronic_diseases: triage.chronic_diseases || '',
    medications: triage.medications || '',
    human_priority: triage.human_priority,
    nurse_notes: triage.nurse_notes || '',
  }
}

function payloadFromForm(form: TriageForm) {
  return {
    ...form,
    symptom_start_time: form.symptom_start_time || null,
    pain_level: optionalNumber(form.pain_level),
    temperature: optionalNumber(form.temperature),
    systolic_bp: optionalNumber(form.systolic_bp),
    diastolic_bp: optionalNumber(form.diastolic_bp),
    heart_rate: optionalNumber(form.heart_rate),
    respiratory_rate: optionalNumber(form.respiratory_rate),
    oxygen_saturation: optionalNumber(form.oxygen_saturation),
    blood_glucose: optionalNumber(form.blood_glucose),
    weight: optionalNumber(form.weight),
    height: optionalNumber(form.height),
    symptoms: form.symptoms || null,
    chronic_diseases: form.chronic_diseases || null,
    medications: form.medications || null,
    nurse_notes: form.nurse_notes || null,
    consciousness_level: form.consciousness_level || null,
  }
}

export function TriagePage() {
  const { t, enumLabel, locale } = useLanguage()
  const [visits, setVisits] = useState<Visit[]>([])
  const [selected, setSelected] = useState<Visit | null>(null)
  const [result, setResult] = useState<Triage | null>(null)
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [form, setForm] = useState<TriageForm>(emptyForm)
  const [finalPriority, setFinalPriority] = useState<Priority>('NORMAL')
  const [disagreementReason, setDisagreementReason] = useState('')
  const selectionVersion = useRef(0)

  const load = () => api.get<Visit[]>('/visits/active').then((data) => {
    const nextVisits = data.filter((visit) => ['WAITING_FOR_TRIAGE', 'IN_TRIAGE'].includes(visit.status))
    setVisits(nextVisits)
    setSelected((current) => {
      if (!current) return null
      return nextVisits.find((visit) => visit.id === current.id) || null
    })
  })

  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : t('triage.loadFailed')))
    const timer = window.setInterval(() => load().catch(() => undefined), 5000)
    return () => window.clearInterval(timer)
  }, [])

  async function selectVisit(visit: Visit) {
    const requestVersion = ++selectionVersion.current
    setSelected(visit)
    setResult(null)
    setForm(emptyForm())
    setFinalPriority('NORMAL')
    setDisagreementReason('')
    setMessage('')
    if (visit.status === 'IN_TRIAGE') {
      try {
        const existing = await api.get<Triage>('/visits/' + visit.id + '/triage')
        if (requestVersion !== selectionVersion.current) return
        setResult(existing)
        setForm(formFromTriage(existing))
        setFinalPriority(existing.final_priority || existing.human_priority)
        setDisagreementReason(existing.disagreement_reason || '')
      } catch (error) {
        setMessage(error instanceof Error ? error.message : t('triage.loadFailed'))
      }
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!selected || pending) return
    setPending(true)
    try {
      const path = '/visits/' + selected.id + '/triage'
      const triage = result
        ? await api.patch<Triage>(path, payloadFromForm(form))
        : await api.post<Triage>(path, payloadFromForm(form))
      setResult(triage)
      setForm(formFromTriage(triage))
      setFinalPriority(triage.human_priority)
      setMessage(t('triage.saved'))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('triage.saveFailed'))
    } finally {
      setPending(false)
    }
  }

  async function finalize() {
    if (!selected || !result || pending) return
    const disagrees = Boolean(result.ai_priority && result.ai_priority !== finalPriority)
    if (disagrees && !disagreementReason.trim()) {
      setMessage(t('triage.reasonRequired'))
      return
    }
    setPending(true)
    try {
      await api.post<Triage>('/visits/' + selected.id + '/triage/finalize', {
        final_priority: finalPriority,
        disagreement_reason: disagrees ? disagreementReason.trim() : null,
      })
      setMessage(t('triage.finalized'))
      setSelected(null)
      setResult(null)
      setForm(emptyForm())
      setDisagreementReason('')
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('triage.finalizeFailed'))
    } finally {
      setPending(false)
    }
  }

  async function closeVisit(status: 'CANCELLED' | 'LEFT_WITHOUT_BEING_SEEN') {
    if (!selected || pending) return
    const visit = selected
    const promptKey = status === 'CANCELLED' ? 'triage.cancelReasonPrompt' : 'triage.lwbsReasonPrompt'
    const reason = window.prompt(t(promptKey))?.trim()
    if (!reason) return
    setPending(true)
    try {
      await api.post('/visits/' + visit.id + '/closure', {
        status,
        reason,
        expected_status: visit.status,
      })
      selectionVersion.current += 1
      setSelected(null)
      setResult(null)
      setForm(emptyForm())
      setFinalPriority('NORMAL')
      setDisagreementReason('')
      setMessage(t(status === 'CANCELLED' ? 'triage.cancelled' : 'triage.lwbsRecorded', { ticket: visit.ticket_code }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('triage.closureFailed'))
    } finally {
      setPending(false)
    }
  }

  const vitalFields: Array<[string, keyof TriageForm, string, string, string]> = [
    ['triage.temperature', 'temperature', '25', '45', '0.1'],
    ['triage.heartRate', 'heart_rate', '20', '260', '1'],
    ['triage.systolic', 'systolic_bp', '30', '300', '1'],
    ['triage.diastolic', 'diastolic_bp', '20', '200', '1'],
    ['triage.respiratory', 'respiratory_rate', '4', '80', '1'],
    ['triage.spo2', 'oxygen_saturation', '30', '100', '0.1'],
    ['triage.pain', 'pain_level', '0', '10', '1'],
    ['triage.glucose', 'blood_glucose', '10', '1000', '0.1'],
    ['triage.weight', 'weight', '0.5', '500', '0.1'],
    ['triage.height', 'height', '20', '260', '0.1'],
  ]
  const emergencyFlags: Array<[string, keyof TriageForm]> = [
    ['triage.severeBleeding', 'severe_bleeding'],
    ['triage.difficultyBreathing', 'difficulty_breathing'],
    ['triage.chestPain', 'chest_pain'],
    ['triage.seizure', 'seizure'],
    ['triage.lossConsciousness', 'loss_of_consciousness'],
    ['triage.severeAllergy', 'severe_allergy'],
    ['triage.pregnancy', 'pregnancy'],
    ['triage.recentSurgery', 'recent_surgery'],
  ]

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('triage.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('triage.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('triage.subtitle')}</p></div>
    {message && <div className="rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-800">{message}</div>}
    <div className="grid gap-6 xl:grid-cols-[0.72fr_1.28fr]">
      <section className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-navy-950">{t('triage.awaiting')}</h3><span className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs font-bold text-cyan-700">{visits.length}</span></div>
        <div className="space-y-2">{visits.map((visit) => <button type="button" key={visit.id} onClick={() => selectVisit(visit)} className={'w-full rounded-xl border p-4 text-left transition ' + (selected?.id === visit.id ? 'border-cyan-400 bg-cyan-50' : 'border-slate-200 hover:border-slate-300')}><div className="flex items-center justify-between"><span className="text-xl font-black text-navy-950" dir="ltr">{visit.ticket_code}</span><span className="text-xs font-semibold text-slate-400">#{visit.id}</span></div><p className="mt-2 text-xs text-slate-500">{t('triage.arrival')}: {new Date(visit.arrival_time).toLocaleTimeString(locale, {hour: '2-digit', minute: '2-digit'})}</p></button>)}{visits.length === 0 && <p className="py-10 text-center text-sm text-slate-400">{t('triage.noPatients')}</p>}</div>
      </section>
      <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="mb-6 flex items-center justify-between"><div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-50 p-3 text-cyan-600"><Activity className="h-5 w-5"/></div><div><h3 className="font-bold text-navy-950">{t('triage.assessment')}</h3><p className="text-xs text-slate-500">{selected ? t('common.ticket') + ' ' + selected.ticket_code : t('triage.select')}</p></div></div>{result?.final_priority && <PriorityBadge priority={result.final_priority}/>}</div>
        {selected && <div className="mb-5 grid gap-2 sm:grid-cols-2">
          <button type="button" disabled={pending || !['WAITING_FOR_TRIAGE', 'IN_TRIAGE'].includes(selected.status)} onClick={() => closeVisit('CANCELLED')} className="flex items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm font-bold text-red-700 disabled:opacity-40"><Ban className="h-4 w-4"/>{t('triage.cancelVisit')}</button>
          {['WAITING_FOR_TRIAGE', 'IN_TRIAGE'].includes(selected.status) && <button type="button" disabled={pending} onClick={() => closeVisit('LEFT_WITHOUT_BEING_SEEN')} className="flex items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm font-bold text-amber-800 disabled:opacity-40"><UserX className="h-4 w-4"/>{t('triage.markLwbs')}</button>}
        </div>}
        <fieldset disabled={!selected || pending || Boolean(result?.finalized_at)} className="space-y-5 disabled:opacity-50">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold">{t('triage.chiefComplaint')}</span><textarea required value={form.chief_complaint} onChange={(e) => setForm({...form, chief_complaint: e.target.value})} className={fieldClass + ' min-h-20'}/></label>
            <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold">{t('triage.symptoms')}</span><input value={form.symptoms} onChange={(e) => setForm({...form, symptoms: e.target.value})} className={fieldClass}/></label>
            <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.symptomStart')}</span><input type="datetime-local" value={form.symptom_start_time} onChange={(e) => setForm({...form, symptom_start_time: e.target.value})} className={fieldClass}/></label>
            <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.consciousness')}</span><select value={form.consciousness_level} onChange={(e) => setForm({...form, consciousness_level: e.target.value})} className={fieldClass}><option value="">{t('common.select')}</option>{consciousnessLevels.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label>
            {vitalFields.map(([labelKey, key, min, max, step]) => <label key={key}><span className="mb-1.5 block text-xs font-semibold">{t(labelKey)}</span><input type="number" min={min} max={max} step={step} value={form[key] as string} onChange={(e) => setForm({...form, [key]: e.target.value})} className={fieldClass}/></label>)}
            <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold">{t('triage.chronicDiseases')}</span><textarea value={form.chronic_diseases} onChange={(e) => setForm({...form, chronic_diseases: e.target.value})} className={fieldClass + ' min-h-16'}/></label>
            <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-semibold">{t('triage.medications')}</span><textarea value={form.medications} onChange={(e) => setForm({...form, medications: e.target.value})} className={fieldClass + ' min-h-16'}/></label>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">{emergencyFlags.map(([labelKey, key]) => <label key={key} className="flex items-center gap-2 rounded-xl bg-slate-50 p-3 text-sm font-medium"><input type="checkbox" checked={form[key] as boolean} onChange={(e) => setForm({...form, [key]: e.target.checked})} className="accent-cyan-600"/>{t(labelKey)}</label>)}</div>
          <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.humanPriority')}</span><select required value={form.human_priority} onChange={(e) => setForm({...form, human_priority: e.target.value as Priority | ''})} className={fieldClass}><option value="">{t('common.select')}</option>{priorities.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label>
          <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.nurseNotes')}</span><textarea value={form.nurse_notes} onChange={(e) => setForm({...form, nurse_notes: e.target.value})} className={fieldClass + ' min-h-20'}/></label>
          <button disabled={pending} className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy-950 py-3 font-bold text-white disabled:opacity-50"><HeartPulse className="h-4 w-4"/>{t(result ? 'triage.update' : 'triage.save')}</button>
        </fieldset>
        {result && <div className="mt-6 rounded-2xl border border-cyan-200 bg-gradient-to-br from-cyan-50 to-white p-5">
          <div className="flex items-center gap-2 text-cyan-700"><BrainCircuit className="h-5 w-5"/><p className="text-sm font-bold uppercase tracking-wider">{t('triage.decisionSupport')}</p></div>
          <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3"><p className="text-xs font-black uppercase tracking-wider text-amber-800">{t('triage.leakageDemoTitle')}</p><p className="mt-1 text-xs leading-5 text-amber-800">{t('triage.leakageDemoNotice')}</p></div>
          <div className="mt-4 flex items-center justify-between"><div><p className="text-xs text-slate-500">{t('triage.aiRecommendation')}</p><div className="mt-2"><PriorityBadge priority={result.ai_priority || 'NORMAL'}/></div></div><div className="text-right"><p className="text-xs text-slate-500">{t('triage.confidence')}</p><p className="mt-1 text-2xl font-black text-navy-950">{Math.round((result.ai_confidence || 0) * 100)}%</p></div></div>
          <p className="mt-4 text-xs leading-5 text-slate-500">{t('triage.aiNotice')}</p>
          {!result.finalized_at && <div className="mt-4 space-y-3">
            <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.finalPriority')}</span><select value={finalPriority} onChange={(e) => setFinalPriority(e.target.value as Priority)} className={fieldClass}>{priorities.map((value) => <option key={value} value={value}>{enumLabel(value)}</option>)}</select></label>
            {result.ai_priority !== finalPriority && <label><span className="mb-1.5 block text-xs font-semibold">{t('triage.disagreementReason')}</span><textarea required value={disagreementReason} onChange={(e) => setDisagreementReason(e.target.value)} className={fieldClass + ' min-h-20'}/></label>}
            <button type="button" disabled={pending} onClick={finalize} className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-600 py-3 font-bold text-white disabled:opacity-50"><CheckCircle2 className="h-4 w-4"/>{t('triage.confirm', { priority: enumLabel(finalPriority) })}</button>
          </div>}
        </div>}
      </form>
    </div>
  </div>
}
