import { useEffect, useState } from "react";
import {
  Zap, AlertTriangle, Building2, Cpu, IndianRupee,
  Home, Store, Factory, Crown,
} from "lucide-react";
import { apartmentApi } from "../api/client";
import type { TenantDetail } from "../api/types";

const TYPE_ICONS: Record<string, typeof Home> = {
  home: Home, commercial: Store, industrial: Factory,
};

const TYPE_COLORS: Record<string, string> = {
  home:        "bg-green-100 text-green-700 border-green-300",
  commercial:  "bg-purple-100 text-purple-700 border-purple-300",
  industrial:  "bg-orange-100 text-orange-700 border-orange-300",
};

const PLAN_COLORS: Record<string, string> = {
  basic:      "bg-gray-100 text-gray-700 border-gray-300",
  pro:        "bg-blue-100 text-blue-700 border-blue-300",
  enterprise: "bg-amber-100 text-amber-700 border-amber-300",
};

type TabKey = "devices" | "buildings" | "billing";

export default function MyUnitPage() {
  const [detail, setDetail] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("devices");

  useEffect(() => {
    setLoading(true);
    apartmentApi.tenants.myUnit()
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-gray-500">Loading your unit details...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <p className="text-gray-500">No unit linked to your account yet.</p>
        <p className="text-sm text-gray-400">Contact the admin to assign a unit to your account.</p>
      </div>
    );
  }

  const t = detail.tenant;
  const TypeIcon = TYPE_ICONS[t.tenant_type ?? "home"] ?? Home;
  const sub = detail.subscription;

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: "devices",   label: "Devices",   count: detail.device_count },
    { key: "buildings", label: "Buildings", count: detail.building_count },
    { key: "billing",   label: "Billing",   count: sub ? 1 : 0 },
  ];

  return (
    <div className="text-gray-900">
      <div className="max-w-6xl mx-auto px-6 py-8">

        {/* Tenant Header Card */}
        <div className="bg-white rounded-3xl border border-sky-100 shadow-sm p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            {/* Avatar */}
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-2xl font-black text-white shadow-lg flex-shrink-0">
              {t.image ? (
                <img src={t.image} alt={t.name} className="rounded-2xl w-16 h-16 object-cover" />
              ) : (
                t.name.charAt(0).toUpperCase()
              )}
            </div>

            {/* Name + badges */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl font-black text-gray-900 truncate">{t.name}</h1>
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border capitalize ${TYPE_COLORS[t.tenant_type ?? ""] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                  <TypeIcon size={10} /> {t.tenant_type || "home"}
                </span>
                <span className={`text-xs px-2.5 py-0.5 rounded-full border font-semibold capitalize ${PLAN_COLORS[t.subscription_plan ?? "basic"] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                  <Crown size={10} className="inline mr-1" />{t.subscription_plan || "basic"}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${t.is_active ? "bg-emerald-100 text-emerald-700 border border-emerald-300" : "bg-gray-100 text-gray-500 border border-gray-300"}`}>
                  {t.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <p className="text-gray-500 text-sm mt-1">{t.email} · Unit: <span className="font-mono text-blue-600">{t.unit_key}</span></p>
            </div>
          </div>

          {/* KPI Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
            <div className="bg-sky-50 rounded-2xl p-4 border border-sky-100 text-center">
              <Cpu size={18} className="mx-auto text-violet-600 mb-1" />
              <p className="text-2xl font-black text-gray-900">{detail.device_count}/{detail.device_limit}</p>
              <p className="text-xs text-gray-500">Devices</p>
            </div>
            <div className="bg-sky-50 rounded-2xl p-4 border border-sky-100 text-center">
              <Zap size={18} className="mx-auto text-emerald-600 mb-1" />
              <p className="text-2xl font-black text-gray-900">{detail.total_consumption_kwh}</p>
              <p className="text-xs text-gray-500">kWh Total</p>
            </div>
            <div className="bg-sky-50 rounded-2xl p-4 border border-sky-100 text-center">
              <IndianRupee size={18} className="mx-auto text-amber-600 mb-1" />
              <p className="text-2xl font-black text-gray-900">{sub ? `₹${sub.price_per_month}` : "—"}</p>
              <p className="text-xs text-gray-500">Monthly Cost</p>
            </div>
            <div className="bg-sky-50 rounded-2xl p-4 border border-sky-100 text-center">
              <AlertTriangle size={18} className="mx-auto text-red-500 mb-1" />
              <p className="text-2xl font-black text-gray-900">{detail.active_alerts}</p>
              <p className="text-xs text-gray-500">Active Alerts</p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white rounded-2xl border border-sky-100 p-1 w-fit">
          {tabs.map((tb) => (
            <button key={tb.key} onClick={() => setTab(tb.key)}
              className={`px-5 py-2 rounded-xl text-sm font-semibold transition ${
                tab === tb.key
                  ? "bg-blue-600 text-white shadow-md"
                  : "text-gray-600 hover:bg-sky-50"
              }`}>
              {tb.label}
              <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
                tab === tb.key ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-500"
              }`}>{tb.count}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-3xl border border-sky-100 shadow-sm p-6 min-h-[300px]">

          {/* Devices Tab */}
          {tab === "devices" && (
            <div>
              <h3 className="text-lg font-bold mb-4">Devices</h3>
              {detail.devices.length === 0 ? (
                <p className="text-gray-500 text-sm">No devices assigned to your unit.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {detail.devices.map((d) => (
                    <div key={d.id} className="p-4 rounded-2xl border border-sky-100 bg-sky-50">
                      <div className="flex items-center gap-2 mb-2">
                        <Cpu size={14} className="text-violet-600" />
                        <span className="font-mono text-sm font-bold text-gray-900">{d.device_id || `Device #${d.id}`}</span>
                      </div>
                      <p className="text-xs text-gray-500">Unit: <span className="font-mono text-blue-600">{d.unit_key}</span></p>
                      {d.bacnet_object_no != null && (
                        <p className="text-xs text-gray-500">BACnet: {d.bacnet_object_no}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Buildings Tab */}
          {tab === "buildings" && (
            <div>
              <h3 className="text-lg font-bold mb-4">Buildings</h3>
              {detail.buildings.length === 0 ? (
                <p className="text-gray-500 text-sm">No buildings added yet.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {detail.buildings.map((b) => (
                    <div key={b.id} className="p-4 rounded-2xl border border-sky-100 bg-sky-50">
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 size={14} className="text-purple-600" />
                        <span className="font-bold text-sm text-gray-900">{b.name}</span>
                      </div>
                      {b.address && <p className="text-xs text-gray-500">{b.address}</p>}
                      <div className="flex gap-3 mt-1">
                        {b.area_sqm && <span className="text-xs text-gray-500">{b.area_sqm} m²</span>}
                        {b.floor_count && <span className="text-xs text-gray-500">{b.floor_count} floors</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Billing Tab */}
          {tab === "billing" && (
            <div>
              <h3 className="text-lg font-bold mb-4">Subscription & Billing</h3>
              {sub ? (
                <div className="p-4 rounded-2xl border border-sky-100 bg-sky-50 max-w-md">
                  <div className="flex items-center gap-2 mb-3">
                    <Crown size={16} className="text-amber-600" />
                    <span className="font-bold capitalize text-gray-900">{sub.plan} Plan</span>
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-semibold ${
                      sub.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
                    }`}>{sub.status}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                    <p>Monthly Price:</p><p className="font-semibold text-gray-900">₹{sub.price_per_month}</p>
                    <p>Max Devices:</p><p className="font-semibold text-gray-900">{sub.max_devices}</p>
                    <p>Max Users:</p><p className="font-semibold text-gray-900">{sub.max_users}</p>
                    <p>Max Buildings:</p><p className="font-semibold text-gray-900">{sub.max_buildings}</p>
                    {sub.starts_at && <><p>Start Date:</p><p className="font-semibold text-gray-900">{sub.starts_at}</p></>}
                    {sub.ends_at && <><p>End Date:</p><p className="font-semibold text-gray-900">{sub.ends_at}</p></>}
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No active subscription found.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
