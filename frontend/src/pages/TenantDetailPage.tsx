import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Zap, AlertTriangle, Building2, Cpu, IndianRupee,
  Home, Store, Factory, Crown, Plus,
} from "lucide-react";
import { apartmentApi } from "../api/client";
import type { TenantDetail, Building, BuildingCreate } from "../api/types";

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

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("devices");
  const [showAddBuilding, setShowAddBuilding] = useState(false);
  const [buildingForm, setBuildingForm] = useState<BuildingCreate>({ name: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    apartmentApi.tenants.detail(Number(id))
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [id]);

  const handleAddBuilding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await apartmentApi.tenants.addBuilding(Number(id), buildingForm);
      const updated = await apartmentApi.tenants.detail(Number(id));
      setDetail(updated);
      setShowAddBuilding(false);
      setBuildingForm({ name: "" });
    } catch { /* toast or silent */ }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-sky-50 flex items-center justify-center">
        <div className="text-gray-500">Loading tenant details...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-screen bg-sky-50 flex flex-col items-center justify-center gap-4">
        <p className="text-gray-500">Tenant not found.</p>
        <button onClick={() => navigate("/tenants")} className="text-blue-500 underline text-sm">Back to Tenants</button>
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
    <div className="min-h-screen bg-sky-50 text-gray-900">
      <div className="max-w-6xl mx-auto px-6 py-8">

        {/* Back + Header */}
        <button onClick={() => navigate("/tenants")}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-900 text-sm mb-6 transition">
          <ArrowLeft size={14} /> Back to Tenants
        </button>

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

          {/* ── Devices Tab ── */}
          {tab === "devices" && (
            <div>
              <h3 className="text-lg font-bold mb-4">Devices</h3>
              {detail.devices.length === 0 ? (
                <p className="text-gray-500 text-sm">No devices assigned to this tenant.</p>
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

          {/* ── Buildings Tab ── */}
          {tab === "buildings" && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold">Buildings</h3>
                <button onClick={() => setShowAddBuilding(true)}
                  className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition">
                  <Plus size={12} /> Add Building
                </button>
              </div>

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

              {/* Add Building Modal */}
              {showAddBuilding && (
                <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-900/50 backdrop-blur-sm px-4">
                  <div className="w-full max-w-md rounded-3xl border border-sky-100 shadow-2xl p-7 bg-white">
                    <h2 className="text-lg font-black mb-4">Add Building</h2>
                    <form onSubmit={handleAddBuilding} className="space-y-4">
                      <div>
                        <label className="text-xs text-gray-700 mb-1 block">Building Name *</label>
                        <input required value={buildingForm.name}
                          onChange={(e) => setBuildingForm({ ...buildingForm, name: e.target.value })}
                          className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="text-xs text-gray-700 mb-1 block">Address</label>
                        <input value={buildingForm.address ?? ""}
                          onChange={(e) => setBuildingForm({ ...buildingForm, address: e.target.value })}
                          className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-gray-700 mb-1 block">Area (m²)</label>
                          <input type="number" step="0.01"
                            value={buildingForm.area_sqm ?? ""}
                            onChange={(e) => setBuildingForm({ ...buildingForm, area_sqm: e.target.value ? Number(e.target.value) : undefined })}
                            className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        </div>
                        <div>
                          <label className="text-xs text-gray-700 mb-1 block">Floors</label>
                          <input type="number"
                            value={buildingForm.floor_count ?? ""}
                            onChange={(e) => setBuildingForm({ ...buildingForm, floor_count: e.target.value ? Number(e.target.value) : undefined })}
                            className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button type="button" onClick={() => setShowAddBuilding(false)}
                          className="flex-1 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm border border-gray-200">
                          Cancel
                        </button>
                        <button type="submit" disabled={saving}
                          className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white disabled:opacity-50 shadow-lg shadow-blue-500/20"
                          style={{ background: "linear-gradient(135deg,#3b82f6,#06b6d4)" }}>
                          {saving ? "Adding..." : "Add Building"}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Billing Tab ── */}
          {tab === "billing" && (
            <div>
              <h3 className="text-lg font-bold mb-4">Subscription & Billing</h3>
              {sub ? (
                <div className="p-5 rounded-2xl border border-sky-100 bg-sky-50">
                  <div className="flex items-center gap-3 mb-4">
                    <Crown size={20} className="text-amber-600" />
                    <span className="text-xl font-black capitalize text-gray-900">{sub.plan} Plan</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold capitalize ${
                      sub.status === "active" ? "bg-emerald-100 text-emerald-700 border border-emerald-300" :
                      "bg-gray-100 text-gray-500 border border-gray-300"
                    }`}>{sub.status}</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-gray-500">Price</p>
                      <p className="font-bold text-gray-900">₹{sub.price_per_month}/mo</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Billing Cycle</p>
                      <p className="font-bold capitalize text-gray-900">{sub.billing_cycle}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Max Devices</p>
                      <p className="font-bold text-gray-900">{sub.max_devices === 9999 ? "Unlimited" : sub.max_devices}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Max Buildings</p>
                      <p className="font-bold text-gray-900">{sub.max_buildings === 9999 ? "Unlimited" : sub.max_buildings}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Max Users</p>
                      <p className="font-bold text-gray-900">{sub.max_users === 9999 ? "Unlimited" : sub.max_users}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Started</p>
                      <p className="font-bold text-gray-900">{sub.starts_at}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Ends</p>
                      <p className="font-bold text-gray-900">{sub.ends_at ?? "Ongoing"}</p>
                    </div>
                  </div>

                  {/* Plan comparison */}
                  <div className="mt-6">
                    <h4 className="text-sm font-bold mb-3 text-gray-900">Plan Comparison</h4>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { plan: "basic", price: "₹499/mo", devices: 5, users: 2, buildings: 1 },
                        { plan: "pro", price: "₹1,999/mo", devices: 25, users: 10, buildings: 5 },
                        { plan: "enterprise", price: "₹7,999+/mo", devices: "∞", users: "∞", buildings: "∞" },
                      ].map((p) => (
                        <div key={p.plan}
                          className={`p-4 rounded-2xl border text-center ${
                            sub.plan === p.plan
                              ? "border-blue-300 bg-blue-50 ring-2 ring-blue-200"
                              : "border-sky-100 bg-white"
                          }`}>
                          <p className="font-black capitalize text-sm text-gray-900">{p.plan}</p>
                          <p className="text-lg font-bold text-blue-600 mt-1">{p.price}</p>
                          <div className="mt-2 space-y-1 text-xs text-gray-500">
                            <p>{p.devices} devices</p>
                            <p>{p.users} users</p>
                            <p>{p.buildings} buildings</p>
                          </div>
                          {sub.plan !== p.plan && (
                            <button
                              onClick={async () => {
                                try {
                                  await apartmentApi.tenants.updateSubscription(Number(id), { plan: p.plan });
                                  const updated = await apartmentApi.tenants.detail(Number(id));
                                  setDetail(updated);
                                } catch { /* silent */ }
                              }}
                              className="mt-3 text-xs font-semibold text-blue-600 hover:text-blue-700 underline">
                              Switch to {p.plan}
                            </button>
                          )}
                          {sub.plan === p.plan && (
                            <p className="mt-3 text-xs font-semibold text-emerald-600">Current Plan</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No active subscription.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
