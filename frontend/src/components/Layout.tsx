import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  TrendingUp,
  AlertTriangle,
  Thermometer,
  PiggyBank,
  Cpu,
  Radio,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/',          label: 'Dashboard',  icon: LayoutDashboard },
  { to: '/forecast',  label: 'Forecast',   icon: TrendingUp },
  { to: '/anomalies', label: 'Anomalies',  icon: AlertTriangle },
  { to: '/hvac',      label: 'HVAC',       icon: Thermometer },
  { to: '/savings',   label: 'Savings',    icon: PiggyBank },
  { to: '/models',    label: 'Models',     icon: Cpu },
  { to: '/pipeline',  label: 'Pipeline',   icon: Radio },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
          <Zap className="text-brand-400" size={22} />
          <span className="font-bold text-sm leading-tight">
            Energy<br />Saver AI
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-600/20 text-brand-400'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Version */}
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          v1.0.0 · 8 AI Models
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
