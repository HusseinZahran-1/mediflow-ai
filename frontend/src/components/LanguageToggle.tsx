import { Languages } from 'lucide-react'
import { useLanguage } from '../store/LanguageContext'

export function LanguageToggle({ dark = false }: { dark?: boolean }) {
  const { t, toggleLanguage } = useLanguage()
  return <button type="button" onClick={toggleLanguage} aria-label="Change language" className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold transition ${dark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-slate-100 text-navy-950 hover:bg-slate-200'}`}>
    <Languages className="h-4 w-4" />{t('common.language')}
  </button>
}
