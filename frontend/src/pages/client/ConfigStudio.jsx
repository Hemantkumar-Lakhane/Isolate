// frontend/src/pages/client/ConfigStudio.jsx
// Dual-mode config editor: Form-based OR raw JSON.
// Reads from /api/v1/tenants/{id} and saves to /api/v1/tenants/{id}/config

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth }  from '../../contexts/AuthContext'
import { Card, Button, Input, Textarea, Select, Toggle, Alert, Spinner, TabGroup, Modal, CodeBlock } from '../../components/ui'

// ── Field renderer ─────────────────────────────────────────────────────────────
function FieldRow({ field, value, onChange }) {
  const { key, label, type, options, hint, required, min, max, step } = field

  if (type === 'range') {
    return (
      <div>
        <label className="block text-xs text-gray-400 mb-1">
          {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={min ?? 0}
            max={max ?? 1}
            step={step ?? 0.05}
            value={value ?? (min ?? 0)}
            onChange={e => onChange(key, parseFloat(e.target.value))}
            className="flex-1 accent-blue-500"
          />
          <span className="text-white font-mono text-sm w-12 text-right">{value ?? (min ?? 0)}</span>
        </div>
        {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
      </div>
    )
  }

  if (type === 'textarea') {
    return (
      <Textarea
        label={label}
        value={value ?? ''}
        onChange={e => onChange(key, e.target.value)}
        hint={hint}
        rows={3}
      />
    )
  }

  if (type === 'select') {
    return (
      <Select
        label={label}
        value={value ?? ''}
        onChange={e => onChange(key, e.target.value)}
        options={options?.map(o => ({ value: o, label: o })) ?? []}
      />
    )
  }

  if (type === 'multiselect') {
    const current = Array.isArray(value) ? value : []
    return (
      <div>
        <label className="block text-xs text-gray-400 mb-2">{label}</label>
        <div className="flex flex-wrap gap-2">
          {options?.map(opt => {
            const on = current.includes(opt)
            return (
              <button
                key={opt}
                onClick={() => onChange(key, on ? current.filter(x => x !== opt) : [...current, opt])}
                className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                  on ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                }`}
              >
                {opt}
              </button>
            )
          })}
        </div>
        {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
      </div>
    )
  }

  if (type === 'number') {
    return (
      <Input
        label={label}
        type="number"
        value={value ?? ''}
        onChange={e => onChange(key, parseFloat(e.target.value) || 0)}
        hint={hint}
        required={required}
      />
    )
  }

  return (
    <Input
      label={label}
      type={type === 'password' ? 'password' : 'text'}
      value={value ?? ''}
      onChange={e => onChange(key, e.target.value)}
      hint={hint}
      required={required}
    />
  )
}

// ── Section renderer ───────────────────────────────────────────────────────────
function SectionForm({ section, config, onChange }) {
  const get = (key) => {
    const parts = key.split('.')
    let v = config
    for (const p of parts) v = v?.[p]
    return v
  }

  const set = (key, value) => {
    const parts = key.split('.')
    onChange(prev => {
      const next = { ...prev }
      let obj = next
      for (let i = 0; i < parts.length - 1; i++) {
        if (typeof obj[parts[i]] !== 'object' || obj[parts[i]] === null) obj[parts[i]] = {}
        obj[parts[i]] = { ...obj[parts[i]] }
        obj = obj[parts[i]]
      }
      obj[parts[parts.length - 1]] = value
      return next
    })
  }

  return (
    <div className="space-y-5">
      {section.fields.map(field => (
        <FieldRow key={field.key} field={field} value={get(field.key)} onChange={set} />
      ))}
    </div>
  )
}

// ── Main ConfigStudio ──────────────────────────────────────────────────────────
export default function ConfigStudio() {
  const { user, api }     = useAuth()
  const [mode,   setMode] = useState('form')   // 'form' | 'json'
  const [schema, setSchema] = useState(null)
  const [config, setConfig] = useState({})
  const [rawJson,setRawJson] = useState('')
  const [jsonErr, setJsonErr] = useState('')
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [success,  setSuccess]  = useState('')
  const [error,    setError]    = useState('')
  const [activeSection, setActiveSection] = useState('')
  const [showPreview, setShowPreview] = useState(false)

  const tenantId = user?.tenant_id

  const load = useCallback(async () => {
    if (!tenantId) { setLoading(false); return }
    try {
      const [tenantData, schemaData] = await Promise.all([
        api.get(`/tenants/${tenantId}`),
        api.get(`/tenants/${tenantId}/config-schema`).catch(() => ({ sections: [] })),
      ])
      const cfg = tenantData?.config || {}
      setConfig(cfg)
      setRawJson(JSON.stringify(cfg, null, 2))
      setSchema(schemaData)
      if (schemaData?.sections?.length > 0) setActiveSection(schemaData.sections[0].id)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [api, tenantId])

  useEffect(() => { load() }, [load])

  // Sync raw JSON when switching to JSON mode
  const handleModeChange = (newMode) => {
    if (newMode === 'json') {
      setRawJson(JSON.stringify(config, null, 2))
      setJsonErr('')
    } else {
      // Validate JSON before switching back
      try {
        const parsed = JSON.parse(rawJson)
        setConfig(parsed)
        setJsonErr('')
      } catch {
        setJsonErr('Fix JSON errors before switching to form mode')
        return
      }
    }
    setMode(newMode)
  }

  const handleJsonChange = (val) => {
    setRawJson(val)
    try {
      setConfig(JSON.parse(val))
      setJsonErr('')
    } catch {
      setJsonErr('Invalid JSON')
    }
  }

  const save = async () => {
    let finalConfig = config
    if (mode === 'json') {
      try {
        finalConfig = JSON.parse(rawJson)
        setJsonErr('')
      } catch {
        setJsonErr('Cannot save — fix JSON errors first')
        return
      }
    }
    setSaving(true); setSuccess(''); setError('')
    try {
      await api.put(`/tenants/${tenantId}/config`, { config: finalConfig })
      setSuccess('Configuration saved successfully!')
      setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!tenantId) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="text-4xl mb-3">🏢</div>
        <p className="text-gray-400">No tenant associated with your account.</p>
        <p className="text-gray-600 text-sm mt-1">Ask your admin to assign you to a tenant.</p>
      </div>
    </div>
  )

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>

  const sections = schema?.sections || []
  const sectionTabs = sections.map(s => ({ value: s.id, label: s.title }))
  const currentSection = sections.find(s => s.id === activeSection)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-white">⚙️ Config Studio</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            Edit your SMBFlow configuration · {config.client_name || 'Your Company'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowPreview(true)}>👁 Preview JSON</Button>
          <Button size="sm" variant="success" loading={saving} onClick={save}>
            💾 Save Config
          </Button>
        </div>
      </div>

      {error   && <Alert type="error"   onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>}
      {jsonErr && <Alert type="error">{jsonErr}</Alert>}

      {/* Mode switcher */}
      <div className="flex items-center gap-4">
        <TabGroup
          tabs={[
            { value: 'form', label: '📋 Form Mode',    icon: null },
            { value: 'json', label: '{ } JSON Mode',  icon: null },
          ]}
          value={mode}
          onChange={handleModeChange}
        />
        {mode === 'form' && sectionTabs.length > 0 && (
          <div className="flex-1 flex gap-2 flex-wrap">
            {sectionTabs.map(tab => (
              <button
                key={tab.value}
                onClick={() => setActiveSection(tab.value)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                  activeSection === tab.value
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Editor area */}
      {mode === 'form' ? (
        <Card title={currentSection?.title || 'Configuration'}>
          {currentSection ? (
            <SectionForm
              key={activeSection}
              section={currentSection}
              config={config}
              onChange={setConfig}
            />
          ) : (
            <div className="text-center py-8 text-gray-500">
              No form schema available — use JSON mode to edit directly.
            </div>
          )}
        </Card>
      ) : (
        <Card title="Raw JSON Configuration">
          <div className="text-xs text-gray-500 mb-3">
            Edit the raw JSON directly. Changes are validated on save.
          </div>
          <textarea
            value={rawJson}
            onChange={e => handleJsonChange(e.target.value)}
            rows={30}
            spellCheck={false}
            className={`w-full bg-gray-950 border rounded-lg px-4 py-3 text-green-400 font-mono text-xs focus:outline-none focus:ring-1 resize-y min-h-[300px] ${
              jsonErr ? 'border-red-500 focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
            }`}
          />
        </Card>
      )}

      {/* JSON Preview Modal */}
      <Modal open={showPreview} onClose={() => setShowPreview(false)} title="Config JSON Preview" width="max-w-2xl">
        <CodeBlock lang="json">{JSON.stringify(config, null, 2)}</CodeBlock>
      </Modal>
    </div>
  )
}