// ── Shared API types matching backend Pydantic schemas ─────────────────────

export interface KPISummary {
  total_consumption_kwh: number
  anomalies_detected: number
  occupancy_rate: number
  solar_generation_kwh: number
  current_tariff: number
  estimated_savings_today: number
  peak_demand_kw: number
  timestamp: string
}

export interface ForecastPoint {
  timestamp: string
  predicted_kwh: number
  lower_bound: number
  upper_bound: number
}

export interface ForecastResponse {
  device_id: string
  horizon_hours: number
  forecasts: ForecastPoint[]
}

export interface AnomalyEvent {
  device_id: string
  timestamp: string
  anomaly_score: number
  is_anomaly: boolean
  consumption_kwh: number
  reconstruction_error: number
}

export interface AnomalyResponse {
  total: number
  anomalies: AnomalyEvent[]
}

export interface HVACCommandRequest {
  zone_id?: string
  mode: 'COMFORT' | 'ECO' | 'DEMAND_RESPONSE' | 'PRE_CONDITION' | 'OFF'
  setpoint_c: number
}

export interface HVACCommandResponse {
  zone_id: string
  mode: string
  setpoint_c: number
  estimated_saving_pct: number
  issued_at: string
}

export interface HVACStatus {
  zone_id: string
  mode: string
  setpoint_c: number
  estimated_saving_pct: number
  last_updated: string
}

export interface SavingsRequest {
  baseline_kwh_per_day: number
  tariff_per_kwh: number
}

export interface SavingsBreakdown {
  hvac_kwh_per_year: number
  ev_kwh_per_year: number
  anomaly_kwh_per_year: number
}

export interface SavingsResponse {
  kwh_saved_per_day: number
  kwh_saved_per_year: number
  cost_saved_per_year: number
  co2_saved_kg_per_year: number
  breakdown: SavingsBreakdown
}

export interface ModelInfo {
  name: string
  version: string
  loaded: boolean
  path: string
  metrics: Record<string, unknown>
}

export interface ModelListResponse {
  models: ModelInfo[]
}

export interface PipelineStatus {
  running: boolean
  mode: string
  uptime_s: number
  messages_processed: number
  anomalies_detected: number
  kafka_connected: boolean
  mqtt_connected: boolean
  ws_clients: number
}

export interface LiveReading {
  device_id: string
  timestamp: string
  consumption_kwh: number
  temperature: number
  humidity: number
  occupancy: number
  solar_kwh: number
  tariff: number
  anomaly_score: number
}

// ── Smart Apartment — Tenants ─────────────────────────────────────────────────

export interface Tenant {
  id: number
  name: string
  email: string
  phone: string | null
  unit_key: string
  image: string | null
  tenant_type: string | null
  subscription_plan: string | null
  timezone: string
  currency: string
  is_active: boolean
  plan_start_date: string | null
  plan_end_date: string | null
  created_at: string
  updated_at: string | null
}

export interface TenantCreate {
  name: string
  email: string
  phone?: string
  unit_key: string
  image?: string
  tenant_type?: string
  subscription_plan?: string
  timezone?: string
  currency?: string
}

export interface TenantUpdate extends Partial<TenantCreate> {
  is_active?: boolean
}

export interface Building {
  id: number
  tenant_id: number
  name: string
  address: string | null
  area_sqm: number | null
  floor_count: number | null
  is_active: boolean
  created_at: string
}

export interface BuildingCreate {
  name: string
  address?: string
  area_sqm?: number
  floor_count?: number
}

export interface SubscriptionInfo {
  id: number
  tenant_id: number
  plan: string
  max_devices: number
  max_users: number
  max_buildings: number
  price_per_month: number
  billing_cycle: string
  status: string
  starts_at: string
  ends_at: string | null
  created_at: string
}

export interface TenantStats {
  total_tenants: number
  active_tenants: number
  by_type: Record<string, number>
  by_plan: Record<string, number>
  total_devices: number
  total_consumption_kwh: number
  active_alerts: number
}

export interface TenantDetail {
  tenant: Tenant
  device_count: number
  device_limit: number
  total_consumption_kwh: number
  active_alerts: number
  building_count: number
  buildings: Building[]
  subscription: SubscriptionInfo | null
  devices: DeviceInfo[]
}

export interface DeviceInfo {
  id: number
  device_id: string | null
  unit_key: string
  bacnet_object_no: number | null
}

// ── Smart Apartment — Energy ──────────────────────────────────────────────────

export interface EnergyLog {
  id: number
  unit_key: string
  timestamp: string
  voltage: number | null
  current: number | null
  power: number | null
  consumption: number
}

