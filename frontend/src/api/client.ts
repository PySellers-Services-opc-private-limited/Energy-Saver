/**
 * Typed REST client – thin wrapper over fetch.
 * All requests go through Vite's dev-proxy so we use relative paths.
 */

import type {
  AnomalyResponse,
  ApplianceInfo,
  ApplianceResult,
  BillPrediction,
  EVSchedule,
  ForecastResponse,
  HVACCommandRequest,
  HVACCommandResponse,
  HVACStatus,
  KPISummary,
  ModelListResponse,
  PipelineStatus,
  SavingsRequest,
  SavingsResponse,
  SolarForecast,
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
  bill: {
    predict: (daysElapsed = 15, avgDailyKwh = 30, tariff = 6.5, avgTemp = 28) =>
      get<BillPrediction>(`/bill/predict?days_elapsed=${daysElapsed}&avg_daily_kwh=${avgDailyKwh}&tariff=${tariff}&avg_temp=${avgTemp}`),
  },
  solar: {
    forecast: (systemKw = 5.0) => get<SolarForecast>(`/solar/forecast?system_kw=${systemKw}`),
  },
  ev: {
    optimize: (currentSoc = 20, departureHour = 8, targetSoc = 80) =>
      get<EVSchedule>(`/ev/optimize?current_soc=${currentSoc}&departure_hour=${departureHour}&target_soc=${targetSoc}`),
  },
  appliance: {
    identify: (readings?: number[]) =>
      post<{ power_readings: number[] | null }, ApplianceResult>('/appliance/identify', { power_readings: readings ?? null }),
    list: () => get<ApplianceInfo[]>('/appliance/list'),
    demo: () => get<ApplianceResult>('/appliance/demo'),
  },
}

// ── Smart Apartment typed client (uses absolute URL so it works outside proxy) ─

import type {
  AuthToken,
  Building,
  BuildingCreate,
  EnergyLog,
  EnergyLogCreate,
  EnergySummary,
  ForecastChartResponse,
  ForecastHistoryResponse,
  ForecastScorecardResponse,
  ForecastVsActualSummary,
  SettingsProfile,
  SubscriptionInfo,
  SystemStatus,
  Tenant,
  TenantAlert,
  TenantCreate,
  TenantDetail,
  TenantStats,
  TenantUpdate,
  UserCreate,
  UserLogin,
} from './types'

const BASE_URL = '/api/v1'

