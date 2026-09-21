import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { useAuth } from './store/AuthContext'
import { useLanguage } from './store/LanguageContext'
import type { Role } from './types'

const AdminPage = lazy(() => import('./pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const CompletedPatientsPage = lazy(() => import('./pages/CompletedPatientsPage').then((module) => ({ default: module.CompletedPatientsPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })))
const DisplayPage = lazy(() => import('./pages/DisplayPage').then((module) => ({ default: module.DisplayPage })))
const DoctorPage = lazy(() => import('./pages/DoctorPage').then((module) => ({ default: module.DoctorPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })))
const OrdersPage = lazy(() => import('./pages/OrdersPage').then((module) => ({ default: module.OrdersPage })))
const PharmacyPage = lazy(() => import('./pages/PharmacyPage').then((module) => ({ default: module.PharmacyPage })))
const ReceptionPage = lazy(() => import('./pages/ReceptionPage').then((module) => ({ default: module.ReceptionPage })))
const TriagePage = lazy(() => import('./pages/TriagePage').then((module) => ({ default: module.TriagePage })))

function Protected({ roles }: { roles?: Role[] }) {
  const { user, loading } = useAuth()
  const { t } = useLanguage()
  if (loading) return <div className="flex min-h-screen items-center justify-center bg-navy-950 text-cyan-300">{t('common.loading')}</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <AppLayout />
}

function HomePage() {
  const { user } = useAuth()
  if (user?.role === 'DISPLAY') return <Navigate to="/display" replace />
  if (user?.role === 'LAB_TECHNICIAN') return <Navigate to="/lab" replace />
  if (user?.role === 'RADIOLOGY_TECHNICIAN') return <Navigate to="/radiology" replace />
  if (user?.role === 'PHARMACIST') return <Navigate to="/pharmacy" replace />
  return <DashboardPage />
}

export default function App() {
  const { t } = useLanguage()
  return <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-navy-950 text-cyan-300">{t('common.loading')}</div>}><Routes>
    <Route path="/login" element={<LoginPage/>}/>
    <Route element={<Protected/>}>
      <Route index element={<HomePage/>}/>
    </Route>
    <Route element={<Protected roles={['ADMIN','RECEPTIONIST']}/>}><Route path="/reception" element={<ReceptionPage/>}/></Route>
    <Route element={<Protected roles={['ADMIN','TRIAGE_NURSE']}/>}><Route path="/triage" element={<TriagePage/>}/></Route>
    <Route element={<Protected roles={['ADMIN','DOCTOR']}/>}><Route path="/doctor" element={<DoctorPage/>}/></Route>
    <Route element={<Protected roles={['ADMIN','LAB_TECHNICIAN']}/>}><Route path="/lab" element={<OrdersPage type="lab"/>}/></Route>
    <Route element={<Protected roles={['ADMIN','RADIOLOGY_TECHNICIAN']}/>}><Route path="/radiology" element={<OrdersPage type="radiology"/>}/></Route>
    <Route element={<Protected roles={['ADMIN','PHARMACIST']}/>}><Route path="/pharmacy" element={<PharmacyPage/>}/></Route>
    <Route element={<Protected roles={['ADMIN','DISPLAY']}/>}><Route path="/display" element={<DisplayPage/>}/></Route>
    <Route element={<Protected roles={['ADMIN']}/>}><Route path="/completed-patients" element={<CompletedPatientsPage/>}/></Route>
    <Route element={<Protected roles={['ADMIN']}/>}><Route path="/admin" element={<AdminPage/>}/></Route>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes></Suspense>
}
