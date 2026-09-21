import { Activity, CheckCircle2, Clock3, TimerReset, UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { QueueTable } from '../components/QueueTable'
import { StatCard } from '../components/StatCard'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { Metrics, QueueItem } from '../types'

const emptyMetrics: Metrics = { patients_today: 0, waiting: 0, critical: 0, urgent: 0, normal: 0, completed: 0, average_wait_minutes: 0, longest_wait_minutes: 0, by_department: [] }

export function DashboardPage() {
  const { t, locale } = useLanguage()
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    const load = () => Promise.all([api.get<Metrics>('/admin/metrics'), api.get<QueueItem[]>('/queue')]).then(([nextMetrics, nextQueue]) => { setMetrics(nextMetrics); setQueue(nextQueue); setError('') }).catch((err) => setError(err.message))
    load(); const timer = window.setInterval(load, 5000); return () => window.clearInterval(timer)
  }, [])
  return <div className="space-y-7"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('dashboard.eyebrow')}</p><h2 className="mt-1 text-3xl font-black tracking-tight text-navy-950">{t('dashboard.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('dashboard.subtitle')}</p></div><span className="w-fit rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-sm">{t('common.today')} • {new Date().toLocaleDateString(locale)}</span></div>{error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label={t('dashboard.patientsToday')} value={metrics.patients_today} detail={t('dashboard.completedCount', {count: metrics.completed})} icon={UsersRound}/><StatCard label={t('dashboard.waitingNow')} value={metrics.waiting} detail={t('dashboard.criticalCount', {count: metrics.critical})} icon={Activity} tone="red"/><StatCard label={t('dashboard.averageWait')} value={`${metrics.average_wait_minutes} ${t('common.minutes')}`} detail={t('dashboard.longest', {count: metrics.longest_wait_minutes})} icon={Clock3} tone="orange"/><StatCard label={t('dashboard.completed')} value={metrics.completed} detail={t('dashboard.todayVisits')} icon={CheckCircle2} tone="green"/></div><div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]"><section><div className="mb-4 flex items-center justify-between"><div><h3 className="text-lg font-bold text-navy-950">{t('dashboard.priorityQueue')}</h3><p className="text-sm text-slate-500">{t('dashboard.priorityHelp')}</p></div><TimerReset className="h-5 w-5 text-cyan-600"/></div><QueueTable items={queue.slice(0, 8)}/></section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><h3 className="text-lg font-bold text-navy-950">{t('dashboard.byDepartment')}</h3><p className="mb-5 text-sm text-slate-500">{t('dashboard.volume')}</p><div className="h-80"><ResponsiveContainer width="100%" height="100%"><BarChart data={metrics.by_department} layout="vertical" margin={{ left: 12, right: 12 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0"/><XAxis type="number" hide/><YAxis dataKey="department" type="category" width={110} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false}/><Tooltip cursor={{ fill: '#ecfeff' }}/><Bar dataKey="patients" fill="#06b6d4" radius={[0, 8, 8, 0]}/></BarChart></ResponsiveContainer></div></section></div></div>
}
