import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  TrendingUp,
  AlertTriangle,
  Thermometer,
  PiggyBank,
  Cpu,
  Radio,
  Zap,
  LogOut,
  User,
  Users,
  ChevronDown,
  BarChart3,
  Receipt,
  Sun,
  Home,
  Settings,
} from 'lucide-react'
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { apartmentApi } from '../api/client'
import type { Tenant } from '../api/types'

const navItems = [
  { to: '/',          label: 'Dashboard',  icon: LayoutDashboard, roles: ['admin', 'tenant'] },
  { to: '/forecast',  label: 'Forecast',   icon: TrendingUp,      roles: ['admin', 'tenant'] },
  { to: '/anomalies', label: 'Anomalies',  icon: AlertTriangle,   roles: ['admin', 'tenant'] },
  { to: '/hvac',      label: 'HVAC',       icon: Thermometer,     roles: ['admin', 'tenant'] },
  { to: '/savings',   label: 'Savings',    icon: PiggyBank,       roles: ['admin', 'tenant'] },
  { to: '/bill',      label: 'Bill Predict',icon: Receipt,         roles: ['admin', 'tenant'] },
  { to: '/solar',     label: 'Solar',      icon: Sun,             roles: ['admin', 'tenant'] },
  { to: '/models',    label: 'Models',     icon: Cpu,             roles: ['admin'] },
  { to: '/pipeline',  label: 'Pipeline',   icon: Radio,           roles: ['admin'] },
  { to: '/forecast-vs-actual', label: 'F vs A', icon: BarChart3,  roles: ['admin', 'tenant'] },
  { to: '/my-unit',   label: 'My Unit',    icon: Home,            roles: ['tenant'] },
  { to: '/tenants',   label: 'Tenants',    icon: Users,           roles: ['admin'] },
  { to: '/settings',  label: 'Settings',   icon: Settings,        roles: ['admin', 'tenant'] },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [selectedTenant, setSelectedTenant] = useState<string>('')
  const [showDropdown, setShowDropdown] = useState(false)

  useEffect(() => {
    apartmentApi.tenants.list()
      .then((list) => {
        setTenants(list)
        if (list.length > 0 && !selectedTenant) {
          setSelectedTenant(list[0].unit_key)
        }
      })
      .catch(() => {})
  }, [])

  const currentTenant = tenants.find(t => t.unit_key === selectedTenant)

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-sky-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-sky-200 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-sky-200">
          <Zap className="text-blue-500" size={22} />
          <span className="font-bold text-sm leading-tight">
            Energy<br />Saver AI
          </span>
        </div>

        {/* Tenant Selector — admin only */}
        {user?.role === 'admin' && tenants.length > 0 && (
          <div className="px-3 pt-3 pb-1">
            <div className="relative">
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-blue-50 border border-blue-200 text-sm text-gray-800 hover:bg-blue-100 transition"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 h-5 rounded bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                    {currentTenant?.name?.charAt(0) ?? 'T'}
                  </div>
                  <span className="truncate text-xs font-semibold">{currentTenant?.name ?? 'Select Tenant'}</span>
                </div>
                <ChevronDown size={12} className={`text-gray-400 transition ${showDropdown ? 'rotate-180' : ''}`} />
              </button>
              {showDropdown && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-sky-200 rounded-xl shadow-lg z-50 max-h-48 overflow-y-auto">
                  {tenants.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        setSelectedTenant(t.unit_key)
                        setShowDropdown(false)
                      }}
                      className={clsx(
                        'w-full text-left px-3 py-2 text-xs hover:bg-sky-50 transition flex items-center gap-2',
                        selectedTenant === t.unit_key && 'bg-blue-50 font-semibold text-blue-700'
                      )}
                    >
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${t.is_active ? 'bg-emerald-400' : 'bg-gray-400'}`} />
                      <span className="truncate">{t.name}</span>
                      <span className="ml-auto text-gray-400 font-mono">{t.unit_key}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems
            .filter(({ roles }) => roles.includes(user?.role ?? 'tenant'))
            .map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-sky-100'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User + Logout */}
        <div className="px-3 py-3 border-t border-sky-200">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg bg-sky-50 mb-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center flex-shrink-0">
              <User size={13} className="text-white" />
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-gray-800 truncate">{user?.username ?? 'User'}</p>
              <p className="text-xs text-gray-500 truncate capitalize">{user?.role ?? ''}{user?.unit_key ? ` · ${user.unit_key}` : ''}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <LogOut size={14} />
            Sign Out
          </button>
          <p className="text-center text-xs text-gray-700 mt-2">v2.0.0 · Multi-Tenant</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
