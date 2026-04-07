import { useEffect, useState } from 'react'
import { User, Lock, Server, Save, Eye, EyeOff } from 'lucide-react'
import { apartmentApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import type { SettingsProfile, SystemStatus } from '../api/types'
import { useAuth } from '../context/AuthContext'

export default function SettingsPage() {
  const { user } = useAuth()

  // ── Profile state
  const [profile, setProfile] = useState<SettingsProfile | null>(null)
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [profileMsg, setProfileMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [savingProfile, setSavingProfile] = useState(false)

  // ── Password state
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [pwMsg, setPwMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [savingPw, setSavingPw] = useState(false)

  // ── System state (admin only)
  const [system, setSystem] = useState<SystemStatus | null>(null)

  useEffect(() => {
    apartmentApi.settings.getProfile().then((p) => {
      setProfile(p)
      setUsername(p.username)
      setEmail(p.email)
    }).catch(() => { })

    if (user?.role === 'admin') {
      apartmentApi.settings.systemStatus().then(setSystem).catch(() => { })
    }
  }, [user?.role])

  // ── Save profile
  const saveProfile = async () => {
    setSavingProfile(true)
    setProfileMsg(null)
    try {
      const updated = await apartmentApi.settings.updateProfile({ username, email })
      setProfile(updated)
      setProfileMsg({ text: 'Profile updated successfully', ok: true })
    } catch (e: unknown) {
      setProfileMsg({ text: e instanceof Error ? e.message : 'Failed to update profile', ok: false })
    } finally {
      setSavingProfile(false)
      setTimeout(() => setProfileMsg(null), 4000)
    }
  }

  // ── Change password
  const changePassword = async () => {
    if (newPw !== confirmPw) {
      setPwMsg({ text: 'New passwords do not match', ok: false })
      setTimeout(() => setPwMsg(null), 3000)
      return
    }
    setSavingPw(true)
    setPwMsg(null)
    try {
      await apartmentApi.settings.changePassword({
        current_password: currentPw,
        new_password: newPw,
      })
      setPwMsg({ text: 'Password changed successfully', ok: true })
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
    } catch (e: unknown) {
      setPwMsg({ text: e instanceof Error ? e.message : 'Failed to change password', ok: false })
    } finally {
      setSavingPw(false)
      setTimeout(() => setPwMsg(null), 4000)
    }
  }

  const formatUptime = (sec: number) => {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    return `${h}h ${m}m`
  }

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your profile, security, and system preferences" />

      <div className="px-6 pb-8 space-y-6 max-w-3xl">

        {/* ── Profile Section ───────────────────────────────────────── */}
        <section className="bg-white rounded-2xl shadow p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
              <User size={18} className="text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-800">Profile</h2>
              <p className="text-xs text-gray-500">Update your account information</p>
            </div>
          </div>

          {profile && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1">Username</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs text-gray-500 bg-gray-50 p-3 rounded-xl">
                <span>Role: <strong className="text-gray-700 capitalize">{profile.role}</strong></span>
                <span>Unit: <strong className="text-gray-700">{profile.unit_key ?? '—'}</strong></span>
                <span>Since: <strong className="text-gray-700">{new Date(profile.created_at).toLocaleDateString()}</strong></span>
              </div>

              {profileMsg && (
                <div className={`px-4 py-2 rounded-xl text-sm font-semibold text-white ${profileMsg.ok ? 'bg-emerald-600' : 'bg-red-600'}`}>
                  {profileMsg.text}
                </div>
              )}

              <button
                onClick={saveProfile}
                disabled={savingProfile}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 transition disabled:opacity-50"
              >
                <Save size={14} />
                {savingProfile ? 'Saving…' : 'Save Profile'}
              </button>
            </div>
          )}
        </section>

        {/* ── Change Password Section ───────────────────────────────── */}
        <section className="bg-white rounded-2xl shadow p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
              <Lock size={18} className="text-amber-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-800">Security</h2>
              <p className="text-xs text-gray-500">Change your password</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Current Password</label>
              <div className="relative">
                <input
                  type={showCurrent ? 'text' : 'password'}
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
                >
                  {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">New Password</label>
                <div className="relative">
                  <input
                    type={showNew ? 'text' : 'password'}
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew(!showNew)}
                    className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
                  >
                    {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
                />
              </div>
            </div>

            {pwMsg && (
              <div className={`px-4 py-2 rounded-xl text-sm font-semibold text-white ${pwMsg.ok ? 'bg-emerald-600' : 'bg-red-600'}`}>
                {pwMsg.text}
              </div>
            )}

            <button
              onClick={changePassword}
              disabled={savingPw || !currentPw || !newPw || !confirmPw}
              className="flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-xl text-sm font-semibold hover:bg-amber-700 transition disabled:opacity-50"
            >
              <Lock size={14} />
              {savingPw ? 'Changing…' : 'Change Password'}
            </button>
          </div>
        </section>

        {/* ── System Info (admin only) ──────────────────────────────── */}
        {user?.role === 'admin' && system && (
          <section className="bg-white rounded-2xl shadow p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center">
                <Server size={18} className="text-purple-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-800">System Info</h2>
                <p className="text-xs text-gray-500">Server and database information</p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Version', value: `v${system.version}` },
                { label: 'Python', value: system.python_version },
                { label: 'Database', value: system.database },
                { label: 'Uptime', value: formatUptime(system.uptime_seconds) },
                { label: 'Users', value: system.total_users.toString() },
                { label: 'Tenants', value: system.total_tenants.toString() },
                { label: 'Devices', value: system.total_devices.toString() },
                { label: 'OS', value: system.os_platform },
              ].map((item) => (
                <div key={item.label} className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500">{item.label}</p>
                  <p className="text-sm font-bold text-gray-800">{item.value}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
