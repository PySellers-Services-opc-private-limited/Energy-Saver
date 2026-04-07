import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apartmentApi } from "../api/client";

interface FormData {
  name: string;
  email: string;
  phone: string;
  unit_key: string;
  image: string;
  tenant_type: string;
  subscription_plan: string;
  timezone: string;
  currency: string;
}

const EMPTY: FormData = {
  name: "",
  email: "",
  phone: "",
  unit_key: "",
  image: "",
  tenant_type: "home",
  subscription_plan: "basic",
  timezone: "UTC",
  currency: "INR",
};

// ── Defined OUTSIDE AddTenant so React never remounts it on re-render ──────
interface FieldProps {
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}

function Field({ label, value, onChange, type = "text", placeholder, required = false }: FieldProps) {
  return (
    <div>
      <label className="text-xs text-gray-700 mb-1 block">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <input
        type={type}
        required={required}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}
// ──────────────────────────────────────────────────────────────────────────────

export default function AddTenant() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const set = (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

  // Resize image to max 300×300 then convert to base64 (keeps payload small)
  const handleImagePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      const MAX = 300;
      const scale = Math.min(MAX / img.width, MAX / img.height, 1);
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      const base64 = canvas.toDataURL("image/jpeg", 0.85);
      setForm((prev) => ({ ...prev, image: base64 }));
      URL.revokeObjectURL(objectUrl);
    };
    img.src = objectUrl;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apartmentApi.tenants.create(form);
      navigate("/tenants");
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Error adding tenant";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-sky-50 text-gray-900 flex items-start justify-center pt-12 px-4">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate("/tenants")}
            className="text-gray-500 hover:text-gray-900 text-sm mb-4 flex items-center gap-1 transition"
          >
            ← Back to Tenants
          </button>
          <h1 className="text-3xl font-bold">🏢 Add New Tenant</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Fill in the details below. <span className="text-blue-400 font-semibold">unit_key</span>{" "}
            is permanent and used as the BACnet device identifier.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-300 text-red-600 rounded-xl px-4 py-3 text-sm mb-4">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="space-y-4 bg-white border border-sky-100 p-6 rounded-2xl shadow-sm"
        >
          {/* Profile Image Upload Box */}
          <div className="flex flex-col items-center gap-2">
            <label className="text-xs text-gray-400">Profile Photo</label>
            <div
              onClick={() => fileInputRef.current?.click()}
              style={{ width: 112, height: 112, flexShrink: 0 }}
              className="rounded-2xl border-2 border-dashed border-gray-300 hover:border-blue-500 cursor-pointer overflow-hidden flex items-center justify-center bg-sky-50 transition-colors"
            >
              {form.image ? (
                <img
                  src={form.image}
                  alt="Preview"
                  style={{ width: 112, height: 112, objectFit: "cover", display: "block" }}
                />
              ) : (
                <div className="flex flex-col items-center gap-1 text-gray-500">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                  </svg>
                  <span className="text-xs">Upload</span>
                </div>
              )}
            </div>
            {form.image && (
              <button
                type="button"
                onClick={() => setForm((p) => ({ ...p, image: "" }))}
                className="text-xs text-red-400 hover:text-red-300 transition"
              >
                ✕ Remove
              </button>
            )}
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleImagePick}
            />
          </div>

          {/* Row: Name + Unit Key */}
          <div className="grid grid-cols-2 gap-4">
            <Field
              label="Full Name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              required
              placeholder="e.g. John Doe"
            />
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                Unit Key <span className="text-red-400">*</span>{" "}
                <span className="text-blue-400">(BACnet / Primary ID)</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. A101"
                value={form.unit_key}
                onChange={set("unit_key")}
                className="w-full bg-white border border-blue-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <Field
            label="Email Address"
            value={form.email}
            onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
            type="email"
            required
            placeholder="john@example.com"
          />

          <Field
            label="Phone"
            value={form.phone}
            onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value }))}
            placeholder="+1 555 000 0000"
          />

          {/* Row: Type + Plan */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-700 mb-1 block">Tenant Type</label>
              <select
                value={form.tenant_type}
                onChange={set("tenant_type")}
                className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="home">Home</option>
                <option value="commercial">Commercial</option>
                <option value="industrial">Industrial</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-700 mb-1 block">Subscription Plan</label>
              <select
                value={form.subscription_plan}
                onChange={set("subscription_plan")}
                className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="basic">Basic — ₹499/mo</option>
                <option value="pro">Pro — ₹1,999/mo</option>
                <option value="enterprise">Enterprise — ₹7,999+/mo</option>
              </select>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate("/tenants")}
              className="flex-1 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl bg-green-600 hover:bg-green-700 font-semibold text-sm transition disabled:opacity-50"
            >
              {loading ? "Adding…" : "✅ Add Tenant"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
