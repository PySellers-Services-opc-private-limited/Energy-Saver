import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Building2, Home, Star, Zap, AlertTriangle, IndianRupee,
  Search, Plus, Edit2, Trash2, Eye, Factory, Store, ChevronRight, Mail,
} from "lucide-react";
import { apartmentApi } from "../api/client";
import type { Tenant, TenantStats } from "../api/types";

// ── Helpers ──────────────────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, string> = {
  basic:      "bg-gray-100 text-gray-700 border-gray-300",
  pro:        "bg-blue-100 text-blue-700 border-blue-300",
  enterprise: "bg-amber-100 text-amber-700 border-amber-300",
};

const PLAN_PRICES: Record<string, string> = {
  basic: "₹499/mo", pro: "₹1,999/mo", enterprise: "₹7,999+/mo",
};

const TYPE_ICONS: Record<string, typeof Home> = {
  home: Home, commercial: Store, industrial: Factory,
};

const TYPE_COLORS: Record<string, string> = {
  home:        "bg-green-100 text-green-700 border-green-300",
  commercial:  "bg-purple-100 text-purple-700 border-purple-300",
  industrial:  "bg-orange-100 text-orange-700 border-orange-300",
};

const AVATAR_GRADIENTS = [
  "from-blue-500 to-cyan-500",
  "from-violet-500 to-purple-600",
  "from-emerald-500 to-teal-600",
  "from-rose-500 to-pink-600",
  "from-amber-500 to-orange-500",
  "from-sky-500 to-indigo-600",
];

type ToastType = "success" | "error" | "info";
interface Toast { id: number; msg: string; type: ToastType; }
let _toastId = 0;

function resizeImageFile(file: File, maxPx = 300): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(maxPx / img.width, maxPx / img.height, 1);
      const c = document.createElement("canvas");
      c.width  = Math.round(img.width  * scale);
      c.height = Math.round(img.height * scale);
      c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
      resolve(c.toDataURL("image/jpeg", 0.85));
      URL.revokeObjectURL(url);
    };
    img.src = url;
  });
}

interface TenantFormData {
  name: string; email: string; phone: string; unit_key: string;
  image: string; tenant_type: string; subscription_plan: string;
  timezone: string; currency: string;
}

const EMPTY_FORM: TenantFormData = {
  name: "", email: "", phone: "", unit_key: "", image: "",
  tenant_type: "home", subscription_plan: "basic",
  timezone: "UTC", currency: "INR",
};

// ── Main Component ───────────────────────────────────────────────────────────

