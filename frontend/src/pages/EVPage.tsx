import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { api } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { EVSchedule } from '../api/types'

export default function EVPage() {
  const [soc, setSoc] = useState(20)
  const [departure, setDeparture] = useState(8)
  const [targetSoc, setTargetSoc] = useState(80)

  const { data, loading, error } = usePolling<EVSchedule>(
    () => api.ev.optimize(soc, departure, targetSoc),
    30_000,
  )

  const chartData = data?.schedule.map(s => ({
    hour: `${s.hour}:00`,
    soc: s.soc_pct,
    kwh: s.kwh_added,
    tariff: s.tariff_inr,
    action: s.action,
  })) ?? []

  const actionColors: Record<string, string> = {
    no_charge: '#e5e7eb',
    slow_charge: '#93c5fd',
    fast_charge: '#3b82f6',
  }

  return (
    <div className="space-y-6">
      <PageHeader title="EV Charging Optimizer" subtitle="Model 7 — Q-Learning optimal charging schedule" />

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Current SOC</label>
          <input type="range" min={0} max={100} value={soc} onChange={e => setSoc(+e.target.value)} className="w-full" />
          <span className="text-lg font-bold text-blue-600">{soc}%</span>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Departure Hour</label>
          <input type="range" min={0} max={23} value={departure} onChange={e => setDeparture(+e.target.value)} className="w-full" />
          <span className="text-lg font-bold text-blue-600">{departure}:00</span>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Target SOC</label>
          <input type="range" min={50} max={100} value={targetSoc} onChange={e => setTargetSoc(+e.target.value)} className="w-full" />
          <span className="text-lg font-bold text-green-600">{targetSoc}%</span>
        </div>
      </div>

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {data && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Final SOC</p>
              <p className="text-2xl font-bold text-green-600">{data.final_soc_pct}%</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Total Charged</p>
              <p className="text-2xl font-bold text-blue-600">{data.total_kwh_charged} kWh</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Total Cost</p>
              <p className="text-2xl font-bold text-orange-600">₹{data.total_cost_inr}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Savings vs Naive</p>
              <p className="text-2xl font-bold text-green-600">₹{data.savings_vs_naive_inr}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Model</p>
              <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${data.model === 'real' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                {data.model === 'real' ? '🧠 Q-Learning' : '📊 Fallback'}
              </span>
            </div>
          </div>

          {/* SOC Chart */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-4">Battery SOC Over Time</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis domain={[0, 100]} label={{ value: 'SOC %', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="soc" stroke="#3b82f6" strokeWidth={2} name="Battery SOC %" />
                <Line type="monotone" dataKey="tariff" stroke="#ef4444" strokeWidth={1} strokeDasharray="5 5" name="Tariff ₹/kWh" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Charging schedule */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-4">Charging Schedule</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis label={{ value: 'kWh', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Bar dataKey="kwh" fill="#3b82f6" name="kWh Added" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
