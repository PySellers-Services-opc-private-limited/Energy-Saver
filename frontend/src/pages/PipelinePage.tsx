import { useCallback } from 'react'
import { Radio, CheckCircle, XCircle, Clock, MessageSquare } from 'lucide-react'

import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { useWebSocket } from '../hooks/useWebSocket'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${active ? 'bg-brand-400' : 'bg-gray-600'}`} />
  )
}

export default function PipelinePage() {
  const fetchStatus = useCallback(() => api.pipeline.status(), [])
  const { data, loading, error } = usePolling(fetchStatus, 5_000)
  const { connected, history } = useWebSocket(10)

  return (
    <div>
      <PageHeader
        title="Streaming Pipeline"
        subtitle="Real-time IoT data processing status (Kafka · MQTT · WebSocket)"
      />

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {data && (
        <div className="px-6 pt-5 pb-8 space-y-6">
          {/* Main status */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Pipeline', active: data.running,        icon: Radio },
              { label: 'Kafka',    active: data.kafka_connected, icon: CheckCircle },
              { label: 'MQTT',     active: data.mqtt_connected,  icon: CheckCircle },
              { label: 'WebSocket (browser)', active: connected, icon: CheckCircle },
            ].map(({ label, active, icon: Icon }) => (
              <div key={label} className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <StatusDot active={active} />
                  <span className="text-xs font-medium text-gray-600">{label}</span>
                </div>
                <p className={`text-sm font-bold ${active ? 'text-blue-600' : 'text-gray-400'}`}>
                  {active ? 'Connected' : 'Offline'}
                </p>
              </div>
            ))}
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
              <div className="flex items-center gap-2 text-gray-500 text-xs mb-2">
                <Clock size={12} /> Uptime
              </div>
              <p className="text-xl font-bold text-gray-900">
                {Math.floor(data.uptime_s / 60)}m {Math.floor(data.uptime_s % 60)}s
              </p>
            </div>
            <div className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
              <div className="flex items-center gap-2 text-gray-500 text-xs mb-2">
                <MessageSquare size={12} /> Messages
              </div>
              <p className="text-xl font-bold text-gray-900">{data.messages_processed}</p>
            </div>
            <div className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
              <p className="text-xs text-gray-500 mb-2">Anomalies detected</p>
              <p className="text-xl font-bold text-red-500">{data.anomalies_detected}</p>
            </div>
            <div className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
              <p className="text-xs text-gray-500 mb-2">Mode</p>
              <p className="text-xl font-bold text-gray-900 capitalize">{data.mode}</p>
            </div>
          </div>

          {/* Live messages from WebSocket */}
          <div className="bg-white border border-sky-100 rounded-xl p-4 shadow-sm">
            <p className="text-xs text-gray-500 font-medium mb-3">
              WebSocket – last {history.length} messages
              <span className={`ml-3 ${connected ? 'text-blue-600' : 'text-gray-400'}`}>
                ● {connected ? 'live' : 'disconnected'}
              </span>
            </p>
            {history.length === 0 ? (
              <p className="text-xs text-gray-600">Waiting for messages…</p>
            ) : (
              <div className="space-y-1 font-mono text-xs max-h-48 overflow-y-auto">
                {[...history].reverse().map((r, i) => (
                  <div key={i} className="flex items-center gap-3 text-gray-600 hover:bg-sky-50 px-1 py-0.5 rounded">
                    <span className="text-gray-400 w-20 flex-shrink-0">{new Date(r.timestamp).toLocaleTimeString()}</span>
                    <span className="text-blue-600 w-24 flex-shrink-0">{r.device_id}</span>
                    <span>{r.consumption_kwh.toFixed(3)} kWh</span>
                    <span className="text-yellow-400">{r.solar_kwh.toFixed(3)} ☀</span>
                    {r.anomaly_score > 0.6 && <span className="text-red-400">⚠ {r.anomaly_score.toFixed(3)}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Start instructions */}
          {!data.running && (
            <div className="rounded-lg bg-yellow-50 border border-yellow-300 px-4 py-3 text-sm text-yellow-800">
              Pipeline is not running. Start it with:
              <code className="block mt-1 text-xs font-mono bg-gray-200 text-gray-800 px-2 py-1 rounded">
                python main.py stream
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
