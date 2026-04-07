import { useEffect, useState } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Sun,
  Zap,
  IndianRupee,
  AlertTriangle,
  Activity,
  Target,
  ChevronDown,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
} from 'recharts'
import clsx from 'clsx'
import { apartmentApi } from '../api/client'
import type {
  ForecastVsActualSummary,
  ForecastChartResponse,
  ForecastScorecardResponse,
  ForecastMetricCard,
  Tenant,
} from '../api/types'

// ── RAG badge colours ────────────────────────────────────────────────────────

const RAG_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  green: { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  amber: { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500' },
  red:   { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
}

const METRIC_ICONS: Record<string, typeof Zap> = {
  Consumption: Zap,
  'Monthly Bill': IndianRupee,
  'Solar Gen': Sun,
  'Peak Demand': Activity,
  Anomalies: AlertTriangle,
  'Accuracy Score': Target,
}

const PERIODS = ['day', 'week', 'month'] as const
const METRICS = ['consumption', 'bill', 'solar', 'peak'] as const

type Period = (typeof PERIODS)[number]
type Metric = (typeof METRICS)[number]

// ── RAG Badge component ──────────────────────────────────────────────────────

function RagBadge({ rag }: { rag: string }) {
  const s = RAG_STYLES[rag] ?? RAG_STYLES.green
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold', s.bg, s.text)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', s.dot)} />
      {rag.toUpperCase()}
    </span>
  )
}

// ── Delta arrow ──────────────────────────────────────────────────────────────

function DeltaArrow({ direction, value, unit }: { direction: string; value: number; unit: string }) {
  const Icon = direction === 'up' ? TrendingUp : direction === 'down' ? TrendingDown : Minus
  const color = direction === 'up' ? 'text-red-600' : direction === 'down' ? 'text-emerald-600' : 'text-gray-500'
  // For solar, up is good
  return (
    <span className={clsx('inline-flex items-center gap-1 text-sm font-medium', color)}>
      <Icon className="w-4 h-4" />
      {Math.abs(value)} {unit}
    </span>
  )
}

// ── Scorecard card ───────────────────────────────────────────────────────────

function ScorecardCard({ card }: { card: ForecastMetricCard }) {
  const Icon = METRIC_ICONS[card.name] ?? BarChart3
  const s = RAG_STYLES[card.rag] ?? RAG_STYLES.green
  return (
    <div className={clsx('bg-white rounded-xl p-5 border border-sky-100 hover:border-sky-200 shadow-sm transition-colors')}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={clsx('w-5 h-5', s.text)} />
          <span className="text-sm font-medium text-gray-600">{card.name}</span>
        </div>
        <RagBadge rag={card.rag} />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Forecast</p>
          <p className="text-lg font-bold text-gray-800">
            {card.unit === 'INR' && '₹'}{card.forecast.toLocaleString()} {card.unit !== 'INR' && card.unit}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Actual</p>
          <p className="text-lg font-bold text-gray-900">
            {card.unit === 'INR' && '₹'}{card.actual.toLocaleString()} {card.unit !== 'INR' && card.unit}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between pt-2 border-t border-gray-200">
        <DeltaArrow direction={card.direction} value={card.delta} unit={card.unit} />
        {card.delta_pct !== 0 && (
          <span className="text-xs text-gray-500">{card.delta_pct > 0 ? '+' : ''}{card.delta_pct}%</span>
        )}
      </div>
    </div>
  )
}

