import { Archive, ChevronLeft, ChevronRight, Clock3, Search, Stethoscope, UserRound } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { CompletedVisitItem, CompletedVisitPage, Department } from '../types'

const terminalStatuses = ['COMPLETED', 'DISCHARGED', 'ADMITTED', 'TRANSFERRED', 'CANCELLED', 'LEFT_WITHOUT_BEING_SEEN']
const input = 'rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10'

export function CompletedPatientsPage() {
  const { t, enumLabel, locale } = useLanguage()
  const [data, setData] = useState<CompletedVisitPage>({ items: [], total: 0, page: 1, page_size: 50 })
  const [departments, setDepartments] = useState<Department[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<CompletedVisitItem | null>(null)

  useEffect(() => {
    api.get<Department[]>('/departments').then(setDepartments).catch(() => setDepartments([]))
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      setLoading(true)
      setError('')
      try {
        const params = new URLSearchParams({ page: String(page), page_size: '50' })
        if (search.trim()) params.set('search', search.trim())
        if (status) params.set('status', status)
        if (departmentId) params.set('department_id', departmentId)
        const result = await api.get<CompletedVisitPage>(`/admin/completed-visits?${params.toString()}`)
        setData(result)
        setSelected((current) => current ? result.items.find((item) => item.visit_id === current.visit_id) || null : null)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('completed.loadFailed'))
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => window.clearTimeout(timer)
  }, [search, status, departmentId, page, t])

  useEffect(() => { setPage(1) }, [search, status, departmentId])

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size))
  const completedOnPage = useMemo(() => data.items.filter((item) => item.status === 'COMPLETED' || item.status === 'DISCHARGED').length, [data.items])

  const formatDate = (value?: string) => value ? new Date(value).toLocaleString(locale) : t('common.none')

  return <div className="space-y-6">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-600">{t('completed.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('completed.title')}</h2><p className="mt-2 max-w-3xl text-sm text-slate-500">{t('completed.subtitle')}</p></div>
      <div className="rounded-2xl border border-cyan-100 bg-cyan-50 px-5 py-3 text-sm font-semibold text-cyan-800">{t('completed.adminOnly')}</div>
    </div>

    <div className="grid gap-4 md:grid-cols-3">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><p className="text-sm font-semibold text-slate-500">{t('completed.total')}</p><Archive className="h-5 w-5 text-cyan-600"/></div><p className="mt-2 text-3xl font-black text-navy-950">{data.total}</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><p className="text-sm font-semibold text-slate-500">{t('completed.currentPage')}</p><UserRound className="h-5 w-5 text-cyan-600"/></div><p className="mt-2 text-3xl font-black text-navy-950">{data.items.length}</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><p className="text-sm font-semibold text-slate-500">{t('completed.completedShown')}</p><Clock3 className="h-5 w-5 text-cyan-600"/></div><p className="mt-2 text-3xl font-black text-navy-950">{completedOnPage}</p></div>
    </div>

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_220px_220px]">
        <label className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400 rtl:left-auto rtl:right-3"/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('completed.searchPlaceholder')} className={`${input} w-full pl-10 rtl:pl-3 rtl:pr-10`}/></label>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={input}><option value="">{t('completed.allStatuses')}</option>{terminalStatuses.map((item) => <option key={item} value={item}>{enumLabel(item)}</option>)}</select>
        <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} className={input}><option value="">{t('completed.allDepartments')}</option>{departments.map((department) => <option key={department.id} value={department.id}>{enumLabel(department.name)}</option>)}</select>
      </div>
    </section>

    {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div>}

    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="overflow-x-auto">
        <table className="min-w-[1050px] w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 rtl:text-right"><tr><th className="px-5 py-4">{t('common.patient')}</th><th className="px-4 py-4">{t('common.ticket')}</th><th className="px-4 py-4">{t('common.department')}</th><th className="px-4 py-4">{t('completed.doctor')}</th><th className="px-4 py-4">{t('common.priority')}</th><th className="px-4 py-4">{t('common.status')}</th><th className="px-4 py-4">{t('completed.completedAt')}</th><th className="px-4 py-4">{t('completed.duration')}</th><th className="px-4 py-4"></th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? <tr><td colSpan={9} className="px-5 py-12 text-center text-slate-400">{t('common.loading')}</td></tr> : data.items.length === 0 ? <tr><td colSpan={9} className="px-5 py-12 text-center text-slate-400">{t('completed.empty')}</td></tr> : data.items.map((item) => <tr key={item.visit_id} className="hover:bg-slate-50/80"><td className="px-5 py-4"><p className="font-bold text-slate-800">{item.patient_name}</p><p className="mt-0.5 text-xs text-slate-400" dir="ltr">{item.medical_record_number}</p></td><td className="px-4 py-4 font-black text-navy-950" dir="ltr">{item.ticket_code}</td><td className="px-4 py-4">{enumLabel(item.department_name)}</td><td className="px-4 py-4">{item.doctor_name || t('common.none')}</td><td className="px-4 py-4"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold">{enumLabel(item.priority)}</span></td><td className="px-4 py-4"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">{enumLabel(item.status)}</span></td><td className="px-4 py-4 text-xs text-slate-500">{formatDate(item.completed_at)}</td><td className="px-4 py-4">{item.duration_minutes == null ? t('common.none') : `${item.duration_minutes} ${t('common.minutes')}`}</td><td className="px-4 py-4"><button onClick={() => setSelected(item)} className="rounded-lg bg-navy-950 px-3 py-2 text-xs font-bold text-white hover:bg-navy-800">{t('completed.details')}</button></td></tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4"><p className="text-xs text-slate-500">{t('completed.pageOf', { page: data.page, pages: totalPages })}</p><div className="flex gap-2"><button disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft className="h-4 w-4 rtl:rotate-180"/></button><button disabled={page >= totalPages || loading} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronRight className="h-4 w-4 rtl:rotate-180"/></button></div></div>
    </section>

    {selected && <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="mb-5 flex items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-cyan-600">{t('completed.visitDetails')}</p><h3 className="mt-1 text-xl font-black text-navy-950">{selected.patient_name} · {selected.ticket_code}</h3></div><button onClick={() => setSelected(null)} className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-600">{t('completed.closeDetails')}</button></div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Detail label={t('completed.mrn')} value={selected.medical_record_number}/><Detail label={t('completed.identity')} value={selected.identity_number}/><Detail label={t('completed.age')} value={selected.age == null ? t('common.none') : String(selected.age)}/><Detail label={t('completed.phone')} value={selected.phone_number || t('common.none')}/>
        <Detail label={t('completed.arrivedAt')} value={formatDate(selected.arrival_time)}/><Detail label={t('completed.startedAt')} value={formatDate(selected.started_at)}/><Detail label={t('completed.completedAt')} value={formatDate(selected.completed_at)}/><Detail label={t('completed.doctor')} value={selected.doctor_name || t('common.none')}/>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-3"><ClinicalBlock icon={<Stethoscope className="h-4 w-4"/>} title={t('completed.diagnosis')} value={selected.diagnosis}/><ClinicalBlock title={t('completed.clinicalNotes')} value={selected.clinical_notes}/><ClinicalBlock title={t('completed.treatmentPlan')} value={selected.treatment_plan}/></div>
    </section>}
  </div>
}

function Detail({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 break-words font-semibold text-slate-700">{value}</p></div> }
function ClinicalBlock({ title, value, icon }: { title: string; value?: string; icon?: ReactNode }) { return <div className="rounded-xl border border-slate-200 p-4"><div className="flex items-center gap-2 text-sm font-bold text-navy-950">{icon}{title}</div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{value || '—'}</p></div> }
