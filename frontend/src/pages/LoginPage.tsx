import { Activity, ArrowRight, ClipboardPlus, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Disclaimer } from '../components/Disclaimer'
import { LanguageToggle } from '../components/LanguageToggle'
import { useAuth } from '../store/AuthContext'
import { useLanguage } from '../store/LanguageContext'

export function LoginPage() {
  const { login, user } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()
  const [email, setEmail] = useState('admin@mediflow.example.com')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  if (user) return <Navigate to="/" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('login.failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return <div className="flex min-h-screen flex-col bg-navy-950">
    <div className="absolute end-5 top-5 z-20"><LanguageToggle dark /></div>
    <div className="grid flex-1 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden overflow-hidden p-14 text-white lg:flex lg:flex-col lg:justify-between"><div className="absolute -left-36 -top-36 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl"/><div className="absolute -bottom-40 right-0 h-[32rem] w-[32rem] rounded-full bg-blue-500/10 blur-3xl"/><div className="relative flex items-center gap-3"><div className="rounded-xl bg-cyan-400 p-2.5 text-navy-950"><ClipboardPlus className="h-7 w-7"/></div><div><p className="text-2xl font-black">MediFlow <span className="text-cyan-300">AI</span></p><p className="text-[10px] uppercase tracking-[0.24em] text-slate-400">{t('login.tagline')}</p></div></div><div className="relative max-w-2xl"><div className="mb-6 flex w-fit items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-xs font-semibold text-cyan-200"><Activity className="h-4 w-4"/>{t('login.live')}</div><h1 className="text-5xl font-black leading-[1.08] tracking-tight">{t('login.headline1')}<br/><span className="text-cyan-300">{t('login.headline2')}</span><br/>{t('login.headline3')}</h1><p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">{t('login.description')}</p><div className="mt-10 grid grid-cols-3 gap-4"><div className="rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-2xl font-black text-cyan-300">{t('login.realtime')}</p><p className="mt-1 text-xs text-slate-400">{t('login.queueUpdates')}</p></div><div className="rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-2xl font-black text-cyan-300">RBAC</p><p className="mt-1 text-xs text-slate-400">{t('login.secureAccess')}</p></div><div className="rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-2xl font-black text-cyan-300">AI + Human</p><p className="mt-1 text-xs text-slate-400">{t('login.reviewedDecisions')}</p></div></div></div><p className="relative text-xs text-slate-500">MediFlow AI v1.1 • Hussein Ali Zahran</p></section>
      <section className="flex items-center justify-center bg-[#f4f7f9] p-6 sm:p-12"><div className="w-full max-w-md"><div className="mb-8 lg:hidden"><p className="text-2xl font-black text-navy-950">MediFlow <span className="text-cyan-600">AI</span></p></div><div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-card sm:p-10"><div className="mb-8"><div className="mb-5 inline-flex rounded-2xl bg-cyan-50 p-3 text-cyan-600"><LockKeyhole className="h-6 w-6"/></div><h2 className="text-3xl font-black tracking-tight text-navy-950">{t('login.welcome')}</h2><p className="mt-2 text-sm text-slate-500">{t('login.prompt')}</p></div><form onSubmit={submit} className="space-y-5"><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{t('login.email')}</span><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" dir="ltr" required className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10"/></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{t('login.password')}</span><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" dir="ltr" required className="w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10"/></label>{error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}<button disabled={submitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy-950 px-4 py-3.5 font-bold text-white transition hover:bg-navy-800 disabled:opacity-50">{submitting ? t('login.signingIn') : t('login.signIn')}<ArrowRight className="h-4 w-4 rtl:rotate-180"/></button></form><div className="mt-7 flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700"><ShieldCheck className="h-4 w-4"/>{t('login.protected')}</div></div></div></section>
    </div><Disclaimer />
  </div>
}
