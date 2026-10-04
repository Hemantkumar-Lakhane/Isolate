import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'

export default function CasesPage() {
  const { api } = useAuth()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [alias, setAlias] = useState('')
  const [country, setCountry] = useState('United States')
  const [specialty, setSpecialty] = useState('fertility_ivf')

  useEffect(() => {
    loadCases()
  }, [])

  const loadCases = async () => {
    setLoading(true)
    try {
      const res = await api.get('/medical/cases').catch(() => [])
      setCases(res || [])
    } catch (_) {
    } finally {
      setLoading(false)
    }
  }

  const handleCreateCase = async (e) => {
    e.preventDefault()
    try {
      await api.post('/medical/cases', {
        patient_alias: alias,
        country,
        specialty,
      })
      setShowModal(false)
      setAlias('')
      await loadCases()
    } catch (err) {
      alert(`Intake failed: ${err.message}`)
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-gray-400">Loading Medical Tourism Cases...</div>
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Medical Tourism Care Coordination</h1>
          <p className="text-sm text-gray-400">Non-clinical patient journey coordination & document intelligence (Fertility/IVF & Orthopedics).</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-md shadow transition"
        >
          + New Patient Intake
        </button>
      </div>

      <div className="bg-amber-950/30 border border-amber-800/50 rounded-xl p-4 text-xs text-amber-200/90 leading-relaxed">
        <strong>Strict Safety Policy Active:</strong> This platform assists care coordinators with administrative intake, quote normalization, and document organization. It does <u>NOT</u> diagnose patients, prescribe treatment, rank hospitals clinically, or make autonomous clinical recommendations.
      </div>

      {cases.length === 0 ? (
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-12 text-center space-y-3">
          <p className="text-gray-300 font-medium">No active medical coordination cases found.</p>
          <p className="text-xs text-gray-500">Click "+ New Patient Intake" to open a new coordinator case brief.</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-950 text-gray-400 font-semibold border-b border-gray-800">
              <tr>
                <th className="p-4">Case #</th>
                <th className="p-4">Specialty</th>
                <th className="p-4">Stage</th>
                <th className="p-4">Coordinator</th>
                <th className="p-4">Status</th>
                <th className="p-4">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 text-gray-200">
              {cases.map(c => (
                <tr key={c.id} className="hover:bg-gray-800/40 transition">
                  <td className="p-4 font-mono font-medium text-indigo-300">{c.case_number}</td>
                  <td className="p-4 capitalize">{c.specialty.replace('_', ' ')}</td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700 text-[11px]">
                      {c.stage}
                    </span>
                  </td>
                  <td className="p-4 text-gray-400">{c.assigned_coordinator}</td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-700/50 text-[11px]">
                      {c.status}
                    </span>
                  </td>
                  <td className="p-4 text-gray-500">{c.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-bold text-gray-100">New Patient Intake Triage</h3>
            <form onSubmit={handleCreateCase} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Patient Alias / Reference</label>
                <input
                  type="text"
                  value={alias}
                  onChange={(e) => setAlias(e.target.value)}
                  placeholder="e.g. Patient-Alpha-88"
                  className="w-full bg-gray-950 border border-gray-800 rounded-md p-2 text-xs text-gray-200"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Country of Origin</label>
                <input
                  type="text"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-md p-2 text-xs text-gray-200"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Care Specialty</label>
                <select
                  value={specialty}
                  onChange={(e) => setSpecialty(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-md p-2 text-xs text-gray-200"
                >
                  <option value="fertility_ivf">Fertility / IVF Care</option>
                  <option value="revision_orthopedics">Revision Orthopedics</option>
                </select>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 bg-gray-800 text-xs text-gray-300 rounded-md hover:bg-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-xs font-semibold text-white rounded-md hover:bg-indigo-500"
                >
                  Create Case
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
