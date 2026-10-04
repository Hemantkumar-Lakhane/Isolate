// frontend/src/pages/AuthPage.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Mail, Lock, User, Building2, Layers, ArrowRight, Sparkles } from 'lucide-react'
import { useAuth }   from '../contexts/AuthContext'
import { apiCall }   from '../api/client'
import { Alert, Spinner, Button, Input, Select } from '../components/ui'
import { useTheme }    from '../contexts/ThemeContext'

const FEATURE_CARDS = [
  { icon: Zap,      title: 'Autonomous Agents', desc: 'Multi-step AI workflows that run without babysitting' },
  { icon: Layers,   title: 'Visual Builder',    desc: 'Drag-and-drop DAG builder, no code required' },
  { icon: Sparkles, title: 'Memory & Learning', desc: 'Patterns improve with every workflow run' },
]

export default function AuthPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { isDark, toggle: toggleTheme } = useTheme()
  const [mode, setMode] = useState('login')

  const [email,      setEmail]      = useState('admin@smbflow.com')
  const [password,   setPassword]   = useState('admin123')
  const [fullName,   setFullName]   = useState('')
  const [tenantName, setTenantName] = useState('')
  const [industry,   setIndustry]   = useState('saas')

  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const validate = () => {
    if (!email.trim())        { setError('Email is required');          return false }
    if (!email.includes('@')) { setError('Enter a valid email');        return false }
    if (password.length < 6)  { setError('Password min 6 characters'); return false }
    if (mode === 'signup' && !fullName.trim()) { setError('Full name required'); return false }
    return true
  }

  const handleSubmit = async (e) => {
    e?.preventDefault()
    setError('')
    if (!validate()) return
    setLoading(true)
    try {
      let data
      if (mode === 'login') {
        data = await apiCall('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.trim(), password }) })
      } else {
        data = await apiCall('/auth/signup', { method: 'POST', body: JSON.stringify({ email: email.trim(), password, full_name: fullName.trim(), tenant_name: tenantName.trim() || undefined, industry }) })
      }
      login(data.access_token, data.user)
      navigate(data.user.role === 'super_admin' ? '/admin' : '/dashboard', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen surface-base flex">
      {/* ── Left panel: form ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 relative">
        {/* Theme toggle */}
        <div className="absolute top-5 right-5">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-hover))] hover:border-primary-500/40 transition-all text-[rgb(var(--text-secondary))]"
          >
            {isDark ? '☀️' : '🌙'}
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-sm"
        >
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-primary shadow-glow-primary mb-4">
              <Zap className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-[rgb(var(--text-primary))]">SMBFlow</h1>
            <p className="text-sm text-[rgb(var(--text-muted))] mt-1">Autonomous Multi-Agent Engine</p>
          </div>

          {/* Mode switcher */}
          <div className="flex bg-[rgb(var(--bg-surface))] border border-[rgb(var(--border))] rounded-xl p-1 mb-6">
            {[{ id: 'login', label: 'Sign In' }, { id: 'signup', label: 'Create Account' }].map(m => (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setError('') }}
                className={`flex-1 py-2 text-sm rounded-lg font-semibold transition-all duration-200 ${
                  mode === m.id
                    ? 'bg-primary-500 text-white shadow-md shadow-primary-500/25'
                    : 'text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email" type="email" value={email}
              onChange={e => setEmail(e.target.value)}
              icon={Mail} placeholder="you@company.com" required autoFocus
            />
            <Input
              label="Password" type="password" value={password}
              onChange={e => setPassword(e.target.value)}
              icon={Lock} placeholder="••••••••" required
            />

            <AnimatePresence>
              {mode === 'signup' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-4 overflow-hidden"
                >
                  <Input
                    label="Full Name" value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    icon={User} placeholder="Jane Smith" required
                  />
                  <Input
                    label="Company Name" value={tenantName}
                    onChange={e => setTenantName(e.target.value)}
                    icon={Building2} placeholder="Acme Corp (optional)"
                  />
                  <Select
                    label="Industry" value={industry}
                    onChange={e => setIndustry(e.target.value)}
                    options={['saas','cpg','finance','healthcare','retail','logistics','real_estate'].map(i => ({
  value: i,
  label: i.replace('_', ' ').toUpperCase(),
}))}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}

            <Button type="submit" loading={loading} className="w-full" size="lg" iconRight={!loading && <ArrowRight className="w-4 h-4" />}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </Button>
          </form>

          {mode === 'login' && (
            <p className="text-xs text-[rgb(var(--text-muted))] text-center mt-4">
              Default: admin@smbflow.com / admin123
            </p>
          )}
        </motion.div>
      </div>

      {/* ── Right panel: features (hidden on mobile) ─────────────────────── */}
      <div className="hidden lg:flex flex-col justify-center flex-1 bg-gradient-to-br from-primary-900/30 to-accent/5 border-l border-[rgb(var(--border))] p-12 relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 bg-dot-grid opacity-60" />
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />

        <div className="relative">
          <h2 className="text-3xl font-bold text-[rgb(var(--text-primary))] mb-2">
            Intelligent Automation
          </h2>
          <p className="text-gradient text-3xl font-bold mb-8">at Enterprise Scale</p>

          <div className="space-y-4">
            {FEATURE_CARDS.map(({ icon: Icon, title, desc }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.1 }}
                className="flex items-start gap-4 p-4 surface-card rounded-2xl"
              >
                <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center flex-shrink-0">
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[rgb(var(--text-primary))]">{title}</p>
                  <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5 leading-relaxed">{desc}</p>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="mt-8 flex items-center gap-3">
            <div className="flex -space-x-2">
              {['A','B','C','D'].map((l, i) => (
                <div key={l} className={`w-8 h-8 rounded-full border-2 border-[rgb(var(--bg-surface))] bg-gradient-to-br from-primary-400 to-accent flex items-center justify-center text-[10px] font-bold text-white`} style={{ zIndex: 4-i }}>
                  {l}
                </div>
              ))}
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              Trusted by <span className="text-[rgb(var(--text-primary))] font-semibold">500+ teams</span> worldwide
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}