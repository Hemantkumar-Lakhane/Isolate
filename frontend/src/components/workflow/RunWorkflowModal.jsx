// frontend/src/components/workflow/RunWorkflowModal.jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, X, Mail, Sparkles, CheckCircle2, AlertCircle, RefreshCw, Sliders, Layers, Settings, Save } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Modal, Button, Badge, Spinner, Alert } from '../ui'

// ── Config form field definitions ────────────────────────────────────────────
// Maps validator error fields to user-facing form fields.
const CONFIG_FIELD_DEFS = [
  {
    key: 'client_name',
    label: 'Company Name',
    type: 'text',
    placeholder: 'Acme Corp',
    required: true,
    getValue: (org) => org?.organization_name || '',
    saveTo: 'profile', // saved via PUT /organizations/me/profile  { name: ... }
  },
  {
    key: 'industry',
    label: 'Industry',
    type: 'select',
    options: ['saas', 'retail', 'healthcare', 'finance', 'real_estate', 'logistics', 'cpg', 'general'],
    required: true,
    getValue: (org) => org?.industry || 'saas',
    saveTo: 'profile', // saved via PUT /organizations/me/profile  { industry: ... }
  },
  {
    key: 'business_rules',
    label: 'Business Rules',
    type: 'textarea',
    placeholder: '{"confidence_threshold": 0.75, "high_value_deal_threshold": 50000}',
    required: true,
    getValue: (org) => '',
    saveTo: 'config', // saved via PUT /organizations/me/config  { business_rules: ... }
  },
  {
    key: 'tone_profile',
    label: 'Tone Profile',
    type: 'textarea',
    placeholder: '{"brand_voice": "Professional and empathetic", "formality": "high", "sign_off_name": "Team"}',
    required: true,
    getValue: (org) => '',
    saveTo: 'config',
  },
  {
    key: 'action_library',
    label: 'Action Library',
    type: 'textarea',
    placeholder: '{"actions": [{"id": "action_respond", "action_type": "send_email", "description": "Send response", "required_approval": true}]}',
    required: true,
    getValue: (org) => '',
    saveTo: 'config',
  },
]

