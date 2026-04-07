import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { api } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { SolarForecast } from '../api/types'

export default function SolarPage() {
  const [systemKw, setSystemKw] = useState(5)

  const { data, loading, error } = usePolling<SolarForecast>(
    () => api.solar.forecast(systemKw),
    30_000,
  )

  const chartData = data?.hourly_forecast.map(h => ({
    hour: `${h.hour}:00`,
    solar_kwh: h.solar_kwh,
  })) ?? []

  return (
    <div className="space-y-6">
      <PageHeader title="Solar Forecast" subtitle="Model 6 — 24-hour solar generation prediction" />

      {/* Controls */}
      <div className="bg-white p-4 rounded-lg shadow">
        <label className="block text-sm font-medium text-gray-600 mb-1">Solar System Size</label>
        <input type="range" min={1} max={20} step={0.5} value={systemKw} onChange={e => setSystemKw(+e.target.value)}
          className="w-full" />
        <span className="text-lg font-bold text-yellow-600">{systemKw} kW system</span>
      </div>

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {data && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Total 24h Generation</p>
              <p className="text-2xl font-bold text-yellow-600">{data.total_24h_kwh} kWh</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Daily Savings</p>
              <p className="text-2xl font-bold text-green-600">₹{data.estimated_daily_savings_inr}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Annual Savings</p>
              <p className="text-2xl font-bold text-blue-600">₹{data.estimated_annual_savings_inr.toLocaleString()}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Model</p>
              <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${data.model === 'real' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                {data.model === 'real' ? '🧠 Real LSTM' : '📊 Simulated'}
              </span>
            </div>
          </div>

          {/* Chart */}
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-4">Hourly Solar Generation Forecast</h3>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis label={{ value: 'kWh', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Area type="monotone" dataKey="solar_kwh" stroke="#f59e0b" fill="#fef3c7" strokeWidth={2} name="Solar kWh" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
