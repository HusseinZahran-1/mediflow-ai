import { BellRing, Maximize, UsersRound, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { Priority } from '../types'

interface DisplayItem { ticket_code: string; department: string; priority?: Priority | null; status: string; room?: string | null }
interface CallEvent { event: string; ticket: string; room: string; priority: Priority }

const priorityColors: Record<Priority, string> = {
  CRITICAL: 'border-red-400 bg-red-500',
  URGENT: 'border-orange-400 bg-orange-500',
  NORMAL: 'border-emerald-400 bg-emerald-500',
}

function spokenIdentifier(value: string) {
  return value.replace(/[-_/\s]/g, '').split('').join(' ')
}

export function DisplayPage() {
  const { language, t, enumLabel } = useLanguage()
  const [items, setItems] = useState<DisplayItem[]>([])
  const [lastCall, setLastCall] = useState<CallEvent | null>(null)
  // Browsers can block programmatic speech before the user interacts with the page.
  // Keep announcements disabled until the waiting-display operator explicitly enables them.
  const [audio, setAudio] = useState(false)
  const audioRef = useRef(false)
  const languageRef = useRef(language)
  const lastSpokenRef = useRef<{ key: string; at: number } | null>(null)

  useEffect(() => { audioRef.current = audio }, [audio])
  useEffect(() => { languageRef.current = language }, [language])

  const enableAudio = () => {
    if (!('speechSynthesis' in window)) return
    // Prime the browser's speech engine inside a real user gesture without making a sound.
    window.speechSynthesis.cancel()
    const unlock = new SpeechSynthesisUtterance(' ')
    unlock.volume = 0
    window.speechSynthesis.speak(unlock)
    audioRef.current = true
    setAudio(true)
  }

  const disableAudio = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    audioRef.current = false
    setAudio(false)
  }

  const announceCall = (call: CallEvent) => {
    if (!audioRef.current || !('speechSynthesis' in window)) return

    const now = Date.now()
    const key = `${call.event}:${call.ticket}:${call.room}`
    if (lastSpokenRef.current?.key === key && now - lastSpokenRef.current.at < 3000) return
    lastSpokenRef.current = { key, at: now }

    const activeLanguage = languageRef.current
    const ticket = spokenIdentifier(call.ticket)
    const room = spokenIdentifier(call.room)
    const message = activeLanguage === 'ar'
      ? `المريض رقم ${ticket}، يرجى التوجه إلى الغرفة ${room}`
      : `Patient ${ticket}, please proceed to room ${room}`

    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(message)
    utterance.lang = activeLanguage === 'ar' ? 'ar-JO' : 'en-GB'
    utterance.rate = 0.9
    utterance.volume = 1

    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find((voice) => activeLanguage === 'ar'
      ? voice.lang.toLowerCase().startsWith('ar')
      : voice.lang.toLowerCase().startsWith('en'))
    if (preferred) utterance.voice = preferred

    window.speechSynthesis.speak(utterance)
  }

  useEffect(() => {
    let active = true
    let ws: WebSocket | null = null
    let reconnectTimer: number | null = null
    let pingTimer: number | null = null

    const load = () => api.get<DisplayItem[]>('/display/queue').then((data) => {
      if (!active) return
      setItems(data)
      setLastCall((current) => current && data.some((item) => item.ticket_code === current.ticket && item.status === 'CALLED') ? current : null)
    }).catch(() => undefined)

    load()
    const timer = window.setInterval(load, 5000)

    const connect = () => {
      const url = new URL(api.websocketUrl('ws/display'))
      url.searchParams.set('token', api.getToken() || '')
      ws = new WebSocket(url)
      ws.onopen = () => {
        if (pingTimer !== null) window.clearInterval(pingTimer)
        pingTimer = window.setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('ping'), 20000)
      }
      ws.onmessage = (event) => {
        try {
          const call = JSON.parse(event.data) as CallEvent
          // Announcements are event-driven: only a doctor Call or Recall can trigger speech.
          if (!['PATIENT_CALLED', 'PATIENT_RECALLED'].includes(call.event)) return
          setLastCall(call)
          void load()
          announceCall(call)
        } catch {
          // Ignore malformed realtime events and keep the display polling.
        }
      }
      ws.onclose = () => {
        if (pingTimer !== null) window.clearInterval(pingTimer)
        if (active) reconnectTimer = window.setTimeout(connect, 2000)
      }
    }

    connect()
    return () => {
      active = false
      window.clearInterval(timer)
      if (pingTimer !== null) window.clearInterval(pingTimer)
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      ws?.close()
      if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    }
  }, [])

  return <div className="-m-5 min-h-[calc(100vh-8rem)] overflow-hidden rounded-2xl bg-navy-950 p-6 text-white lg:-m-8 lg:p-10">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-sm font-bold uppercase tracking-[0.25em] text-cyan-300">MediFlow Academic Hospital</p><h2 className="mt-2 text-4xl font-black">{t('display.nowCalling')}</h2></div>
      <div className="flex items-center gap-2">
        <button type="button" aria-label={audio ? 'Disable voice announcements' : 'Enable voice announcements'} onClick={audio ? disableAudio : enableAudio} className={`flex items-center gap-2 rounded-xl px-4 py-3 font-bold ${audio ? 'bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-400/40' : 'bg-amber-500/20 text-amber-200 ring-1 ring-amber-400/40'}`}>
          {audio ? <Volume2 className="h-5 w-5"/> : <VolumeX className="h-5 w-5"/>}
          <span className="hidden sm:inline">{audio ? t('display.voiceOn') : t('display.enableVoice')}</span>
        </button>
        <button type="button" aria-label="Fullscreen" onClick={() => document.documentElement.requestFullscreen()} className="rounded-xl bg-white/10 p-3"><Maximize/></button>
      </div>
    </div>

    {!audio && <div className="mt-6 rounded-2xl border border-amber-400/30 bg-amber-400/10 px-5 py-4 text-center text-sm font-semibold text-amber-100">
      {t('display.voiceHelp')}
    </div>}

    {lastCall && <div className={`mx-auto mt-10 max-w-4xl animate-pulse rounded-3xl border-4 p-8 text-center ${priorityColors[lastCall.priority]}`}><BellRing className="mx-auto h-10 w-10"/><p className="mt-4 text-7xl font-black tracking-tight sm:text-8xl" dir="ltr">{lastCall.ticket}</p><p className="mt-3 text-2xl font-bold sm:text-3xl">{t('display.proceed', { room: lastCall.room })}</p></div>}
    <div className="mt-10 flex items-center justify-between"><div className="flex items-center gap-3"><UsersRound className="h-6 w-6 text-cyan-300"/><h3 className="text-2xl font-black">{t('display.waiting')}</h3></div><span className="rounded-full bg-white/10 px-3 py-1 text-sm font-bold">{items.length}</span></div>
    <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{items.map((item) => <article key={item.ticket_code} className={`rounded-2xl border p-6 ${item.status === 'CALLED' ? 'border-cyan-300 bg-cyan-400/15' : 'border-white/10 bg-white/5'}`}><div className="flex items-center justify-between gap-3"><span className="text-4xl font-black" dir="ltr">{item.ticket_code}</span><span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold">{item.priority ? enumLabel(item.priority) : t('display.pendingTriage')}</span></div><div className="mt-5 grid grid-cols-2 gap-4 border-t border-white/10 pt-4"><div><p className="text-xs uppercase tracking-wider text-slate-400">{t('common.department')}</p><p className="mt-1 font-semibold">{enumLabel(item.department)}</p></div><div><p className="text-xs uppercase tracking-wider text-slate-400">{t('common.status')}</p><p className="mt-1 font-semibold text-cyan-300">{enumLabel(item.status)}</p></div>{item.room && <div className="col-span-2"><p className="text-xs uppercase tracking-wider text-slate-400">{t('common.room')}</p><p className="mt-1 text-2xl font-black text-cyan-300" dir="ltr">{item.room}</p></div>}</div></article>)}</div>
    {items.length === 0 && <p className="mt-5 rounded-2xl border border-dashed border-white/15 py-16 text-center text-slate-400">{t('display.noPatients')}</p>}
    <p className="mt-10 text-center text-xs text-slate-500">{t('display.waitingPrivacy')}</p>
  </div>
}