// ── Config Input Form ────────────────────────────────────────────────────────
function ConfigInputForm({ missingFields, orgInfo, onSubmit, onCancel, saving, error }) {
  const [values, setValues] = useState({})

  // Pre-fill from org info and existing config where possible
  useEffect(() => {
    const initial = {}
    CONFIG_FIELD_DEFS.forEach(f => {
      if (missingFields.includes(f.key) || missingFields.some(m => m.startsWith(f.key))) {
        initial[f.key] = f.getValue(orgInfo) || ''
      }
    })
    setValues(initial)
  }, [missingFields, orgInfo])

  const handleChange = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(values)
  }

  // Determine which fields to show based on missing_fields
  const fieldsToShow = CONFIG_FIELD_DEFS.filter(f =>
    missingFields.includes(f.key) || missingFields.some(m => m.startsWith(f.key + '.'))
  )

  if (fieldsToShow.length === 0) {
    // Fallback: show all required fields
    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-slate-500">Provide the required configuration to run this workflow.</p>
        {CONFIG_FIELD_DEFS.map(f => (
          <ConfigField key={f.key} field={f} value={values[f.key] || ''} onChange={handleChange} />
        ))}
        {error && <Alert type="danger">{error}</Alert>}
        <div className="flex gap-2 pt-2">
          <Button variant="gradient" size="sm" type="submit" loading={saving} icon={<Save className="w-3.5 h-3.5" />}>
            Save & Run
          </Button>
          <Button variant="ghost" size="sm" type="button" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
        <p className="font-semibold mb-1">Configuration Required</p>
        <p className="text-amber-700">This workflow needs the following settings before it can run. Values are saved to your organization profile.</p>
      </div>
      {fieldsToShow.map(f => (
        <ConfigField key={f.key} field={f} value={values[f.key] || ''} onChange={handleChange} />
      ))}
      {error && <Alert type="danger">{error}</Alert>}
      <div className="flex gap-2 pt-2">
        <Button variant="gradient" size="sm" type="submit" loading={saving} icon={<Save className="w-3.5 h-3.5" />}>
          Save & Run
        </Button>
        <Button variant="ghost" size="sm" type="button" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

function ConfigField({ field, value, onChange }) {
  const isJson = field.type === 'textarea'
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-700 mb-1">
        {field.label} {field.required && <span className="text-red-500">*</span>}
      </label>
      {field.type === 'select' ? (
        <select
          value={value}
          onChange={e => onChange(field.key, e.target.value)}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          {field.options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      ) : (
        <textarea
          value={value}
          onChange={e => onChange(field.key, e.target.value)}
          placeholder={field.placeholder}
          rows={isJson ? 4 : 2}
          className={`w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none ${isJson ? 'bg-slate-50' : ''}`}
        />
      )}
      {isJson && value && (() => {
        try { JSON.parse(value); return null } catch {
          return <p className="text-[11px] text-red-500 mt-1">Invalid JSON</p>
        }
      })()}
    </div>
  )
}

// ── Main RunWorkflowModal ────────────────────────────────────────────────────
export default function RunWorkflowModal({
  open,
  onClose,
  workflowName = 'email_summarizer',
  displayName = 'Email Summarizer',
  onSuccess,
}) {
  const navigate = useNavigate()
  const { api, user } = useAuth()
  const [loadingInfo, setLoadingInfo] = useState(true)
  const [triggerInfo, setTriggerInfo] = useState(null)
  const [limit, setLimit] = useState(40)
  const [isAll, setIsAll] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState('')
  const [successRun, setSuccessRun] = useState(null)
  const [showConfigForm, setShowConfigForm] = useState(false)
  const [configSaving, setConfigSaving] = useState(false)
  const [orgInfo, setOrgInfo] = useState(null)

  useEffect(() => {
    if (!open) {
      setError('')
      setSuccessRun(null)
      setShowConfigForm(false)
      return
    }

    let isMounted = true
    setLoadingInfo(true)
    setError('')
    setSuccessRun(null)
    setShowConfigForm(false)

    async function fetchInfo() {
      try {
        console.log('[RUN MODAL] Fetching trigger info for', workflowName, 'URL:', `/workflows/${workflowName}/trigger-info`);
        const info = await api.get(`/workflows/${workflowName}/trigger-info`);
        console.log('[RUN MODAL] Trigger info response', info);
        if (isMounted) {
          setTriggerInfo(info);
          const avail = info.available_messages_count || 40;
          setLimit(avail);

          // Check if config is valid
          if (info.config_validation && !info.config_validation.valid) {
            setShowConfigForm(true);
          }

          // Fetch org info for pre-filling config form
          try {
            const org = await api.get('/organizations/me');
            if (isMounted) setOrgInfo(org);
          } catch {
            // org info fetch failed — form still works, just no pre-fill
          }
        }
      } catch (err) {
        console.warn('Could not fetch trigger-info, using fallback defaults', err)
        if (isMounted) {
          setTriggerInfo({
            workflow_name: workflowName,
            display_name: displayName,
            trigger_type: 'New Email',
            source: 'Synthetic Inbox',
            available_messages_count: 40,
            status: 'active',
          })
          setLimit(40)
        }
      } finally {
        if (isMounted) setLoadingInfo(false)
      }
    }

    fetchInfo()
    return () => { isMounted = false }
  }, [open, workflowName, displayName, api])

  const handleRun = async ({ skipExecutingState = false } = {}) => {
    if (!skipExecutingState) setExecuting(true)
    setError('')
    try {
      const payload = {
        workflow_name: workflowName,
        tenant_id: user?.organization_id || user?.tenant_id || undefined,
        trigger_signal: {
          source: 'manual_ui',
          limit: isAll ? (triggerInfo?.available_messages_count || 40) : parseInt(limit, 10) || 10,
        },
      }

      console.log('[RUN MODAL] Triggering workflow', workflowName, 'payload:', payload);
      const res = await api.post('/workflows/trigger', payload);
      console.log('[RUN MODAL] Trigger response', res);
      setSuccessRun(res)
      if (onSuccess) {
        onSuccess(res)
      }
    } catch (err) {
      const detail = err?.response?.data?.detail
      // If 422 with missing_fields → show config form
      if (err?.response?.status === 422 && detail?.missing_fields) {
        setShowConfigForm(true)
        setError('')
        setConfigSaving(false)
        return
      }
      let msg = 'Failed to trigger workflow'
      if (typeof detail === 'string') {
        msg = detail
      } else if (detail?.message) {
        msg = detail.message
      } else if (err?.message) {
        msg = err.message
      }
      setError(msg)
    } finally {
      if (!skipExecutingState) setExecuting(false)
    }
  }

  const handleConfigSaveAndRun = async (fieldValues) => {
    setConfigSaving(true)
    setError('')

    try {
      // Separate profile fields from config fields
      const profileUpdate = {}
      const configUpdate = {}

      CONFIG_FIELD_DEFS.forEach(f => {
        const val = fieldValues[f.key]
        if (val === undefined || val === '') return

        if (f.saveTo === 'profile') {
          if (f.key === 'client_name') profileUpdate.name = val
          else if (f.key === 'industry') profileUpdate.industry = val
        } else if (f.saveTo === 'config') {
          // Parse JSON for textarea fields
          if (f.type === 'textarea') {
            try {
              configUpdate[f.key] = JSON.parse(val)
            } catch {
              setError(`Invalid JSON in ${f.label}. Please fix the format.`)
              setConfigSaving(false)
              return
            }
          } else {
            configUpdate[f.key] = val
          }
        }
      })

      // Save profile fields (name, industry)
      if (profileUpdate.name || profileUpdate.industry) {
        await api.put('/organizations/me/profile', profileUpdate)
      }

      // Save config fields (business_rules, tone_profile, action_library)
      if (Object.keys(configUpdate).length > 0) {
        await api.put('/organizations/me/config', { config: configUpdate })
      }

      // Re-fetch trigger-info to verify config is now valid
      const updatedInfo = await api.get(`/workflows/${workflowName}/trigger-info`)
      setTriggerInfo(updatedInfo)

      if (updatedInfo.config_validation && !updatedInfo.config_validation.valid) {
        setError('Configuration still has validation errors. Please check your values.')
        setConfigSaving(false)
        return
      }

      // Config is valid — trigger the workflow
      setShowConfigForm(false)
      await handleRun({ skipExecutingState: true })

    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to save configuration'
      setError(typeof msg === 'string' ? msg : msg.message || 'Failed to save configuration')
    } finally {
      setConfigSaving(false)
    }
  }

  const availCount = triggerInfo?.available_messages_count ?? 40
  const isEmail = workflowName.includes('email') || triggerInfo?.trigger_type === 'New Email'
  const configValid = triggerInfo?.config_validation?.valid !== false

  return (
    <Modal
      open={open}
      onClose={() => !executing && !configSaving && onClose()}
      title={showConfigForm ? 'Configure Workflow' : 'Run Workflow'}
      subtitle={triggerInfo?.display_name || displayName}
      width="max-w-lg"
    >
      <div className="space-y-5">
        {/* Success Banner */}
        {successRun ? (
          <div className="p-4 bg-green-50 border border-green-200 rounded-xl space-y-3">
            <div className="flex items-center gap-2.5 text-green-800 font-semibold text-sm">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <span>Workflow Successfully Queued!</span>
            </div>
            <p className="text-xs text-green-700">
              Run ID: <code className="font-mono font-semibold">{successRun.run_id}</code>
            </p>
            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={() => {
                  onClose()
                  navigate(`/workflows/${successRun.run_id}`)
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
              >
                View Live Run <Play className="w-3 h-3" />
              </button>
              <button
                onClick={onClose}
                className="px-3 py-1.5 border border-green-300 hover:bg-green-100 text-green-800 rounded-lg text-xs font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            {error && (
              <Alert type="danger" dismissible onDismiss={() => setError('')}>
                {error}
              </Alert>
            )}

            {/* Config Input Form */}
            {showConfigForm ? (
              <ConfigInputForm
                missingFields={triggerInfo?.config_validation?.errors?.map(e => e.field) || []}
                orgInfo={orgInfo}
                onSubmit={handleConfigSaveAndRun}
                onCancel={() => { setShowConfigForm(false); setError('') }}
                saving={configSaving}
                error={error}
              />
            ) : (
              <>
                {/* Workflow summary card */}
                <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
                        <Mail className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">{triggerInfo?.display_name || displayName}</h4>
                        <p className="text-[11px] text-slate-500 font-mono">{workflowName}</p>
                      </div>
                    </div>
                    <Badge variant="success">Active</Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-200 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[11px]">Trigger Mode</span>
                      <span className="font-semibold text-slate-700 flex items-center gap-1 mt-0.5">
                        <Play className="w-3 h-3 text-blue-600" /> Manual Run
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Data Source</span>
                      <span className="font-semibold text-slate-700 flex items-center gap-1 mt-0.5">
                        <Layers className="w-3 h-3 text-purple-600" /> {triggerInfo?.source || 'Synthetic Inbox'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Config validation warnings */}
                {triggerInfo?.config_validation && !configValid && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs">
                    <div className="flex items-center gap-2 text-amber-800 font-semibold mb-1">
                      <Settings className="w-3.5 h-3.5" />
                      <span>Configuration Incomplete</span>
                    </div>
                    <p className="text-amber-700 mb-2">This workflow requires configuration before it can run.</p>
                    <ul className="space-y-0.5 text-amber-700">
                      {triggerInfo.config_validation.errors?.slice(0, 5).map((e, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-amber-500 mt-0.5">•</span>
                          <span>{e.message}</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      onClick={() => setShowConfigForm(true)}
                      className="mt-2 flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                    >
                      <Settings className="w-3 h-3" /> Configure Now
                    </button>
                  </div>
                )}

                {/* Messages / Input Dataset Info */}
                <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                        <Sliders className="w-3.5 h-3.5 text-blue-600" />
                        Available Fixture Messages
                      </span>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Live count from runtime environment data store
                      </p>
                    </div>
                    {loadingInfo ? (
                      <Spinner className="w-4 h-4 text-blue-600" />
                    ) : (
                      <span className="text-sm font-bold text-blue-600 px-2.5 py-1 bg-blue-50 border border-blue-200 rounded-lg">
                        {availCount} {availCount === 1 ? 'message' : 'messages'}
                      </span>
                    )}
                  </div>

                  {/* Message Limit Toggle / Input */}
                  {isEmail && availCount > 0 && (
                    <div className="pt-2 border-t border-slate-100 space-y-2.5">
                      <div className="flex items-center justify-between text-xs">
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                          <input
                            type="checkbox"
                            checked={isAll}
                            onChange={(e) => {
                              setIsAll(e.target.checked)
                              if (e.target.checked) setLimit(availCount)
                            }}
                            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span className="text-slate-700 font-medium">Process all available ({availCount})</span>
                        </label>
                      </div>

                      {!isAll && (
                        <div className="flex items-center gap-3 pt-1">
                          <label className="text-xs text-slate-500 whitespace-nowrap">Limit batch size:</label>
                          <input
                            type="number"
                            min={1}
                            max={availCount}
                            value={limit}
                            onChange={(e) => setLimit(Math.max(1, Math.min(availCount, parseInt(e.target.value, 10) || 1)))}
                            className="w-24 px-2.5 py-1 border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <span className="text-[11px] text-slate-400">emails</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center justify-end gap-2.5 pt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClose}
                    disabled={executing}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="gradient"
                    size="sm"
                    onClick={handleRun}
                    loading={executing}
                    disabled={!configValid}
                    icon={<Play className="w-3.5 h-3.5 fill-white" />}
                  >
                    Run Workflow
                  </Button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}
