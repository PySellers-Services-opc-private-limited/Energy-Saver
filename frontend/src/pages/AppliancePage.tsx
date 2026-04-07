import { useState } from 'react'
import { api } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'
import type { ApplianceResult } from '../api/types'

export default function AppliancePage() {
  const [result, setResult] = useState<ApplianceResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runDemo = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.appliance.demo()
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    }
    setLoading(false)
  }

  const identifyRandom = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.appliance.identify()
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Appliance Fingerprinting" subtitle="Model 5 — Identify appliances from power signature" />

      {/* Action buttons */}
      <div className="flex gap-4">
        <button onClick={runDemo}
          className="px-6 py-3 bg-indigo-600 text-white rounded-lg shadow hover:bg-indigo-700 transition font-semibold">
          Demo: Random Appliance
        </button>
        <button onClick={identifyRandom}
          className="px-6 py-3 bg-purple-600 text-white rounded-lg shadow hover:bg-purple-700 transition font-semibold">
          Identify from Signature
        </button>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {result && (
        <>
          {/* Main result */}
          <div className="bg-gradient-to-r from-indigo-500 to-blue-600 text-white rounded-xl p-8 shadow-lg text-center">
            <p className="text-sm opacity-80 mb-2">Identified Appliance</p>
            <p className="text-4xl font-bold mb-2">{result.identified_appliance}</p>
            <p className="text-xl">
              Confidence: <span className="font-bold">{result.confidence_pct}%</span>
            </p>
            <span className={`inline-block mt-3 px-3 py-1 rounded-full text-xs font-semibold ${result.model === 'real' ? 'bg-green-400/30' : 'bg-yellow-400/30'}`}>
              {result.model === 'real' ? '🧠 Real CNN Model' : '📊 Estimated'}
            </span>
          </div>

          {/* Top predictions */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Top Predictions</h3>
            <div className="space-y-3">
              {result.top_predictions.map((pred, i) => (
                <div key={i} className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-600 w-40">{pred.appliance}</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-4">
                    <div
                      className={`h-4 rounded-full ${i === 0 ? 'bg-indigo-500' : i === 1 ? 'bg-blue-400' : 'bg-gray-400'}`}
                      style={{ width: `${pred.confidence}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold w-16 text-right">{pred.confidence}%</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Info section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">How It Works</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="font-semibold text-gray-800 mb-1">1. Power Signature</p>
            <p>Each appliance creates a unique 60-point power draw pattern when it runs.</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="font-semibold text-gray-800 mb-1">2. CNN Analysis</p>
            <p>A 1D Convolutional Neural Network analyzes the pattern to identify the appliance.</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="font-semibold text-gray-800 mb-1">3. Classification</p>
            <p>Recognizes 7 types: Idle, Refrigerator, Washing Machine, Microwave, AC, EV Charger, Dishwasher.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
