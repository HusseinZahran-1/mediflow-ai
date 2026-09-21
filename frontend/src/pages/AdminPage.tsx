import { Building2, DoorOpen, FileClock, Plus, ShieldCheck, UserCog } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../services/api'
import { useLanguage } from '../store/LanguageContext'
import type { Department, Role, User } from '../types'

interface Audit { id: number; action: string; entity_type: string; entity_id?: string; created_at: string; user_id?: number }
interface Room { id: number; department_id: number; room_number: string; room_name?: string; status: string }

const input = 'w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10'
const roles: Role[] = ['ADMIN', 'RECEPTIONIST', 'TRIAGE_NURSE', 'NURSE', 'DOCTOR', 'LAB_TECHNICIAN', 'RADIOLOGY_TECHNICIAN', 'PHARMACIST', 'DISPLAY']
const emptyStaff = { email: '', full_name: '', password: '', role: 'RECEPTIONIST' as Role, department_id: '', specialization: '', medical_license_number: '' }
const emptyRoom = { department_id: '', room_number: '', room_name: '' }

export function AdminPage() {
  const { t, enumLabel, locale } = useLanguage()
  const [users, setUsers] = useState<User[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [rooms, setRooms] = useState<Room[]>([])
  const [audits, setAudits] = useState<Audit[]>([])
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [form, setForm] = useState(emptyStaff)
  const [roomForm, setRoomForm] = useState(emptyRoom)

  const load = () => Promise.all([
    api.get<User[]>('/admin/users'),
    api.get<Department[]>('/departments'),
    api.get<Room[]>('/admin/rooms'),
    api.get<Audit[]>('/admin/audit-logs?limit=8'),
  ]).then(([nextUsers, nextDepartments, nextRooms, nextAudits]) => {
    setUsers(nextUsers)
    setDepartments(nextDepartments)
    setRooms(nextRooms)
    setAudits(nextAudits)
  })

  useEffect(() => { load().catch((error) => setMessage(error.message)) }, [])

  async function createStaff(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setPending(true)
    try {
      const base = { email: form.email, full_name: form.full_name, password: form.password, role: form.role }
      const payload = form.role === 'DOCTOR'
        ? { ...base, department_id: Number(form.department_id), specialization: form.specialization, medical_license_number: form.medical_license_number }
        : base
      await api.post('/admin/users', payload)
      setMessage(t('admin.created'))
      setForm(emptyStaff)
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.failed'))
    } finally {
      setPending(false)
    }
  }

  async function createRoom(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setPending(true)
    try {
      await api.post('/admin/rooms', {
        department_id: Number(roomForm.department_id),
        room_number: roomForm.room_number,
        room_name: roomForm.room_name || null,
        room_type: 'CONSULTATION',
        status: 'AVAILABLE',
      })
      setMessage(t('admin.roomCreated'))
      setRoomForm(emptyRoom)
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.failed'))
    } finally {
      setPending(false)
    }
  }

  return <div className="space-y-6">
    <div><p className="text-sm font-bold uppercase tracking-wider text-cyan-600">{t('admin.eyebrow')}</p><h2 className="mt-1 text-3xl font-black text-navy-950">{t('admin.title')}</h2><p className="mt-2 text-sm text-slate-500">{t('admin.subtitle')}</p></div>
    {message && <p className="rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-800">{message}</p>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><UserCog className="h-5 w-5 text-cyan-600"/><p className="mt-4 text-3xl font-black text-navy-950">{users.length}</p><p className="text-sm text-slate-500">{t('admin.systemUsers')}</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><Building2 className="h-5 w-5 text-cyan-600"/><p className="mt-4 text-3xl font-black text-navy-950">{departments.length}</p><p className="text-sm text-slate-500">{t('admin.departments')}</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><DoorOpen className="h-5 w-5 text-cyan-600"/><p className="mt-4 text-3xl font-black text-navy-950">{rooms.length}</p><p className="text-sm text-slate-500">{t('admin.rooms')}</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><ShieldCheck className="h-5 w-5 text-cyan-600"/><p className="mt-4 text-3xl font-black text-navy-950">9</p><p className="text-sm text-slate-500">{t('admin.protectedRoles')}</p></div>
    </div>
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <div className="space-y-6">
        <form onSubmit={createStaff} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
          <div className="mb-5 flex items-center gap-2"><Plus className="h-5 w-5 text-cyan-600"/><h3 className="font-bold text-navy-950">{t('admin.createStaff')}</h3></div>
          <div className="space-y-4">
            <input required placeholder={t('admin.fullName')} value={form.full_name} onChange={(e) => setForm({...form, full_name: e.target.value})} className={input}/>
            <input required type="email" dir="ltr" placeholder={t('admin.email')} value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className={input}/>
            <input required minLength={8} type="password" dir="ltr" placeholder={t('admin.tempPassword')} value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} className={input}/>
            <select value={form.role} onChange={(e) => setForm({...form, role: e.target.value as Role})} className={input}>{roles.map((role) => <option key={role} value={role}>{enumLabel(role)}</option>)}</select>
            {form.role === 'DOCTOR' && <div className="space-y-4 rounded-xl border border-cyan-100 bg-cyan-50/50 p-4">
              <select required value={form.department_id} onChange={(e) => setForm({...form, department_id: e.target.value})} className={input}><option value="">{t('admin.doctorDepartment')}</option>{departments.filter((department) => department.is_active).map((department) => <option key={department.id} value={department.id}>{enumLabel(department.name)}</option>)}</select>
              <input required placeholder={t('admin.specialization')} value={form.specialization} onChange={(e) => setForm({...form, specialization: e.target.value})} className={input}/>
              <input required dir="ltr" placeholder={t('admin.license')} value={form.medical_license_number} onChange={(e) => setForm({...form, medical_license_number: e.target.value})} className={input}/>
            </div>}
            <button disabled={pending} className="w-full rounded-xl bg-navy-950 py-3 font-bold text-white disabled:opacity-50">{t('admin.createSecure')}</button>
          </div>
        </form>
        <form onSubmit={createRoom} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
          <div className="mb-5 flex items-center gap-2"><DoorOpen className="h-5 w-5 text-cyan-600"/><h3 className="font-bold text-navy-950">{t('admin.createRoom')}</h3></div>
          <div className="space-y-4">
            <select required value={roomForm.department_id} onChange={(e) => setRoomForm({...roomForm, department_id: e.target.value})} className={input}><option value="">{t('common.department')}</option>{departments.filter((department) => department.is_active).map((department) => <option key={department.id} value={department.id}>{enumLabel(department.name)}</option>)}</select>
            <input required dir="ltr" placeholder={t('admin.roomNumber')} value={roomForm.room_number} onChange={(e) => setRoomForm({...roomForm, room_number: e.target.value})} className={input}/>
            <input placeholder={t('admin.roomName')} value={roomForm.room_name} onChange={(e) => setRoomForm({...roomForm, room_name: e.target.value})} className={input}/>
            <button disabled={pending} className="w-full rounded-xl bg-cyan-600 py-3 font-bold text-white disabled:opacity-50">{t('admin.createRoom')}</button>
          </div>
        </form>
      </div>
      <section className="h-fit overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card"><div className="border-b border-slate-100 p-5"><h3 className="font-bold text-navy-950">{t('admin.usersRoles')}</h3></div><div className="divide-y divide-slate-100">{users.map((user) => <div key={user.id} className="flex items-center justify-between px-5 py-4"><div><p className="font-semibold text-slate-800">{user.full_name}</p><p className="text-xs text-slate-400" dir="ltr">{user.email}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{enumLabel(user.role)}</span></div>)}</div></section>
    </div>
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card"><div className="mb-5 flex items-center gap-2"><FileClock className="h-5 w-5 text-cyan-600"/><h3 className="font-bold text-navy-950">{t('admin.audit')}</h3></div><div className="grid gap-2">{audits.map((audit) => <div key={audit.id} className="grid grid-cols-[1fr_auto] items-center rounded-xl bg-slate-50 px-4 py-3"><div><p className="text-sm font-semibold text-slate-700">{enumLabel(audit.action)}</p><p className="text-xs text-slate-400">{enumLabel(audit.entity_type)} {audit.entity_id ? `#${audit.entity_id}` : ''}</p></div><time className="text-xs text-slate-400">{new Date(audit.created_at).toLocaleString(locale)}</time></div>)}</div></section>
  </div>
}
