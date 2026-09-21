import { Ban, CheckCircle2, Pill } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'

interface Prescription { id:number; visit_id:number; ticket_code?:string|null; priority?:string|null; status:string; created_at:string; items:Array<{id:number;medication_name:string;dosage:string;frequency:string;duration:string}> }

export function PharmacyPage() {
  const { t, enumLabel, locale } = useLanguage()
  const [items, setItems] = useState<Prescription[]>([])
  const [message, setMessage] = useState('')
  const [pendingId, setPendingId] = useState<number | null>(null)
  const load = () => api.get<Prescription[]>('/prescriptions?worklist=true').then(setItems)
  useEffect(() => {
    load().catch((error) => setMessage(error.message))
    const timer = window.setInterval(() => load().catch(() => undefined), 5000)
    return () => window.clearInterval(timer)
  }, [])

  async function updateStatus(id: number, status: 'DISPENSED' | 'CANCELLED') {
    if (pendingId !== null) return
    setPendingId(id)
    try {
      await api.patch(`/prescriptions/${id}`, { status })
      setMessage(t(status === 'DISPENSED' ? 'pharmacy.dispensed' : 'pharmacy.cancelled', { id }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('pharmacy.failed'))
    } finally {
      setPendingId(null)
    }
  }

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('pharmacy.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('pharmacy.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('pharmacy.subtitle')}</p></div>
    {message && <p className="rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-800">{message}</p>}
    <div className="grid gap-4">{items.map((prescription) => <article key={prescription.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-50 p-3 text-cyan-600"><Pill className="h-5 w-5"/></div><div><p className="font-bold text-navy-950">{t('pharmacy.prescription', {id: prescription.id})}</p><p className="text-xs text-slate-400">{prescription.ticket_code ? `${t('common.ticket')} ${prescription.ticket_code}` : `${t('common.visit')} #${prescription.visit_id}`} • {new Date(prescription.created_at).toLocaleString(locale)}</p></div></div><div className="flex flex-col items-end gap-1">{prescription.priority && <span className="text-xs font-bold text-cyan-700">{enumLabel(prescription.priority)}</span>}<span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{enumLabel(prescription.status)}</span></div></div><div className="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-100">{prescription.items.map((item) => <div key={item.id} className="grid gap-1 p-3 sm:grid-cols-4"><p className="font-semibold text-slate-700">{item.medication_name}</p><p className="text-sm text-slate-500">{item.dosage}</p><p className="text-sm text-slate-500">{item.frequency}</p><p className="text-sm text-slate-500">{item.duration}</p></div>)}</div><div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={pendingId !== null || prescription.status !== 'ACTIVE'} onClick={() => updateStatus(prescription.id, 'DISPENSED')} className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40"><CheckCircle2 className="h-4 w-4"/>{t('pharmacy.dispense')}</button><button type="button" disabled={pendingId !== null || prescription.status !== 'ACTIVE'} onClick={() => updateStatus(prescription.id, 'CANCELLED')} className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-700 disabled:opacity-40"><Ban className="h-4 w-4"/>{t('pharmacy.cancel')}</button></div></article>)}{items.length === 0 && <p className="rounded-2xl border border-dashed border-slate-300 py-16 text-center text-sm text-slate-400">{t('pharmacy.empty')}</p>}</div>
  </div>
}
