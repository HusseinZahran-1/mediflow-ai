import type { LucideIcon } from 'lucide-react'

export function StatCard({ label, value, detail, icon: Icon, tone = 'cyan' }: { label: string; value: string | number; detail?: string; icon: LucideIcon; tone?: 'cyan' | 'red' | 'orange' | 'green' }) {
  const colors = { cyan: 'bg-cyan-50 text-cyan-600', red: 'bg-red-50 text-red-600', orange: 'bg-orange-50 text-orange-600', green: 'bg-emerald-50 text-emerald-600' }
  return <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
    <div className="flex items-start justify-between"><div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-2 text-3xl font-bold tracking-tight text-navy-950">{value}</p>{detail && <p className="mt-1 text-xs text-slate-400">{detail}</p>}</div><div className={`rounded-xl p-3 ${colors[tone]}`}><Icon className="h-5 w-5" /></div></div>
  </div>
}

