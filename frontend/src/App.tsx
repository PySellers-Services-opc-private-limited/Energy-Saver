import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ForecastPage from './pages/ForecastPage'
import AnomaliesPage from './pages/AnomaliesPage'
import HVACPage from './pages/HVACPage'
import SavingsPage from './pages/SavingsPage'
import ModelsPage from './pages/ModelsPage'
import PipelinePage from './pages/PipelinePage'
import TenantsPage from './pages/TenantsPage'
import TenantDetailPage from './pages/TenantDetailPage'
import AddTenant from './pages/AddTenant'
import ForecastVsActualPage from './pages/ForecastVsActualPage'
import BillPage from './pages/BillPage'
import SolarPage from './pages/SolarPage'
import EVPage from './pages/EVPage'
import AppliancePage from './pages/AppliancePage'
import MyUnitPage from './pages/MyUnitPage'
import SettingsPage from './pages/SettingsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import { AuthProvider, useAuth } from './context/AuthContext'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="forecast" element={<ForecastPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="hvac" element={<HVACPage />} />
        <Route path="savings" element={<SavingsPage />} />
        <Route path="models" element={<AdminRoute><ModelsPage /></AdminRoute>} />
        <Route path="pipeline" element={<AdminRoute><PipelinePage /></AdminRoute>} />
        <Route path="tenants" element={<AdminRoute><TenantsPage /></AdminRoute>} />
        <Route path="tenants/:id" element={<AdminRoute><TenantDetailPage /></AdminRoute>} />
        <Route path="forecast-vs-actual" element={<ForecastVsActualPage />} />
        <Route path="my-unit" element={<MyUnitPage />} />
        <Route path="bill" element={<BillPage />} />
        <Route path="solar" element={<SolarPage />} />
        <Route path="ev" element={<EVPage />} />
        <Route path="appliance" element={<AppliancePage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="add-tenant" element={<AdminRoute><AddTenant /></AdminRoute>} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
