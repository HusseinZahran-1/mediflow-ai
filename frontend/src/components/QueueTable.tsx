import { Clock3, DoorOpen } from 'lucide-react'
import type { QueueItem } from '../types'
import { PriorityBadge } from './PriorityBadge'
import { useLanguage } from '../store/LanguageContext'

export function QueueTable({ items, onSelect }: { items: QueueItem[]; onSelect?: (item: QueueItem) => void }) {
  const { t, enumLabel } = useLanguage()
  return <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="border-b border-slate-200 bg-slate-50/80 text-xs uppercase tracking-wider text-slate-500"><tr>
        <th className="px-5 py-4">{t('common.ticket')}</th><th className="px-5 py-4">{t('queue.patient')}</th><th className="px-5 py-4">{t('common.priority')}</th><th className="px-5 py-4">{t('common.status')}</th><th className="px-5 py-4">{t('queue.wait')}</th><th className="px-5 py-4">{t('common.room')}</th>
      </tr></thead>
      <tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.visit_id} onClick={() => onSelect?.(item)} className="cursor-pointer transition hover:bg-cyan-50/40">
        <td className="px-5 py-4 text-lg font-black text-navy-900">{item.ticket_code}</td><td className="px-5 py-4"><p className="font-semibold text-slate-800">{item.patient_name}</p><p className="text-xs text-slate-400">{item.department}</p></td><td className="px-5 py-4"><PriorityBadge priority={item.priority} /></td><td className="px-5 py-4 font-medium text-slate-600">{enumLabel(item.status)}</td><td className="px-5 py-4"><span className="flex items-center gap-1.5 text-slate-600"><Clock3 className="h-4 w-4" />{item.wait_minutes} {t('common.minutes')}</span></td><td className="px-5 py-4"><span className="flex items-center gap-1.5 text-slate-600"><DoorOpen className="h-4 w-4" />{item.room || t('common.none')}</span></td>
      </tr>)}</tbody>
    </table></div>{items.length === 0 && <div className="px-6 py-14 text-center text-sm text-slate-400">{t('queue.empty')}</div>}
  </div>
}
