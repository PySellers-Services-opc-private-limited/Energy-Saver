import type { ReactNode } from 'react'
import clsx from 'clsx'

interface StatCardProps {
  title: string
  value: string | number
  unit?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'gray'
}

const colorMap = {
  green:  'text-emerald-600 bg-emerald-100',
  red:    'text-red-600 bg-red-100',
  yellow: 'text-amber-600 bg-amber-100',
  blue:   'text-blue-600 bg-blue-100',
  gray:   'text-gray-600 bg-gray-100',
}

export default function StatCard({ title, value, unit, icon, color = 'gray' }: StatCardProps) {
  return (
    <div className="rounded-xl bg-white border border-sky-100 p-5 flex items-start gap-4 shadow-sm">
      {icon && (
        <div className={clsx('rounded-lg p-2.5 flex-shrink-0', colorMap[color])}>
          {icon}
        </div>
      )}
      <div>
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{title}</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">
          {value}
          {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
        </p>
      </div>
    </div>
  )
}
