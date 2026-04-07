import { useCallback, useState } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell } from 'recharts'
import { Mail, Download } from 'lucide-react'

import { api, apartmentApi } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import { exportAnomaliesPDF } from '../utils/pdfExport'

export default function AnomaliesPage() {
  const fetchAnomalies = useCallback(() => api.anomalies.recent(50), [])
  const { data, loading, error } = usePolling(fetchAnomalies, 10_000)
  const [sending, setSending] = useState(false)
  const [emailMsg, setEmailMsg] = useState<{ text: string; ok: boolean } | null>(null)

  const sendAnomalyAlert = async (deviceId: string, score: number, kwh: number) => {
    setSending(true)
    setEmailMsg(null)
    try {
      const res = await apartmentApi.notifications.sendAnomalyAlert({
        device_id: deviceId,
        anomaly_score: score,
        consumption_kwh: kwh,
        reconstruction_error: 0.001,
      })
      setEmailMsg({ text: `Alert sent to ${res.to}`, ok: true })
    } catch {
      setEmailMsg({ text: 'Failed to send alert email. Please login first.', ok: false })
    } finally {
      setSending(false)
      setTimeout(() => setEmailMsg(null), 4000)
    }
  }

  const scatterData = data?.anomalies.map((a) => ({
    x:     a.consumption_kwh,
    y:     a.anomaly_score,
    flag:  a.is_anomaly,
    label: a.device_id,
    time:  new Date(a.timestamp).toLocaleTimeString(),
  })) ?? []

  return (
    <div>
      <PageHeader
        title="Anomaly Detection"
        subtitle="LSTM autoencoder anomaly scores and flagged events"
      />

      {/* PDF Export */}
      {data && (
        <div className="px-6 pt-4 flex justify-end">
          <button
            onClick={() => exportAnomaliesPDF(data.anomalies)}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition"
          >
            <Download size={14} /> Download PDF Report
          </button>
        </div>
      )}

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {/* Email notification toast */}
      {emailMsg && (
        <div className={`mx-6 mb-2 px-4 py-3 rounded-xl text-sm font-semibold text-white shadow-lg ${emailMsg.ok ? 'bg-emerald-600' : 'bg-red-600'}`}>
          {emailMsg.text}
        </div>
      )}

      {data && (
        <div className="px-6 pt-5 pb-8">
          {/* Stats */}
          <div className="flex gap-6 mb-6">
            <div className="bg-white border border-sky-100 rounded-xl px-5 py-4 shadow-sm">
              <p className="text-xs text-gray-500">Total Events</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{data.total}</p>
            </div>
            <div className="bg-white border border-red-200 rounded-xl px-5 py-4 shadow-sm">
              <p className="text-xs text-gray-500">Anomalies</p>
              <p className="text-2xl font-bold text-red-400 mt-1">
                {data.anomalies.filter((a) => a.is_anomaly).length}
              </p>
            </div>
            <div className="bg-white border border-sky-100 rounded-xl px-5 py-4 shadow-sm">
              <p className="text-xs text-gray-500">Avg Score</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {data.anomalies.length
                  ? (data.anomalies.reduce((s, a) => s + a.anomaly_score, 0) / data.anomalies.length).toFixed(3)
                  : '–'}
              </p>
            </div>
          </div>

          {/* Scatter chart */}
          <div className="bg-white border border-sky-100 rounded-xl p-4 h-64 mb-6 shadow-sm">
            <p className="text-xs text-gray-500 mb-3">Consumption vs Anomaly Score</p>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0f2fe" />
                <XAxis dataKey="x" name="kWh" tick={{ fontSize: 10, fill: '#6b7280' }} unit=" kWh" />
                <YAxis dataKey="y" name="Score" tick={{ fontSize: 10, fill: '#6b7280' }} domain={[0, 1]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  contentStyle={{ background: '#ffffff', border: '1px solid #bae6fd', borderRadius: 8 }}
                  content={({ payload }) => {
                    if (!payload?.length) return null
                    const d = payload[0].payload as { x: number; y: number; label: string; time: string; flag: boolean }
                    return (
                      <div className="text-xs p-2">
                        <p className="text-gray-400">{d.label} · {d.time}</p>
                        <p className="text-emerald-600">{d.x.toFixed(3)} kWh</p>
                        <p className={d.flag ? 'text-red-500' : 'text-gray-600'}>
                          score: {d.y.toFixed(4)} {d.flag ? '⚠ ANOMALY' : ''}
                        </p>
                      </div>
                    )
                  }}
                />
                <Scatter data={scatterData}>
                  {scatterData.map((entry, i) => (
                    <Cell key={i} fill={entry.flag ? '#f87171' : '#06d669'} fillOpacity={0.7} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-sky-100 text-gray-500 text-xs uppercase">
                  <th className="pb-2 pr-6">Device</th>
                  <th className="pb-2 pr-6">Time</th>
                  <th className="pb-2 pr-6 text-right">kWh</th>
                  <th className="pb-2 pr-6 text-right">Score</th>
                  <th className="pb-2 text-center">Flag</th>
                  <th className="pb-2 text-center">Email Alert</th>
                </tr>
              </thead>
              <tbody>
                {data.anomalies.map((a, i) => (
                  <tr key={i} className="border-b border-sky-50 hover:bg-sky-50">
                    <td className="py-2 pr-6 text-gray-700 font-mono text-xs">{a.device_id}</td>
                    <td className="py-2 pr-6 text-gray-500 text-xs">{new Date(a.timestamp).toLocaleString()}</td>
                    <td className="py-2 pr-6 text-right font-mono">{a.consumption_kwh.toFixed(3)}</td>
                    <td className={`py-2 pr-6 text-right font-mono ${a.anomaly_score > 0.6 ? 'text-red-400' : 'text-gray-400'}`}>
                      {a.anomaly_score.toFixed(4)}
                    </td>
                    <td className="py-2 text-center">
                      {a.is_anomaly
                        ? <span className="text-red-400 text-xs font-bold">ANOMALY</span>
                        : <span className="text-gray-600 text-xs">–</span>}
                    </td>
                    <td className="py-2 text-center">
                      {a.is_anomaly && (
                        <button
                          disabled={sending}
                          onClick={() => sendAnomalyAlert(a.device_id, a.anomaly_score, a.consumption_kwh)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition disabled:opacity-50"
                        >
                          <Mail size={11} /> Send
                        </button>
                      )}
                    </td>
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
