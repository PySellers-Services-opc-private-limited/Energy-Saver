import { useCallback, useState } from 'react'
import { Thermometer, Zap } from 'lucide-react'

import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import type { HVACCommandRequest } from '../api/types'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import clsx from 'clsx'

type Mode = HVACCommandRequest['mode']

const MODES: { value: Mode; label: string; saving: string; color: string }[] = [
  { value: 'COMFORT',         label: 'Comfort',         saving: '0%',   color: 'bg-blue-600/20 border-blue-600 text-blue-300' },
  { value: 'ECO',             label: 'Eco',             saving: '15%',  color: 'bg-brand-600/20 border-brand-500 text-brand-300' },
  { value: 'DEMAND_RESPONSE', label: 'Demand Response', saving: '30%',  color: 'bg-yellow-600/20 border-yellow-600 text-yellow-300' },
  { value: 'PRE_CONDITION',   label: 'Pre-condition',   saving: '5%',   color: 'bg-purple-600/20 border-purple-600 text-purple-300' },
  { value: 'OFF',             label: 'Off',             saving: '100%', color: 'bg-red-600/20 border-red-600 text-red-300' },
]

export default function HVACPage() {
  const [mode, setMode]     = useState<Mode>('ECO')
  const [setpoint, setSetpoint] = useState(21)
  const [sending, setSending] = useState(false)
  const [cmdResult, setCmdResult] = useState<string | null>(null)

  const fetchStatus = useCallback(() => api.hvac.status(), [])
  const { data: status, loading, error } = usePolling(fetchStatus, 10_000)

  async function handleSend() {
    setSending(true)
    try {
      const res = await api.hvac.command({ mode, setpoint_c: setpoint })
      setCmdResult(`✅ Command sent · ${res.mode} @ ${res.setpoint_c}°C · Est. saving: ${res.estimated_saving_pct}%`)
    } catch (e) {
      setCmdResult(`❌ ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="HVAC Optimisation"
        subtitle="AI-driven heating & cooling control with demand-response support"
      />

      {loading && !status && <Spinner />}
      {error && <ErrorBanner message={error} />}

      <div className="px-6 pt-5 pb-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current status */}
        {status && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-300 mb-4">Current Status</h2>
            <div className="flex items-center gap-3 mb-4">
              <Thermometer className="text-brand-400" size={28} />
              <div>
                <p className="text-2xl font-bold text-gray-100">{status.setpoint_c}°C</p>
                <p className="text-xs text-gray-500">{status.zone_id}</p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Mode</span>
                <span className="font-medium text-gray-200">{status.mode}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Est. Saving</span>
                <span className="font-medium text-brand-400">{status.estimated_saving_pct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Last updated</span>
                <span className="text-gray-400 text-xs">{new Date(status.last_updated).toLocaleTimeString()}</span>
              </div>
            </div>
          </div>
        )}

        {/* Command panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Issue Command</h2>

          {/* Mode selector */}
          <p className="text-xs text-gray-500 mb-2">Mode</p>
          <div className="grid grid-cols-2 gap-2 mb-4">
            {MODES.map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={clsx(
                  'rounded-lg border px-3 py-2 text-xs font-medium text-left transition-all',
                  mode === m.value ? m.color : 'border-gray-700 text-gray-500 hover:border-gray-600'
                )}
              >
                {m.label}
                <span className="ml-2 text-gray-500">({m.saving} saved)</span>
              </button>
            ))}
          </div>

          {/* Setpoint slider */}
          <p className="text-xs text-gray-500 mb-1">Setpoint: <span className="text-gray-200 font-semibold">{setpoint}°C</span></p>
          <input
            type="range" min={10} max={35} value={setpoint}
            onChange={(e) => setSetpoint(Number(e.target.value))}
            className="w-full accent-brand-500 mb-4"
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={sending}
            className="w-full bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Zap size={15} />
            {sending ? 'Sending…' : 'Send Command'}
          </button>

          {cmdResult && (
            <p className={`mt-3 text-xs ${cmdResult.startsWith('✅') ? 'text-brand-400' : 'text-red-400'}`}>
              {cmdResult}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
