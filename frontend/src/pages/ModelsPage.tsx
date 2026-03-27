import { useCallback } from 'react'
import { CheckCircle, XCircle, Cpu } from 'lucide-react'

import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import PageHeader from '../components/PageHeader'
import { Spinner, ErrorBanner } from '../components/Feedback'

export default function ModelsPage() {
  const fetchModels = useCallback(() => api.models.list(), [])
  const { data, loading, error } = usePolling(fetchModels, 30_000)

  const loaded = data?.models.filter((m) => m.loaded).length ?? 0
  const total  = data?.models.length ?? 0

  return (
    <div>
      <PageHeader
        title="AI Models"
        subtitle="Status of all 8 trained models available for inference"
      />

      {loading && !data && <Spinner />}
      {error && <ErrorBanner message={error} />}

      {data && (
        <div className="px-6 pt-5 pb-8">
          {/* Summary */}
          <div className="flex items-center gap-3 mb-6">
            <Cpu className="text-brand-400" size={20} />
            <span className="text-sm text-gray-300">
              <span className="font-bold text-brand-400">{loaded}</span> / {total} models loaded
            </span>
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all"
                style={{ width: `${total ? (loaded / total) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* Model cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.models.map((m) => (
              <div
                key={m.name}
                className={`rounded-xl border p-4 flex items-start gap-3 ${
                  m.loaded ? 'bg-gray-900 border-gray-800' : 'bg-gray-950 border-gray-900 opacity-60'
                }`}
              >
                {m.loaded
                  ? <CheckCircle className="text-brand-400 flex-shrink-0 mt-0.5" size={18} />
                  : <XCircle     className="text-gray-600   flex-shrink-0 mt-0.5" size={18} />}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-200 truncate">{m.name}</p>
                  <p className="text-xs text-gray-500 font-mono truncate mt-0.5">{m.path}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      m.loaded ? 'bg-brand-400/10 text-brand-400' : 'bg-gray-800 text-gray-500'
                    }`}>
                      {m.loaded ? 'Ready' : 'Not trained'}
                    </span>
                    <span className="text-xs text-gray-600">v{m.version}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {loaded < total && (
            <div className="mt-6 rounded-lg bg-yellow-900/20 border border-yellow-800/50 px-4 py-3 text-sm text-yellow-300">
              ⚠ Run <code className="font-mono bg-gray-900 px-1 py-0.5 rounded text-xs">python main.py train</code> to train all models and enable full inference.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