export interface EnergyLogCreate {
  unit_key: string
  voltage?: number
  current?: number
  power?: number
  consumption: number
}

export interface EnergySummary {
  unit_key: string
  count: number
  avg_kwh: number
  max_kwh: number
  total_kwh: number
}

// ── Smart Apartment — Alerts ──────────────────────────────────────────────────

export interface TenantAlert {
  id: number
  unit_key: string
  message: string
  created_at: string
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface UserCreate {
  username: string
  email: string
  password: string
  role?: 'admin' | 'tenant'
  unit_key?: string
}

export interface UserLogin {
  email: string
  password: string
}

export interface UserResponse {
  id: number
  username: string
  email: string
  role: string
  unit_key?: string | null
  is_active: boolean
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  user?: UserResponse
}

// ── Forecast vs Actual ──────────────────────────────────────────────────────

export interface ForecastMetricCard {
  name: string
  forecast: number
  actual: number
  delta: number
  delta_pct: number
  rag: 'green' | 'amber' | 'red'
  unit: string
  direction: 'up' | 'down' | 'neutral'
}

export interface ForecastVsActualSummary {
  tenant_id: number
  period: string
  date: string
  overall_rag: 'green' | 'amber' | 'red'
  metrics: Record<string, {
    forecast_kwh?: number
    actual_kwh?: number
    forecast_inr?: number
    actual_inr?: number
    forecast_kw?: number
    actual_kw?: number
    delta_kwh?: number
    delta_inr?: number
    delta_kw?: number
    delta_pct: number
    rag: 'green' | 'amber' | 'red'
    label: string
    forecast?: number
    actual?: number
  }>
  model_accuracy: {
    model_1_mape: number
    model_1_mae_kwh: number
    accuracy_pct: number
  }
}

export interface ForecastChartPoint {
  date: string
  forecast: number
  actual: number
  delta_pct: number
  rag: 'green' | 'amber' | 'red'
}

export interface ForecastChartResponse {
  tenant_id: number
  metric: string
  period: string
  points: ForecastChartPoint[]
}

export interface ForecastScorecardResponse {
  tenant_id: number
  date: string
  overall_rag: 'green' | 'amber' | 'red'
  cards: ForecastMetricCard[]
  model_accuracy: {
    mape: number
    mae: number
    accuracy_pct: number
  }
}

export interface ForecastHistoryResponse {
  tenant_id: number
  metric: string
  from_date: string
  to_date: string
  points: ForecastChartPoint[]
  avg_accuracy_pct: number
}

// ── Bill Prediction (Model 8) ────────────────────────────────────────────────

export interface BillPrediction {
  predicted_bill: number
  lower_bound: number
  upper_bound: number
  confidence_pct: number
  daily_budget: number
  remaining_budget: number
  days_elapsed: number
  kwh_so_far: number
  projected_kwh: number
  model: 'real' | 'fallback'
  timestamp: string
}

// ── Solar Forecast (Model 6) ─────────────────────────────────────────────────

export interface SolarHourly {
  timestamp: string
  solar_kwh: number
  hour: number
}

export interface SolarForecast {
  system_kw: number
  hourly_forecast: SolarHourly[]
  total_24h_kwh: number
  estimated_daily_savings_inr: number
  estimated_annual_savings_inr: number
  model: 'real' | 'fallback'
  timestamp: string
}

// ── EV Charging Optimizer (Model 7) ──────────────────────────────────────────

export interface EVSlot {
  timestamp: string
  hour: number
  action: 'no_charge' | 'slow_charge' | 'fast_charge'
  soc_pct: number
  kwh_added: number
  tariff_inr: number
  cost_inr: number
}

export interface EVSchedule {
  schedule: EVSlot[]
  final_soc_pct: number
  total_kwh_charged: number
  total_cost_inr: number
  savings_vs_naive_inr: number
  departure_hour: number
  target_soc_pct: number
  model: 'real' | 'fallback'
  timestamp: string
}

// ── Appliance Fingerprinting (Model 5) ───────────────────────────────────────

export interface ApplianceResult {
  identified_appliance: string
  confidence_pct: number
  top_predictions: { appliance: string; confidence: number }[]
  power_readings_count: number
  model: 'real' | 'fallback'
  timestamp: string
}

export interface ApplianceInfo {
  name: string
  typical_power_kw: number
}

// ── Settings ─────────────────────────────────────────────────────────────────

export interface SettingsProfile {
  id: number
  username: string
  email: string
  role: string
  unit_key: string | null
  is_active: boolean
  created_at: string
}

export interface SystemStatus {
  version: string
  python_version: string
  database: string
  uptime_seconds: number
  total_users: number
  total_tenants: number
  total_devices: number
  os_platform: string
}