// ── Custom tooltip for the chart ─────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const forecast = payload.find((p: any) => p.dataKey === 'forecast')
  const actual = payload.find((p: any) => p.dataKey === 'actual')
  const point = payload[0]?.payload
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg">
      <p className="text-xs text-gray-500 mb-2">{label}</p>
      <div className="space-y-1">
        {forecast && (
          <p className="text-sm text-gray-700">
            <span className="inline-block w-3 h-3 rounded-full bg-teal-500 mr-2" />
            Forecast: <span className="font-bold text-teal-600">{forecast.value}</span>
          </p>
        )}
        {actual && (
          <p className="text-sm text-gray-700">
            <span className="inline-block w-3 h-3 rounded-full bg-blue-500 mr-2" />
            Actual: <span className="font-bold text-blue-600">{actual.value}</span>
          </p>
        )}
        {point?.delta_pct !== undefined && (
          <p className="text-xs text-gray-500 pt-1 border-t border-gray-200">
            Delta: {point.delta_pct > 0 ? '+' : ''}{point.delta_pct}% <RagBadge rag={point.rag} />
          </p>
        )}
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function ForecastVsActualPage() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [selectedTenant, setSelectedTenant] = useState<number | null>(null)
  const [period, setPeriod] = useState<Period>('day')
  const [metric, setMetric] = useState<Metric>('consumption')
  const [tab, setTab] = useState<'scorecard' | 'chart' | 'history'>('scorecard')

  const [summary, setSummary] = useState<ForecastVsActualSummary | null>(null)
  const [scorecard, setScorecard] = useState<ForecastScorecardResponse | null>(null)
  const [chartData, setChartData] = useState<ForecastChartResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Load tenants on mount
  useEffect(() => {
    apartmentApi.tenants.list().then((list) => {
      const active = list.filter((t) => t.is_active)
      setTenants(active)
      if (active.length > 0) setSelectedTenant(active[0].id)
    }).catch(() => setError('Failed to load tenants'))
  }, [])

  // Load data when tenant or period changes
  useEffect(() => {
    if (!selectedTenant) return
    setLoading(true)
    setError('')

    Promise.all([
      apartmentApi.forecastVsActual.summary(selectedTenant, period),
      apartmentApi.forecastVsActual.scorecard(selectedTenant),
      apartmentApi.forecastVsActual.chart(selectedTenant, period === 'day' ? 'week' : period, metric),
    ])
      .then(([s, sc, ch]) => {
        setSummary(s)
        setScorecard(sc)
        setChartData(ch)
      })
      .catch(() => setError('Failed to load forecast data'))
      .finally(() => setLoading(false))
  }, [selectedTenant, period])

  // Reload chart when metric changes
  useEffect(() => {
    if (!selectedTenant) return
    apartmentApi.forecastVsActual
      .chart(selectedTenant, period === 'day' ? 'week' : period, metric)
      .then(setChartData)
      .catch(() => {})
  }, [metric])

  const currentTenant = tenants.find((t) => t.id === selectedTenant)

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-teal-600" />
            Forecast vs Actual
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Compare AI predictions against real measurements
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Tenant selector */}
          <div className="relative">
            <select
              className="appearance-none bg-white border border-gray-300 text-gray-700 text-sm rounded-lg pl-3 pr-8 py-2 focus:ring-teal-500 focus:border-teal-500"
              value={selectedTenant ?? ''}
              onChange={(e) => setSelectedTenant(Number(e.target.value))}
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Period selector */}
          <div className="flex bg-white border border-gray-300 rounded-lg overflow-hidden">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={clsx(
                  'px-3 py-2 text-sm font-medium capitalize transition-colors',
                  period === p
                    ? 'bg-teal-600 text-white'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Overall RAG Banner ──────────────────────────────────────────── */}
      {summary && (
        <div className={clsx(
          'rounded-xl p-4 border flex items-center justify-between',
          summary.overall_rag === 'green' ? 'bg-emerald-500/10 border-emerald-500/30' :
          summary.overall_rag === 'amber' ? 'bg-amber-500/10 border-amber-500/30' :
          'bg-red-500/10 border-red-500/30'
        )}>
          <div className="flex items-center gap-3">
            <RagBadge rag={summary.overall_rag} />
            <span className="text-gray-600 text-sm">
              Overall performance for <span className="font-medium text-gray-900">{currentTenant?.name}</span> — {summary.period} view ({summary.date})
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-600">
              Model Accuracy: <span className="font-bold text-teal-600">{summary.model_accuracy.accuracy_pct}%</span>
            </span>
            <span className="text-gray-600">
              MAPE: <span className="font-bold text-gray-900">{summary.model_accuracy.model_1_mape}%</span>
            </span>
          </div>
        </div>
      )}

      {/* ── Tab selector ────────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-white border border-gray-300 rounded-lg p-1 w-fit">
        {(['scorecard', 'chart', 'history'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-md capitalize transition-colors',
              tab === t ? 'bg-teal-600 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            )}
          >
            {t === 'chart' ? 'Dual-Line Chart' : t}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-teal-500" />
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-600 text-sm">{error}</div>
      )}

      {/* ── SCORECARD TAB ───────────────────────────────────────────────── */}
      {!loading && !error && tab === 'scorecard' && scorecard && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {scorecard.cards.map((card) => (
              <ScorecardCard key={card.name} card={card} />
            ))}
          </div>
          {/* Accuracy summary bar */}
          <div className="bg-white rounded-xl border border-sky-100 shadow-sm p-5">
            <h3 className="text-sm font-medium text-gray-600 mb-3">Model Accuracy Overview</h3>
            <div className="flex items-center gap-6">
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Forecast Accuracy</span>
                  <span className="font-bold text-teal-600">{scorecard.model_accuracy.accuracy_pct}%</span>
                </div>
                <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      scorecard.model_accuracy.accuracy_pct >= 90 ? 'bg-emerald-500' :
                      scorecard.model_accuracy.accuracy_pct >= 80 ? 'bg-amber-500' : 'bg-red-500'
                    )}
                    style={{ width: `${Math.min(100, scorecard.model_accuracy.accuracy_pct)}%` }}
                  />
                </div>
              </div>
              <div className="text-center px-4 border-l border-gray-200">
                <p className="text-xs text-gray-500">MAPE</p>
                <p className="text-lg font-bold text-gray-800">{scorecard.model_accuracy.mape}%</p>
              </div>
              <div className="text-center px-4 border-l border-gray-200">
                <p className="text-xs text-gray-500">MAE</p>
                <p className="text-lg font-bold text-gray-800">{scorecard.model_accuracy.mae} kWh</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── CHART TAB ───────────────────────────────────────────────────── */}
      {!loading && !error && tab === 'chart' && chartData && (
        <div className="space-y-4">
          {/* Metric selector */}
          <div className="flex gap-2">
            {METRICS.map((m) => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                className={clsx(
                  'px-3 py-1.5 text-sm rounded-lg capitalize transition-colors',
                  metric === m ? 'bg-teal-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-100'
                )}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Chart */}
          <div className="bg-white rounded-xl border border-sky-100 shadow-sm p-5">
            <h3 className="text-sm font-medium text-gray-600 mb-4">
              {metric.charAt(0).toUpperCase() + metric.slice(1)} — Forecast vs Actual
            </h3>
            <ResponsiveContainer width="100%" height={380}>
              <AreaChart data={chartData.points} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <defs>
                  <linearGradient id="gradForecast" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#60a5fa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: 16 }}
                  formatter={(value: string) => <span className="text-gray-700 text-sm">{value}</span>}
                />
                <Area
                  type="monotone"
                  dataKey="forecast"
                  name="AI Forecast"
                  stroke="#2dd4bf"
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  fill="url(#gradForecast)"
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  name="Actual Reading"
                  stroke="#60a5fa"
                  strokeWidth={2}
                  fill="url(#gradActual)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── HISTORY TAB ─────────────────────────────────────────────────── */}
      {!loading && !error && tab === 'history' && chartData && (
        <div className="space-y-4">
          {/* Metric selector */}
          <div className="flex gap-2">
            {METRICS.map((m) => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                className={clsx(
                  'px-3 py-1.5 text-sm rounded-lg capitalize transition-colors',
                  metric === m ? 'bg-teal-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-100'
                )}
              >
                {m}
              </button>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-sky-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-gray-600">Accuracy Trend — last 30 days</h3>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData.points} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: 16 }}
                  formatter={(value: string) => <span className="text-gray-700 text-sm">{value}</span>}
                />
                <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#2dd4bf" strokeWidth={2} strokeDasharray="6 3" dot={false} />
                <Line type="monotone" dataKey="actual" name="Actual" stroke="#60a5fa" strokeWidth={2} dot={{ r: 3, fill: '#60a5fa' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Delta table */}
          <div className="bg-white rounded-xl border border-sky-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left text-gray-600 font-medium px-4 py-3">Date</th>
                  <th className="text-right text-gray-600 font-medium px-4 py-3">Forecast</th>
                  <th className="text-right text-gray-600 font-medium px-4 py-3">Actual</th>
                  <th className="text-right text-gray-600 font-medium px-4 py-3">Delta %</th>
                  <th className="text-center text-gray-600 font-medium px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {chartData.points.map((p) => (
                  <tr key={p.date} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-gray-700">{p.date}</td>
                    <td className="px-4 py-2.5 text-right text-teal-600">{p.forecast}</td>
                    <td className="px-4 py-2.5 text-right text-blue-600">{p.actual}</td>
                    <td className={clsx('px-4 py-2.5 text-right font-medium', p.delta_pct > 0 ? 'text-red-600' : 'text-emerald-600')}>
                      {p.delta_pct > 0 ? '+' : ''}{p.delta_pct}%
                    </td>
                    <td className="px-4 py-2.5 text-center"><RagBadge rag={p.rag} /></td>
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
