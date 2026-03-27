import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { PiggyBank, Leaf, Zap, IndianRupee } from 'lucide-react'

import { api } from '../api/client'
import type { SavingsResponse } from '../api/types'
import PageHeader from '../components/PageHeader'
import { Spinner } from '../components/Feedback'
import StatCard from '../components/StatCard'

export default function SavingsPage() {
  const [kwh, setKwh]       = useState(30)
  const [tariff, setTariff] = useState(6.50)
  const [data, setData]     = useState<SavingsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState<string | null>(null)

  async function handleEstimate() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.savings.estimate({ baseline_kwh_per_day: kwh, tariff_per_kwh: tariff })
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const barData = data
    ? [
        { name: 'HVAC',     kwh: data.breakdown.hvac_kwh_per_year },
        { name: 'EV Opt.',  kwh: data.breakdown.ev_kwh_per_year },
        { name: 'Anomaly',  kwh: data.breakdown.anomaly_kwh_per_year },
      ]
    : []

  const BAR_COLORS = ['#06d669', '#facc15', '#60a5fa', '#a78bfa']

  return (
    <div>
      <PageHeader
        title="Savings Estimator"
        subtitle="Calculate annual energy and cost savings from AI optimisation"
      />

      {/* Input panel */}
      <div className="px-6 pt-5 pb-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-wrap gap-6 items-end">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Baseline: <span className="text-gray-200 font-semibold">{kwh} kWh/day</span>
            </label>
            <input
              type="range" min={5} max={100} value={kwh}
              onChange={(e) => setKwh(Number(e.target.value))}
              className="w-48 accent-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Tariff: <span className="text-gray-200 font-semibold">₹{tariff.toFixed(2)}/kWh</span>
            </label>
            <input
              type="range" min={3} max={15} step={0.50} value={tariff}
              onChange={(e) => setTariff(Number(e.target.value))}
              className="w-48 accent-brand-500"
            />
          </div>
          <button
            onClick={handleEstimate}
            disabled={loading}
            className="bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition-colors"
          >
            {loading ? 'Calculating…' : 'Calculate Savings'}
          </button>
        </div>
      </div>

      {loading && <Spinner />}
      {error && <div className="px-6 text-sm text-red-400">{error}</div>}

      {data && (
        <div className="px-6 pb-8">
          {/* KPI cards */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="kWh saved/day"
              value={data.kwh_saved_per_day.toFixed(2)}
              unit="kWh"
              icon={<Zap size={18} />}
              color="green"
            />
            <StatCard
              title="kWh saved/year"
              value={data.kwh_saved_per_year.toFixed(0)}
              unit="kWh"
              icon={<Zap size={18} />}
              color="green"
            />
            <StatCard
              title="Cost saved/year"
              value={`₹${data.cost_saved_per_year.toFixed(2)}`}
              icon={<IndianRupee size={18} />}
              color="blue"
            />
            <StatCard
              title="CO₂ avoided/year"
              value={data.co2_saved_kg_per_year.toFixed(1)}
              unit="kg"
              icon={<Leaf size={18} />}
              color="green"
            />
          </div>

          {/* Breakdown chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-64">
            <p className="text-xs text-gray-500 mb-3">Savings Breakdown by Category (kWh/year)</p>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} unit=" kWh" />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(v: number) => [`${v.toFixed(1)} kWh`, 'Savings']}
                />
                <Bar dataKey="kwh" radius={[4, 4, 0, 0]}>
                  {barData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
