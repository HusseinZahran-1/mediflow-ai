import { Ban, CheckCircle2, FlaskConical, Play, ScanLine, TestTube2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'

interface Order { id: number; visit_id: number; ticket_code?: string | null; status: string; priority: string; test_name?: string; scan_type?: string; body_area?: string; requested_at: string; result?: string; report?: string }

export function OrdersPage({ type }: { type: 'lab' | 'radiology' }) {
  const { t, enumLabel } = useLanguage()
  const [orders, setOrders] = useState<Order[]>([])
  const [message, setMessage] = useState('')
  const [pendingId, setPendingId] = useState<number | null>(null)
  const isLab = type === 'lab'
  const path = isLab ? '/lab-orders' : '/radiology-orders'
  const load = () => api.get<Order[]>(path + '?worklist=true').then(setOrders)

  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : t('orders.failed')))
    const timer = window.setInterval(() => load().catch(() => undefined), 5000)
    return () => window.clearInterval(timer)
  }, [path])

  async function updateStatus(order: Order, status: 'RECEIVED' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED') {
    if (pendingId !== null) return
    const payload: Record<string, string> = { status }
    if (status === 'COMPLETED') {
      const result = window.prompt(isLab ? t('orders.enterLab') : t('orders.enterRadiology'))?.trim()
      if (!result) return
      payload[isLab ? 'result' : 'report'] = result
    }
    setPendingId(order.id)
    try {
      await api.patch(path + '/' + order.id, payload)
      setMessage(status === 'COMPLETED'
        ? t('orders.completed', { id: order.id })
        : status === 'CANCELLED'
          ? t('orders.cancelled', { id: order.id })
          : t('orders.statusUpdated', { id: order.id }))
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('orders.failed'))
    } finally {
      setPendingId(null)
    }
  }

  const Icon = isLab ? FlaskConical : ScanLine
  const service = t(isLab ? 'orders.lab' : 'orders.radiology')

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('orders.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('orders.worklist', {service})}</h2><p className="mt-2 text-sm text-slate-500">{t('orders.subtitle')}</p></div>
    {message && <p className="rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-800">{message}</p>}
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card"><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-4">{t('common.order')}</th><th className="px-5 py-4">{t('common.visit')}</th><th className="px-5 py-4">{t('orders.testScan')}</th><th className="px-5 py-4">{t('common.priority')}</th><th className="px-5 py-4">{t('common.status')}</th><th className="px-5 py-4">{t('common.action')}</th></tr></thead>
      <tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={order.id}><td className="px-5 py-4"><span className="flex items-center gap-2 font-bold text-navy-950"><Icon className="h-4 w-4 text-cyan-600"/>#{order.id}</span></td><td className="px-5 py-4"><span className="font-bold text-navy-950" dir="ltr">{order.ticket_code || '#' + order.visit_id}</span><p className="mt-0.5 text-[11px] text-slate-400">#{order.visit_id}</p></td><td className="px-5 py-4 font-semibold">{order.test_name || order.scan_type + ' • ' + order.body_area}</td><td className="px-5 py-4">{enumLabel(order.priority)}</td><td className="px-5 py-4">{enumLabel(order.status)}</td><td className="px-5 py-4"><div className="flex flex-wrap gap-2">
        {order.status === 'REQUESTED' && <button type="button" disabled={pendingId !== null} onClick={() => updateStatus(order, 'RECEIVED')} className="flex items-center gap-1.5 rounded-lg bg-cyan-50 px-3 py-2 text-xs font-bold text-cyan-700 disabled:opacity-40"><TestTube2 className="h-3.5 w-3.5"/>{t('orders.receive')}</button>}
        {['REQUESTED', 'RECEIVED'].includes(order.status) && <button type="button" disabled={pendingId !== null} onClick={() => updateStatus(order, 'PROCESSING')} className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700 disabled:opacity-40"><Play className="h-3.5 w-3.5"/>{t('orders.process')}</button>}
        <button type="button" disabled={pendingId !== null} onClick={() => updateStatus(order, 'COMPLETED')} className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 disabled:opacity-40"><CheckCircle2 className="h-3.5 w-3.5"/>{t('common.complete')}</button>
        {!['COMPLETED', 'CANCELLED'].includes(order.status) && <button type="button" disabled={pendingId !== null} onClick={() => updateStatus(order, 'CANCELLED')} className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-xs font-bold text-red-700 disabled:opacity-40"><Ban className="h-3.5 w-3.5"/>{t('orders.cancel')}</button>}
      </div></td></tr>)}</tbody></table></div>{orders.length === 0 && <p className="py-16 text-center text-sm text-slate-400">{t('orders.empty')}</p>}</div>
  </div>
}
