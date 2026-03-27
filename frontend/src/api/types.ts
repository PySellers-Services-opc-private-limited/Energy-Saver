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
