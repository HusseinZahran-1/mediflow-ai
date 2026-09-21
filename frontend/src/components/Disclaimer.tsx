import { ShieldAlert } from 'lucide-react'
import { useLanguage } from '../store/LanguageContext'

export function Disclaimer() {
  const { t } = useLanguage()
  return <div className="flex items-center justify-center gap-2 border-t border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-500">
    <ShieldAlert className="h-3.5 w-3.5 text-amber-500" /> {t('disclaimer')}
  </div>
}