export default function TenantsPage() {
  const navigate = useNavigate();
  const [tenants,  setTenants]  = useState<Tenant[]>([]);
  const [stats,    setStats]    = useState<TenantStats | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [search,   setSearch]   = useState("");

  const [editTarget,      setEditTarget]      = useState<Tenant | null>(null);
  const [showEditModal,   setShowEditModal]   = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget,    setDeleteTarget]    = useState<Tenant | null>(null);

  const [form,       setForm]       = useState<TenantFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [toasts,     setToasts]     = useState<Toast[]>([]);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();
  const editFileRef = useRef<HTMLInputElement>(null);
  const [sendingEmail, setSendingEmail] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tenantList, tenantStats] = await Promise.all([
        apartmentApi.tenants.list(),
        apartmentApi.tenants.stats(),
      ]);
      setTenants(tenantList);
      setStats(tenantStats);
    } catch { toast("Failed to load tenants.", "error"); }
    finally  { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, []);

  const toast = (msg: string, type: ToastType = "info") => {
    const id = ++_toastId;
    setToasts((prev) => [...prev, { id, msg, type }]);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(
      () => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500
    );
  };

  const confirmDelete = (t: Tenant) => { setDeleteTarget(t); setShowDeleteModal(true); };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await apartmentApi.tenants.delete(deleteTarget.id);
      toast(`Tenant "${deleteTarget.name}" has been deactivated.`, "success");
      setShowDeleteModal(false);
      setDeleteTarget(null);
      fetchData();
    } catch { toast("Delete failed. Please try again.", "error"); }
  };

  const sendTestEmail = async (emailOrUnitKey?: string) => {
    setSendingEmail(true);
    try {
      const res = await apartmentApi.notifications.testEmail(emailOrUnitKey);
      toast(`Email sent to ${res.to}`, "success");
    } catch {
      toast("Failed to send email.", "error");
    } finally { setSendingEmail(false); }
  };

  const openEdit = (t: Tenant) => {
    setEditTarget(t);
    setForm({
      name: t.name, email: t.email, phone: t.phone ?? "",
      unit_key: t.unit_key, image: t.image ?? "",
      tenant_type: t.tenant_type ?? "home",
      subscription_plan: t.subscription_plan ?? "basic",
      timezone: t.timezone ?? "UTC", currency: t.currency ?? "INR",
    });
    setShowEditModal(true);
  };

  const handleEditImagePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const b64 = await resizeImageFile(file);
    setForm((p) => ({ ...p, image: b64 }));
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTarget) return;
    setSubmitting(true);
    try {
      await apartmentApi.tenants.update(editTarget.id, form);
      toast("Tenant details updated successfully.", "success");
      setShowEditModal(false);
      setEditTarget(null);
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Update failed.";
      toast(msg, "error");
    } finally { setSubmitting(false); }
  };

  const filtered = tenants.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.unit_key.toLowerCase().includes(search.toLowerCase()) ||
    t.email.toLowerCase().includes(search.toLowerCase())
  );

  // Stats cards
  const statCards = [
    {
      label: "Total Tenants",
      value: stats?.total_tenants ?? tenants.length,
      Icon: Users,
      grad: "from-blue-600 to-cyan-500",
      iconBg: "bg-blue-100 text-blue-600",
    },
    {
      label: "Total Devices",
      value: stats?.total_devices ?? 0,
      Icon: Zap,
      grad: "from-violet-600 to-purple-500",
      iconBg: "bg-violet-100 text-violet-600",
    },
    {
      label: "Consumption (kWh)",
      value: stats?.total_consumption_kwh?.toFixed(1) ?? "0",
      Icon: IndianRupee,
      grad: "from-emerald-600 to-teal-500",
      iconBg: "bg-emerald-100 text-emerald-600",
    },
    {
      label: "Active Alerts",
      value: stats?.active_alerts ?? 0,
      Icon: AlertTriangle,
      grad: "from-amber-500 to-orange-500",
      iconBg: "bg-amber-100 text-amber-600",
    },
  ];

  return (
    <div className="min-h-screen bg-sky-50 text-gray-900">

      {/* Toast Notifications */}
      <div className="fixed top-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id}
            className={`px-5 py-3 rounded-xl shadow-2xl text-sm font-semibold backdrop-blur-md border transition-all text-white ${
              t.type === "success" ? "bg-emerald-600/90 border-emerald-400" :
              t.type === "error"   ? "bg-red-600/90 border-red-400" :
                                     "bg-blue-600/90 border-blue-400"
            }`}>
            {t.msg}
          </div>
        ))}
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">

        {/* Page Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-10">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-gray-900">
              Tenant Management
            </h1>
            <p className="text-gray-500 mt-1 text-sm">
              Multi-tenant SaaS platform — Homes, Offices &amp; Buildings
            </p>
          </div>
          <div className="flex gap-3">
            <button
              disabled={sendingEmail}
              onClick={() => sendTestEmail()}
              className="inline-flex items-center gap-2 font-bold text-sm px-5 py-3 rounded-2xl transition-all active:scale-95 shadow-lg shadow-emerald-500/20 text-white disabled:opacity-50"
              style={{ background: "linear-gradient(135deg,#10b981,#059669)" }}>
              <Mail size={16} /> {sendingEmail ? "Sending..." : "Send Test Email"}
            </button>
            <button
              onClick={() => navigate("/add-tenant")}
              className="inline-flex items-center gap-2 font-bold text-sm px-6 py-3 rounded-2xl transition-all active:scale-95 shadow-lg shadow-blue-500/20 text-white"
              style={{ background: "linear-gradient(135deg,#3b82f6,#06b6d4)" }}>
              <Plus size={16} /> Add Tenant
            </button>
          </div>
        </div>

        {/* Statistics Overview */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {statCards.map((s) => (
            <div key={s.label}
              className="relative overflow-hidden rounded-2xl p-5 bg-white border border-sky-100 shadow-sm">
              <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl ${s.iconBg} mb-3`}>
                <s.Icon size={20} />
              </div>
              <p className="text-3xl font-black text-gray-900">{s.value}</p>
              <p className="text-gray-500 text-xs mt-1 font-medium">{s.label}</p>
              <div className={`absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br ${s.grad} opacity-10 blur-xl`} />
            </div>
          ))}
        </div>

        {/* Plan breakdown mini-bar */}
        {stats && (
          <div className="flex flex-wrap gap-3 mb-8">
            {Object.entries(stats.by_plan).map(([plan, count]) => (
              <div key={plan} className={`px-3 py-1.5 rounded-full border text-xs font-semibold capitalize ${PLAN_COLORS[plan] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                {plan}: {count}
              </div>
            ))}
            {Object.entries(stats.by_type).map(([type, count]) => (
              <div key={type} className={`px-3 py-1.5 rounded-full border text-xs font-semibold capitalize ${TYPE_COLORS[type] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                {type}: {count}
              </div>
            ))}
          </div>
        )}

        {/* Search Bar */}
        <div className="mb-7 relative max-w-sm">
          <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, unit or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-3 rounded-2xl text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 border border-sky-200"
          />
        </div>

        {/* Tenant Cards */}
        {loading ? (
          <div className="flex justify-center py-24 text-gray-500">Loading tenants...</div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-24 gap-4 text-gray-500">
            <div className="w-16 h-16 rounded-full bg-gray-100 border border-gray-200 flex items-center justify-center text-2xl font-black text-gray-400">0</div>
            <p>{search ? "No tenants match your search." : "No tenants yet."}</p>
            {!search && (
              <button onClick={() => navigate("/add-tenant")} className="text-blue-500 hover:text-blue-600 text-sm underline">
                Add your first tenant
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filtered.map((t, i) => {
              const grad = AVATAR_GRADIENTS[i % AVATAR_GRADIENTS.length];
              const TypeIcon = TYPE_ICONS[t.tenant_type ?? "home"] ?? Home;
              return (
                <div key={t.id}
                  className="group relative rounded-3xl overflow-hidden border border-sky-100 bg-white shadow-sm transition-all duration-300 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-100 hover:-translate-y-1">

                  {/* Colored top strip */}
                  <div className={`h-1.5 w-full bg-gradient-to-r ${grad}`} />

                  <div className="p-5 flex flex-col h-full">

                    {/* Header: Photo + Badges */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="relative">
                        {t.image ? (
                          <img src={t.image} alt={t.name}
                            style={{ width: 64, height: 64, objectFit: "cover" }}
                            className="rounded-2xl ring-2 ring-white/10 shadow-lg" />
                        ) : (
                          <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${grad} flex items-center justify-center text-2xl font-black shadow-lg ring-2 ring-white/10 text-white`}>
                            {t.name.charAt(0).toUpperCase()}
                          </div>
                        )}
                        {/* Status indicator */}
                        <span className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-white shadow ${t.is_active ? "bg-emerald-400" : "bg-gray-400"}`} />
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {/* Type badge */}
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border capitalize ${TYPE_COLORS[t.tenant_type ?? ""] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                          <TypeIcon size={10} /> {t.tenant_type || "home"}
                        </span>
                        {/* Plan badge */}
                        {t.subscription_plan && (
                          <span className={`text-xs px-2.5 py-0.5 rounded-full border font-semibold capitalize ${PLAN_COLORS[t.subscription_plan] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
                            {t.subscription_plan}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Name + Email */}
                    <h3 className="font-bold text-base leading-tight truncate text-gray-900">{t.name}</h3>
                    <p className="text-gray-500 text-xs mt-0.5 truncate">{t.email}</p>

                    {/* Detail rows */}
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 w-14 flex-shrink-0">Unit</span>
                        <span className="bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold tracking-wide truncate max-w-[120px]">
                          {t.unit_key}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 w-14 flex-shrink-0">Status</span>
                        <span className={`text-xs font-semibold ${t.is_active ? "text-emerald-600" : "text-gray-400"}`}>
                          {t.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 w-14 flex-shrink-0">Plan</span>
                        <span className="text-xs text-gray-600">
                          {PLAN_PRICES[t.subscription_plan ?? "basic"] ?? "₹499/mo"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 w-14 flex-shrink-0">Added</span>
                        <span className="text-xs text-gray-400">
                          {new Date(t.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                        </span>
                      </div>
                    </div>

                    <div className="flex-1" />

                    {/* Actions */}
                    <div className="flex gap-2 mt-4 pt-4 border-t border-sky-100">
                      <button onClick={() => navigate(`/tenants/${t.id}`)}
                        className="flex-1 py-2 rounded-xl text-xs font-semibold transition active:scale-95 border border-sky-200 text-sky-600 hover:bg-sky-50 flex items-center justify-center gap-1">
                        <Eye size={12} /> View
                      </button>
                      <button onClick={() => openEdit(t)}
                        className="flex-1 py-2 rounded-xl text-xs font-semibold transition active:scale-95 border border-blue-200 text-blue-600 hover:bg-blue-50 flex items-center justify-center gap-1">
                        <Edit2 size={12} /> Edit
                      </button>
                      <button onClick={() => sendTestEmail(t.unit_key)} disabled={sendingEmail}
                        className="flex-1 py-2 rounded-xl text-xs font-semibold transition active:scale-95 border border-emerald-200 text-emerald-600 hover:bg-emerald-50 flex items-center justify-center gap-1 disabled:opacity-50">
                        <Mail size={12} /> Email
                      </button>
                      <button onClick={() => confirmDelete(t)}
                        className="flex-1 py-2 rounded-xl text-xs font-semibold transition active:scale-95 border border-red-200 text-red-500 hover:bg-red-50 flex items-center justify-center gap-1">
                        <Trash2 size={12} /> Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Edit Tenant Modal */}
      {showEditModal && editTarget && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-lg rounded-3xl border border-sky-100 shadow-2xl p-7 bg-white max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-black text-gray-900">Edit Tenant</h2>
              <button onClick={() => setShowEditModal(false)}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 hover:text-gray-900 transition text-sm font-bold">
                X
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4">
              {/* Profile Photo */}
              <div className="flex flex-col items-center gap-2">
                <label className="text-xs text-gray-400">Profile Photo</label>
                <div onClick={() => editFileRef.current?.click()}
                  style={{ width: 96, height: 96 }}
                  className="rounded-2xl border-2 border-dashed border-gray-300 hover:border-blue-500 cursor-pointer overflow-hidden flex items-center justify-center bg-sky-50 transition-colors">
                  {form.image ? (
                    <img src={form.image} alt="preview" style={{ width: 96, height: 96, objectFit: "cover" }} />
                  ) : (
                    <span className="text-gray-500 text-xs">Upload</span>
                  )}
                </div>
                {form.image && (
                  <button type="button" onClick={() => setForm((p) => ({ ...p, image: "" }))}
                    className="text-xs text-red-400 hover:text-red-300 transition">Remove</button>
                )}
                <input ref={editFileRef} type="file" accept="image/*" className="hidden" onChange={handleEditImagePick} />
              </div>

              {/* Name + Unit Key */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Full Name *</label>
                  <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Unit Key *</label>
                  <input required value={form.unit_key} onChange={(e) => setForm({ ...form, unit_key: e.target.value })}
                    className="w-full bg-white border border-blue-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-700 mb-1 block">Email *</label>
                <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              <div>
                <label className="text-xs text-gray-700 mb-1 block">Phone</label>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              {/* Type + Plan */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Tenant Type</label>
                  <select value={form.tenant_type} onChange={(e) => setForm({ ...form, tenant_type: e.target.value })}
                    className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="home">Home</option>
                    <option value="commercial">Commercial</option>
                    <option value="industrial">Industrial</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Plan</label>
                  <select value={form.subscription_plan} onChange={(e) => setForm({ ...form, subscription_plan: e.target.value })}
                    className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="basic">Basic — ₹499/mo</option>
                    <option value="pro">Pro — ₹1,999/mo</option>
                    <option value="enterprise">Enterprise — ₹7,999+/mo</option>
                  </select>
                </div>
              </div>

              {/* Timezone + Currency */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Timezone</label>
                  <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                    className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="text-xs text-gray-700 mb-1 block">Currency</label>
                  <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}
                    className="w-full bg-white border border-gray-300 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowEditModal(false)}
                  className="flex-1 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm transition border border-gray-200">
                  Cancel
                </button>
                <button type="submit" disabled={submitting}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white transition active:scale-95 disabled:opacity-50 shadow-lg shadow-blue-500/20"
                  style={{ background: "linear-gradient(135deg,#3b82f6,#06b6d4)" }}>
                  {submitting ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && deleteTarget && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-3xl border border-red-200 shadow-2xl p-7 text-center bg-white">
            <div className="w-16 h-16 rounded-full bg-red-100 border border-red-300 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={28} className="text-red-500" />
            </div>
            <h2 className="text-xl font-black mb-2 text-gray-900">Deactivate Tenant</h2>
            <p className="text-gray-700 text-sm">
              You are about to deactivate{" "}
              <span className="font-bold text-gray-900">{deleteTarget.name}</span>.
            </p>
            <p className="text-gray-500 text-xs mt-2 mb-6">
              Unit <span className="font-mono text-blue-500">{deleteTarget.unit_key}</span> will be
              marked inactive. This can be reversed.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setShowDeleteModal(false)}
                className="flex-1 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm transition border border-gray-200">
                Cancel
              </button>
              <button onClick={handleDelete}
                className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-bold transition active:scale-95">
                Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
