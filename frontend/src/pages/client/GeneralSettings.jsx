// frontend/src/pages/client/GeneralSettings.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Profile & Workspace Settings
//   • User Profile with clickable Avatar photo upload/edit/remove
//   • Organization Details (Name, Industry + Custom Tag, Website, Size, Timezone)
//   • System Notifications, Security & Data Retention preferences
//   • Real backend database sync via /auth/profile, /organizations/me/profile, /organizations/me/config
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Camera, Check, AlertCircle, Loader2, User, Building2, Globe, Users,
  Mail, ShieldCheck, Bell, Clock, Database, Save, Trash2, Edit3
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

const INDUSTRIES = [
  { label: 'SaaS / Technology', value: 'saas' },
  { label: 'Healthcare & Life Sciences', value: 'healthcare' },
  { label: 'E-commerce & Retail', value: 'ecommerce' },
  { label: 'Financial Services & FinTech', value: 'finance' },
  { label: 'Education & EdTech', value: 'education' },
  { label: 'Marketing & Creative Agency', value: 'marketing' },
  { label: 'Professional & Legal Services', value: 'services' },
  { label: 'Manufacturing & Logistics', value: 'logistics' },
  { label: 'Real Estate & Construction', value: 'realestate' },
  { label: 'Other', value: 'other' },
]

