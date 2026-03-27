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
  green:  'text-brand-400 bg-brand-400/10',
  red:    'text-red-400 bg-red-400/10',
  yellow: 'text-yellow-400 bg-yellow-400/10',
  blue:   'text-blue-400 bg-blue-400/10',
  gray:   'text-gray-400 bg-gray-400/10',
}

export default function StatCard({ title, value, unit, icon, color = 'gray' }: StatCardProps) {
  return (
    <div className="rounded-xl bg-gray-900 border border-gray-800 p-5 flex items-start gap-4">
      {icon && (
        <div className={clsx('rounded-lg p-2.5 flex-shrink-0', colorMap[color])}>
          {icon}
        </div>
      )}
      <div>
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{title}</p>
        <p className="mt-1 text-2xl font-bold text-gray-100">
          {value}
          {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
        </p>
      </div>
    </div>
  )
}