async function apiFetch<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = localStorage.getItem('esai_token')
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    // Stale or invalid token → force logout
    if (res.status === 401) {
      localStorage.removeItem('esai_token')
      localStorage.removeItem('esai_user')
      window.location.href = '/login'
      throw new Error('Session expired — please log in again')
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `${method} ${path} → ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const apartmentApi = {
  // ── Auth
  auth: {
    register: (data: UserCreate) => apiFetch<{ message: string; id: number }>('POST', '/auth/register', data),
    login: (data: UserLogin) => apiFetch<AuthToken>('POST', '/auth/login', data),
    me: () => apiFetch<AuthToken['user']>('GET', '/auth/me'),
  },

  // ── Tenants
  tenants: {
    list: () => apiFetch<Tenant[]>('GET', '/tenants/'),
    stats: () => apiFetch<TenantStats>('GET', '/tenants/stats'),
    myUnit: () => apiFetch<TenantDetail>('GET', '/tenants/my-unit'),
    get: (id: number) => apiFetch<Tenant>('GET', `/tenants/${id}`),
    detail: (id: number) => apiFetch<TenantDetail>('GET', `/tenants/${id}/detail`),
    getByUnit: (unitKey: string) => apiFetch<Tenant>('GET', `/tenants/unit/${unitKey}`),
    create: (data: TenantCreate) => apiFetch<Tenant>('POST', '/tenants/', data),
    update: (id: number, data: TenantUpdate) => apiFetch<Tenant>('PUT', `/tenants/${id}`, data),
    delete: (id: number) => apiFetch<void>('DELETE', `/tenants/${id}`),
    // Buildings
    listBuildings: (id: number) => apiFetch<Building[]>('GET', `/tenants/${id}/buildings`),
    addBuilding: (id: number, data: BuildingCreate) => apiFetch<Building>('POST', `/tenants/${id}/buildings`, data),
    // Subscription
    getSubscription: (id: number) => apiFetch<SubscriptionInfo>('GET', `/tenants/${id}/subscription`),
    updateSubscription: (id: number, data: { plan: string; billing_cycle?: string }) =>
      apiFetch<SubscriptionInfo>('PUT', `/tenants/${id}/subscription`, data),
  },

  // ── Energy
  energy: {
    logs: (unitKey: string, limit = 50) =>
      apiFetch<EnergyLog[]>('GET', `/energy/${unitKey}?limit=${limit}`),
    summary: (unitKey: string) =>
      apiFetch<EnergySummary>('GET', `/energy/${unitKey}/summary`),
    add: (data: EnergyLogCreate) => apiFetch<EnergyLog>('POST', '/energy/', data),
  },

  // ── Alerts
  alerts: {
    list: (unitKey?: string, limit = 50) =>
      apiFetch<TenantAlert[]>(
        'GET',
        `/tenant-alerts/${unitKey ? unitKey : ''}?limit=${limit}`,
      ),
  },

  // ── Forecast vs Actual
  forecastVsActual: {
    summary: (tenantId: number, period: 'day' | 'week' | 'month' = 'day') =>
      apiFetch<ForecastVsActualSummary>('GET', `/forecast-vs-actual/${tenantId}?period=${period}`),
    chart: (tenantId: number, period: 'day' | 'week' | 'month' = 'week', metric = 'consumption') =>
      apiFetch<ForecastChartResponse>('GET', `/forecast-vs-actual/${tenantId}/chart?period=${period}&metric=${metric}`),
    scorecard: (tenantId: number, date?: string) =>
      apiFetch<ForecastScorecardResponse>('GET', `/forecast-vs-actual/${tenantId}/scorecard${date ? `?date=${date}` : ''}`),
    history: (tenantId: number, metric = 'consumption', fromDate?: string, toDate?: string) => {
      let url = `/forecast-vs-actual/${tenantId}/history?metric=${metric}`
      if (fromDate) url += `&from_date=${fromDate}`
      if (toDate) url += `&to_date=${toDate}`
      return apiFetch<ForecastHistoryResponse>('GET', url)
    },
  },

  // ── Notifications / Email
  notifications: {
    testEmail: (to?: string) =>
      apiFetch<{ sent: boolean; to: string; message: string }>(
        'POST', `/notifications/test-email${to ? `?to=${encodeURIComponent(to)}` : ''}`, {},
      ),
    sendAnomalyAlert: (data: {
      device_id: string; anomaly_score: number; consumption_kwh: number;
      reconstruction_error: number; unit_key?: string;
    }) => apiFetch<{ sent: boolean; to: string; message: string }>('POST', '/notifications/anomaly-alert', data),
    sendBillReport: (data: {
      unit_key?: string; days_elapsed?: number; avg_daily_kwh?: number;
      tariff?: number; avg_temp?: number;
    }) => apiFetch<{ sent: boolean; to: string; message: string }>('POST', '/notifications/bill-report', data),
  },

  // ── Settings
  settings: {
    getProfile: () => apiFetch<SettingsProfile>('GET', '/settings/profile'),
    updateProfile: (data: { username?: string; email?: string }) =>
      apiFetch<SettingsProfile>('PUT', '/settings/profile', data),
    changePassword: (data: { current_password: string; new_password: string }) =>
      apiFetch<{ message: string }>('PUT', '/settings/change-password', data),
    systemStatus: () => apiFetch<SystemStatus>('GET', '/settings/system'),
  },
}
