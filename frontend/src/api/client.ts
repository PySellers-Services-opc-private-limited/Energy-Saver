/**
 * Typed REST client – thin wrapper over fetch.
 * All requests go through Vite's dev-proxy so we use relative paths.
 */

import type {
  AnomalyResponse,
  ForecastResponse,
  HVACCommandRequest,
  HVACCommandResponse,
  HVACStatus,
  KPISummary,
  ModelListResponse,
  PipelineStatus,
  SavingsRequest,
  SavingsResponse,
} from './types'

const BASE = '/api/v1'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<B, T>(path: string, body: B): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  dashboard: {
    kpis: () => get<KPISummary>('/dashboard'),
  },
  forecast: {
    get: (deviceId: string, horizonHours: number) =>
      get<ForecastResponse>(`/forecast?device_id=${deviceId}&horizon_hours=${horizonHours}`),
  },
  anomalies: {
    recent: (limit = 20, deviceId?: string) =>
      get<AnomalyResponse>(
        `/anomalies?limit=${limit}${deviceId ? `&device_id=${deviceId}` : ''}`
      ),
  },
  hvac: {
    status: () => get<HVACStatus>('/hvac/status'),
    command: (cmd: HVACCommandRequest) => post<HVACCommandRequest, HVACCommandResponse>('/hvac/command', cmd),
  },
  savings: {
    estimate: (req: SavingsRequest) => post<SavingsRequest, SavingsResponse>('/savings', req),
  },
  models: {
    list: () => get<ModelListResponse>('/models'),
  },
  pipeline: {
    status: () => get<PipelineStatus>('/pipeline/status'),
  },
}