const COMPANY_SIZES = ['1-10', '11-50', '51-200', '201-500', '500+']
const TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Asia/Kolkata', 'Asia/Tokyo', 'Australia/Sydney'
]
const RETENTION_OPTS = ['30 days', '60 days', '90 days', '6 months', '1 year', 'Indefinite']

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 cursor-pointer ${
        checked ? 'bg-blue-600' : 'bg-slate-300'
      }`}
    >
      <div
        className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function SectionCard({ title, subtitle, icon: Icon, children }) {
  return (
    <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-xs space-y-5">
      <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
        {Icon && (
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <div>
          <h2 className="text-base font-bold text-slate-900 tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  )
}

export default function GeneralSettings() {
  const { user, api, login, token } = useAuth()
  const fileInputRef = useRef(null)

  const [form, setForm] = useState({
    // User Profile
    fullName: user?.full_name || '',
    email: user?.email || '',
    avatarUrl: localStorage.getItem(`avatar_${user?.id}`) || '',
    
    // Organization Profile
    orgName: '',
    industry: 'saas',
    customIndustry: '',
    website: '',
    companySize: '11-50',
    timezone: 'UTC',

    // Notifications & System
    emailNotif: true,
    slackNotif: false,
    approvalAlerts: true,
    twoFA: false,
    sessionTimeout: 30,
    runLogsRetention: '90 days',
    evidenceRetention: '1 year',
  })

  const [isEditingProfile, setIsEditingProfile] = useState(false)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  const loadOrg = useCallback(async () => {
    try {
      const org = await api.get('/organizations/me')
      if (org) {
        const isKnownIndustry = INDUSTRIES.some(i => i.value === org.industry)
        setForm(f => ({
          ...f,
          fullName: user?.full_name || org.full_name || f.fullName,
          email: user?.email || f.email,
          orgName: org.name || f.orgName,
          industry: isKnownIndustry ? org.industry : 'other',
          customIndustry: isKnownIndustry ? '' : (org.industry || ''),
          website: org.website || f.website,
          companySize: org.company_size || f.companySize,
          timezone: org.config?.timezone || f.timezone,
          emailNotif: org.config?.notifications?.email ?? f.emailNotif,
          slackNotif: org.config?.notifications?.slack ?? f.slackNotif,
          approvalAlerts: org.config?.notifications?.approvals ?? f.approvalAlerts,
        }))
      }
    } catch (err) {
      setError(err.message || 'Failed to load organization settings')
    }
  }, [api, user])

  useEffect(() => { loadOrg() }, [loadOrg])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  // Handle Profile Photo Upload
  const handleAvatarFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > 3 * 1024 * 1024) {
      setError('Image size should be less than 3MB')
      return
    }

    const reader = new FileReader()
    reader.onload = (event) => {
      const dataUrl = event.target.result
      set('avatarUrl', dataUrl)
      if (user?.id) {
        try {
          localStorage.setItem(`avatar_${user.id}`, dataUrl)
          localStorage.setItem('smbflow_avatar', dataUrl)
        } catch (_) {}
      }
      if (user && token) {
        login(token, { ...user, avatar_url: dataUrl })
      }
      setSuccess('Profile photo updated!')
      setTimeout(() => setSuccess(''), 3000)
    }
    reader.readAsDataURL(file)
  }

  const handleRemoveAvatar = () => {
    set('avatarUrl', '')
    if (user?.id) {
      try {
        localStorage.removeItem(`avatar_${user.id}`)
        localStorage.removeItem('smbflow_avatar')
      } catch (_) {}
    }
    if (user && token) {
      login(token, { ...user, avatar_url: null })
    }
    setSuccess('Profile photo removed.')
    setTimeout(() => setSuccess(''), 3000)
  }

  const handleSaveAll = async () => {
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const resolvedInd = form.industry === 'other'
        ? (form.customIndustry.trim() || 'other')
        : form.industry

      // 1. Update User Profile in backend
      await api.put('/auth/profile', {
        full_name: form.fullName.trim(),
        avatar_url: form.avatarUrl || null,
      }).catch(() => {})

      // 2. Update Organization Profile in database
      await api.put('/organizations/me/profile', {
        name: form.orgName.trim() || undefined,
        industry: resolvedInd,
        website: form.website.trim() || undefined,
        company_size: form.companySize || undefined,
      })

      // 3. Update runtime config (Timezone, Notifications)
      await api.put('/organizations/me/config', {
        config: {
          timezone: form.timezone,
          notifications: {
            email: form.emailNotif,
            slack: form.slackNotif,
            approvals: form.approvalAlerts,
          },
          retention: {
            run_logs: form.runLogsRetention,
            evidence: form.evidenceRetention,
          }
        },
      })

      // Update AuthContext user session cache if full name or avatar changed
      if (user && token) {
        const updatedUser = {
          ...user,
          full_name: form.fullName.trim(),
          avatar_url: form.avatarUrl || null,
          organization_name: form.orgName.trim() || user.organization_name,
          industry: resolvedInd,
          website: form.website.trim(),
          company_size: form.companySize,
        }
        login(token, updatedUser)
      }

      setIsEditingProfile(false)
      setSuccess('Profile and workspace settings saved successfully!')
      setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(err.message || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  // Initials for avatar fallback
  const getInitials = () => {
    const name = form.fullName || user?.email || 'Admin User'
    return name
      .split(' ')
      .map(n => n[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()
  }

  return (
    <div className="p-6 sm:p-8 bg-slate-50/50 min-h-full font-sans antialiased text-slate-800 max-w-5xl mx-auto space-y-6">
      
      {/* ── Top Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Profile & Workspace Settings
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Manage your personal identity, company profile, and agent operational preferences
          </p>
        </div>

        <button
          type="button"
          onClick={handleSaveAll}
          disabled={saving}
          className="inline-flex items-center justify-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs sm:text-sm font-semibold rounded-full transition-all shadow-sm cursor-pointer active:scale-98"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Saving changes...</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Save changes</span>
            </>
          )}
        </button>
      </div>

      {/* ── Status Banners ────────────────────────────────────────────── */}
      {success && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs sm:text-sm flex items-center gap-2.5 shadow-xs">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span className="font-semibold">{success}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs sm:text-sm flex items-center gap-2.5 shadow-xs">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span className="font-semibold">{error}</span>
        </div>
      )}

      <div className="space-y-6">

        {/* ══════════════════════════════════════════════════════════════════
            CARD 1: USER PROFILE & IDENTITY
            ══════════════════════════════════════════════════════════════════ */}
        <SectionCard
          title="Personal Profile & Account"
          subtitle="Manage your avatar, name, and administrative credentials"
          icon={User}
        >
          <div className="flex flex-col sm:flex-row sm:items-center gap-6 pt-2">
            
            {/* Clickable Profile Photo / Avatar */}
            <div className="relative group">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleAvatarFileSelect}
                accept="image/*"
                className="hidden"
              />
              
              <div
                onClick={() => fileInputRef.current?.click()}
                className="w-20 h-20 rounded-2xl border-2 border-slate-200 overflow-hidden bg-gradient-to-br from-blue-600 to-indigo-700 text-white flex items-center justify-center font-bold text-xl shadow-sm cursor-pointer group-hover:border-blue-500 transition-all relative"
                title="Click to upload/change photo"
              >
                {form.avatarUrl ? (
                  <img src={form.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <span>{getInitials()}</span>
                )}
                
                <div className="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-opacity text-white text-[10px] font-semibold">
                  <Camera className="w-4 h-4 mb-0.5" />
                  <span>Change</span>
                </div>
              </div>
            </div>

            {/* Photo Action Buttons */}
            <div className="space-y-1.5 flex-1">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3.5 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition-colors cursor-pointer inline-flex items-center gap-1.5"
                >
                  <Camera className="w-3.5 h-3.5" />
                  <span>Upload Photo</span>
                </button>
                {form.avatarUrl && (
                  <button
                    type="button"
                    onClick={handleRemoveAvatar}
                    className="px-3 py-1.5 rounded-full text-rose-600 hover:bg-rose-50 text-xs font-semibold transition-colors cursor-pointer inline-flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Remove</span>
                  </button>
                )}
              </div>
              <p className="text-[11px] text-slate-400">Recommended: Square JPG or PNG, max 3MB.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                value={form.fullName}
                onChange={e => set('fullName', e.target.value)}
                placeholder="Your full name"
                className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Work Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={form.email}
                  readOnly
                  disabled
                  className="w-full border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm text-slate-600 bg-slate-50 font-medium cursor-not-allowed"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 text-[11px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Verified</span>
                </div>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* ══════════════════════════════════════════════════════════════════
            CARD 2: ORGANIZATION PROFILE
            ══════════════════════════════════════════════════════════════════ */}
        <SectionCard
          title="Organization & Company Profile"
          subtitle="Update company identity, website, and industry categorization"
          icon={Building2}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Organization / Company Name
              </label>
              <input
                type="text"
                value={form.orgName}
                onChange={e => set('orgName', e.target.value)}
                placeholder="e.g. Edupluscampus, Acme Corp"
                className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Industry
              </label>
              <div className="relative">
                <select
                  value={form.industry}
                  onChange={e => set('industry', e.target.value)}
                  className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium appearance-none pr-10 cursor-pointer outline-none"
                >
                  {INDUSTRIES.map(i => (
                    <option key={i.value} value={i.value}>{i.label}</option>
                  ))}
                </select>
                <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▾</div>
              </div>
            </div>
          </div>

          {form.industry === 'other' && (
            <div className="animate-in fade-in slide-in-from-top-1 duration-150">
              <label className="block text-xs font-semibold text-blue-700 mb-1.5">
                Custom Industry Tag
              </label>
              <input
                type="text"
                value={form.customIndustry}
                onChange={e => set('customIndustry', e.target.value)}
                placeholder="e.g. Clean Energy, Robotics, BioTech..."
                className="w-full border border-blue-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-blue-50/20 font-medium outline-none"
              />
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Company Website
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={form.website}
                  onChange={e => set('website', e.target.value)}
                  placeholder="https://example.com"
                  className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium outline-none transition-all pl-9"
                />
                <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Company Size
              </label>
              <div className="relative">
                <select
                  value={form.companySize}
                  onChange={e => set('companySize', e.target.value)}
                  className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium appearance-none pr-10 cursor-pointer outline-none"
                >
                  {COMPANY_SIZES.map(s => (
                    <option key={s} value={s}>{s} employees</option>
                  ))}
                </select>
                <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▾</div>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Operating Timezone
            </label>
            <div className="relative max-w-xs">
              <select
                value={form.timezone}
                onChange={e => set('timezone', e.target.value)}
                className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 bg-white font-medium appearance-none pr-10 cursor-pointer outline-none"
              >
                {TIMEZONES.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
              <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▾</div>
            </div>
          </div>
        </SectionCard>

        {/* ══════════════════════════════════════════════════════════════════
            CARD 3: NOTIFICATIONS & AGENT DISPATCHES
            ══════════════════════════════════════════════════════════════════ */}
        <SectionCard
          title="Notification & Escalation Preferences"
          subtitle="Configure how SMBFlow alerts your team for human reviews and system events"
          icon={Bell}
        >
          <div className="divide-y divide-slate-100">
            {[
              { key: 'emailNotif', label: 'Email notifications', desc: 'Receive email alerts for approvals and workflow completion events' },
              { key: 'slackNotif', label: 'Slack dispatch alerts', desc: 'Post workflow escalations and real-time updates directly to a connected Slack channel' },
              { key: 'approvalAlerts', label: 'Urgent human-in-the-loop approvals', desc: 'Immediately notify administrators when an agent requests sign-off' },
            ].map(({ key, label, desc }) => (
              <div key={key} className="flex items-center justify-between py-3.5 first:pt-0 last:pb-0 gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{label}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
                </div>
                <Toggle checked={form[key]} onChange={v => set(key, v)} />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* ══════════════════════════════════════════════════════════════════
            CARD 4: DATA RETENTION & SECURITY
            ══════════════════════════════════════════════════════════════════ */}
        <SectionCard
          title="Data Governance & Retention"
          subtitle="Configure multi-tenant audit trail lifespan and evidence retention"
          icon={Database}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Run Logs Retention
              </label>
              <div className="relative">
                <select
                  value={form.runLogsRetention}
                  onChange={e => set('runLogsRetention', e.target.value)}
                  className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm font-medium appearance-none pr-10 bg-white cursor-pointer outline-none"
                >
                  {RETENTION_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
                <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▾</div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Evidence Artifacts Retention
              </label>
              <div className="relative">
                <select
                  value={form.evidenceRetention}
                  onChange={e => set('evidenceRetention', e.target.value)}
                  className="w-full border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-xl px-3.5 py-2.5 text-sm font-medium appearance-none pr-10 bg-white cursor-pointer outline-none"
                >
                  {RETENTION_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
                <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">▾</div>
              </div>
            </div>
          </div>
        </SectionCard>

      </div>
    </div>
  )
}
