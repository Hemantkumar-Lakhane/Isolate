import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

// ── Streaming / Live Output Store ─────────────────────────────────────────────
// High-frequency WS data lives here to avoid re-rendering the whole tree
export const useStreamingStore = create(
  subscribeWithSelector((set, get) => ({
    // nodeId → accumulated streaming string
    streamingTexts: {},
    // nodeId → array of live output entries
    agentLiveOutputs: {},
    // nodeId → agent status
    agentStatuses: {},

    setStreamingText: (nodeId, text) =>
      set(s => ({ streamingTexts: { ...s.streamingTexts, [nodeId]: text } })),

    appendStreamingText: (nodeId, token) =>
      set(s => ({
        streamingTexts: {
          ...s.streamingTexts,
          [nodeId]: (s.streamingTexts[nodeId] || '') + token,
        },
      })),

    clearStreamingText: (nodeId) =>
      set(s => {
        const t = { ...s.streamingTexts }
        delete t[nodeId]
        return { streamingTexts: t }
      }),

    addLiveOutput: (nodeId, entry) =>
      set(s => ({
        agentLiveOutputs: {
          ...s.agentLiveOutputs,
          [nodeId]: [...(s.agentLiveOutputs[nodeId] || []).slice(-12), entry],
        },
      })),

    clearLiveOutput: (nodeId) =>
      set(s => {
        const o = { ...s.agentLiveOutputs }
        delete o[nodeId]
        return { agentLiveOutputs: o }
      }),

    setAgentStatus: (nodeId, status) =>
      set(s => ({ agentStatuses: { ...s.agentStatuses, [nodeId]: status } })),

    resetAll: () =>
      set({ streamingTexts: {}, agentLiveOutputs: {}, agentStatuses: {} }),
  }))
)

// ── Badge / Notification Store ─────────────────────────────────────────────────
export const useBadgeStore = create((set) => ({
  escalations: 0,
  a2a:         0,
  emails:      0,
  patterns:    0,

  setEscalations: (n) => set({ escalations: n }),
  setA2A:         (n) => set({ a2a: n }),
  setEmails:      (n) => set({ emails: n }),
  setPatterns:    (n) => set({ patterns: n }),

  incEscalations: () => set(s => ({ escalations: s.escalations + 1 })),
  decEscalations: () => set(s => ({ escalations: Math.max(0, s.escalations - 1) })),
  incA2A:         () => set(s => ({ a2a: s.a2a + 1 })),
  decA2A:         () => set(s => ({ a2a: Math.max(0, s.a2a - 1) })),

  totalActions: () => 0, // selector – computed outside
}))

// ── UI / Navigation Store ──────────────────────────────────────────────────────
export const useUIStore = create((set) => ({
  mobileMenuOpen:    false,
  notificationPanel: false,
  commandPaletteOpen:false,
  activeToasts:      [],

  setMobileMenu:        (v) => set({ mobileMenuOpen: v }),
  toggleMobileMenu:     ()  => set(s => ({ mobileMenuOpen: !s.mobileMenuOpen })),
  setNotificationPanel: (v) => set({ notificationPanel: v }),
  toggleNotificationPanel: () => set(s => ({ notificationPanel: !s.notificationPanel })),
  setCommandPalette:    (v) => set({ commandPaletteOpen: v }),

  addToast: (toast) => set(s => ({
    activeToasts: [...s.activeToasts, { id: Date.now(), ...toast }].slice(-5),
  })),
  removeToast: (id) => set(s => ({
    activeToasts: s.activeToasts.filter(t => t.id !== id),
  })),
}))

// ── Workflow Builder Canvas Store ──────────────────────────────────────────────
export const useBuilderStore = create((set) => ({
  selectedNode:  null,
  selectedEdge:  null,
  isDirty:       false,
  zoom:          1,
  showMinimap:   true,

  setSelectedNode: (node) => set({ selectedNode: node, selectedEdge: null }),
  setSelectedEdge: (edge) => set({ selectedEdge: edge, selectedNode: null }),
  setDirty:        (v)    => set({ isDirty: v }),
  setZoom:         (z)    => set({ zoom: z }),
  toggleMinimap:   ()     => set(s => ({ showMinimap: !s.showMinimap })),
  clearSelection:  ()     => set({ selectedNode: null, selectedEdge: null }),
}))