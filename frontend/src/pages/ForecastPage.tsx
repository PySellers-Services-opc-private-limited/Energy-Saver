import { useCallback, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'

import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'

export default function ForecastPage() {
  const [horizon, setHorizon] = useState(24)
  const [deviceId, setDeviceId] = useState('device_001')

  const fetchForecast = useCallback(
    () => api.forecast.get(deviceId, horizon),
    [deviceId, horizon]
  )
  const { data, loading, error } = usePolling(fetchForecast, 30_000)

  const chartData = data?.forecasts.map((p) => ({
    time: new Date(p.timestamp).toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', weekday: 'short' }),
    predicted: p.predicted_kwh,
    lower:     p.lower_bound,
    upper:     p.upper_bound,
  })) ?? []

  return (
    <div>
      <PageHeader
        title="Energy Forecast"
        subtitle="LSTM-based energy consumption predictions with confidence bounds"
      />

      {/* Controls */}
      <div className="px-6 pt-5 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-gray-600 mb-1">Device</label>
          <select
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={`device_00${n}`}>{`device_00${n}`}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">Horizon</label>
          <select
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          >
            {[12, 24, 48, 72, 168].map((h) => (
              <option key={h} value={h}>{h} h</option>
            ))}
          </select>
        </div>
      </div>

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {data && (
        <div className="px-6 pt-6 pb-8">
          <div className="bg-white border border-sky-100 rounded-xl p-4 h-80 shadow-sm">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="gradBand" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#06d669" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#06d669" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0f2fe" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} interval={Math.floor(chartData.length / 8)} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} unit=" kWh" />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #bae6fd', borderRadius: 8 }}
                  labelStyle={{ color: '#475569' }}
                />
                <Area type="monotone" dataKey="upper"     name="Upper bound" stroke="transparent" fill="url(#gradBand)" strokeWidth={0} />
                <Area type="monotone" dataKey="predicted" name="Forecast (kWh)" stroke="#06d669" fill="none" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="lower"     name="Lower bound" stroke="transparent" fill="white" fillOpacity={0} strokeWidth={0} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Summary table */}
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-sky-100 text-gray-500 text-xs uppercase">
                  <th className="pb-2 pr-6">Time</th>
                  <th className="pb-2 pr-6 text-right">Forecast (kWh)</th>
                  <th className="pb-2 pr-6 text-right">Lower</th>
                  <th className="pb-2 text-right">Upper</th>
                </tr>
              </thead>
              <tbody>
                {data.forecasts.slice(0, 12).map((p) => (
                  <tr key={p.timestamp} className="border-b border-sky-50 hover:bg-sky-50">
                    <td className="py-2 pr-6 text-gray-600">
                      {new Date(p.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 pr-6 text-right text-emerald-600 font-mono">
                      {p.predicted_kwh.toFixed(3)}
                    </td>
                    <td className="py-2 pr-6 text-right text-gray-500 font-mono">{p.lower_bound.toFixed(3)}</td>
                    <td className="py-2 text-right text-gray-500 font-mono">{p.upper_bound.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
