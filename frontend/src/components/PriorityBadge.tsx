import type { Priority } from '../types'
import { useLanguage } from '../store/LanguageContext'

const styles: Record<Priority, string> = {
  CRITICAL: 'border-red-200 bg-red-50 text-red-700',
  URGENT: 'border-orange-200 bg-orange-50 text-orange-700',
  NORMAL: 'border-emerald-200 bg-emerald-50 text-emerald-700',
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const { enumLabel } = useLanguage()
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold tracking-wide ${styles[priority]}`}>
    <span className={`me-1.5 h-1.5 w-1.5 rounded-full ${priority === 'CRITICAL' ? 'bg-red-500' : priority === 'URGENT' ? 'bg-orange-500' : 'bg-emerald-500'}`} />
    {enumLabel(priority)}
  </span>
}
