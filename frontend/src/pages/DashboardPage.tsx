import { useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Zap, Sun, AlertTriangle, IndianRupee, Users, TrendingUp, Wifi, Download } from 'lucide-react'

import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { useWebSocket } from '../hooks/useWebSocket'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import { Spinner, ErrorBanner } from '../components/Feedback'
import { exportDashboardPDF } from '../utils/pdfExport'

export default function DashboardPage() {
  const fetchKPIs = useCallback(() => api.dashboard.kpis(), [])
  const { data: kpis, loading, error } = usePolling(fetchKPIs, 5000)
  const { reading, connected, history } = useWebSocket(60)

  const chartData = history.map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString(),
    kwh:  r.consumption_kwh,
    solar: r.solar_kwh,
    score: r.anomaly_score,
  }))

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Live overview of your energy consumption and AI insights"
      />

      {/* PDF Export */}
      {kpis && (
        <div className="px-6 pt-4 flex justify-end">
          <button
            onClick={() => exportDashboardPDF(kpis)}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition"
          >
            <Download size={14} /> Download PDF Report
          </button>
        </div>
      )}

      {/* WebSocket status */}
      <div className="px-6 pt-4 flex items-center gap-2 text-xs">
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-brand-400' : 'bg-red-400'}`} />
        <span className={connected ? 'text-blue-600' : 'text-red-500'}>
          {connected ? 'Live stream connected' : 'Reconnecting…'}
        </span>
        {reading && (
          <span className="text-gray-500 ml-2">
            Device: <span className="text-gray-700 font-mono">{reading.device_id}</span>
          </span>
        )}
      </div>

      {loading && !kpis && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {/* KPI cards */}
      {kpis && (
        <div className="px-6 pt-5 grid grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title="Consumption"
            value={(reading?.consumption_kwh ?? kpis.total_consumption_kwh).toFixed(2)}
            unit="kWh"
            icon={<Zap size={18} />}
            color="green"
          />
          <StatCard
            title="Solar Generation"
            value={(reading?.solar_kwh ?? kpis.solar_generation_kwh).toFixed(2)}
            unit="kWh"
            icon={<Sun size={18} />}
            color="yellow"
          />
          <StatCard
            title="Anomalies (today)"
            value={kpis.anomalies_detected}
            icon={<AlertTriangle size={18} />}
            color={kpis.anomalies_detected > 0 ? 'red' : 'gray'}
          />
          <StatCard
            title="Savings (today)"
            value={`₹${kpis.estimated_savings_today.toFixed(2)}`}
            icon={<IndianRupee size={18} />}
            color="blue"
          />
          <StatCard
            title="Occupancy Rate"
            value={`${(kpis.occupancy_rate * 100).toFixed(0)}%`}
            icon={<Users size={18} />}
            color="gray"
          />
          <StatCard
            title="Current Tariff"
            value={`₹${(reading?.tariff ?? kpis.current_tariff).toFixed(2)}`}
            unit="/kWh"
            icon={<TrendingUp size={18} />}
            color="gray"
          />
          <StatCard
            title="Peak Demand"
            value={kpis.peak_demand_kw.toFixed(2)}
            unit="kW"
            icon={<Zap size={18} />}
            color="yellow"
          />
          <StatCard
            title="WS Clients"
            value={connected ? 1 : 0}
            icon={<Wifi size={18} />}
            color={connected ? 'green' : 'gray'}
          />
        </div>
      )}

      {/* Live chart */}
      <div className="px-6 pt-8 pb-8">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Live Consumption · Last 60 s</h2>
        <div className="bg-white border border-sky-100 rounded-xl p-4 h-64 shadow-sm">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="gradKwh" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#06d669" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06d669" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradSolar" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#facc15" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#facc15" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0f2fe" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #bae6fd', borderRadius: 8 }}
                labelStyle={{ color: '#475569' }}
              />
              <Area type="monotone" dataKey="kwh"   name="Consumption (kWh)" stroke="#06d669" fill="url(#gradKwh)"   strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="solar" name="Solar (kWh)"        stroke="#facc15" fill="url(#gradSolar)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
