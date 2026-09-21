import { Activity, Archive, ClipboardPlus, FlaskConical, Gauge, LogOut, Menu, Monitor, Pill, ScanLine, Settings, Stethoscope, UsersRound, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Disclaimer } from '../components/Disclaimer'
import { LanguageToggle } from '../components/LanguageToggle'
import { useAuth } from '../store/AuthContext'
import { useLanguage } from '../store/LanguageContext'
import type { Role } from '../types'

const links: Array<{ to: string; labelKey: string; icon: typeof Gauge; roles: Role[] }> = [
  { to: '/', labelKey: 'nav.overview', icon: Gauge, roles: ['ADMIN', 'RECEPTIONIST', 'TRIAGE_NURSE', 'NURSE', 'DOCTOR'] },
  { to: '/reception', labelKey: 'nav.reception', icon: UsersRound, roles: ['ADMIN', 'RECEPTIONIST'] },
  { to: '/triage', labelKey: 'nav.triage', icon: Activity, roles: ['ADMIN', 'TRIAGE_NURSE'] },
  { to: '/doctor', labelKey: 'nav.doctor', icon: Stethoscope, roles: ['ADMIN', 'DOCTOR'] },
  { to: '/lab', labelKey: 'nav.lab', icon: FlaskConical, roles: ['ADMIN', 'LAB_TECHNICIAN'] },
  { to: '/radiology', labelKey: 'nav.radiology', icon: ScanLine, roles: ['ADMIN', 'RADIOLOGY_TECHNICIAN'] },
  { to: '/pharmacy', labelKey: 'nav.pharmacy', icon: Pill, roles: ['ADMIN', 'PHARMACIST'] },
  { to: '/display', labelKey: 'nav.display', icon: Monitor, roles: ['ADMIN', 'DISPLAY'] },
  { to: '/completed-patients', labelKey: 'nav.completedPatients', icon: Archive, roles: ['ADMIN'] },
  { to: '/admin', labelKey: 'nav.admin', icon: Settings, roles: ['ADMIN'] },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const { language, t, enumLabel } = useLanguage()
  const [mobileOpen, setMobileOpen] = useState(false)
  const visibleLinks = links.filter((link) => user && link.roles.includes(user.role))
  const sidebarPosition = language === 'ar' ? 'right-0' : 'left-0'
  const contentPadding = language === 'ar' ? 'lg:pr-64' : 'lg:pl-64'

  const navigation = (mobile = false) => visibleLinks.map(({ to, labelKey, icon: Icon }) => <NavLink
    key={to}
    to={to}
    end={to === '/'}
    onClick={mobile ? () => setMobileOpen(false) : undefined}
    className={({ isActive }) => `flex items-center gap-3 rounded-xl px-4 py-3 font-semibold transition ${isActive ? 'bg-cyan-400 text-navy-950' : mobile ? 'bg-white/5 text-slate-200' : 'text-slate-300 hover:bg-white/10 hover:text-white'} ${mobile ? '' : 'text-sm'}`}
  ><Icon className="h-5 w-5" />{t(labelKey)}</NavLink>)

  return <div className="min-h-screen bg-[#f4f7f9] text-slate-800">
    <aside className={`fixed inset-y-0 ${sidebarPosition} z-30 hidden w-64 flex-col bg-navy-950 text-white lg:flex`}>
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-6"><div className="rounded-xl bg-cyan-400 p-2 text-navy-950"><ClipboardPlus className="h-6 w-6" /></div><div><p className="text-xl font-black tracking-tight">MediFlow <span className="text-cyan-300">AI</span></p><p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">{t('layout.subtitle')}</p></div></div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-6">{navigation()}</nav>
      <div className="border-t border-white/10 p-4"><div className="mb-3 rounded-xl bg-white/5 p-3"><p className="truncate text-sm font-semibold">{user?.full_name}</p><p className="mt-0.5 text-xs text-cyan-300">{enumLabel(user?.role)}</p></div><button onClick={logout} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-300 transition hover:bg-red-500/15 hover:text-red-300"><LogOut className="h-4 w-4" />{t('layout.signOut')}</button></div>
    </aside>
    {mobileOpen && <div className="fixed inset-0 z-50 bg-navy-950 p-5 text-white lg:hidden"><div className="flex items-center justify-between"><p className="text-xl font-black">MediFlow <span className="text-cyan-300">AI</span></p><button onClick={() => setMobileOpen(false)} className="rounded-xl bg-white/10 p-2"><X className="h-6 w-6" /></button></div><nav className="mt-8 space-y-2">{navigation(true)}</nav><button onClick={logout} className="mt-8 flex items-center gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-red-300"><LogOut className="h-4 w-4" />{t('layout.signOut')}</button></div>}
    <div className={`flex min-h-screen flex-col ${contentPadding}`}>
      <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur lg:px-8"><div className="flex items-center gap-3"><button onClick={() => setMobileOpen(true)} className="rounded-xl bg-slate-100 p-2 text-navy-950 lg:hidden"><Menu className="h-5 w-5" /></button><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-600">{t('layout.commandCenter')}</p><h1 className="mt-1 text-lg font-bold text-navy-950">{t('layout.greeting', { name: user?.full_name.split(' ')[0] || '' })}</h1></div></div><div className="flex items-center gap-3"><LanguageToggle /><span className="hidden rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700 sm:inline">● {t('common.systemOperational')}</span><div className="flex h-10 w-10 items-center justify-center rounded-full bg-navy-900 text-sm font-bold text-white">{user?.full_name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div></div></header>
      <main className="flex-1 p-5 lg:p-8"><Outlet /></main><Disclaimer />
    </div>
  </div>
}
