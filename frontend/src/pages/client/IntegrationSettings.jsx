// frontend/src/pages/client/IntegrationSettings.jsx
// Matches Figma: Integration Settings — manage connection credentials and integration config

import { useNavigate } from 'react-router-dom'
import { Plug, ExternalLink } from 'lucide-react'

const CATEGORIES = [
  { id: 'crm',         name: 'CRM',             desc: 'Connect customer relationship management systems to power lead and customer workflows.', examples: 'Examples: Salesforce, HubSpot, Zoho CRM' },
  { id: 'finance',     name: 'Finance & Billing', desc: 'Access invoice, payment, and financial data for finance automation workflows.',          examples: 'Examples: QuickBooks, Xero, Stripe' },
  { id: 'support',     name: 'Customer Support', desc: 'Integrate support desks for ticket triage and customer interaction workflows.',           examples: 'Examples: Zendesk, Freshdesk, Intercom' },
  { id: 'comms',       name: 'Communication',    desc: 'Send automated emails and notifications as workflow actions.',                            examples: 'Examples: SendGrid, Mailchimp, Slack' },
  { id: 'erp',         name: 'ERP & Operations', desc: 'Connect operational and procurement systems for business process automation.',            examples: 'Examples: SAP, NetSuite, Microsoft Dynamics' },
  { id: 'storage',     name: 'File Storage',     desc: 'Access documents and files as data sources within workflows.',                           examples: 'Examples: Google Drive, Dropbox, SharePoint' },
]

export default function IntegrationSettings() {
  const navigate = useNavigate()

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Integration Settings</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage connection credentials and integration configuration</p>
        </div>
        <button onClick={() => navigate('/tools')}
          className="flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors">
          View all integrations <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Info banner */}
      <div className="mb-5 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-2.5">
        <div className="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-white text-[10px] font-bold">i</span>
        </div>
        <p className="text-sm text-gray-700">
          Integration credentials and API keys will be stored securely once the backend is connected. Configure
          connections from the{' '}
          <button onClick={() => navigate('/tools')} className="text-blue-600 hover:underline font-medium">
            Integrations
          </button>{' '}
          page.
        </p>
      </div>

      {/* Categories */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-900">Available Integration Categories</h2>
        </div>
        <div className="divide-y divide-gray-50">
          {CATEGORIES.map(cat => (
            <div key={cat.id} className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Plug className="w-4 h-4 text-gray-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900">{cat.name}</p>
                <p className="text-sm text-gray-500 mt-0.5 leading-relaxed">{cat.desc}</p>
                <p className="text-xs text-blue-500 mt-1">{cat.examples}</p>
              </div>
              <span className="text-xs font-medium text-gray-400 flex-shrink-0 mt-1">Not connected</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
