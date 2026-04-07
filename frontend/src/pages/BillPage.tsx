import { useState } from 'react'
import { Mail, Download } from 'lucide-react'
import { usePolling } from '../hooks/usePolling'
import { api, apartmentApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import { exportBillPDF } from '../utils/pdfExport'
import type { BillPrediction } from '../api/types'

export default function BillPage() {
  const [daysElapsed, setDaysElapsed] = useState(15)
  const [avgKwh, setAvgKwh] = useState(30)
  const [tariff, setTariff] = useState(6.5)
  const [sending, setSending] = useState(false)
  const [emailMsg, setEmailMsg] = useState<{ text: string; ok: boolean } | null>(null)

  const sendBillReport = async () => {
    setSending(true)
    setEmailMsg(null)
    try {
      const res = await apartmentApi.notifications.sendBillReport({
        days_elapsed: daysElapsed,
        avg_daily_kwh: avgKwh,
        tariff,
        avg_temp: 28,
      })
      setEmailMsg({ text: `Bill report sent to ${res.to}`, ok: true })
    } catch {
      setEmailMsg({ text: 'Failed to send bill report. Please login first.', ok: false })
    } finally {
      setSending(false)
      setTimeout(() => setEmailMsg(null), 4000)
    }
  }

  const { data, loading, error } = usePolling<BillPrediction>(
    () => api.bill.predict(daysElapsed, avgKwh, tariff),
    30_000,
  )

  return (
    <div className="space-y-6">
      <PageHeader title="Bill Predictor" subtitle="Model 8 — Mid-month bill forecast with confidence interval" />

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Days Elapsed</label>
          <input type="range" min={1} max={31} value={daysElapsed} onChange={e => setDaysElapsed(+e.target.value)}
            className="w-full" />
          <span className="text-lg font-bold text-indigo-600">{daysElapsed} days</span>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Avg Daily kWh</label>
          <input type="range" min={5} max={100} value={avgKwh} onChange={e => setAvgKwh(+e.target.value)}
            className="w-full" />
          <span className="text-lg font-bold text-indigo-600">{avgKwh} kWh/day</span>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <label className="block text-sm font-medium text-gray-600 mb-1">Tariff (₹/kWh)</label>
          <input type="range" min={3} max={15} step={0.5} value={tariff} onChange={e => setTariff(+e.target.value)}
            className="w-full" />
          <span className="text-lg font-bold text-indigo-600">₹{tariff}/kWh</span>
        </div>
      </div>

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {/* Email notification toast */}
      {emailMsg && (
        <div className={`px-4 py-3 rounded-xl text-sm font-semibold text-white shadow-lg ${emailMsg.ok ? 'bg-emerald-600' : 'bg-red-600'}`}>
          {emailMsg.text}
        </div>
      )}

      {data && (
        <>
          {/* Main prediction card */}
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl p-6 shadow-lg">
            <div className="text-center">
              <p className="text-sm opacity-80">Predicted Monthly Bill</p>
              <p className="text-5xl font-bold my-2">₹{data.predicted_bill.toLocaleString()}</p>
              <p className="text-sm opacity-80">
                {data.confidence_pct}% confidence: ₹{data.lower_bound.toLocaleString()} – ₹{data.upper_bound.toLocaleString()}
              </p>
              <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-semibold ${data.model === 'real' ? 'bg-green-400/30' : 'bg-yellow-400/30'}`}>
                {data.model === 'real' ? '🧠 Real ML Model' : '📊 Estimated'}
              </span>
              {/* Email Bill Report + PDF buttons */}
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  disabled={sending}
                  onClick={sendBillReport}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold bg-white/20 hover:bg-white/30 border border-white/30 text-white transition active:scale-95 disabled:opacity-50"
                >
                  <Mail size={15} /> {sending ? 'Sending...' : 'Email Bill Report'}
                </button>
                <button
                  onClick={() => exportBillPDF(data)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold bg-white/20 hover:bg-white/30 border border-white/30 text-white transition active:scale-95"
                >
                  <Download size={15} /> Download PDF
                </button>
              </div>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Daily Budget</p>
              <p className="text-2xl font-bold text-green-600">₹{data.daily_budget}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Remaining Budget</p>
              <p className="text-2xl font-bold text-blue-600">₹{data.remaining_budget}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">kWh So Far</p>
              <p className="text-2xl font-bold text-orange-600">{data.kwh_so_far}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <p className="text-sm text-gray-500">Projected kWh</p>
              <p className="text-2xl font-bold text-purple-600">{data.projected_kwh}</p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
